"""Unit tests for motion_style.py's template branding -- the source transform
that swaps in Poppins, defers the template script until fonts load, and
applies preset/content.json `replace` swaps. No browser needed."""
import os

import pytest

import motion_style


def tpl(name):
    return os.path.join(motion_style.STYLES_ROOT, name, "template.html")


@pytest.mark.parametrize("name", motion_style.list_styles())
def test_every_style_brands_and_has_a_preset(name):
    html = motion_style.branded_html(tpl(name), True, motion_style.presets()[name].get("replace"))
    assert motion_style.BRAND_SANS in html
    assert motion_style.UPSTREAM_SANS not in html
    assert 'id="tpl"' in html and "document.fonts.load" in html
    assert set(motion_style.presets()[name]["colors"]) >= {"bg", "c1"}


def test_twenty_styles_vendored():
    assert len(motion_style.list_styles()) == 20


def test_no_brand_leaves_template_untouched():
    src = open(tpl("motion-split-flap"), encoding="utf-8").read()
    assert motion_style.branded_html(tpl("motion-split-flap"), False) == src


def test_preset_replace_removes_demo_content():
    name = "motion-glassmorphism"
    html = motion_style.branded_html(tpl(name), True, motion_style.presets()[name]["replace"])
    assert "'Dubai'" not in html and "8240" not in html


def test_stale_replace_key_is_an_error():
    with pytest.raises(SystemExit, match="not found"):
        motion_style.branded_html(tpl("motion-split-flap"), True, {"'NO SUCH TEXT'": "'x'"})


def test_unknown_style_is_an_error():
    with pytest.raises(SystemExit, match="unknown motion style"):
        motion_style.style_dir("not-a-style")
