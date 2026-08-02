import zipfile
from pathlib import Path

import pytest

from arklight.cli.main import main
from arklight.compiler.pipeline import build
from arklight.packer.bundle import PackError, pack

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


def test_pack_produces_a_bundle_file(tmp_path):
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"

    result = pack(out_dir, bundle_path)

    assert bundle_path.exists()
    assert result.output_path == bundle_path
    assert "index.html" in result.packed_paths
    assert "styles.css" in result.packed_paths
    assert "arklight.js" in result.packed_paths
    assert "about.html" in result.packed_paths


def test_bundle_front_matter_is_self_contained_html(tmp_path):
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"
    pack(out_dir, bundle_path)

    data = bundle_path.read_bytes()
    html_end = data.index(b"</html>") + len(b"</html>")
    front_matter = data[:html_end].decode("utf-8")

    assert front_matter.startswith("<!DOCTYPE html")
    # The <link>/<script src> tags are replaced with inlined content --
    # nothing in the front matter should still point at an external file.
    assert "styles.css" not in front_matter
    assert "arklight.js" not in front_matter
    assert "<style>" in front_matter
    assert "<script>" in front_matter
    # The actual CSS/JS content made it into the inlined tags.
    assert "body" in front_matter  # from the default stylesheet


def test_bundle_is_still_a_valid_zip_of_the_original_build(tmp_path):
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"
    pack(out_dir, bundle_path)

    with zipfile.ZipFile(bundle_path) as zf:
        assert zf.testzip() is None
        names = set(zf.namelist())
        assert names == {"index.html", "about.html", "styles.css", "arklight.js"}
        # The zip's copy of index.html is the *original*, un-inlined
        # build output -- extracting it should work exactly like a
        # normal `arklight build` folder.
        extracted_index = zf.read("index.html").decode("utf-8")
        assert '<link rel="stylesheet" href="styles.css">' in extracted_index
        assert '<script src="arklight.js" defer></script>' in extracted_index


def test_assets_are_carried_into_the_bundle(tmp_path):
    out_dir = build_dir(tmp_path)
    assets_dir = out_dir / "assets"
    assets_dir.mkdir()
    raw_png = b"\x89PNG\r\n fake"
    (assets_dir / "logo.png").write_bytes(raw_png)

    bundle_path = tmp_path / "site.ark"
    result = pack(out_dir, bundle_path)

    assert "assets/logo.png" in result.packed_paths
    assert result.skipped_paths == []

    with zipfile.ZipFile(bundle_path) as zf:
        assert "assets/logo.png" in zf.namelist()
        # Carried in as raw bytes, untouched.
        assert zf.read("assets/logo.png") == raw_png


def test_pack_raises_on_missing_build_dir(tmp_path):
    with pytest.raises(PackError, match="not found"):
        pack(tmp_path / "does-not-exist", tmp_path / "site.ark")


def test_pack_raises_on_incomplete_build_dir(tmp_path):
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    (incomplete / "index.html").write_text("<html></html>")
    # styles.css / arklight.js missing

    with pytest.raises(PackError, match="styles.css"):
        pack(incomplete, tmp_path / "site.ark")


def test_cli_pack_success(tmp_path, capsys):
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"

    exit_code = main(["pack", str(out_dir), "-o", str(bundle_path)])

    assert exit_code == 0
    assert bundle_path.exists()
    captured = capsys.readouterr()
    assert "packed" in captured.out
    assert str(bundle_path) in captured.out


def test_cli_pack_default_output_is_site_ark(tmp_path, monkeypatch):
    out_dir = build_dir(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["pack", str(out_dir)])

    assert exit_code == 0
    assert (tmp_path / "site.ark").exists()


def test_cli_pack_failure_returns_nonzero(tmp_path, capsys):
    missing_dir = tmp_path / "nope"

    exit_code = main(["pack", str(missing_dir)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "ARKlight pack failed" in captured.err
