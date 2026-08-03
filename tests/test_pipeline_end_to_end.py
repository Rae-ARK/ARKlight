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


def test_build_writes_custom_style_classes_to_stylesheet(tmp_path):
    site_path = write_site(
        tmp_path,
        """
from arklight import *

site = Site()
site.style("pull-quote", {"font-style": "italic"})

@site.page("/")
def home():
    return Page(Text("A quote", class_name="pull-quote"))
""",
    )
    out_dir = tmp_path / "ARK"

    build(site_path, out_dir)

    css = (out_dir / "styles.css").read_text(encoding="utf-8")
    html = (out_dir / "index.html").read_text(encoding="utf-8")

    assert ".pull-quote {" in css
    assert "font-style: italic;" in css
    assert 'class="pull-quote"' in html


def test_added_backend_can_postprocess_combined_output_without_editing_existing_backends(tmp_path):
    """
    Demonstrates the "add a backend" extension point: a new Backend can
    see and transform the *combined* output of every other backend's
    render() via postprocess(), without touching HTMLBackend/CSSBackend/
    JSBackend source at all.
    """
    from arklight.backend.base import Backend
    from arklight.compiler.pipeline import default_backends

    class BuildStampBackend(Backend):
        name = "build-stamp"

        def render(self, ir):
            return {"BUILD_STAMP.txt": f"pages={len(ir.pages)}\n"}

        def postprocess(self, output_files):
            # Prove we can see files HTMLBackend/CSSBackend/JSBackend
            # already produced, e.g. to append a generated-by comment.
            stamped = dict(output_files)
            if "index.html" in stamped:
                stamped["index.html"] += "<!-- built by BuildStampBackend -->\n"
            return stamped

    site_path = write_site(tmp_path, SIMPLE_SITE)
    out_dir = tmp_path / "ARK"

    build(site_path, out_dir, backends=[*default_backends(), BuildStampBackend()])

    assert (out_dir / "BUILD_STAMP.txt").read_text(encoding="utf-8") == "pages=2\n"
    assert "<!-- built by BuildStampBackend -->" in (out_dir / "index.html").read_text(encoding="utf-8")


def test_build_on_stage_reports_every_stage_in_order(tmp_path):
    """
    `on_stage` (consumed by the CLI's --verbose/--debug) is called once
    per pipeline stage, in pipeline order, and doesn't change the
    result -- it's purely an observability hook.
    """
    site_path = write_site(tmp_path, SIMPLE_SITE)
    out_dir = tmp_path / "ARK"

    messages: list[str] = []
    result = build(site_path, out_dir, on_stage=messages.append)

    assert messages == [
        "Discovering site and compiling AST trees...",
        "Normalizing AST...",
        "Running validation...",
        "Building website IR...",
        "Rendering backend 'html'...",
        "Rendering backend 'css'...",
        "Rendering backend 'js'...",
        "Postprocessing backend 'html'...",
        "Postprocessing backend 'css'...",
        "Postprocessing backend 'js'...",
        f"Writing {len(result.output_files)} file(s) -> {out_dir}/...",
        "Copying assets...",
        f"Build complete -> {out_dir}/index.html",
    ]


def test_build_without_on_stage_prints_nothing_and_behaves_as_before():
    """`on_stage` is optional -- omitting it must be identical to pre-feature
    behavior (default is a silent no-op, not a required argument)."""
    import inspect

    from arklight.compiler.pipeline import build as build_fn

    sig = inspect.signature(build_fn)
    assert sig.parameters["on_stage"].default is None


def test_compile_site_file_on_stage_reports_its_own_stages(tmp_path):
    site_path = write_site(tmp_path, SIMPLE_SITE)

    messages: list[str] = []
    compile_site_file(site_path, on_stage=messages.append)

    assert messages == [
        "Discovering site and compiling AST trees...",
        "Normalizing AST...",
        "Running validation...",
        "Building website IR...",
    ]
