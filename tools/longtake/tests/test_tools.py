"""pytest tests/ -- render.py's shutter maths and check.py's verdicts on two
tiny compositions: one whose beats replace each other (must FAIL) and one
whose beats are carried by a surviving element (must pass)."""
import os
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import check  # noqa: E402
import render  # noqa: E402

COMP = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0}} #stage{{position:relative;overflow:hidden;background:#0a0560}}
.lt{{position:absolute;left:0;top:0;font:700 80px sans-serif;color:#fff}}</style>
<script src="longtake.js"></script></head><body><div id="stage"><div id="world">
<div class="lt" data-lt="a" id="a">ONE</div><div class="lt" data-lt="b" id="b">TWO</div>
<div class="lt" data-lt="keep" id="keep" style="width:80px;height:80px;background:#FFC500"></div>
</div></div><script>
LT.comp({{ dur: 4, render: t => {{
  LT.set(LT.el("a"), {{ x: 540, y: 900, alpha: t < 2 ? 1 : 0 }});
  LT.set(LT.el("b"), {{ x: 540, y: 900, alpha: t < 2 ? 0 : 1 }});
  LT.set(LT.el("keep"), {{ x: 540 + 200 * Math.sin(t), y: 1100, w: 80, h: 80, alpha: {keep} }});
}}, beats: [{{ t: 2, handoff: {handoff} }}] }});
</script></body></html>"""


def make(tmp_path, keep, handoff):
    d = tmp_path / "comp"
    d.mkdir()
    shutil.copy(os.path.join(HERE, "lib", "longtake.js"), d)
    (d / "comp.html").write_text(COMP.format(keep=keep, handoff=handoff), encoding="utf-8")
    return str(d / "comp.html")


def levels(res):
    return {(i["check"].split(" ")[0], i["level"]) for i in res["items"]}


def test_sample_times_centred_on_frame():
    ts = render.sample_times(1.0, 30, 180, 4, [])
    assert len(ts) == 4 and abs(sum(ts) / 4 - 1.0) < 1e-9
    assert max(ts) - min(ts) < (180 / 360) / 30


def test_sample_times_never_cross_a_cut():
    t, cut = 1.0, 1.0 + 0.004
    ts = render.sample_times(t, 30, 180, 6, [cut])
    assert ts and all(s < cut for s in ts)
    assert render.sample_times(1.0, 30, 0, 6, []) == [1.0]


def test_slideshow_fails(tmp_path):
    res = check.analyse(make(tmp_path, keep=0, handoff="null"))
    assert res["fails"] >= 1
    assert any("nothing survives" in i["msg"] for i in res["items"])


def test_carried_beat_passes(tmp_path):
    res = check.analyse(make(tmp_path, keep=1, handoff='"keep"'))
    assert res["fails"] == 0, res["items"]
    assert any("carried by" in i["msg"] and "keep" in i["msg"] for i in res["items"])


def test_wrong_handoff_fails(tmp_path):
    res = check.analyse(make(tmp_path, keep=1, handoff='"a"'))
    assert any(i["level"] == "FAIL" and "handoff 'a'" in i["msg"] for i in res["items"])


def test_audio_filter_mixes_cues():
    args, graph = render.audio_args(os.path.join(HERE, "templates", "comp.html"),
                                    [{"t": 0.5, "file": "pop.mp3", "vol": 0.4}], 3.0)
    assert "adelay=500|500" in graph and graph.endswith("[a]") and args.count("-i") == 2
    assert render.loudnorm_tail(graph).endswith("loudnorm=I=-14:TP=-1.5:LRA=11[a]")
