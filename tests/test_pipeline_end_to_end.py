from pathlib import Path

import pytest

from arklight.compiler.pipeline import CompileError, build, compile_site_file


def write_site(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "site.py"
    path.write_text(source)
    return path


SIMPLE_SITE = """
from arklight import *

site = Site()

@site.page("/")
def home():
    return Page(
        Container(Link("Home", href="/"), Link("About", href="/about"), class_name="nav"),
        Heading("ARKlight"),
        Text("Build websites with Python."),
        Button("Get Started"),
        title="ARKlight",
    )

@site.page("/about")
def about():
    return Page(
        Container(Link("Home", href="/"), Link("About", href="/about"), class_name="nav"),
        Heading("About"),
        Text("More info."),
        title="About",
    )
"""


def test_compile_site_file_returns_ir(tmp_path):
    path = write_site(tmp_path, SIMPLE_SITE)
    ir = compile_site_file(path)
    routes = {p.route for p in ir.pages}
    assert routes == {"/", "/about"}


def test_build_writes_html_files(tmp_path):
    site_path = write_site(tmp_path, SIMPLE_SITE)
    out_dir = tmp_path / "dist"

    result = build(site_path, out_dir)

    index_html = (out_dir / "index.html").read_text()
    about_html = (out_dir / "about.html").read_text()

    assert "<h1>ARKlight</h1>" in index_html
    assert "<button>Get Started</button>" in index_html
    assert "<h1>About</h1>" in about_html
    assert len(result.written_paths) == 4  # index.html, about.html, styles.css, arklight.js
    assert (out_dir / "styles.css").exists()
    assert (out_dir / "arklight.js").exists()

    # Nav links must be relative file paths, not root-absolute routes --
    # otherwise opening the file directly (file://) or serving from a
    # subdirectory would break navigation between pages.
    assert 'href="about.html"' in index_html
    assert 'href="index.html"' in about_html
    assert 'href="/about"' not in index_html
    assert '<link rel="stylesheet" href="styles.css">' in index_html


def test_build_raises_compile_error_on_bad_component(tmp_path):
    bad_source = """
from arklight import *
site = Site()

@site.page("/")
def home():
    return Page(Frobnicate("nope"))
"""
    # Frobnicate isn't defined, so this is a NameError at exec time,
    # which load_site wraps as SiteLoadError -> CompileError.
    path = write_site(tmp_path, bad_source)
    with pytest.raises(CompileError):
        build(path, tmp_path / "dist")


def test_build_raises_compile_error_on_validation_failure(tmp_path):
    bad_source = """
from arklight import *
site = Site()

@site.page("/")
def home():
    return Page(Link("no href here"))
"""
    path = write_site(tmp_path, bad_source)
    with pytest.raises(CompileError, match="missing required prop 'href'"):
        build(path, tmp_path / "dist")


def test_build_creates_output_directory(tmp_path):
    path = write_site(tmp_path, SIMPLE_SITE)
    out_dir = tmp_path / "nested" / "dist"
    build(path, out_dir)
    assert (out_dir / "index.html").exists()
