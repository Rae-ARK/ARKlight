"""
Reserved for v0.004 (`arklight new` CLI scaffolding).

Scaffolding only -- no `new` subcommand and no template file contents
live here yet, only the folder shape. Per `docs/DESIGN-NOTES.md`
("v0.004: CLI scaffolding (`arklight new`)"), this package will hold
two templates as an in-package dict of relative path -> file contents
(f-strings, no templating dependency):

- `templates/simple/` -- a single `site.py`, mirroring
  `examples/hello_site/` almost exactly. Zero-thinking path from
  `arklight new my-site` to a working `arklight build`.
- `templates/production/` -- mirrors Product-Showcase's proven layout
  (`site.py` + `components/` + `pages/` + `content/` + `assets/`),
  with `components/__init__.py` / `pages/__init__.py` /
  `content/__init__.py` present up front so the package-shaped layout
  imports cleanly from line one, and every generated page wired with a
  real `@site.page("/route")` decorator (never the equivalent call
  form), since static discovery only recognizes the decorator.

Each template directory's `assets/` folder is a placeholder for now
(see the `.gitkeep` inside) -- deliberately not populated by copying
Product-Showcase's actual images/content, only the folder shape it
expects. `arklight build` copying a top-level `assets/` into
`dist/assets` automatically is a related, separate fix tracked
alongside this milestone (see `docs/DESIGN-NOTES.md`).

Nothing here is wired into `arklight/cli/main.py` yet. See
`PROGRESS.md` for current status.
"""

from __future__ import annotations
