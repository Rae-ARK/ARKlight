"""
`production` template for `arklight new` -- see docs/DESIGN-NOTES.md,
"v0.004: CLI scaffolding (`arklight new`)".

Mirrors a proven multi-file layout for sites that outgrow a single
`site.py`: `site.py` + `components/` + `pages/` + `content/` +
`assets/`, plus fixes for the real gotchas that shape hit in practice:

- `site.py` registers every route with a real `@site.page("/route")`
  decorator (never the equivalent call form), since static discovery
  (`arklight.parser.discover`) only recognizes the decorator -- and,
  specifically, only recognizes it in the *entry* file's own source.
  That's why the decorators themselves live in `site.py`, wrapping a
  plain content-building function imported from `pages/`, rather than
  living in `pages/home.py` directly.
- `components/__init__.py` / `pages/__init__.py` / `content/__init__.py`
  are present up front so the package-shaped layout imports cleanly
  from line one.
- `pages/*.py` import `components.*` and `content.*` with ordinary
  absolute imports. That only resolves if the project directory is on
  `sys.path`, which `arklight.parser.loader.load_site` now guarantees
  regardless of how `arklight` was invoked (console script or
  otherwise) -- see that module for the fix.
- A top-level `assets/` folder is copied into the build output
  automatically by `arklight build` (no manual `cp -r` step to forget
  or to document here).
"""

from __future__ import annotations

from arklight.cli.templates._common import ARKLIGHT_CONFIG_PY


def build(name: str) -> dict[str, str]:
    """Return {relative_path: contents} for a fresh `production` project called `name`."""
    title = repr(name)
    return {
        "site.py": _SITE_PY,
        "components/__init__.py": _COMPONENTS_INIT_PY,
        "components/nav.py": _COMPONENTS_NAV_PY,
        "pages/__init__.py": _PAGES_INIT_PY,
        "pages/home.py": _PAGES_HOME_PY,
        "pages/about.py": _PAGES_ABOUT_PY,
        "content/__init__.py": _CONTENT_INIT_PY,
        "content/site_content.py": _CONTENT_SITE_CONTENT_PY.format(title=title),
        "assets/.gitkeep": "",
        "arklight.config.py": ARKLIGHT_CONFIG_PY,
        "README.md": _README_MD.format(name=name),
    }


_SITE_PY = '''\
from arklight import *

from pages.about import about
from pages.home import home

site = Site()


# Real @site.page(...) decorators live here, not in pages/*.py --
# static discovery (arklight.parser.discover) only looks at the entry
# file's own source, so this is the one place routes must be declared.
# Each function below just delegates to the actual page-content
# function in pages/, which is free to import components/ and
# content/ however it likes.


@site.page("/")
def home_page():
    return home()


@site.page("/about")
def about_page():
    return about()
'''

_COMPONENTS_INIT_PY = '''\
"""Reusable pieces shared across pages. Plain functions -- no special
"component" mechanism, just ordinary Python composition."""
'''

_COMPONENTS_NAV_PY = '''\
from arklight import *


def nav():
    """A shared nav bar, reused across every page."""
    return Container(
        Link("Home", href="/"),
        Link("About", href="/about"),
        class_name="nav",
    )
'''

_PAGES_INIT_PY = '''\
"""One module per route. Each exposes a plain function that returns a
`Page(...)` -- the real `@site.page(...)` decorators live in site.py,
which imports these and wires them up (see site.py for why)."""
'''

_PAGES_HOME_PY = '''\
from arklight import *

from components.nav import nav
from content.site_content import TAGLINE, TITLE


def home():
    return Page(
        nav(),
        Heading(TITLE),
        Text(TAGLINE, class_name="muted"),
        title=TITLE,
    )
'''

_PAGES_ABOUT_PY = '''\
from arklight import *

from components.nav import nav
from content.site_content import TITLE


def about():
    return Page(
        nav(),
        Heading("About", level=2),
        Text(f"Say something about {TITLE} here."),
        Link("Back home", href="/"),
        title="About",
    )
'''

_CONTENT_INIT_PY = '''\
"""Copy/text constants, kept separate from markup so pages/ stays
readable and content can be edited without touching component code."""
'''

_CONTENT_SITE_CONTENT_PY = '''\
TITLE = {title}
TAGLINE = "Build websites with Python."
'''

_README_MD = '''\
# {name}

An ARKlight site, scaffolded with `arklight new {name} --template production`.

## Layout

```
site.py               routes -- @site.page(...) decorators live here
components/            reusable pieces (nav, etc.), plain functions
pages/                 one module per route, returns Page(...)
content/               copy/text constants, kept out of the markup
assets/                images, fonts, favicons, ... (see below)
arklight.config.py     optional project settings (dev-server host/
                        port, etc.) -- commented out by default
```

## Build it

```
arklight build site.py -o ARK
```

This writes `ARK/index.html`, `ARK/styles.css`, and `ARK/arklight.js`
for every route, then opens `ARK/index.html` in your default browser
(pass `--no-open` to skip that). Anything in `assets/` is copied into
`ARK/assets/` automatically -- no manual copy step.

## Adding a page

1. Add `pages/<name>.py` with a function that returns `Page(...)`
   (copy `pages/about.py` as a starting point).
2. In `site.py`, import it and add a decorated wrapper:

   ```python
   from pages.<name> import <name>

   @site.page("/<route>")
   def <name>_page():
       return <name>()
   ```

The decorator has to live in `site.py` itself -- ARKlight discovers
routes by statically scanning the entry file's own source, not any
file it imports.
'''
