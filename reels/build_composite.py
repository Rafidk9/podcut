"""Final reel composite (ffmpeg only) on top of captioned.mp4:
  logo chip (top-center) -> concat disclaimer(3s)+consultation(3s) end cards
  -> music bed (Inspired, under speech, fade in 1.5s / out 2.4s) -> two-pass
  loudnorm to -14 LUFS / -1 dBTP. B-roll is a later pass."""
import os, json, shutil, subprocess

from reel_paths import WORK, OUT, REEL, ASSETS_ROOT  # noqa: E402 -- per-reel folders
ASSETS = ASSETS_ROOT
FF = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"
os.makedirs(OUT, exist_ok=True)

LOGO = os.path.join(ASSETS, "derived", "logo_chip.png")
DIS = os.path.join(ASSETS, "endcards", "disclaimer-card.mp4")
CON = os.path.join(ASSETS, "endcards", "consultation-card.mp4")
MUSIC = os.path.join(ASSETS, "music", "funky-chunk-kevin-macleod.mp3")
CAPTIONED = os.path.join(WORK, "captioned.mp4")
OPENER = os.path.join(WORK, "opener.mp4")     # optional cold open (build_opener.py)


def music_volume():
    """Per-reel override via <reel>/content.json -> {"music": {"volume": 0.05}}.
    Defaults to 0.05 (the Lakemba reel's tuned level) if not overridden."""
    cfg = os.path.join(REEL, "content.json")
    if os.path.isfile(cfg):
        return json.load(open(cfg, encoding="utf-8")).get("music", {}).get("volume", 0.05)
    return 0.05


def dur(p):
    return float(subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nokey=1", p], capture_output=True, text=True).stdout.strip())


def run(args):
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error"] + args, check=True)


# Explicit SDR/BT.709 tags on every encode -- without these, libx264 just
# forwards whatever ambiguous/wrong tags rode in on the input (this is how the
# HDR-tagged raw iPhone footage's colour metadata ended up stamped onto the
# ENTIRE final file, including the plain-SDR end cards concatenated on here).
VENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-r", "30", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-colorspace", "bt709", "-color_range", "tv", "-video_track_timescale", "90000"]
AENC = ["-c:a", "aac", "-ar", "48000", "-ac", "2"]


def norm_segment(src, dst, silent=False):
    """Re-encode a clip to identical params so the concat demuxer can stream-copy."""
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
    if silent:
        run(["-i", src, "-f", "lavfi", "-t", f"{dur(src):.3f}", "-i",
             "anullsrc=r=48000:cl=stereo", "-vf", vf, "-map", "0:v", "-map", "1:a",
             "-shortest", *VENC, *AENC, dst])
    else:
        run(["-i", src, "-vf", vf, "-map", "0:v", "-map", "0:a?", *VENC, *AENC, dst])


def main():
    # 1) logo chip on the captioned content (top-center, ~40% width, ~2% top)
    content = os.path.join(WORK, "content.mp4")
    run(["-i", CAPTIONED, "-i", LOGO,
         "-filter_complex", "[1]scale=432:-1[lg];[0][lg]overlay=(W-w)/2:38[v]",
         "-map", "[v]", "-map", "0:a", *VENC, *AENC, content])

    # 2) normalize + concat: (opener) + content + disclaimer + consultation
    segs = []
    if os.path.exists(OPENER):
        print("cold open found -- prepending", OPENER)
        op_norm = os.path.join(WORK, "seg_opener.mp4"); norm_segment(OPENER, op_norm); segs.append(op_norm)
    c_norm = os.path.join(WORK, "seg_content.mp4"); norm_segment(content, c_norm); segs.append(c_norm)
    d_norm = os.path.join(WORK, "seg_dis.mp4"); norm_segment(DIS, d_norm, silent=True); segs.append(d_norm)
    o_norm = os.path.join(WORK, "seg_con.mp4"); norm_segment(CON, o_norm, silent=True); segs.append(o_norm)
    lst = os.path.join(WORK, "final_concat.txt")
    open(lst, "w").write("\n".join(f"file '{os.path.abspath(s)}'" for s in segs) + "\n")
    assembled = os.path.join(WORK, "assembled_full.mp4")
    run(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", assembled])

    total = dur(assembled)

    # 3) music bed with real sidechain ducking: the music sits quiet on its own
    # (volume 0.05, ~-26dB off the raw master) AND automatically dips further
    # under her voice via sidechaincompress keyed off the speech track -- this
    # is the standard broadcast technique for "music present but voice always
    # clear", rather than a single static blanket-quiet volume.
    mixed = os.path.join(WORK, "mixed.mp4")
    fade_out_st = max(0.0, total - 2.4)
    vol = music_volume()
    run(["-i", assembled, "-stream_loop", "-1", "-i", MUSIC,
         "-filter_complex",
         f"[1:a]atrim=0:{total:.3f},volume={vol},afade=t=in:st=0:d=1.5,"
         f"afade=t=out:st={fade_out_st:.3f}:d=2.4[m];"
         f"[0:a]asplit=2[voice1][voice2];"
         f"[m][voice1]sidechaincompress=threshold=0.04:ratio=10:attack=40:release=450:makeup=1[mduck];"
         f"[voice2][mduck]amix=inputs=2:duration=first:normalize=0[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", *AENC, mixed])

    # 4) two-pass loudnorm to -14 LUFS / -1 dBTP
    ln = "loudnorm=I=-14:TP=-1:LRA=11"
    p1 = subprocess.run([FF, "-hide_banner", "-i", mixed, "-af", ln + ":print_format=json",
                         "-f", "null", "-"], capture_output=True, text=True)
    txt = p1.stderr
    js = json.loads(txt[txt.rfind("{"): txt.rfind("}") + 1])
    final = os.path.join(OUT, "reel_final.mp4")
    run(["-i", mixed, "-af",
         f"{ln}:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
         f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:"
         f"offset={js['target_offset']}:linear=true",
         "-c:v", "copy", *AENC, final])
    print("FINAL REEL:", final, f"({total:.2f}s)")


if __name__ == "__main__":
    main()
