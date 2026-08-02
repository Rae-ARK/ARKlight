import sys
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


def test_load_site_adds_site_dir_to_sys_path_for_sibling_imports(tmp_path):
    """Package-shaped sites (the `arklight new --template production`
    scaffold: site.py + pages/ + components/ + content/) import
    sibling packages with ordinary absolute imports. Those only
    resolve if the site file's own directory is on sys.path -- true by
    accident when running `python site.py` directly, but not
    guaranteed for the installed `arklight` console script. Regression
    test for that fix in arklight.parser.loader.load_site."""
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "__init__.py").write_text("")
    (tmp_path / "pages" / "home.py").write_text(
        "from arklight import *\n\ndef home():\n    return Page(Heading('Hi'))\n"
    )
    path = write_site(
        tmp_path,
        """
from arklight import *
from pages.home import home

site = Site()

@site.page("/")
def home_page():
    return home()
""",
    )

    site, _discovered = load_site(path)

    assert "/" in site.routes


def test_load_site_removes_site_dir_from_sys_path_afterward(tmp_path):
    """The sys.path entry load_site adds for sibling imports should not
    leak into the rest of the process once loading finishes."""
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

    load_site(path)

    assert str(tmp_path.resolve()) not in sys.path


def test_load_site_does_not_leak_module_cache_across_projects(tmp_path):
    """Two different projects that both happen to use a top-level
    `pages` package must not see each other's modules. Before this
    fix, whichever project loaded first won: Python's import system
    caches the first `pages` package it sees in sys.modules and hands
    it back for the second project too, even though its __path__
    points at the first project's directory."""
    project_a = tmp_path / "project_a"
    project_b = tmp_path / "project_b"
    for project, marker in [(project_a, "A"), (project_b, "B")]:
        (project / "pages").mkdir(parents=True)
        (project / "pages" / "__init__.py").write_text("")
        (project / "pages" / "home.py").write_text(
            f"from arklight import *\n\ndef home():\n    return Page(Heading('{marker}'))\n"
        )
        (project / "site.py").write_text(
            """
from arklight import *
from pages.home import home

site = Site()

@site.page("/")
def home_page():
    return home()
"""
        )

    site_a, _ = load_site(project_a / "site.py")
    site_b, _ = load_site(project_b / "site.py")

    page_a = site_a.routes["/"]()
    page_b = site_b.routes["/"]()
    assert page_a.children[0].children[0] == "A"
    assert page_b.children[0].children[0] == "B"
