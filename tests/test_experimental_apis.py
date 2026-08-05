"""
Tests for the experimental/legacy API framework -- see
docs/EXPERIMENTAL-APIS.md and arklight/experimental.py.
"""

from __future__ import annotations

import pytest

from arklight import Site, Page, Heading
from arklight.backend.css.custom_styles import render_media_queries
from arklight.compiler.pipeline import compile_site_file, build
from arklight import experimental


def test_media_query_registers_and_records_experimental_usage():
    site = Site(name="Test")
    site.media_query("max-width: 600px", "hero", {"flex-direction": "column"})

    assert site.custom_media_queries == [
        ("max-width: 600px", "hero", {"flex-direction": "column"})
    ]
    assert len(site.experimental_usages) == 1
    assert site.experimental_usages[0].feature_id == "css-media-queries"


def test_media_query_validates_class_name():
    site = Site(name="Test")
    with pytest.raises(ValueError):
        site.media_query("max-width: 600px", "1bad", {"color": "red"})


def test_media_query_validates_non_empty_rules():
    site = Site(name="Test")
    with pytest.raises(ValueError):
        site.media_query("max-width: 600px", "hero", {})


def test_media_query_rejects_pseudo_class_keys():
    site = Site(name="Test")
    with pytest.raises(ValueError):
        site.media_query("max-width: 600px", "hero", {":hover:color": "red"})


def test_render_media_queries_empty_is_empty_string():
    assert render_media_queries([]) == ""


def test_render_media_queries_produces_at_media_block():
    css = render_media_queries([("max-width: 600px", "hero", {"flex-direction": "column"})])
    assert "@media (max-width: 600px)" in css
    assert ".hero {" in css
    assert "flex-direction: column;" in css


def test_compile_site_file_threads_media_queries_into_ir(tmp_path):
    site_file = tmp_path / "site.py"
    site_file.write_text(
        "from arklight import Site, Page, Heading\n"
        "site = Site(name='Test')\n"
        "site.media_query('max-width: 600px', 'hero', {'flex-direction': 'column'})\n"
        "@site.page('/')\n"
        "def home():\n"
        "    return Page(Heading('Hi'))\n"
    )
    ir = compile_site_file(site_file)
    assert ir.media_queries == [("max-width: 600px", "hero", {"flex-direction": "column"})]
    assert len(ir.experimental_usages) == 1
    assert ir.experimental_usages[0].feature_id == "css-media-queries"


def test_compile_site_file_no_media_queries_is_empty(tmp_path):
    site_file = tmp_path / "site.py"
    site_file.write_text(
        "from arklight import Site, Page, Heading\n"
        "site = Site(name='Test')\n"
        "@site.page('/')\n"
        "def home():\n"
        "    return Page(Heading('Hi'))\n"
    )
    ir = compile_site_file(site_file)
    assert ir.media_queries == []
    assert ir.experimental_usages == []


def test_build_emits_inline_banner_via_on_stage(tmp_path):
    site_file = tmp_path / "site.py"
    site_file.write_text(
        "from arklight import Site, Page, Heading\n"
        "site = Site(name='Test')\n"
        "site.media_query('max-width: 600px', 'hero', {'flex-direction': 'column'})\n"
        "@site.page('/')\n"
        "def home():\n"
        "    return Page(Heading('Hi'))\n"
    )
    messages: list[str] = []
    build(site_file, tmp_path / "ARK", on_stage=messages.append)
    banners = [m for m in messages if m.startswith("\u26a0")]
    assert len(banners) == 1
    assert "css-media-queries" in banners[0]

    css = (tmp_path / "ARK" / "styles.css").read_text(encoding="utf-8")
    assert "@media (max-width: 600px)" in css


def test_experimental_emit_unknown_feature_raises():
    with pytest.raises(KeyError):
        experimental.emit("not-a-real-feature")


def test_experimental_print_summary_deduplicates(capsys):
    usages = [
        experimental.emit("css-media-queries"),
        experimental.emit("css-media-queries"),
    ]
    experimental.print_summary(usages)
    out = capsys.readouterr().out
    assert out.count("Legacy API detected: css-media-queries") == 1
