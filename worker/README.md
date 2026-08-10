# PodCut render worker

The laptop half of the remote control plane. It polls Supabase for queued jobs,
runs the existing reel pipeline as a subprocess, streams the logs back live, and
uploads only the finished deliverables.

```
 phone/browser ──▶ Cloudflare Pages (cloud/) ──▶ Supabase ◀── this worker ──▶ reels/build_all.py
                                                                                 ffmpeg, HyperFrames
```

Nothing under `reels/` or `engine/` is imported or patched. The worker drives
them through the same entry points you use by hand, so your local workflow is
unchanged and you can always ignore all of this and just run `build_all.py`.

## What crosses the network

| Direction | What |
|---|---|
| laptop → cloud | reel folder names, clip filenames and sizes, which config files exist, log lines, and on success `reel_final.mp4` / `thumbnail.jpg` / `caption.txt` |
| cloud → laptop | nothing but job rows: which reel, which kind, and a Drive URL if you queued a fetch |

**Raw footage, transcripts and the ~2 GB `work/` scratch never leave the
machine.** `upload_deliverables()` iterates a fixed allow-list of three
filenames rather than globbing `output/`, so a stray file dropped in that folder
cannot be uploaded by accident.

## Setup

1. **Create the Supabase project** (free tier, no card). In the dashboard open
   *SQL Editor → New query*, paste `supabase/schema.sql`, run it. Re-running is
   safe.
2. **Change the allowed email** if it isn't `rafidk9@gmail.com` — it's the
   `public.allowed_user()` function at the top of the schema.
3. **Configure the worker:**
   ```
   copy worker\.env.example worker\.env
   ```
   Fill in `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` from *Project settings →
   API*. Use the **service role** key, not the anon key. `worker/.env` is
   gitignored by the repo-wide `**/.env` rule.
4. **Check it can see your reels** — this touches no network:
   ```
   python worker\podcut_worker.py --dry-run
   ```
5. **Run it:**
   ```
   python worker\podcut_worker.py
   ```
   Or install it as a logon task so it is always up:
   ```
   powershell -ExecutionPolicy Bypass -File worker\install-task.ps1
   ```

## Usage

```
python worker/podcut_worker.py             # daemon
python worker/podcut_worker.py --once      # handle at most one job, then exit
python worker/podcut_worker.py --dry-run   # catalog + preflight, no network
```

## Job kinds

| kind | what it runs |
|---|---|
| `fetch` | `gdown` the given Drive link into `<reel>/input/` — the bytes go Drive → laptop, never through the cloud |
| `transcribe` | `python -m podcut transcribe` for each clip missing `work/<clip>.transcript.json` |
| `build` | transcribe-if-missing, then `python build_all.py` with `PODCUT_REEL` set |
| `preview` | the same with `--preview` — draft quality, isolated `work_preview/` |
| `qa` | `qa_reel.py` alone, against the existing output |

## Preflight

A build queued from a phone fails fast rather than quietly producing the wrong
reel. It refuses when:

- **`clips.json` is missing** — `build_base.load_clips()` falls back to a
  hardcoded legacy `IMG_68xx` clip order from an old reel. Sitting at the
  machine you'd spot it; from a phone you'd find out nine minutes later.
- **neither `broll.py` nor `broll_plan.json` exists** — `build_broll.py` already
  refuses this, but catching it here saves re-encoding every clip first. Declare
  a B-roll-free reel with `broll_plan.json` containing `"plan": {}`.
- **`content.json` is missing** — captions, music, SFX and end cards would all
  silently be skipped.
- **`clips.json` names a file that isn't in `input/`**.
- **free disk is under `MIN_FREE_GB`** (default 10). A build needs ~2 GB of
  `work/` scratch, and this machine has had a stalled caption render that turned
  out to be a full `C:` drive, not memory pressure — it presents as a hang.
- **ffmpeg / ffprobe / node are not on `PATH`**.
- **a HyperFrames dev server is holding `cap_proj` open** — `build_captions.py`
  hangs rather than failing when the `reels-preview` server is up.

## Things worth knowing

- **One job at a time, always.** Two builds sharing a reel's `work/` would
  corrupt each other.
- **Each job is its own subprocess.** `reel_paths.py` resolves `PODCUT_REEL` at
  import time, so it must be in the environment before the interpreter starts
  and cannot be changed mid-process.
- **Transcripts always go to `work/`**, never `work_preview/`. A preview build
  copies them forward itself (`reel_paths.py`).
- **A preview build failing QA is success.** `qa_reel.py` is designed to refuse
  anything marked preview as a deliverable; the worker reports that as done.
- **Cancelling kills the whole process tree.** ffmpeg and headless Chromium are
  grandchildren; terminating only the Python parent would leave them holding
  `work/` open.
- **Storage pruning.** The free tier is 1 GB and a reel is ~26 MB, so the worker
  keeps the newest `PRUNE_KEEP` reels (default 20) and drops older cloud copies.
  The laptop stays the source of truth — the bucket is a convenience mirror.
- **Asleep means no renders.** Jobs queue and run when the machine wakes. The UI
  shows the worker as offline once the heartbeat goes stale. To keep it up:
  `powercfg /change standby-timeout-ac 0`.
- **Supabase free projects pause after a week idle.** The worker's heartbeat
  counts as activity, so a running laptop keeps the project awake on its own.
