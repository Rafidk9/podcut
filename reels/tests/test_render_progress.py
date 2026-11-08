"""render_progress.py: the bar's throttling, parsing HyperFrames' real output
format, and hf_render against a fake CLI over a real pipe."""
import json
import subprocess
import time

import pytest

import render_progress as rp

# Shape captured from `hyperframes render` 0.7.26 with stdout piped.
REAL_LINE = ("\x1b[2K  " + "\u2588" * 5 + "\u2591" * 20 + "  20%  Processing audio tracks"
             + '[INFO] [Render:trace] {"phase":"compile"}\n').encode("utf-8")


def test_parse_real_progress_line_stops_before_trailing_log():
    assert rp.parse_hf_progress(REAL_LINE) == (20, "Processing audio tracks")


def test_parse_with_forced_colour():
    line = "\x1b[2K  \x1b[32m\u2588\x1b[39m\x1b[2m\u2591\x1b[22m  \x1b[1m7%\x1b[22m  \x1b[2mCompiling\x1b[22m"
    assert rp.parse_hf_progress(line.encode("utf-8")) == (7, "Compiling")


@pytest.mark.parametrize("line", [
    b"", b"[INFO] 50% of something", b"  rendered 100% ok",
    "\u25c7  C:\\out.webm".encode("utf-8")])
def test_parse_ignores_non_progress(line):
    assert rp.parse_hf_progress(line) is None


def test_parse_survives_multibyte_split_across_reads():
    assert rp.parse_hf_progress(REAL_LINE[:9]) is None


def test_log_mode_throttles_to_discrete_lines(capsys, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(rp.time, "time", lambda: clock[0])
    bar = rp.Progress("x", 100)
    for i in range(101):
        clock[0] += 1
        bar.update(i)
    bar.finish()
    lines = capsys.readouterr().out.splitlines()
    assert "\r" not in "".join(lines)
    assert 10 <= len(lines) <= 22
    assert lines[-1] == "x: done in 101.0s"


def test_interactive_redraws_in_place_and_fits_terminal(capsys, monkeypatch):
    monkeypatch.setattr(rp.shutil, "get_terminal_size", lambda: type("S", (), {"columns": 60}))
    clock = [0.0]
    monkeypatch.setattr(rp.time, "time", lambda: clock[0])
    bar = rp.Progress("a-long-render-label", 10)
    bar.interactive = True
    for i in range(1, 11):
        clock[0] += 1
        bar.update(i, "Streaming frame 123/456 with a long tail")
    bar.finish()
    out = capsys.readouterr().out
    assert out.count("\n") == 1
    assert all(len(seg.rstrip("\n")) <= 59 for seg in out.split("\r"))


def test_heartbeat_redraws_while_idle_and_stops_on_finish(capsys, monkeypatch):
    monkeypatch.setattr(rp, "_HEARTBEAT_SECONDS", 0.02)
    monkeypatch.setattr(rp.sys.stdout, "isatty", lambda: True, raising=False)
    bar = rp.Progress("x", 10)
    time.sleep(0.15)  # >_TTY_MIN_INTERVAL, so the first update draws
    bar.update(5, "encoding")
    time.sleep(0.15)
    bar.finish()
    out = capsys.readouterr().out
    assert out.count("encoding") >= 3
    assert out.rstrip().endswith("s")
    time.sleep(0.1)
    assert capsys.readouterr().out == ""


def test_percent_clamped_past_total(capsys, monkeypatch):
    monkeypatch.setattr(rp, "_LOG_MIN_INTERVAL", 0)
    bar = rp.Progress("x", 3)
    bar.update(7)
    assert "100%" in capsys.readouterr().out


def test_tick_counts_up():
    bar = rp.Progress("x", 5)
    bar.tick()
    bar.tick()
    assert bar.done == 2


def test_build_broll_render_accepts_on_progress_keyword():
    import inspect
    import build_broll
    params = inspect.signature(build_broll.render).parameters
    assert list(params)[:4] == ["name", "dur", "body_html", "extra_css"]
    assert "on_progress" in params


FAKE_CLI = r"""
const bar = '\u2588'.repeat(5) + '\u2591'.repeat(20);
const fs = require('fs');
fs.writeFileSync('argv.json', JSON.stringify({argv: process.argv, stdinTTY: !!process.stdin.isTTY}));
process.stdout.write('[INFO] starting\n');
process.stdout.write('\r\x1b[2K  ' + bar + '  25%  Starting frame capture');
process.stdout.write('\r\x1b[2K  ' + bar + '  80%  Streaming frame 15/15[INFO] x\n');
if (process.env.FAKE_FAIL) {
  console.error('Error: Chrome crashed');
  process.exit(3);
}
process.stdout.write('\r\x1b[2K  ' + bar + '  100%  Render complete');
"""


@pytest.fixture
def cli(tmp_path):
    p = tmp_path / "cli.js"
    p.write_text(FAKE_CLI, encoding="utf-8")
    return str(p)


def test_hf_render_reports_progress_and_builds_command(cli, tmp_path):
    seen = []
    rp.hf_render(cli, str(tmp_path), str(tmp_path / "o.webm"), 30, "draft", fmt="webm",
                 on_progress=lambda p, s: seen.append((p, s)))
    assert (25, "Starting frame capture") in seen
    assert (80, "Streaming frame 15/15") in seen
    assert seen[-1] == (100, "Render complete")
    info = json.load(open(tmp_path / "argv.json"))
    assert "--quiet" not in info["argv"]
    assert info["argv"][-2:] == ["--format", "webm"]


def test_hf_render_stdin_is_never_a_tty(cli, tmp_path):
    """The CLI's "How was this render?" prompt only fires on a TTY stdin."""
    rp.hf_render(cli, str(tmp_path), str(tmp_path / "o.mp4"), 30, "draft", on_progress=lambda p, s: None)
    assert json.load(open(tmp_path / "argv.json"))["stdinTTY"] is False


def test_hf_render_failure_raises_with_cli_error_text(cli, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FAKE_FAIL", "1")
    with pytest.raises(subprocess.CalledProcessError) as e:
        rp.hf_render(cli, str(tmp_path), str(tmp_path / "o.mp4"), 30, "draft")
    assert e.value.returncode == 3
    assert "Chrome crashed" in e.value.output
    assert "[INFO]" not in e.value.output
    captured = capsys.readouterr()
    assert "Chrome crashed" in captured.err
    assert "o.mp4: FAILED after" in captured.out
