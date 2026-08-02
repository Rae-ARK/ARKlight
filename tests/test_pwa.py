import json
from pathlib import Path

import pytest

from arklight.compiler.pipeline import build
from arklight.pwa import MANIFEST_NAME, SERVICE_WORKER_NAME, PWAError, enable_pwa

SIMPLE_SITE = """
from arklight import *
site = Site()

@site.page("/")
def home():
    return Page(Heading("Hi"), Text("Hello from ARKlight."))

@site.page("/about")
def about():
    return Page(Heading("About"))
"""


def write_site(tmp_path: Path) -> Path:
    path = tmp_path / "site.py"
    path.write_text(SIMPLE_SITE)
    return path


def build_dir(tmp_path: Path) -> Path:
    site_path = write_site(tmp_path)
    out_dir = tmp_path / "ARK"
    build(site_path, out_dir)
    return out_dir


def test_enable_pwa_writes_manifest_and_service_worker(tmp_path):
    out_dir = build_dir(tmp_path)

    result = enable_pwa(out_dir, name="My Site")

    manifest_path = out_dir / MANIFEST_NAME
    sw_path = out_dir / SERVICE_WORKER_NAME
    assert manifest_path.exists()
    assert sw_path.exists()
    assert result.manifest_path == manifest_path
    assert result.service_worker_path == sw_path

    manifest = json.loads(manifest_path.read_text())
    assert manifest["name"] == "My Site"
    assert manifest["short_name"] == "My Site"[:12]
    assert manifest["display"] == "standalone"


def test_enable_pwa_injects_every_page(tmp_path):
    out_dir = build_dir(tmp_path)

    result = enable_pwa(out_dir, name="My Site")

    assert set(result.updated_pages) == {"index.html", "about.html"}
    for rel_path in result.updated_pages:
        html = (out_dir / rel_path).read_text()
        assert '<link rel="manifest" href="manifest.json">' in html
        assert 'navigator.serviceWorker.register("sw.js")' in html
        assert '<meta name="theme-color" content="#000000">' in html


def test_enable_pwa_precaches_every_build_file(tmp_path):
    out_dir = build_dir(tmp_path)

    result = enable_pwa(out_dir, name="My Site")

    assert "index.html" in result.cached_paths
    assert "about.html" in result.cached_paths
    assert "styles.css" in result.cached_paths
    assert "arklight.js" in result.cached_paths
    assert MANIFEST_NAME in result.cached_paths

    sw_contents = (out_dir / SERVICE_WORKER_NAME).read_text()
    assert result.cache_name in sw_contents
    for path in result.cached_paths:
        assert json.dumps(path) in sw_contents


def test_enable_pwa_is_idempotent(tmp_path):
    out_dir = build_dir(tmp_path)

    enable_pwa(out_dir, name="My Site")
    first_html = (out_dir / "index.html").read_text()
    first_sw = (out_dir / SERVICE_WORKER_NAME).read_text()

    enable_pwa(out_dir, name="My Site")
    second_html = (out_dir / "index.html").read_text()
    second_sw = (out_dir / SERVICE_WORKER_NAME).read_text()

    assert first_html == second_html
    assert first_sw == second_sw
    # No duplicated injection markers from a second run.
    assert first_html.count("arklight:pwa:head") == 2  # start + end marker
    assert first_html.count("arklight:pwa:sw") == 2


def test_enable_pwa_cache_name_changes_when_build_changes(tmp_path):
    out_dir = build_dir(tmp_path)
    result_one = enable_pwa(out_dir, name="My Site")

    (out_dir / "extra.txt").write_text("new file")
    result_two = enable_pwa(out_dir, name="My Site")

    assert result_one.cache_name != result_two.cache_name
    assert "extra.txt" in result_two.cached_paths


def test_enable_pwa_raises_on_missing_build_dir(tmp_path):
    with pytest.raises(PWAError, match="not found"):
        enable_pwa(tmp_path / "nope", name="My Site")


def test_enable_pwa_raises_on_dir_without_html(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(PWAError, match="No .html files"):
        enable_pwa(empty_dir, name="My Site")


def test_enable_pwa_respects_custom_options(tmp_path):
    out_dir = build_dir(tmp_path)

    result = enable_pwa(
        out_dir,
        name="My Site",
        short_name="MS",
        start_url="index.html",
        theme_color="#123456",
        background_color="#abcdef",
        display="fullscreen",
    )

    manifest = json.loads((out_dir / MANIFEST_NAME).read_text())
    assert manifest["short_name"] == "MS"
    assert manifest["theme_color"] == "#123456"
    assert manifest["background_color"] == "#abcdef"
    assert manifest["display"] == "fullscreen"

    for rel_path in result.updated_pages:
        html = (out_dir / rel_path).read_text()
        assert '<meta name="theme-color" content="#123456">' in html


def test_enable_pwa_relative_hrefs_for_nested_pages(tmp_path):
    nested_site = """
from arklight import *
site = Site()

@site.page("/")
def home():
    return Page(Heading("Hi"))

@site.page("/blog/post")
def post():
    return Page(Heading("Post"))
"""
    site_path = tmp_path / "site.py"
    site_path.write_text(nested_site)
    out_dir = tmp_path / "ARK"
    build(site_path, out_dir)

    enable_pwa(out_dir, name="My Site")

    nested_html = (out_dir / "blog" / "post.html").read_text()
    assert '<link rel="manifest" href="../manifest.json">' in nested_html
    assert 'navigator.serviceWorker.register("../sw.js")' in nested_html

    root_html = (out_dir / "index.html").read_text()
    assert '<link rel="manifest" href="manifest.json">' in root_html
