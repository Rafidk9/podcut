#!/usr/bin/env python3
"""PodCut render worker -- the laptop half of the remote control plane.

Polls Supabase for queued jobs, runs the existing reel pipeline as a
subprocess, streams stdout back as live logs, and uploads only the finished
deliverables. Raw footage, transcripts and the ~2 GB work/ scratch never leave
this machine.

Nothing under reels/ or engine/ is imported or modified -- they are driven as a
black box through the same entry points you use by hand, so the local workflow
is unaffected.

    python worker/podcut_worker.py                 # run forever (the daemon)
    python worker/podcut_worker.py --once          # handle at most one job, then exit
    python worker/podcut_worker.py --dry-run       # print the catalog + preflight, no network

Configuration lives in worker/.env -- see worker/.env.example.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from queue import Empty, Queue

try:
    import requests
except ImportError:  # pragma: no cover - dependency check, not logic
    sys.exit("worker: `requests` is required -- pip install requests "
             "(it is already in engine/requirements.txt)")

VERSION = "1.0.0"

WORKER_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PODCUT_ROOT = os.path.dirname(WORKER_DIR)

# Files a finished reel produces. Only these ever reach the cloud.
DELIVERABLES = ("reel_final.mp4", "thumbnail.jpg", "caption.txt")

# Poll for jobs this often; rescan the reel folders less often (walking a 2 GB
# work/ dir every few seconds is pure waste).
JOB_POLL_S = 5
CATALOG_SCAN_S = 30
LOG_FLUSH_S = 0.6
LOG_BATCH = 25


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_env(path: str) -> None:
    """Merge KEY=VALUE lines from a .env file into os.environ.

    Real environment variables win, so you can override any of these per-run
    without editing the file.
    """
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key, value)


class Config:
    def __init__(self) -> None:
        load_env(os.path.join(WORKER_DIR, ".env"))
        self.supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        self.service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        self.podcut_root = os.path.abspath(
            os.environ.get("PODCUT_ROOT", DEFAULT_PODCUT_ROOT))
        self.bucket = os.environ.get("SUPABASE_BUCKET", "deliverables")
        self.min_free_gb = float(os.environ.get("MIN_FREE_GB", "10"))
        self.prune_keep = int(os.environ.get("PRUNE_KEEP", "20"))
        self.poll_s = float(os.environ.get("POLL_SECONDS", JOB_POLL_S))
        self.python = os.environ.get("PODCUT_PYTHON") or self._default_python()

    def _default_python(self) -> str:
        """Prefer the engine venv -- it is where transcription's optional deps
        (faster-whisper) and any per-reel rembg install actually live."""
        venv = os.path.join(self.podcut_root, "engine", ".venv",
                            "Scripts" if os.name == "nt" else "bin",
                            "python.exe" if os.name == "nt" else "python")
        return venv if os.path.isfile(venv) else sys.executable

    @property
    def reels_root(self) -> str:
        return os.path.join(self.podcut_root, "reels")

    @property
    def engine_root(self) -> str:
        return os.path.join(self.podcut_root, "engine")

    def require_remote(self) -> None:
        missing = [n for n, v in (("SUPABASE_URL", self.supabase_url),
                                  ("SUPABASE_SERVICE_KEY", self.service_key)) if not v]
        if missing:
            sys.exit("worker: missing " + ", ".join(missing) +
                     " -- copy worker/.env.example to worker/.env and fill it in.")


# ---------------------------------------------------------------------------
# Supabase REST / Storage (plain HTTP -- no SDK, no extra dependency)
# ---------------------------------------------------------------------------

class Supabase:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.s = requests.Session()
        self.s.headers.update({
            "apikey": cfg.service_key,
            "Authorization": f"Bearer {cfg.service_key}",
        })

    # -- PostgREST ----------------------------------------------------------
    def _rest(self, method: str, table: str, **kw):
        url = f"{self.cfg.supabase_url}/rest/v1/{table}"
        headers = dict(kw.pop("headers", {}))
        headers.setdefault("Content-Type", "application/json")
        r = self.s.request(method, url, headers=headers, timeout=30, **kw)
        r.raise_for_status()
        if not r.content or r.headers.get("content-type", "").find("json") < 0:
            return None
        return r.json()

    def select(self, table: str, params: dict):
        return self._rest("GET", table, params=params) or []

    def insert(self, table: str, rows, prefer: str = "return=minimal"):
        return self._rest("POST", table, json=rows, headers={"Prefer": prefer})

    def upsert(self, table: str, rows, on_conflict: str):
        return self._rest("POST", table, json=rows,
                          params={"on_conflict": on_conflict},
                          headers={"Prefer": "resolution=merge-duplicates,return=minimal"})

    def update(self, table: str, params: dict, patch: dict, prefer: str = "return=minimal"):
        return self._rest("PATCH", table, params=params, json=patch,
                          headers={"Prefer": prefer})

    def delete(self, table: str, params: dict):
        return self._rest("DELETE", table, params=params)

    # -- Storage ------------------------------------------------------------
    def upload(self, path: str, local_file: str, content_type: str) -> None:
        url = f"{self.cfg.supabase_url}/storage/v1/object/{self.cfg.bucket}/{path}"
        with open(local_file, "rb") as fh:
            r = self.s.post(url, data=fh, timeout=600, headers={
                "Content-Type": content_type,
                "x-upsert": "true",
            })
        r.raise_for_status()

    def storage_list(self, prefix: str = "", limit: int = 1000):
        url = f"{self.cfg.supabase_url}/storage/v1/object/list/{self.cfg.bucket}"
        r = self.s.post(url, timeout=30, json={
            "prefix": prefix, "limit": limit, "offset": 0,
            "sortBy": {"column": "name", "order": "asc"},
        })
        r.raise_for_status()
        return r.json()

    def storage_remove(self, paths: list) -> None:
        if not paths:
            return
        url = f"{self.cfg.supabase_url}/storage/v1/object/{self.cfg.bucket}"
        r = self.s.delete(url, timeout=60, json={"prefixes": paths})
        r.raise_for_status()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Reel catalog + preflight
# ---------------------------------------------------------------------------

_probe_cache: dict = {}


def _dir_bytes(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _probe_duration(path: str):
    """Duration of the finished reel, cached against (size, mtime) so a poll
    loop doesn't shell out to ffprobe every scan."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (path, st.st_size, int(st.st_mtime))
    if key in _probe_cache:
        return _probe_cache[key]
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=30)
        value = round(float(out.stdout.strip()), 2)
    except (ValueError, OSError, subprocess.SubprocessError):
        value = None
    _probe_cache.clear()          # only ever one entry; keeps memory flat
    _probe_cache[key] = value
    return value


def list_reels(cfg: Config) -> list:
    root = cfg.reels_root
    if not os.path.isdir(root):
        return []
    return sorted(d for d in os.listdir(root)
                  if os.path.isdir(os.path.join(root, d, "input")))


def _clip_names(reel_dir: str, input_clips: list) -> list:
    """Clip stems the pipeline will look for transcripts of.

    Mirrors build_base.load_clips(): clips.json wins, otherwise every file in
    input/. We deliberately do NOT mirror the legacy hardcoded ORDER fallback --
    preflight refuses that case outright rather than reproducing it.
    """
    cfg_path = os.path.join(reel_dir, "clips.json")
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as fh:
                return [c["name"] for c in json.load(fh)["clips"]]
        except (OSError, ValueError, KeyError, TypeError):
            return []
    return [c["name"] for c in input_clips]


def scan_reel(cfg: Config, name: str) -> dict:
    reel_dir = os.path.join(cfg.reels_root, name)
    in_dir = os.path.join(reel_dir, "input")
    work_dir = os.path.join(reel_dir, "work")
    out_dir = os.path.join(reel_dir, "output")

    input_clips = []
    for f in sorted(os.listdir(in_dir)) if os.path.isdir(in_dir) else []:
        stem, ext = os.path.splitext(f)
        if ext.lower() in (".md", ".txt", ""):
            continue
        try:
            size = os.path.getsize(os.path.join(in_dir, f))
        except OSError:
            size = 0
        input_clips.append({"name": stem, "ext": ext, "bytes": size})

    transcripts = []
    if os.path.isdir(work_dir):
        transcripts = sorted(
            f[:-len(".transcript.json")] for f in os.listdir(work_dir)
            if f.endswith(".transcript.json") and f != "assembled.transcript.json")

    wanted = _clip_names(reel_dir, input_clips)
    missing = [n for n in wanted if n not in transcripts]

    final = os.path.join(out_dir, "reel_final.mp4")
    has_output = os.path.isfile(final)

    row = {
        "name": name,
        "has_clips": os.path.isfile(os.path.join(reel_dir, "clips.json")),
        "has_content": os.path.isfile(os.path.join(reel_dir, "content.json")),
        "has_broll_plan": os.path.isfile(os.path.join(reel_dir, "broll_plan.json"))
                          or os.path.isfile(os.path.join(reel_dir, "broll.py")),
        "has_bg_swap": os.path.isfile(os.path.join(reel_dir, "bg_swap.py")),
        "input_clips": input_clips,
        "transcripts": transcripts,
        "missing_transcripts": missing,
        "has_output": has_output,
        "output_bytes": os.path.getsize(final) if has_output else None,
        "duration_s": _probe_duration(final) if has_output else None,
        "last_built_at": (datetime.fromtimestamp(os.path.getmtime(final), timezone.utc)
                          .isoformat() if has_output else None),
        "work_bytes": _dir_bytes(work_dir) if os.path.isdir(work_dir) else 0,
        "seen_at": now_iso(),
    }
    ok, notes = preflight(cfg, name, row)
    row["preflight_ok"] = ok
    row["preflight_notes"] = notes
    return row


def preflight(cfg: Config, name: str, row: dict) -> tuple:
    """Refuse a remote build that would silently produce the wrong reel.

    Interactively you would notice these; triggered from a phone you would not,
    and you would only find out 9 minutes later when you watched the output.
    """
    reel_dir = os.path.join(cfg.reels_root, name)
    notes = []

    if not row["input_clips"]:
        notes.append("input/ has no footage -- nothing to build.")

    if not row["has_clips"]:
        # build_base.load_clips() falls back to a hardcoded legacy IMG_68xx
        # order from an old reel when clips.json is absent.
        notes.append("clips.json missing -- build_base would fall back to the "
                     "legacy IMG_68xx clip order and build the wrong reel.")

    if not row["has_broll_plan"]:
        # build_broll.py raises on this, but failing here means failing in
        # 2 seconds instead of after build_base has re-encoded every clip.
        notes.append("neither broll.py nor broll_plan.json -- build_broll has no "
                     'cross-reel default. Add broll.py, or broll_plan.json with '
                     '"plan": {} to declare this reel B-roll-free.')

    if not row["has_content"]:
        notes.append("content.json missing -- captions, music, SFX and end cards "
                     "will all be skipped.")

    known = {c["name"] for c in row["input_clips"]}
    for stem in _clip_names(reel_dir, row["input_clips"]):
        if stem not in known:
            notes.append(f"clips.json names '{stem}' but input/ has no such file.")

    free_gb = shutil.disk_usage(cfg.podcut_root).free / 1e9
    if free_gb < cfg.min_free_gb:
        # A stalled caption render on this machine has been a full disk before,
        # which presents as a hang rather than an error.
        notes.append(f"only {free_gb:.1f} GB free (need {cfg.min_free_gb:.0f} GB) -- "
                     "a build needs ~2 GB of work/ scratch and stalls rather than "
                     "erroring when the disk fills.")

    for tool, label in (("ffmpeg", "ffmpeg"), ("ffprobe", "ffprobe"), ("node", "node")):
        if not shutil.which(tool):
            notes.append(f"{label} is not on PATH.")

    return (not notes), notes


def hyperframes_dev_running() -> bool:
    """True if a HyperFrames dev server is holding a reel's cap_proj open.

    build_captions.py cannot write cap_proj while `reels-preview` is up -- it
    hangs rather than failing, which from a phone looks like a dead build.
    Best-effort: if we cannot inspect processes, assume clear.
    """
    if os.name != "nt":
        return False
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | "
             "Select-Object -ExpandProperty CommandLine"],
            capture_output=True, text=True, timeout=20)
        return "cap_proj" in (out.stdout or "")
    except (OSError, subprocess.SubprocessError):
        return False


# ---------------------------------------------------------------------------
# Log streaming
# ---------------------------------------------------------------------------

class LogStream:
    """Batches stdout lines into job_logs rows.

    One HTTP round-trip per line would make the worker slower than the render
    and burn the free tier's realtime message budget for no benefit.
    """

    def __init__(self, sb: Supabase, job_id: int, echo: bool = True) -> None:
        self.sb, self.job_id, self.echo = sb, job_id, echo
        self.seq = 0
        self.buf: list = []
        self.history: list = []     # kept so the QA verdict can be read back out
        self.last_flush = time.monotonic()

    def add(self, line: str, stream: str = "stdout") -> None:
        line = line.rstrip("\r\n")
        if self.echo:
            print(f"  | {line}", flush=True)
        self.history.append(line)
        self.seq += 1
        self.buf.append({"job_id": self.job_id, "seq": self.seq,
                         "stream": stream, "line": line[:4000]})
        if len(self.buf) >= LOG_BATCH or (time.monotonic() - self.last_flush) > LOG_FLUSH_S:
            self.flush()

    def flush(self) -> None:
        if not self.buf:
            return
        rows, self.buf = self.buf, []
        self.last_flush = time.monotonic()
        try:
            self.sb.insert("job_logs", rows)
        except requests.RequestException as e:
            # Losing a log batch must never kill a render that is going fine.
            print(f"  ! log upload failed: {e}", file=sys.stderr, flush=True)


def _kill_tree(proc: subprocess.Popen) -> None:
    """ffmpeg and headless Chromium are grandchildren -- terminating only the
    python parent would leave them running and holding work/ open."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()


def run_streamed(cmd: list, cwd: str, env: dict, log: LogStream,
                 cancelled=lambda: False) -> int:
    log.add(f"$ {' '.join(cmd)}", stream="worker")
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1)

    q: Queue = Queue()

    def pump():
        for line in proc.stdout:
            q.put(line)
        q.put(None)

    threading.Thread(target=pump, daemon=True).start()

    last_cancel_check = time.monotonic()
    while True:
        try:
            line = q.get(timeout=0.5)
        except Empty:
            log.flush()
            if time.monotonic() - last_cancel_check > 5:
                last_cancel_check = time.monotonic()
                if cancelled():
                    log.add("cancel requested -- stopping the process tree", stream="worker")
                    _kill_tree(proc)
                    log.flush()
                    return 130
            continue
        if line is None:
            break
        log.add(line)

    proc.wait()
    log.flush()
    return proc.returncode


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def child_env(cfg: Config, reel: str, preview: bool = False) -> dict:
    env = dict(os.environ)
    # reel_paths.py resolves PODCUT_REEL at import time, so it has to be set
    # before the interpreter starts -- it cannot be changed mid-process. That
    # is why every job is its own subprocess.
    env["PODCUT_REEL"] = reel
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if preview:
        env["PODCUT_PREVIEW"] = "1"
    else:
        env.pop("PODCUT_PREVIEW", None)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        env["PATH"] = os.path.dirname(ffmpeg) + os.pathsep + env.get("PATH", "")
    return env


def job_transcribe(cfg: Config, sb: Supabase, job: dict, log: LogStream,
                   cancelled) -> int:
    """Fill in missing work/<clip>.transcript.json via the engine CLI.

    build_all.py does not do this -- it just opens the files and fails if they
    are absent. Transcripts always go to work/, never work_preview/: a preview
    build copies them forward from work/ itself (reel_paths.py).
    """
    reel = job["reel"]
    reel_dir = os.path.join(cfg.reels_root, reel)
    row = scan_reel(cfg, reel)
    missing = row["missing_transcripts"]
    if not missing:
        log.add("all clips already have transcripts", stream="worker")
        return 0

    work = os.path.join(reel_dir, "work")
    os.makedirs(work, exist_ok=True)
    by_stem = {c["name"]: c["ext"] for c in row["input_clips"]}

    for stem in missing:
        if cancelled():
            return 130
        ext = by_stem.get(stem)
        if not ext:
            log.add(f"no input file for clip '{stem}' -- skipping", stream="worker")
            continue
        media = os.path.join(reel_dir, "input", stem + ext)
        out = os.path.join(work, stem + ".transcript.json")
        log.add(f"transcribing {stem}{ext}", stream="worker")
        code = run_streamed(
            [cfg.python, "-m", "podcut", "transcribe", "--media", media,
             "--out", out, "--workdir", os.path.join(work, f".podcut_work_{stem}")],
            cwd=cfg.engine_root, env=child_env(cfg, reel), log=log, cancelled=cancelled)
        if code != 0:
            log.add(f"transcription of {stem} failed (exit {code})", stream="worker")
            return code
    return 0


def job_fetch(cfg: Config, sb: Supabase, job: dict, log: LogStream, cancelled) -> int:
    """Pull footage straight from Google Drive onto the laptop.

    This is what keeps client media out of the cloud: the URL travels, the
    bytes go Drive -> laptop and never touch Supabase.
    """
    url = (job.get("args") or {}).get("url", "").strip()
    if not url:
        log.add("no url in job args", stream="worker")
        return 2

    dest = os.path.join(cfg.reels_root, job["reel"], "input")
    os.makedirs(dest, exist_ok=True)

    if "/folders/" in url:
        # -O on a folder download names the destination directory itself.
        cmd = [cfg.python, "-m", "gdown", "--folder", url, "-O", dest]
    else:
        # --fuzzy accepts a full share link rather than a bare file id; the
        # trailing separator tells gdown that -O is a directory, not a filename.
        cmd = [cfg.python, "-m", "gdown", "--fuzzy", url, "-O", dest + os.sep]

    code = run_streamed(cmd, cwd=dest, env=child_env(cfg, job["reel"]),
                        log=log, cancelled=cancelled)
    if code != 0:
        log.add("gdown failed -- if it is not installed, run: "
                f"{cfg.python} -m pip install gdown", stream="worker")
    return code


def job_build(cfg: Config, sb: Supabase, job: dict, log: LogStream, cancelled) -> int:
    preview = job["kind"] == "preview"
    reel = job["reel"]

    row = scan_reel(cfg, reel)
    if not row["preflight_ok"]:
        for note in row["preflight_notes"]:
            log.add(f"preflight: {note}", stream="worker")
        log.add("refusing to build -- fix the above and requeue", stream="worker")
        return 2

    if hyperframes_dev_running():
        log.add("a HyperFrames dev server is holding cap_proj open -- stop the "
                "reels-preview server before building, or build_captions will "
                "hang instead of failing", stream="worker")
        return 2

    if row["missing_transcripts"]:
        log.add(f"missing transcripts for {', '.join(row['missing_transcripts'])} "
                "-- running transcription first", stream="worker")
        code = job_transcribe(cfg, sb, job, log, cancelled)
        if code != 0:
            return code

    args = job.get("args") or {}
    cmd = [cfg.python, "build_all.py"]
    if preview:
        cmd.append("--preview")
    if args.get("no_cache"):
        cmd.append("--no-cache")
    if args.get("clear_cache"):
        cmd.append("--clear-cache")

    return run_streamed(cmd, cwd=cfg.reels_root,
                        env=child_env(cfg, reel, preview=preview),
                        log=log, cancelled=cancelled)


def job_qa(cfg: Config, sb: Supabase, job: dict, log: LogStream, cancelled) -> int:
    return run_streamed([cfg.python, "qa_reel.py"], cwd=cfg.reels_root,
                        env=child_env(cfg, job["reel"]), log=log, cancelled=cancelled)


JOB_HANDLERS = {
    "build": job_build,
    "preview": job_build,
    "transcribe": job_transcribe,
    "fetch": job_fetch,
    "qa": job_qa,
}


# ---------------------------------------------------------------------------
# Deliverables
# ---------------------------------------------------------------------------

def upload_deliverables(cfg: Config, sb: Supabase, reel: str, log: LogStream) -> list:
    """Upload output/ only. input/ and work/ are never touched here -- that is
    the whole privacy contract, so this iterates an explicit allow-list rather
    than globbing the folder."""
    out_dir = os.path.join(cfg.reels_root, reel, "output")
    uploaded = []
    for fname in DELIVERABLES:
        local = os.path.join(out_dir, fname)
        if not os.path.isfile(local):
            continue
        ctype = mimetypes.guess_type(fname)[0] or "application/octet-stream"
        if fname.endswith(".txt"):
            ctype = "text/plain; charset=utf-8"
        remote = f"{reel}/{fname}"
        size = os.path.getsize(local)
        log.add(f"uploading {fname} ({size / 1e6:.1f} MB)", stream="worker")
        try:
            sb.upload(remote, local, ctype)
        except requests.RequestException as e:
            log.add(f"upload of {fname} failed: {e}", stream="worker")
            continue
        uploaded.append({"path": remote, "bytes": size, "content_type": ctype})
    return uploaded


def prune_storage(cfg: Config, sb: Supabase) -> None:
    """Keep the newest PRUNE_KEEP reels in the bucket.

    The free tier gives 1 GB and a reel is ~26 MB. The laptop stays the source
    of truth, so dropping an old mirror costs nothing.
    """
    try:
        entries = sb.storage_list()
    except requests.RequestException:
        return
    folders = sorted({e["name"] for e in entries if e.get("name")})
    stale = folders[:-cfg.prune_keep] if len(folders) > cfg.prune_keep else []
    for folder in stale:
        paths = [f"{folder}/{f}" for f in DELIVERABLES]
        try:
            sb.storage_remove(paths)
            print(f"[prune] removed cloud copy of {folder}", flush=True)
        except requests.RequestException:
            pass


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def heartbeat(cfg: Config, sb: Supabase, current_job=None) -> None:
    usage = shutil.disk_usage(cfg.podcut_root)
    sb.update("worker_status", {"id": "eq.1"}, {
        "online_at": now_iso(),
        "host": platform.node(),
        "version": VERSION,
        "free_disk_gb": round(usage.free / 1e9, 1),
        "total_disk_gb": round(usage.total / 1e9, 1),
        "current_job": current_job,
        "ffmpeg": _tool_version("ffmpeg", "-version"),
        "node": _tool_version("node", "--version"),
        "python": platform.python_version(),
    })


_tool_cache: dict = {}


def _tool_version(tool: str, flag: str):
    if tool in _tool_cache:
        return _tool_cache[tool]
    path = shutil.which(tool)
    value = None
    if path:
        try:
            out = subprocess.run([path, flag], capture_output=True, text=True, timeout=15)
            value = (out.stdout or out.stderr).splitlines()[0][:120]
        except (OSError, IndexError, subprocess.SubprocessError):
            value = None
    _tool_cache[tool] = value
    return value


def push_catalog(cfg: Config, sb: Supabase) -> list:
    rows = [scan_reel(cfg, name) for name in list_reels(cfg)]
    if rows:
        sb.upsert("reels", rows, on_conflict="name")
        live = {r["name"] for r in rows}
        for stale in {r["name"] for r in sb.select("reels", {"select": "name"})} - live:
            sb.delete("reels", {"name": f"eq.{stale}"})
    return rows


def qa_summary_from_logs(log_lines: list):
    for line in reversed(log_lines):
        if line.startswith(("PASS:", "WARN:", "FAIL:")):
            return line.strip()
    return None


def handle_job(cfg: Config, sb: Supabase, job: dict) -> None:
    job_id = job["id"]
    kind, reel = job["kind"], job["reel"]
    print(f"[job {job_id}] {kind} {reel}", flush=True)

    sb.update("jobs", {"id": f"eq.{job_id}"},
              {"status": "running", "started_at": now_iso()})
    heartbeat(cfg, sb, current_job=job_id)

    log = LogStream(sb, job_id)

    def cancelled() -> bool:
        try:
            rows = sb.select("jobs", {"id": f"eq.{job_id}", "select": "cancel_requested"})
            return bool(rows and rows[0]["cancel_requested"])
        except requests.RequestException:
            return False

    error = None
    try:
        code = JOB_HANDLERS[kind](cfg, sb, job, log, cancelled)
    except Exception as e:                      # noqa: BLE001 - report, never crash the daemon
        code, error = 1, f"{type(e).__name__}: {e}"
        log.add(error, stream="worker")

    deliverables = []
    if kind in ("build", "preview") and code == 0:
        deliverables = upload_deliverables(cfg, sb, reel, log)

    status = "done" if code == 0 else ("cancelled" if code == 130 else "failed")
    if kind == "preview" and code != 0 and not error:
        # qa_reel.py is supposed to refuse a preview build as a deliverable.
        # That is the check working, not the build failing.
        log.add("preview finished -- QA correctly refused it as a deliverable",
                stream="worker")
        status = "done"

    log.flush()
    sb.update("jobs", {"id": f"eq.{job_id}"}, {
        "status": status,
        "exit_code": code,
        "error": error,
        "qa_summary": qa_summary_from_logs(log.history),
        "deliverables": deliverables,
        "finished_at": now_iso(),
    })
    if deliverables:
        prune_storage(cfg, sb)
    print(f"[job {job_id}] {status} (exit {code})", flush=True)


def claim_next(cfg: Config, sb: Supabase):
    queued = sb.select("jobs", {"status": "eq.queued", "order": "id.asc", "limit": "1"})
    if not queued:
        return None
    job_id = queued[0]["id"]
    # Conditional on status so a second worker (or a retry) cannot double-claim.
    claimed = sb.update("jobs", {"id": f"eq.{job_id}", "status": "eq.queued"},
                        {"status": "claimed", "claimed_at": now_iso()},
                        prefer="return=representation")
    return claimed[0] if claimed else None


def run_forever(cfg: Config, sb: Supabase, once: bool = False) -> int:
    print(f"[worker] {VERSION} watching {cfg.reels_root}", flush=True)
    print(f"[worker] python: {cfg.python}", flush=True)
    last_scan = 0.0
    while True:
        try:
            if time.monotonic() - last_scan > CATALOG_SCAN_S:
                push_catalog(cfg, sb)
                heartbeat(cfg, sb)
                last_scan = time.monotonic()
            job = claim_next(cfg, sb)
            if job:
                handle_job(cfg, sb, job)
                push_catalog(cfg, sb)
                heartbeat(cfg, sb)
                last_scan = time.monotonic()
                if once:
                    return 0
            elif once:
                print("[worker] nothing queued", flush=True)
                return 0
        except requests.RequestException as e:
            # Laptop lost wifi, Supabase blipped -- keep waiting, don't die.
            print(f"[worker] network: {e}", file=sys.stderr, flush=True)
        except KeyboardInterrupt:
            print("\n[worker] stopped", flush=True)
            return 0
        time.sleep(cfg.poll_s)


def dry_run(cfg: Config) -> int:
    reels = list_reels(cfg)
    usage = shutil.disk_usage(cfg.podcut_root)
    print(f"root         {cfg.podcut_root}")
    print(f"python       {cfg.python}")
    print(f"disk         {usage.free / 1e9:.1f} GB free of {usage.total / 1e9:.1f} GB")
    print(f"ffmpeg       {shutil.which('ffmpeg') or 'NOT FOUND'}")
    print(f"node         {shutil.which('node') or 'NOT FOUND'}")
    print(f"reels        {len(reels)}\n")
    if not reels:
        print("No reel folders found (expected reels/<date>_<slug>/input/).")
        return 1
    for name in reels:
        row = scan_reel(cfg, name)
        mark = "OK  " if row["preflight_ok"] else "STOP"
        print(f"[{mark}] {name}")
        clips = ", ".join(c["name"] + c["ext"] for c in row["input_clips"]) or "none"
        print(f"        input      {clips}")
        print(f"        transcripts {len(row['transcripts'])} present"
              + (f", missing {', '.join(row['missing_transcripts'])}"
                 if row["missing_transcripts"] else ""))
        cfgs = [k for k, v in (("clips.json", row["has_clips"]),
                               ("content.json", row["has_content"]),
                               ("broll", row["has_broll_plan"]),
                               ("bg_swap.py", row["has_bg_swap"])) if v]
        print(f"        config     {', '.join(cfgs) or 'none'}")
        if row["has_output"]:
            print(f"        output     reel_final.mp4 "
                  f"{row['output_bytes'] / 1e6:.1f} MB, {row['duration_s']}s")
        print(f"        work/      {row['work_bytes'] / 1e9:.2f} GB")
        for note in row["preflight_notes"]:
            print(f"        ! {note}")
        print()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PodCut laptop render worker")
    ap.add_argument("--once", action="store_true",
                    help="handle at most one job, then exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the catalog and preflight verdicts; no network")
    a = ap.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    cfg = Config()
    if a.dry_run:
        return dry_run(cfg)
    cfg.require_remote()
    return run_forever(cfg, Supabase(cfg), once=a.once)


if __name__ == "__main__":
    sys.exit(main())
