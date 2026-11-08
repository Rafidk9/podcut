"""Terminal progress for every kind of render in this pipeline.

Progress is the one bar implementation (ffmpeg_util.run, motion_style and
tools/longtake all draw through it). hf_render runs the HyperFrames CLI and
feeds its progress into a Progress bar, replacing the bare `--quiet` calls
that left the slowest stages silent for minutes.

In a real terminal the bar live-updates on one line (\\r). Redirected to a log
file (e.g. this pipeline's backgrounded tool calls) \\r overwrites just pile up
as one unreadable line, so that case prints periodic discrete lines instead,
throttled to roughly every 5% / 3s so a long render doesn't spam hundreds."""
import os
import re
import shutil
import subprocess
import sys
import threading
import time

BAR_WIDTH = 28
_TTY_MIN_INTERVAL = 0.1
_HEARTBEAT_SECONDS = 1
_LOG_MIN_STEP, _LOG_MIN_INTERVAL = 5, 3


def _bar(pct, elapsed, width=BAR_WIDTH):
    filled = int(width * pct / 100)
    eta = f"{elapsed / pct * (100 - pct):4.0f}s" if pct > 0 else "   --"
    return f"[{'#' * filled}{'-' * (width - filled)}] {pct:3d}%  {elapsed:5.1f}s elapsed  ETA {eta}"


class Progress:
    """A labelled bar counting up to total. Thread-safe, so concurrent workers
    can share one (see build_broll.py). update() is cheap to call per frame --
    drawing is throttled here, not by the caller."""

    def __init__(self, label, total=100):
        self.label = label
        self.total = max(total, 1)
        self.done = 0
        self.interactive = sys.stdout.isatty()
        self._t0 = time.time()
        self._last_pct, self._last_draw, self._last_detail = -1, 0.0, ""
        self._lock = threading.Lock()
        self._finished = threading.Event()
        if self.interactive:
            threading.Thread(target=self._heartbeat, daemon=True).start()

    def _heartbeat(self):
        """Keep the clock moving through silent stretches -- HyperFrames says
        nothing for the whole VP9 encode, and a frozen bar looks like a hang."""
        while not self._finished.wait(_HEARTBEAT_SECONDS):
            with self._lock:
                if self._last_pct >= 0 and not self._finished.is_set():
                    self._draw(self._last_pct, time.time() - self._t0, self._last_detail)

    def update(self, done, detail=""):
        with self._lock:
            self.done = done
            pct = max(0, min(100, int(done / self.total * 100)))
            elapsed = time.time() - self._t0
            if self.interactive:
                changed = pct != self._last_pct or detail != self._last_detail
                if changed and elapsed - self._last_draw >= _TTY_MIN_INTERVAL:
                    self._draw(pct, elapsed, detail)
            elif pct >= self._last_pct + _LOG_MIN_STEP and elapsed - self._last_draw >= _LOG_MIN_INTERVAL:
                self._draw(pct, elapsed, detail)

    def tick(self, detail=""):
        self.update(self.done + 1, detail)

    def _draw(self, pct, elapsed, detail):
        self._last_pct, self._last_draw, self._last_detail = pct, elapsed, detail
        self._write(f"{self.label}: {_bar(pct, elapsed)}" + (f"  {detail}" if detail else ""))

    def _write(self, line, end=""):
        if self.interactive:
            # Fit the terminal: a wrapped line can't be overwritten by \r.
            cols = shutil.get_terminal_size().columns - 1
            sys.stdout.write("\r" + line[:cols].ljust(cols) + end)
            sys.stdout.flush()
        else:
            # A redirected stdout is cp1252 here: a stray stage character must
            # not be able to crash a render.
            print(line.encode("ascii", "replace").decode(), flush=True)

    def finish(self, ok=True):
        with self._lock:
            self._finished.set()
            elapsed = time.time() - self._t0
            self._write(f"{self.label}: {'done in' if ok else 'FAILED after'} {elapsed:.1f}s", end="\n")


_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# The CLI's renderProgress() draws "  <bar>  42%  <stage>" after a \r, then the
# next log line lands straight after the stage with no newline between them.
_HF_LINE = re.compile(r"\s*[█░]+\s+(\d{1,3})%\s+([^\r\n\[]*)")
_HF_LOG_TAIL = 64 * 1024
_HF_PENDING_MAX = 4096


def parse_hf_progress(segment):
    """(percent, stage) from one \\r-delimited chunk of HyperFrames output, or
    None if it isn't a progress line. A CLI upgrade that changes this format
    only loses the bar's movement -- the render itself is unaffected."""
    m = _HF_LINE.match(_ANSI.sub("", segment.decode("utf-8", "ignore")))
    return (int(m.group(1)), m.group(2).strip()) if m else None


def _hf_failure_text(log):
    """The useful part of a failed render's output: drop progress redraws and
    the [INFO] stream, keep what the CLI actually said went wrong."""
    text = _ANSI.sub("", bytes(log).decode("utf-8", "replace")).replace("\r", "\n")
    lines = [l for l in text.splitlines()
             if l.strip() and not l.startswith("[INFO]") and not parse_hf_progress(l.encode("utf-8"))]
    return "\n".join(lines[-40:])


def hf_render(cli, proj, out, fps, quality, fmt=None, label=None, on_progress=None):
    """Render the HyperFrames project at proj to out, with a progress bar.

    Pass on_progress(percent, stage) to take the updates yourself instead of
    drawing a bar -- concurrent renders must, or they'd overwrite each other's
    line. Raises CalledProcessError on failure, its .output holding the CLI's
    error text (also printed to stderr when this call owns the bar).

    This can't use --quiet (that also turns off the progress output), and
    without --quiet the CLI occasionally asks "How was this render?" on a TTY
    and waits for an answer. stdin=DEVNULL is what stops that hanging a build."""
    cmd = ["node", cli, "render", ".", "-o", os.path.abspath(out), "-f", str(fps), "-q", quality]
    if fmt:
        cmd += ["--format", fmt]
    env = dict(os.environ)
    ff = shutil.which("ffmpeg")
    if ff:
        env["PATH"] = os.path.dirname(ff) + os.pathsep + env.get("PATH", "")

    bar = None if on_progress else Progress(label or os.path.basename(out))
    report = on_progress or bar.update
    log, pending = bytearray(), b""
    with subprocess.Popen(cmd, cwd=proj, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as proc:
        # read1, not line iteration: a progress update has no newline, so it
        # would sit unread until the next one arrived.
        while chunk := proc.stdout.read1(65536):
            log += chunk
            del log[:-_HF_LOG_TAIL]
            *segments, tail = (pending + chunk).split(b"\r")
            for segment in segments + [tail]:
                parsed = parse_hf_progress(segment)
                if parsed:
                    report(*parsed)
            pending = tail[-_HF_PENDING_MAX:]
    ret = proc.returncode

    if bar:
        bar.finish(ok=ret == 0)
    if ret != 0:
        detail = _hf_failure_text(log)
        if bar and detail:
            print(detail, file=sys.stderr)
        raise subprocess.CalledProcessError(ret, cmd, output=detail)
