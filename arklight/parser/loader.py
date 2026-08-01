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

    try:
        code = compile(source, filename=str(file_path), mode="exec")
        exec(code, module.__dict__)  # noqa: S102 -- intentional: this is the framework's job
    except Exception as exc:  # noqa: BLE001 -- surface any user code error clearly
        raise SiteLoadError(f"Error while running {file_path}: {exc}") from exc

    site_obj = module.__dict__.get(discovered.variable_name)
    if not isinstance(site_obj, Site):
        raise SiteLoadError(
            f"Expected `{discovered.variable_name}` to be a Site instance after "
            f"running {file_path}, but got {type(site_obj).__name__!r}."
        )

    if not site_obj.routes:
        raise SiteLoadError(f"Site `{discovered.variable_name}` has no registered pages.")

    return site_obj, discovered
