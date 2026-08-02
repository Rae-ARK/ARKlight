# ARKlight Architecture v0.001

## Vision

ARKlight is a Python-first compiler for building beautiful static
websites.

Users write Python. ARKlight produces standard HTML. The browser never
executes Python.

## Core Principles

- Flask-like simplicity.
- Functions over classes.
- One obvious way.
- Beginner friendly.
- AI-friendly API.
- Backend independent compiler.

## Compiler Pipeline

```
Python Source
    |
    v
Python AST
    |
    v
ARK AST
    |
    v
Normalization
    |
    v
Validation
    |
    v
Website IR
    |
    v
Backend Interface
    |
    v
HTML Backend
    |
    v
index.html
```

## Website IR

Each node contains:
- type
- props
- children

The IR models website intent rather than HTML.

## Backend Interface

Current:
- HTML

Future:
- CSS
- JavaScript
- Vue
- Svelte

## Public API

Everything is a function.

Children are positional arguments.

Properties are keyword arguments.

Components are Python functions.

```python
from arklight import *

site = Site()

@site.page("/")
def home():
    return Page(
        Heading("ARKlight"),
        Text("Build websites with Python."),
        Button("Get Started")
    )
```

## Repository

```
arklight-framework/
  arklight/
    compiler/
    parser/
    ast/
    ir/
    backend/
      html/
    cli/
  examples/
  tests/
  docs/
```

## Milestones

- v0.001 Python → HTML
- v0.002 CSS
- v0.003 JavaScript helpers (also covers a later vocabulary extension:
  semantic layout, forms, tables, media; intrinsic responsive layout
  utilities; `copy`/`dismiss` behaviors -- see CHANGELOG.md)
- v0.0035 Stateful JS (registry-driven behaviors + actions;
  `State`/`Bind`/`Action.*` -- see CHANGELOG.md/PROGRESS.md)
- v0.004 CLI scaffolding + responsive/head extension (design complete,
  see docs/DESIGN-NOTES.md; not yet implemented)
- v0.010 Components
- v0.036 ARK Bundle spec v1 (single-file `.ark` packaging of a site's
  build output; implemented -- see docs/DESIGN-NOTES.md/CHANGELOG.md)
- v0.037 Sealed ARK Bundles (archive half encrypted by default,
  `assets/`+ all files carried over, new `arklight unpack` command;
  implemented -- see docs/DESIGN-NOTES.md/CHANGELOG.md)
- v0.100 Alternate backends
- v1.0 Stable compiler

## Non-goals

- Browser-side Python
- Virtual DOM
- Runtime Python
- Feature creep

---

See `PROGRESS.md` in the repo root for implementation status and
`CHANGELOG.md` for version history.
