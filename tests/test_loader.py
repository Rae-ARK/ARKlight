from pathlib import Path

import pytest

from arklight.parser.loader import SiteLoadError, load_site

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def write_site(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "site.py"
    path.write_text(source)
    return path


def test_load_site_returns_live_site_object(tmp_path):
    path = write_site(
        tmp_path,
        """
from arklight import *
site = Site()

@site.page("/")
def home():
    return Page(Heading("Hi"))
""",
    )
    site, discovered = load_site(path)
    assert discovered.variable_name == "site"
    assert "/" in site.routes


def test_load_site_missing_file_raises():
    with pytest.raises(SiteLoadError, match="not found"):
        load_site("/does/not/exist.py")


def test_load_site_runtime_error_is_wrapped(tmp_path):
    path = write_site(
        tmp_path,
        """
from arklight import *
site = Site()

@site.page("/")
def home():
    raise RuntimeError("boom")
    return Page(Heading("Hi"))
""",
    )
    # runtime errors inside page functions surface later (build_ark_ast),
    # but errors during *module exec* (e.g. bad top-level code) surface here.
    site, discovered = load_site(path)
    with pytest.raises(RuntimeError, match="boom"):
        site.build_ark_ast()


def test_load_site_bad_toplevel_code_wrapped(tmp_path):
    path = write_site(
        tmp_path,
        """
from arklight import *
site = Site()
1 / 0

@site.page("/")
def home():
    return Page(Heading("Hi"))
""",
    )
    with pytest.raises(SiteLoadError, match="Error while running"):
        load_site(path)


def test_load_site_no_pages_raises(tmp_path):
    path = write_site(tmp_path, "from arklight import *\nsite = Site()\n")
    with pytest.raises(SiteLoadError, match="No pages registered"):
        load_site(path)
