"""
Tests for the experimental/legacy API framework -- see
docs/EXPERIMENTAL-APIS.md and arklight/experimental.py.
"""

from __future__ import annotations

import pytest

from arklight import Site, Page, Heading
from arklight.backend.css.custom_styles import render_media_queries
from arklight.compiler.pipeline import compile_site_file, build, CompileError
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


def test_responsive_style_shares_the_css_media_queries_gate(tmp_path):
    """v0.048 Stage B: a node's `responsive_style={...}` prop is a
    second entry point into the same `css-media-queries` feature gate
    `site.media_query(...)` already uses -- see
    docs/EXPERIMENTAL-APIS.md."""
    site_file = tmp_path / "site.py"
    site_file.write_text(
        "from arklight import Site, Page, Container, Text\n"
        "site = Site(name='Test')\n"
        "site.media_query('max-width: 600px', 'hero', {'flex-direction': 'column'})\n"
        "@site.page('/')\n"
        "def home():\n"
        "    return Page(Container(Text('hi'), responsive_style="
        "{'(max-width: 600px)': {'display': 'none'}}))\n"
    )
    ir = compile_site_file(site_file)

    feature_ids = {u.feature_id for u in ir.experimental_usages}
    assert feature_ids == {"css-media-queries"}
    assert len(ir.experimental_usages) == 2


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


# --- css-import (Site.import_style) -------------------------------------


def test_import_style_registers_and_records_experimental_usage():
    site = Site(name="Test")
    site.import_style("https://fonts.googleapis.com/css2?family=Inter")

    assert site.style_imports == ["https://fonts.googleapis.com/css2?family=Inter"]
    assert len(site.experimental_usages) == 1
    assert site.experimental_usages[0].feature_id == "css-import"


def test_import_style_invalid_url_does_not_record_usage():
    site = Site(name="Test")
    with pytest.raises(ValueError):
        site.import_style("")
    with pytest.raises(Exception):
        site.import_style('evil"; } body { color: red')
    assert site.experimental_usages == []


def test_compile_site_file_threads_import_style_usage_into_ir(tmp_path):
    site_file = tmp_path / "site.py"
    site_file.write_text(
        "from arklight import Site, Page, Heading\n"
        "site = Site(name='Test')\n"
        "site.import_style('https://fonts.googleapis.com/css2?family=Inter')\n"
        "@site.page('/')\n"
        "def home():\n"
        "    return Page(Heading('Hi'))\n"
    )
    ir = compile_site_file(site_file)
    assert ir.style_imports == ["https://fonts.googleapis.com/css2?family=Inter"]
    assert len(ir.experimental_usages) == 1
    assert ir.experimental_usages[0].feature_id == "css-import"


def test_build_emits_inline_banner_for_import_style(tmp_path):
    site_file = tmp_path / "site.py"
    site_file.write_text(
        "from arklight import Site, Page, Heading\n"
        "site = Site(name='Test')\n"
        "site.import_style('https://fonts.googleapis.com/css2?family=Inter')\n"
        "@site.page('/')\n"
        "def home():\n"
        "    return Page(Heading('Hi'))\n"
    )
    messages: list[str] = []
    build(site_file, tmp_path / "ARK", on_stage=messages.append)
    banners = [m for m in messages if m.startswith("\u26a0")]
    assert len(banners) == 1
    assert "css-import" in banners[0]

    css = (tmp_path / "ARK" / "styles.css").read_text(encoding="utf-8")
    assert "@import" in css


def test_css_import_summary_mentions_validation_caveat(capsys):
    usage = experimental.emit("css-import")
    experimental.print_summary([usage])
    out = capsys.readouterr().out
    assert "can't be validated by ARKlight" in out


# --- experimental-install-pwa (arklight pwa --install-button) ---

SIMPLE_SITE = """
from arklight import *
site = Site()

@site.page("/")
def home():
    return Page(Heading("Hi"), Text("Hello from ARKlight."))
"""


def _build_dir(tmp_path):
    from arklight.compiler.pipeline import build

    site_path = tmp_path / "site.py"
    site_path.write_text(SIMPLE_SITE)
    out_dir = tmp_path / "ARK"
    build(site_path, out_dir)
    return out_dir


def test_enable_pwa_without_install_button_has_no_experimental_usage(tmp_path):
    from arklight.pwa import enable_pwa

    out_dir = _build_dir(tmp_path)
    result = enable_pwa(out_dir, name="My Site")
    assert result.experimental_usages == []
    html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "ark-pwa-install" not in html


def test_enable_pwa_with_install_button_records_experimental_usage_and_injects(tmp_path):
    from arklight.pwa import enable_pwa

    out_dir = _build_dir(tmp_path)
    result = enable_pwa(out_dir, name="My Site", install_button=True)

    assert len(result.experimental_usages) == 1
    assert result.experimental_usages[0].feature_id == "experimental-install-pwa"
    assert result.experimental_usages[0].component == "Button"

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert 'id="ark-pwa-install"' in html
    assert "beforeinstallprompt" in html


def test_enable_pwa_install_button_is_idempotent_on_rerun(tmp_path):
    from arklight.pwa import enable_pwa

    out_dir = _build_dir(tmp_path)
    enable_pwa(out_dir, name="My Site", install_button=True)
    enable_pwa(out_dir, name="My Site", install_button=True)

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert html.count('id="ark-pwa-install"') == 1


def test_enable_pwa_install_button_removed_when_flag_dropped(tmp_path):
    from arklight.pwa import enable_pwa

    out_dir = _build_dir(tmp_path)
    enable_pwa(out_dir, name="My Site", install_button=True)
    result = enable_pwa(out_dir, name="My Site")

    assert result.experimental_usages == []
    html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "ark-pwa-install" not in html


# --- raw-postprocess (Site.raw_postprocess) ------------------------------


def test_raw_postprocess_registers_and_records_experimental_usage():
    site = Site(name="Test")

    def add_banner(files):
        files["banner.txt"] = "hi"
        return files

    site.raw_postprocess(add_banner)

    assert site.raw_postprocessors == [add_banner]
    assert len(site.experimental_usages) == 1
    assert site.experimental_usages[0].feature_id == "raw-postprocess"


def test_raw_postprocess_rejects_non_callable():
    site = Site(name="Test")
    with pytest.raises(TypeError):
        site.raw_postprocess("not callable")
    assert site.raw_postprocessors == []
    assert site.experimental_usages == []


def test_raw_postprocess_works_as_bare_decorator():
    site = Site(name="Test")

    @site.raw_postprocess
    def strip_comments(files):
        return {k: v for k, v in files.items() if not k.endswith(".tmp")}

    # decorating doesn't shadow the name
    assert callable(strip_comments)
    assert site.raw_postprocessors == [strip_comments]


def test_compile_site_file_threads_raw_postprocessors_into_ir(tmp_path):
    site_file = tmp_path / "site.py"
    site_file.write_text(
        "from arklight import Site, Page, Heading\n"
        "site = Site(name='Test')\n"
        "@site.raw_postprocess\n"
        "def noop(files):\n"
        "    return files\n"
        "@site.page('/')\n"
        "def home():\n"
        "    return Page(Heading('Hi'))\n"
    )
    ir = compile_site_file(site_file)
    assert len(ir.raw_postprocessors) == 1
    assert len(ir.experimental_usages) == 1
    assert ir.experimental_usages[0].feature_id == "raw-postprocess"


def test_compile_site_file_no_raw_postprocess_is_empty(tmp_path):
    site_file = tmp_path / "site.py"
    site_file.write_text(
        "from arklight import Site, Page, Heading\n"
        "site = Site(name='Test')\n"
        "@site.page('/')\n"
        "def home():\n"
        "    return Page(Heading('Hi'))\n"
    )
    ir = compile_site_file(site_file)
    assert ir.raw_postprocessors == []


def test_build_emits_inline_banner_for_raw_postprocess(tmp_path):
    site_file = tmp_path / "site.py"
    site_file.write_text(
        "from arklight import Site, Page, Heading\n"
        "site = Site(name='Test')\n"
        "@site.raw_postprocess\n"
        "def noop(files):\n"
        "    return files\n"
        "@site.page('/')\n"
        "def home():\n"
        "    return Page(Heading('Hi'))\n"
    )
    messages: list[str] = []
    build(site_file, tmp_path / "ARK", on_stage=messages.append)
    banners = [m for m in messages if m.startswith("\u26a0")]
    assert len(banners) == 1
    assert "raw-postprocess" in banners[0]


def test_build_runs_raw_postprocess_over_combined_output(tmp_path):
    site_file = tmp_path / "site.py"
    site_file.write_text(
        "from arklight import Site, Page, Heading\n"
        "site = Site(name='Test')\n"
        "@site.raw_postprocess\n"
        "def add_file(files):\n"
        "    files['robots.txt'] = 'User-agent: *\\nDisallow:'\n"
        "    return files\n"
        "@site.page('/')\n"
        "def home():\n"
        "    return Page(Heading('Hi'))\n"
    )
    out_dir = tmp_path / "ARK"
    result = build(site_file, out_dir)
    assert "robots.txt" in result.output_files
    assert (out_dir / "robots.txt").read_text(encoding="utf-8") == "User-agent: *\nDisallow:"


def test_build_runs_multiple_raw_postprocessors_in_order(tmp_path):
    site_file = tmp_path / "site.py"
    site_file.write_text(
        "from arklight import Site, Page, Heading\n"
        "site = Site(name='Test')\n"
        "@site.raw_postprocess\n"
        "def first(files):\n"
        "    files['order.txt'] = 'first'\n"
        "    return files\n"
        "@site.raw_postprocess\n"
        "def second(files):\n"
        "    files['order.txt'] += ',second'\n"
        "    return files\n"
        "@site.page('/')\n"
        "def home():\n"
        "    return Page(Heading('Hi'))\n"
    )
    out_dir = tmp_path / "ARK"
    build(site_file, out_dir)
    assert (out_dir / "order.txt").read_text(encoding="utf-8") == "first,second"


def test_build_raw_postprocess_error_raises_compile_error(tmp_path):
    site_file = tmp_path / "site.py"
    site_file.write_text(
        "from arklight import Site, Page, Heading\n"
        "site = Site(name='Test')\n"
        "@site.raw_postprocess\n"
        "def boom(files):\n"
        "    raise RuntimeError('kaboom')\n"
        "@site.page('/')\n"
        "def home():\n"
        "    return Page(Heading('Hi'))\n"
    )
    with pytest.raises(CompileError, match="kaboom"):
        build(site_file, tmp_path / "ARK")


def test_build_raw_postprocess_bad_return_type_raises_compile_error(tmp_path):
    site_file = tmp_path / "site.py"
    site_file.write_text(
        "from arklight import Site, Page, Heading\n"
        "site = Site(name='Test')\n"
        "@site.raw_postprocess\n"
        "def bad(files):\n"
        "    return 'not a dict'\n"
        "@site.page('/')\n"
        "def home():\n"
        "    return Page(Heading('Hi'))\n"
    )
    with pytest.raises(CompileError, match="must return a dict"):
        build(site_file, tmp_path / "ARK")


def test_raw_postprocess_summary_mentions_shoot_yourself_in_the_foot(capsys):
    usage = experimental.emit("raw-postprocess")
    experimental.print_summary([usage])
    out = capsys.readouterr().out
    assert "shoot yourself in the foot" in out
    assert "Feature : raw-postprocess" in out


def test_raw_postprocess_inline_banner_says_experimental_feature_active():
    usage = experimental.emit("raw-postprocess")
    banner = experimental.format_inline_banner(usage)
    assert "[EXPERIMENTAL FEATURE ACTIVE]" in banner
    assert "raw-postprocess" in banner
