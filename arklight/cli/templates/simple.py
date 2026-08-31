"""
`simple` template for `arklight new` -- see docs/DESIGN-NOTES.md,
"v0.004: CLI scaffolding (`arklight new`)".

Beginner-shaped: a single `site.py` with two inline pages, mirroring
`examples/hello_site/site.py` almost exactly. Zero-thinking path from
`arklight new my-site` to a working `arklight build` with nothing to
wire up.
"""

from __future__ import annotations

from arklight.cli.templates._common import ARKLIGHT_CONFIG_PY


def build(name: str) -> dict[str, str]:
    """Return {relative_path: contents} for a fresh `simple` project called `name`."""
    title = repr(name)
    return {
        "site.py": _SITE_PY.format(title=title),
        "arklight.config.py": ARKLIGHT_CONFIG_PY,
        "README.md": _README_MD.format(name=name),
    }


_SITE_PY = '''\
from arklight import *

site = Site()


def nav():
    """A shared nav bar, reused across every page."""
    return Container(
        Link("Home", href="/"),
        Link("About", href="/about"),
        class_name="nav",
    )


@site.page("/")
def home():
    return Page(
        nav(),
        Heading({title}),
        Text("Build websites with Python."),
        title={title},
    )


@site.page("/about")
def about():
    return Page(
        nav(),
        Heading("About", level=2),
        Text("Say something about your project here."),
        Link("Back home", href="/"),
        title="About",
    )
'''

_README_MD = '''\
# {name}

An ARKlight site, scaffolded with `arklight new {name}`.

## Build it

```
arklight build site.py -o ARK
```

This writes `ARK/index.html`, `ARK/styles.css`, and `ARK/arklight.js`,
then opens `ARK/index.html` in your default browser (pass `--no-open`
to skip that).

## Next steps

- Edit `site.py` -- each `@site.page("/route")` function returns a
  `Page(...)`. See the ARKlight README for the full component list.
- Add an `assets/` folder next to `site.py` (images, fonts, favicons,
  ...) and `arklight build` copies it into the output directory
  automatically.
- `arklight.config.py` holds optional project settings (e.g. the dev
  server's host/port) -- everything in it is commented out by default
  and safe to ignore until you need it.
- Outgrowing one file? `arklight new <name> --template production`
  scaffolds a `components/` / `pages/` / `content/` layout instead.
'''
