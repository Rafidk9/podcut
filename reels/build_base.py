"""Reel base assembly: trim each take's trailing filler/backchannel, normalize to
1080x1920 / 30fps + subtle grade, concat into base.mp4. Also emits an assembled
transcript on the OUTPUT timeline for later captioning."""
import json, os, glob

from reel_paths import IN, REEL  # noqa: E402 -- per-reel folders
from reel_paths import WORK  # noqa: E402 -- per-reel folders
from ffmpeg_util import COLOR_TAGS, run  # noqa: E402 -- shared ffmpeg wrappers
import content_check  # noqa: E402 -- per-reel folders

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


def load_zoom():
    """Per-reel subtle push-in/out on the talking-head footage (opt-in). Applied
    HERE (per segment, before B-roll/captions) so the full-frame stingers and the
    fixed-position caption/overlay cards composited on top are never distorted --
    only the footage moves. content.json:

        "zoom": {"amount": 0.06, "segments": ["in", "out", "in", ...],
                 "hits": [{"clip": 0, "at": [4.64, 5.34], "amount": 0.14}, ...]}

    segments[i] is the direction for clip i (in | out | hold/none); a slow
    cosine-eased zoom up to `amount` (0.06 = 6%) spans that whole clip. Absent or
    empty -> no zoom, so every other reel keeps building unchanged.

    "hits" (opt-in, on top of the above): a punch-zoom on a specific emphasis
    moment -- flat at 1.0 for the rest of that clip, quick ease up to
    1+amount right as the named words are spoken, brief hold, quick ease back
    down. "at" is [start, end] in RAW clip time (same clock as clips.json's
    "keep" -- i.e. pick it straight off that clip's own .transcript.json, not
    the assembled/output timeline). A clip with a hit entry has its `segments`
    direction ignored (the punch IS its zoom treatment)."""
    cfg = os.path.join(REEL, "content.json")
    if not os.path.isfile(cfg):
        return 0.0, [], {}
    z = json.load(open(cfg, encoding="utf-8")).get("zoom") or {}
    hits = {int(h["clip"]): h for h in z.get("hits", [])}
    return float(z.get("amount", 0.06)), list(z.get("segments", [])), hits


def zoom_filter(direction, amount, dur):
    """A smooth zoompan push over the clip: supersample x2 first so the sub-pixel
    pan reads jitter-free, then zoompan back down to 1080x1920. 'in' ramps
    1.0 -> 1+amount across the clip (cosine ease); 'out' ramps 1+amount -> 1.0.
    Anything else (hold/none) -> no filter."""
    if direction not in ("in", "out") or amount <= 0 or dur <= 0.1:
        return ""
    n = max(2, round(dur * 30)) - 1          # last output-frame index
    z0, z1 = (1.0, 1.0 + amount) if direction == "in" else (1.0 + amount, 1.0)
    z = f"{z0:.4f}+({z1 - z0:.4f})*(1-cos(PI*on/{n}))/2"
    return _zoompan(z)


def punch_zoom_filter(hit, k_start, dur, ramp_in=0.18, ramp_out=0.22):
    """A quick zoom-punch on one emphasis moment: flat 1.0 everywhere else,
    cosine ease up to 1+amount as the hit's words start, holds across them,
    cosine ease back down. hit['at'] is in RAW clip time (pre-trim); k_start
    is this clip's `keep` start, so `local = raw - k_start` lands it on the
    trimmed segment's own 0-based clock that zoompan's frame counter walks."""
    amount = float(hit.get("amount", 0.12))
    a = max(ramp_in, hit["at"][0] - k_start)      # clamp so a-ramp_in doesn't go negative
    b = min(dur - ramp_out, hit["at"][1] - k_start)
    if amount <= 0 or dur <= 0.1 or b <= a:
        return ""
    t = "(on/30)"
    ramp_up = f"(1-cos(PI*({t}-({a - ramp_in:.4f}))/{ramp_in:.4f}))/2"
    ramp_down = f"(1-cos(PI*(({b + ramp_out:.4f})-{t})/{ramp_out:.4f}))/2"
    pulse = (f"if(lt({t},{a - ramp_in:.4f}),0,"
             f"if(lt({t},{a:.4f}),{ramp_up},"
             f"if(lt({t},{b:.4f}),1,"
             f"if(lt({t},{b + ramp_out:.4f}),{ramp_down},0))))")
    z = f"1+{amount:.4f}*({pulse})"
    return _zoompan(z)


def _zoompan(z_expr):
    # zoompan emits frames with UNSPECIFIED transfer/primaries; the -color_* encoder
    # flags alone only re-stamp matrix+range, leaving trc/primaries "unknown" on the
    # output. Re-assert all four on the frames with setparams (same fix the SDR path
    # uses) so the reel still verifies bt709/tv end to end.
    return (",scale=2160:3840,"
            f"zoompan=z='{z_expr}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            "s=1080x1920:fps=30,setsar=1,"
            "setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709")


def norm(w):
    return w["text"].strip().strip(".,!?;:").lower()


def main():
    content_check.check(REEL)  # catch a typo'd content.json key before the build runs

    seg_dir = os.path.join(WORK, "segments")
    os.makedirs(seg_dir, exist_ok=True)
    concat_list = os.path.join(seg_dir, "concat.txt")
    assembled = []          # words on the output timeline
    out_t = 0.0
    lines = []
    zoom_amount, zoom_segments, zoom_hits = load_zoom()

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
        if i in zoom_hits:
            zf = punch_zoom_filter(zoom_hits[i], k_start, dur)
        else:
            direction = zoom_segments[i] if i < len(zoom_segments) else "hold"
            zf = zoom_filter(direction, zoom_amount, dur)
        vf = (SDR_VF if sdr else VF) + zf
        run(["-ss", f"{k_start:.3f}", "-i", os.path.join(IN, name + ext),
             "-t", f"{dur:.3f}", "-vf", vf, "-r", "30",
             "-c:v", "libx264", "-preset", "medium", "-crf", "19",
             *COLOR_TAGS,
             "-c:a", "aac", "-ar", "48000", "-ac", "2",
             "-video_track_timescale", "90000", seg])
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
    run(["-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", base])
    json.dump({"provider": "elevenlabs+assembled", "words": assembled},
              open(os.path.join(WORK, "assembled.transcript.json"), "w"), indent=2)
    print(f"\nbase.mp4 total = {out_t:.2f}s, {len(assembled)} words assembled")


if __name__ == "__main__":
    main()
