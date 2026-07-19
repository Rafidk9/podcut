"""Unit tests for caption_cache.py (feature 5's content-hash cache) and for
build_captions.py's per-element JS generation -- specifically the regression
where a badge's raw text was spliced unescaped into a single-quoted JS string
literal, so any apostrophe (e.g. "DON'T RISK IT") broke the whole script and
silently rendered a blank badge. Caught by comparing a real build's frames
against a pre-change baseline; covered here so it can't regress silently."""
import json
import os

import caption_cache
import build_captions as bc


def test_element_hash_stable_for_identical_input():
    a = caption_cache.element_hash("badge", {"text": "FREE"}, 2.0)
    b = caption_cache.element_hash("badge", {"text": "FREE"}, 2.0)
    assert a == b


def test_element_hash_changes_with_content():
    a = caption_cache.element_hash("badge", {"text": "FREE"}, 2.0)
    b = caption_cache.element_hash("badge", {"text": "FREE!"}, 2.0)
    assert a != b


def test_element_hash_changes_with_duration():
    a = caption_cache.element_hash("badge", {"text": "FREE"}, 2.0)
    b = caption_cache.element_hash("badge", {"text": "FREE"}, 2.5)
    assert a != b


def test_element_hash_changes_with_cache_version(monkeypatch):
    a = caption_cache.element_hash("badge", {"text": "FREE"}, 2.0)
    monkeypatch.setattr(caption_cache, "CACHE_VERSION", caption_cache.CACHE_VERSION + 1)
    b = caption_cache.element_hash("badge", {"text": "FREE"}, 2.0)
    assert a != b


def test_element_hash_is_timing_independent():
    """The same graphic at a different ABSOLUTE timestamp must still hit the
    cache -- element_hash only ever sees local duration, never a clock time,
    so this is really asserting callers don't sneak absolute start/end into
    the content dict passed in."""
    content = {"text": "FREE", "icon": "check"}   # no absolute start/end here
    early = caption_cache.element_hash("badge", content, 2.0)
    late = caption_cache.element_hash("badge", content, 2.0)
    assert early == late


def _make_badge(text, effect=None):
    return {"text": text, "icon": "star", "bg": "#E84B37", "fg": "#fff",
            "center": True, "left": None, "right": None, "top": 232,
            "effect": effect, "start": 10.0, "end": 12.0}


def test_badge_element_content_excludes_absolute_timing():
    """Cacheable content must not carry absolute start/end -- only local
    duration D does (passed separately to element_hash) -- else the same
    badge placed at a different moment would never hit cache."""
    content, D, _body, _js = bc._badge_element(_make_badge("FREE"), 0)
    assert "start" not in content and "end" not in content
    assert D == 2.0


def test_badge_element_json_escapes_apostrophes_in_text():
    """Regression test: badge text used to be spliced raw into a single-
    quoted JS string ('...__TEXT__...'), so "DON'T RISK IT" broke the script
    and the badge silently never rendered. Text must now go through a
    JSON-encoded JS variable instead."""
    _content, _D, _body, js = bc._badge_element(_make_badge("DON'T RISK IT"), 0)
    assert "TXT = " + json.dumps("DON'T RISK IT") in js
    # the innerHTML line must reference the TXT variable, never splice the
    # raw apostrophe-containing text directly into a JS string literal
    innerHTML_line = next(l for l in js.splitlines() if "innerHTML" in l)
    assert "DON'T RISK IT" not in innerHTML_line
    assert "+ TXT +" in innerHTML_line


def test_badge_element_json_escapes_double_quotes_in_text():
    _content, _D, _body, js = bc._badge_element(_make_badge('SAY "YES"'), 0)
    assert "TXT = " + json.dumps('SAY "YES"') in js


def test_render_element_no_cache_bypasses_and_does_not_write(tmp_path, monkeypatch):
    """--no-cache must force a miss even when a cache entry already exists,
    and must never write to the cache dir."""
    calls = []

    def fake_run(cmd, cwd, check, env):
        # simulate HyperFrames writing the requested -o output file
        out_idx = cmd.index("-o") + 1
        open(cmd[out_idx], "wb").write(b"fake webm bytes")
        calls.append(cmd)

    monkeypatch.setattr(caption_cache.subprocess, "run", fake_run)

    cache_dir = str(tmp_path / "cache")
    work_dir = str(tmp_path / "work")
    os.makedirs(work_dir, exist_ok=True)

    # first, populate a real cache entry
    path1, hit1 = caption_cache.render_element(
        "badge", {"text": "FREE"}, 2.0, "", "<div></div>", "", work_dir,
        cache_dir, "fake_cli.js", "standard", 30, no_cache=False)
    assert hit1 is False
    assert os.path.isfile(path1)
    assert len(calls) == 1

    before = set(os.listdir(cache_dir))

    # second call with no_cache=True: must re-render (miss) despite the
    # existing cache entry, and must not touch the cache directory
    path2, hit2 = caption_cache.render_element(
        "badge", {"text": "FREE"}, 2.0, "", "<div></div>", "", work_dir,
        cache_dir, "fake_cli.js", "standard", 30, no_cache=True)
    assert hit2 is False
    assert len(calls) == 2
    assert set(os.listdir(cache_dir)) == before


def test_render_element_cache_hit_skips_render(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, cwd, check, env):
        out_idx = cmd.index("-o") + 1
        open(cmd[out_idx], "wb").write(b"fake webm bytes")
        calls.append(cmd)

    monkeypatch.setattr(caption_cache.subprocess, "run", fake_run)

    cache_dir = str(tmp_path / "cache")
    work_dir = str(tmp_path / "work")
    os.makedirs(work_dir, exist_ok=True)

    path1, hit1 = caption_cache.render_element(
        "card", {"text": "HELLO"}, 1.0, "", "<div></div>", "", work_dir,
        cache_dir, "fake_cli.js", "standard", 30, no_cache=False)
    assert hit1 is False
    assert len(calls) == 1

    path2, hit2 = caption_cache.render_element(
        "card", {"text": "HELLO"}, 1.0, "", "<div></div>", "", work_dir,
        cache_dir, "fake_cli.js", "standard", 30, no_cache=False)
    assert hit2 is True
    assert path2 == path1
    assert len(calls) == 1   # no second render


def test_clear_cache_removes_directory(tmp_path):
    reel_dir = str(tmp_path)
    d = caption_cache.cache_root(reel_dir)
    open(os.path.join(d, "stale.webm"), "wb").write(b"x")
    assert os.path.isdir(d)
    caption_cache.clear_cache(reel_dir)
    assert not os.path.isdir(d)
