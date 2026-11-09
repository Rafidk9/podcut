"""PFEC Global brand intro: a footage-free reel, so it doesn't go through
build_base/captions. This assembles it from the longtake film instead:

  brand_take/comp.html --longtake render--> work/take.mp4   (28.5 s, SFX bed)
  + assets/endcards/disclaimer-card.mp4 (3 s, compliance: disclaimer in-video)
  + Digital Lemonade music bed under the whole thing, faded out on the card
  -> two-pass loudnorm -14 LUFS / -1 dBTP + alimiter (same as build_composite.py)
  -> output/reel_final.mp4, output/thumbnail.jpg

The shared consultation card isn't appended: the take's own lockup carries
the CTA, and the 7 offices are shown in the route beat. (The card was rebuilt
with all 7 offices on 2026-10-21, so appending it is now an option.)

Run from reels/:  PODCUT_REEL=2026-10-21_pfec-brand-intro ../engine/.venv/Scripts/python.exe <reel>/build_reel.py [--skip-render]
Then: build_caption_txt.py, qa_reel.py (same env)."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REELS = os.path.dirname(HERE)
sys.path.insert(0, REELS)
from ffmpeg_util import FF, COLOR_TAGS, dur  # noqa: E402

PODCUT = os.path.dirname(REELS)
WORK, OUT = os.path.join(HERE, "work"), os.path.join(HERE, "output")
TAKE = os.path.join(WORK, "take.mp4")
DIS = os.path.join(PODCUT, "assets", "endcards", "disclaimer-card.mp4")
MUSIC = os.path.join(PODCUT, "assets", "music", "digital-lemonade-kevin-macleod.mp3")
MUSIC_VOL = 0.30        # music leads (no voice); SFX sit on top
VENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", *COLOR_TAGS]
AENC = ["-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k"]
VF = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"


def ff(args):
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def main():
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    if "--skip-render" not in sys.argv or not os.path.exists(TAKE):
        subprocess.run([sys.executable, os.path.join(PODCUT, "tools", "longtake", "render.py"),
                        os.path.join(HERE, "brand_take", "comp.html"), "--out", TAKE], check=True)

    # 1) take + disclaimer card, one re-encode (cfr) so the seam is clean
    td, dd = dur(TAKE), dur(DIS)
    total = td + dd
    assembled = os.path.join(WORK, "assembled.mp4")
    ff(["-i", TAKE, "-i", DIS, "-f", "lavfi", "-t", f"{dd:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
        "-filter_complex",
        f"[0:v]{VF}[v0];[1:v]{VF}[v1];[v0][0:a][v1][2:a]concat=n=2:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]", "-fps_mode", "cfr", *VENC, *AENC, assembled])

    # 2) music bed under everything, fades out across the disclaimer card
    mixed = os.path.join(WORK, "mixed.mp4")
    fade_st = total - 1.6
    ff(["-i", assembled, "-i", MUSIC, "-filter_complex",
        f"[1:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,volume={MUSIC_VOL},"
        f"afade=t=in:d=0.15,afade=t=out:st={fade_st:.3f}:d=1.6[m];"
        f"[0:a][m]amix=inputs=2:normalize=0:duration=first[a]",
        "-map", "0:v", "-map", "[a]", "-c:v", "copy", *AENC, mixed])

    # 3) two-pass loudnorm + limiter (mirrors build_composite.py)
    ln = "loudnorm=I=-14:TP=-1:LRA=11"
    p1 = subprocess.run([FF, "-hide_banner", "-i", mixed, "-af", ln + ":print_format=json", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    js = json.loads(p1[p1.rfind("{"): p1.rfind("}") + 1])
    final = os.path.join(OUT, "reel_final.mp4")
    ff(["-i", mixed, "-af",
        f"{ln}:measured_I={js['input_i']}:measured_TP={js['input_tp']}:measured_LRA={js['input_lra']}:"
        f"measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true,"
        # 0.72, not the default 0.79: a dense music bed rides the limiter, and AAC
        # overshoot put true peak at -0.5 dBTP on the first build.
        "alimiter=limit=0.720:level=disabled",
        "-c:v", "copy", *AENC, "-movflags", "+faststart", final])

    # 4) thumbnail: the lockup (logo + tagline + CTA), well clear of any motion
    ff(["-ss", "27.2", "-i", final, "-frames:v", "1", "-q:v", "2", os.path.join(OUT, "thumbnail.jpg")])
    print(f"FINAL REEL: {final} ({total:.2f}s)")


if __name__ == "__main__":
    main()
