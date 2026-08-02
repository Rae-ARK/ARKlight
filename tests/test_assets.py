"""
`arklight build` auto-copies a top-level `assets/` folder (next to the
site's entry file) into `<output_dir>/assets`. Previously this was a
manual, easy-to-forget `cp -r assets dist/assets` step -- see
docs/DESIGN-NOTES.md.
"""

from pathlib import Path

from arklight.compiler.pipeline import build

SIMPLE_SITE = """
from arklight import *
site = Site()

@site.page("/")
def home():
    return Page(Heading("Hi"))
"""


def _write_site(tmp_path: Path) -> Path:
    path = tmp_path / "site.py"
    path.write_text(SIMPLE_SITE)
    return path


def test_build_copies_top_level_assets_folder(tmp_path):
    site_path = _write_site(tmp_path)
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "logo.svg").write_text("<svg></svg>")
    (assets_dir / "images").mkdir()
    (assets_dir / "images" / "hero.png").write_text("fake-png-bytes")

    out_dir = tmp_path / "ARK"
    result = build(site_path, out_dir)

    assert (out_dir / "assets" / "logo.svg").read_text() == "<svg></svg>"
    assert (out_dir / "assets" / "images" / "hero.png").exists()
    assert out_dir / "assets" / "logo.svg" in result.written_paths


def test_build_without_assets_folder_does_not_create_one(tmp_path):
    site_path = _write_site(tmp_path)
    out_dir = tmp_path / "ARK"

    build(site_path, out_dir)

    assert not (out_dir / "assets").exists()


def test_build_assets_overwrite_on_rebuild(tmp_path):
    site_path = _write_site(tmp_path)
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "logo.svg").write_text("v1")

    out_dir = tmp_path / "ARK"
    build(site_path, out_dir)
    assert (out_dir / "assets" / "logo.svg").read_text() == "v1"

    (assets_dir / "logo.svg").write_text("v2")
    build(site_path, out_dir)
    assert (out_dir / "assets" / "logo.svg").read_text() == "v2"
