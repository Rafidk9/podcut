# PodCut

An AI-assisted video editing system with two modes:

1. **Podcast / Interview mode** — take two camera angles, automatically sync them,
   figure out who is speaking (and who is *about* to speak), and cut between the
   cameras like a human editor would. Filler words and dead air are removed. The
   result can then be handed to **video-use** for further editing and
   **HyperFrames** for captions / motion graphics.

2. **Single-speaker mode** — one talking-head video. Filler words and pauses are
   removed and the clip is handed straight to **video-use + HyperFrames**.

The genuinely hard, valuable part — camera **sync** and the AI-annotated
**switching engine** — is implemented here and runs **without any API keys**.
Transcription and the AI annotation layer use pluggable providers with a
**local, key-free fallback**, so the whole pipeline runs today; you add keys to
upgrade quality.

## Architecture

```
                        ┌─────────────────────────────────────────┐
 upload 2 cams  ─────▶  │  1. SYNC        audio cross-correlation  │  (deterministic, no key)
                        │  2. TRANSCRIBE  word-level timestamps    │  (provider + local fallback)
                        │  3. DIARIZE     who speaks when          │  (per-mic energy / labels)
                        │  4. ANNOTATE    conversational structure │  (Anthropic + local fallback)
                        │  5. FILLERS     remove um/uh + dead air  │  (deterministic)
                        │  6. SWITCH      annotations → cut list    │  (deterministic ENGINE)
                        │  7. RENDER      ffmpeg → final.mp4        │  (deterministic)
                        └─────────────────────────────────────────┘
                                          │
                        ┌─────────────────┴───────────────────┐
                        ▼                                      ▼
                  video-use (edit)                   HyperFrames (captions / motion gfx)
```

Layered design (from our discussion): **AI annotates conversational structure;
a deterministic engine converts annotations + word timestamps into cuts.** The
LLM never emits raw timecodes — it labels spans, and the engine snaps them to
real word timestamps.

## Layout

```
podcut/
  engine/          Python pipeline (the core)
    podcut/        library + CLI
    tests/         unit tests for the switching engine (no media/keys needed)
  web/             Next.js UI (upload, configure, run, preview) -- runs locally
  reels/           branded vertical-reel pipeline (see reels/README.md)
  cloud/           hosted UI for queueing renders from anywhere
  worker/          the daemon that runs those renders on your machine
  supabase/        schema for the cloud/worker pair
```

## Rendering from anywhere

`cloud/` + `worker/` let you queue and watch a reel build from your phone while
this machine does the actual work. The cloud side is a static page on Cloudflare
Pages plus a free Supabase project; the laptop runs a small daemon that polls for
jobs and streams logs back.

**Raw footage never leaves the machine.** Only reel names, file sizes, log lines
and the three finished deliverables (`reel_final.mp4`, `thumbnail.jpg`,
`caption.txt`) go to the cloud. Footage arrives via a Drive link the laptop
fetches itself.

Setup is in [`worker/README.md`](worker/README.md) (laptop) and
[`cloud/README.md`](cloud/README.md) (hosting). Both free, no card.

```bash
python worker/podcut_worker.py --dry-run   # check it sees your reels; no network
```

## Setup on a new machine

Raw footage, renders and per-reel working folders are **not** in this repo
(see `.gitignore`) -- only code, the editorial config for each reel
(`content.json`, `clips.json`, `broll_plan.json`, per-reel `broll.py` /
`bg_swap.py`) and the shared brand assets. Footage comes from Google Drive.

Prerequisites (on PATH): **Python 3.12**, **ffmpeg + ffprobe**, **Node 20+**, git.
Optional: Tesseract OCR (only for `tools/letter-redactor`).

```bash
git clone https://github.com/Rafidk9/podcut.git
cd podcut

# Python env (engine + reels pipeline share it)
cd engine
python -m venv .venv && .venv\Scripts\activate      # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
pip install pillow                                   # reels: thumbnails/overlays
pip install rembg                                    # optional: "text behind subject" (bg_swap.py)
copy .env.example .env                               # optional keys; leave blank to use local fallbacks
cd ..

# HyperFrames CLI (captions / B-roll / wipes render through it)
cd tools/hyperframes && npm install && cd ../..

# sanity check -- no media or keys needed
cd engine && python -m pytest -q && cd ..
```

Then build a reel per [`reels/README.md`](reels/README.md): `python reels/new_reel.py
<YYYY-MM-DD>_<slug>`, drop the clips into its `input/`, and run the pipeline
scripts in order. To rebuild an existing reel, its config is already in
`reels/<reel>/`; just put the original clips back into `input/`.

## Quick start

```bash
# 1. engine
cd engine
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt

# podcast mode
python -m podcut podcast --cam1 A.mp4 --cam2 B.mp4 --out final.mp4

# single-speaker mode
python -m podcut single --video talk.mp4 --out final.mp4

# run the engine tests (no media or keys required)
python -m pytest -q

# 2. web UI
cd ../web
npm install
npm run dev        # http://localhost:3000
```

## Configuration (optional keys — copy engine/.env.example to engine/.env)

| Var | Purpose | Without it |
|-----|---------|------------|
| `ANTHROPIC_API_KEY`   | AI conversational-structure annotation | heuristic fallback |
| `ELEVENLABS_API_KEY`  | Scribe transcription (word ts + diarization) | Whisper/local fallback |
| `OPENAI_API_KEY`      | Whisper API transcription | local fallback |
| `VIDEO_USE_PATH`      | path to a video-use checkout | step skipped |
| `HYPERFRAMES_PATH`    | path to a HyperFrames checkout | step skipped |

See `engine/podcut/` for each stage. Start with `pipeline.py`.
