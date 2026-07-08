"""Reel base assembly: trim each take's trailing filler/backchannel, normalize to
1080x1920 / 30fps + subtle grade, concat into base.mp4. Also emits an assembled
transcript on the OUTPUT timeline for later captioning."""
import json, os, subprocess, shutil, glob

from reel_paths import IN, REEL  # noqa: E402 -- per-reel folders
from reel_paths import WORK  # noqa: E402 -- per-reel folders
FF = shutil.which("ffmpeg") or "ffmpeg"

# words dropped when trailing a take (the "take-end" confirmations) or leading
DROP = {"mm-hmm", "mmhmm", "mm", "okay", "ok", "yes", "yeah", "um", "uh", "hmm",
        "uh-huh", "right", "so"}
# Default clip order (legacy Lakemba reel). A reel can override this — and add
# explicit per-clip keep spans to cut count-ins / interior bloopers — via a
# clips.json in the reel folder (see load_clips()).
ORDER = ["IMG_6897", "IMG_6900", "IMG_6901", "IMG_6903", "IMG_6904",
         "IMG_6905", "IMG_6909", "IMG_6911", "IMG_6916"]


def load_clips():
    """Return [(name, ext, keep_or_None, sdr), ...]. Prefers <reel>/clips.json;
    falls back to the legacy ORDER with .MOV and edge-trim (keep=None).

    "sdr": true on a clip skips the HLG/BT.2020->SDR tone-map path (see VF vs
    SDR_VF). The tone-map is only correct for genuine HDR input (iPhone HLG,
    10-bit BT.2020); an already-SDR / untagged source (e.g. a screen recording)
    must NOT go through zscale=t=linear -- it errors out on unknown input
    transfer -- so those clips take the plain-SDR normalize path instead."""
    cfg = os.path.join(REEL, "clips.json")
    if os.path.isfile(cfg):
        spec = json.load(open(cfg))["clips"]
        return [(c["name"], c.get("ext", ".mov"), c.get("keep"), c.get("sdr", False))
                for c in spec]
    return [(name, ".MOV", None, False) for name in ORDER]

# The raw iPhone footage is genuine HDR (yuv420p10le, HLG transfer, BT.2020,
# confirmed via ffprobe). Converting straight to yuv420p without properly
# tone-mapping HLG/BT.2020 -> SDR/BT.709 leaves HDR colour tags riding on
# improperly-converted pixel data -- any real player then colour-manages the
# whole file (including the plain-SDR end cards once concatenated on) through
# the wrong lens, producing flat/desaturated results system-wide. zscale+
# tonemap does the real HDR->SDR conversion; the explicit -color_* flags on
# the encoder make sure the OUTPUT file's tags actually say SDR/BT.709.
VF = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
      "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,"
      "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
      "eq=contrast=1.03:saturation=0.98,setsar=1,fps=30")
# Plain-SDR path for already-SDR / untagged sources (clips.json "sdr": true) --
# same scale/crop/grade/fps as VF but WITHOUT the HDR tone-map, which errors on
# input with no colour tags. setparams asserts BT.709/tv on the (untagged) frames
# themselves -- the -color_* encoder flags alone only stick the matrix on
# untagged input, leaving transfer/primaries unsigned; setparams makes libx264
# write all four to the VUI so the OUTPUT verifies as bt709/tv end to end.
SDR_VF = ("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
          "eq=contrast=1.03:saturation=0.98,setsar=1,fps=30,"
          "setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709,"
          "format=yuv420p")
COLOR_TAGS = ["-color_primaries", "bt709", "-color_trc", "bt709",
             "-colorspace", "bt709", "-color_range", "tv"]


def norm(w):
    return w["text"].strip().strip(".,!?;:").lower()


def main():
    seg_dir = os.path.join(WORK, "segments")
    os.makedirs(seg_dir, exist_ok=True)
    concat_list = os.path.join(seg_dir, "concat.txt")
    assembled = []          # words on the output timeline
    out_t = 0.0
    lines = []

    for i, (name, ext, keep, sdr) in enumerate(load_clips()):
        d = json.load(open(os.path.join(WORK, name + ".transcript.json")))
        words = d["words"]
        if keep:
            # explicit keep span [start, end]: cut count-ins + interior bloopers
            k_start, k_end = float(keep[0]), float(keep[1])
            kept = [w for w in words if w["start"] >= k_start - 0.02 and w["start"] < k_end]
        else:
            # legacy: drop leading/trailing filler/backchannel words
            end_idx = len(words) - 1
            while end_idx >= 0 and norm(words[end_idx]) in DROP:
                end_idx -= 1
            start_idx = 0
            while start_idx <= end_idx and norm(words[start_idx]) in DROP:
                start_idx += 1
            kept = words[start_idx:end_idx + 1]
            if not kept:
                continue
            k_start = max(0.0, kept[0]["start"] - 0.10)
            k_end = kept[-1]["end"] + 0.25
        dur = k_end - k_start

        seg = os.path.join(seg_dir, f"seg_{i:02d}.mp4")
        subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                        "-ss", f"{k_start:.3f}", "-i", os.path.join(IN, name + ext),
                        "-t", f"{dur:.3f}", "-vf", SDR_VF if sdr else VF, "-r", "30",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                        *COLOR_TAGS,
                        "-c:a", "aac", "-ar", "48000", "-ac", "2",
                        "-video_track_timescale", "90000", seg], check=True)
        lines.append(f"file '{os.path.abspath(seg)}'")

        # remap kept words onto the output timeline
        for w in kept:
            assembled.append({"text": w["text"], "speaker": w.get("speaker", "A"),
                              "start": round(out_t + (w["start"] - k_start), 3),
                              "end": round(out_t + (w["end"] - k_start), 3)})
        out_t += dur
        print(f"{name}: kept '{' '.join(w['text'] for w in kept)[:60]}...'  -> {dur:.2f}s")

    open(concat_list, "w").write("\n".join(lines) + "\n")
    base = os.path.join(WORK, "base.mp4")
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat",
                    "-safe", "0", "-i", concat_list, "-c", "copy", base], check=True)
    json.dump({"provider": "elevenlabs+assembled", "words": assembled},
              open(os.path.join(WORK, "assembled.transcript.json"), "w"), indent=2)
    print(f"\nbase.mp4 total = {out_t:.2f}s, {len(assembled)} words assembled")


if __name__ == "__main__":
    main()
