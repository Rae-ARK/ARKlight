"""
Loads a user's ARKlight site file and returns the live `Site` object.

Static discovery (arklight.parser.discover) tells us *that* pages exist
and what they're called. To get the actual ARK AST -- the ARKNode trees
returned by each page function -- ARKlight needs those functions to run
in a real Python environment (name resolution, imports, loops,
conditionals, helper functions/components: all ordinary Python). So this
step executes the module source in an isolated namespace and hands back
the `Site` instance found there.

This is the same approach Flask, Pelican, and most Python site/app
frameworks use to load user code, and it keeps ARKlight's component
model to "just call a Python function" instead of reimplementing a
Python interpreter.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

from arklight.api import Site
from arklight.parser.discover import DiscoveredSite, discover


class SiteLoadError(RuntimeError):
    pass


def load_site(path: str | Path) -> tuple[Site, DiscoveredSite]:
    """
    Read, statically discover, and execute the site file at `path`.

    Returns (site, discovered) where `site` is the live Site object and
    `discovered` is the static-analysis result from the Python AST stage.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise SiteLoadError(f"Site file not found: {file_path}")

    source = file_path.read_text(encoding="utf-8")

    try:
        discovered = discover(source, filename=str(file_path))
    except SyntaxError as exc:
        raise SiteLoadError(f"Could not parse {file_path}: {exc}") from exc
    except ValueError as exc:
        raise SiteLoadError(str(exc)) from exc

    module = types.ModuleType(file_path.stem)
    module.__file__ = str(file_path)

    # Package-shaped sites (e.g. the `arklight new --template production`
    # scaffold: site.py + components/ + pages/ + content/) import sibling
    # packages with ordinary absolute imports ("from pages.home import
    # home"). Those only resolve if the site file's own directory is on
    # sys.path -- true by accident when running `python site.py`
    # directly, but NOT true for the installed `arklight` console
    # script, whose sys.path[0] is wherever that script lives, not the
    # user's project directory. Add it here, once, so behavior doesn't
    # depend on how `arklight` was invoked; remove it again afterward so
    # repeated builds (e.g. in a test session) don't accumulate stale
    # entries or leak one project's modules into another's.
    site_dir = str(file_path.resolve().parent)
    added_to_path = site_dir not in sys.path
    if added_to_path:
        sys.path.insert(0, site_dir)

    # Package-shaped sites commonly use generic top-level package names
    # ("pages", "components", "content"). If two different projects are
    # loaded in the same process (e.g. a script that builds several
    # ARKlight sites, or a test suite), Python's import system caches
    # the first one it sees in sys.modules and happily hands it back
    # for the second project too -- even though that cached package's
    # __path__ points at the *first* project's directory, not this
    # one. Record what's in sys.modules before exec so anything it adds
    # can be evicted again afterward, keeping each load_site() call
    # isolated regardless of naming collisions between projects.
    modules_before = set(sys.modules)

    try:
        code = compile(source, filename=str(file_path), mode="exec")
        exec(code, module.__dict__)  # noqa: S102 -- intentional: this is the framework's job
    except Exception as exc:  # noqa: BLE001 -- surface any user code error clearly
        raise SiteLoadError(f"Error while running {file_path}: {exc}") from exc
    finally:
        if added_to_path:
            sys.path.remove(site_dir)
        for mod_name in set(sys.modules) - modules_before:
            mod_file = getattr(sys.modules.get(mod_name), "__file__", None)
            if mod_file and str(Path(mod_file).resolve()).startswith(site_dir + os.sep):
                del sys.modules[mod_name]

    site_obj = module.__dict__.get(discovered.variable_name)
    if not isinstance(site_obj, Site):
        raise SiteLoadError(
            f"Expected `{discovered.variable_name}` to be a Site instance after "
            f"running {file_path}, but got {type(site_obj).__name__!r}."
        )

    if not site_obj.routes:
        raise SiteLoadError(f"Site `{discovered.variable_name}` has no registered pages.")

    return site_obj, discovered
