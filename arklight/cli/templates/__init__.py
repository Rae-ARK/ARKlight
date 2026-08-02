"""
In-package project templates for `arklight new`.

Each template is a callable `name -> dict[relative_path, contents]`
(plain string building, no templating dependency -- consistent with
"no runtime dependencies beyond the build backend"), registered in
`TEMPLATES` below. See docs/DESIGN-NOTES.md, "v0.004: CLI scaffolding
(`arklight new`)", for the full design this implements.

- `simple`     -- `templates.simple.build`: a single `site.py`, the
  zero-thinking path from `arklight new my-site` to a working
  `arklight build`.
- `production` -- `templates.production.build`: a `site.py` +
  `components/` + `pages/` + `content/` + `assets/` layout for sites
  that outgrow one file.
"""

from __future__ import annotations

from typing import Callable

from arklight.cli.templates import production, simple

TemplateBuilder = Callable[[str], dict[str, str]]

TEMPLATES: dict[str, TemplateBuilder] = {
    "simple": simple.build,
    "production": production.build,
}

__all__ = ["TEMPLATES"]
