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
DEFAULT_MUSIC = "funky-chunk-kevin-macleod.mp3"   # the Lakemba reel's track
CAPTIONED = os.path.join(WORK, "captioned.mp4")
OPENER = os.path.join(WORK, "opener.mp4")     # optional cold open (build_opener.py)


def music_config():
    """Per-reel override via <reel>/content.json -> {"music": {"track": "...",
    "volume": 0.05}}. "track" is a filename under assets/music/ (see its
    CREDIT.txt -- every track there must carry a licence entry, and any reel
    using a non-default track must reproduce that credit line in caption.txt
    via content.json's "caption_txt.music_credit", same as the disclaimer).
    Defaults reproduce the Lakemba reel's tuned track+level if unspecified."""
    cfg = os.path.join(REEL, "content.json")
    music = {}
    if os.path.isfile(cfg):
        music = json.load(open(cfg, encoding="utf-8")).get("music", {})
    track = os.path.join(ASSETS, "music", music.get("track", DEFAULT_MUSIC))
    if not os.path.isfile(track):
        raise SystemExit(f"content.json music.track not found: {track}")
    return track, music.get("volume", 0.05)


def sfx_path(filename):
    """Resolve an SFX cue's audio file: reel-local assets/sfx/ first (for a
    bespoke one-off sound), falling back to the shared assets/sfx/ library
    (see its README.md) -- same precedence as a per-reel override with a
    shared default, mirroring how music_config() treats assets/music/."""
    local = os.path.join(REEL, "assets", "sfx", filename)
    if os.path.isfile(local):
        return local
    shared = os.path.join(ASSETS, "sfx", filename)
    if os.path.isfile(shared):
        return shared
    raise SystemExit(f"sfx cue file not found in reel or shared library: {filename}")


def sfx_cues():
    """Per-reel one-shot SFX hits via <reel>/content.json -> {"sfx": {"cues":
    [{"file": "...", "at": <seconds on the assembled/content timeline>,
    "volume": 0.8}, ...]}}. "file" resolves via sfx_path() -- the shared
    Tier-1 set (whoosh-impact.mp3, transition-whoosh.mp3, success-chime.mp3)
    needs no per-reel copy; drop a same-named file in <reel>/assets/sfx/ only
    to override one for this reel specifically. Empty list if content.json
    has no "sfx" key, so every other reel builds unchanged."""
    cfg = os.path.join(REEL, "content.json")
    if not os.path.isfile(cfg):
        return []
    cues = json.load(open(cfg, encoding="utf-8")).get("sfx", {}).get("cues", [])
    for c in cues:
        sfx_path(c["file"])  # raises if missing from both locations
    return cues


def voice_denoise_model():
    """Opt-in RNNoise on the voice bus for reverberant source rooms (e.g. a
    glass-walled office). content.json -> "voice_denoise": true. Returns the
    RNNoise model path, or None when off (so every other reel builds unchanged).
    Applied as a SEPARATE pre-pass (see main) rather than inside the mix
    filtergraph -- a Windows drive-colon in the model path can't be escaped
    through filter_complex parsing, but a bare filename (cwd at the model dir)
    in a plain -af pass is clean. Cleaning here -- before the music mix + the
    two-pass loudnorm -- stops loudnorm from lifting the room's reverb tails and
    making the clip sound echoey."""
    cfg = os.path.join(REEL, "content.json")
    on = False
    if os.path.isfile(cfg):
        on = bool(json.load(open(cfg, encoding="utf-8")).get("voice_denoise", False))
    if not on:
        return None
    model = os.path.join(ASSETS, "audio", "rnnoise.rnnn")
    if not os.path.isfile(model):
        raise SystemExit(f"voice_denoise is on but RNNoise model is missing: {model}")
    return model


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
    music_track, vol = music_config()

    # Optional RNNoise voice clean (reverberant rooms). Separate pre-pass so the
    # mix stays a plain filtergraph; cwd at the model dir -> bare-filename path.
    model = voice_denoise_model()
    extra_in, voice = [], "0:a"
    if model:
        voice_clean = os.path.join(WORK, "voice_clean.wav")
        subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", assembled,
                        "-af", "arnndn=m=" + os.path.basename(model), "-ar", "48000",
                        "-ac", "2", voice_clean], check=True, cwd=os.path.dirname(model))
        extra_in, voice = ["-i", voice_clean], "2:a"
        print("voice cleaned with RNNoise (voice_denoise) ->", voice_clean)

    # Optional one-shot SFX cues (whoosh/thud/chime hits) -- each gets its own
    # input so adelay can place it at an exact timestamp, mixed into its own
    # bus, then folded into the final amix alongside voice+ducked-music.
    cues = sfx_cues()
    sfx_in = []
    sfx_base_idx = 2 + len(extra_in) // 2
    for c in cues:
        sfx_in += ["-i", sfx_path(c["file"])]

    sfx_filters = []
    for i, c in enumerate(cues):
        idx = sfx_base_idx + i
        delay_ms = round(c["at"] * 1000)
        sfx_filters.append(
            f"[{idx}:a]adelay={delay_ms}|{delay_ms},volume={c.get('volume', 0.8)}[sfx{i}]")
    if cues:
        sfx_filters.append(
            "".join(f"[sfx{i}]" for i in range(len(cues)))
            + f"amix=inputs={len(cues)}:duration=longest:normalize=0[sfxbus]")
        final_mix = "[voice2][mduck][sfxbus]amix=inputs=3:duration=first:normalize=0[a]"
    else:
        final_mix = "[voice2][mduck]amix=inputs=2:duration=first:normalize=0[a]"

    filter_complex = (
        f"[1:a]atrim=0:{total:.3f},volume={vol},afade=t=in:st=0:d=1.5,"
        f"afade=t=out:st={fade_out_st:.3f}:d=2.4[m];"
        f"[{voice}]asplit=2[voice1][voice2];"
        f"[m][voice1]sidechaincompress=threshold=0.04:ratio=10:attack=40:release=450:makeup=1[mduck];"
        + "".join(f + ";" for f in sfx_filters) + final_mix)

    run(["-i", assembled, "-stream_loop", "-1", "-i", music_track, *extra_in, *sfx_in,
         "-filter_complex", filter_complex,
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
         f"offset={js['target_offset']}:linear=true,"
         # loudnorm's linear correction is a single static gain -- it can
         # still leave short percussive transients (SFX hits) a shade above
         # the -1 dBTP target; this hard ceiling is the safety net.
         "alimiter=limit=0.79:level=disabled",
         "-c:v", "copy", *AENC, final])
    print("FINAL REEL:", final, f"({total:.2f}s)")


if __name__ == "__main__":
    main()
