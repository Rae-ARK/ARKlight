# ARKlight

A Python-first compiler for building beautiful static websites.

Users write Python. ARKlight produces standard HTML. **The browser never
executes Python.**

```python
from arklight import *

site = Site()

@site.page("/")
def home():
    return Page(
        Heading("ARKlight"),
        Text("Build websites with Python."),
        Button("Get Started"),
    )
```

```
arklight build site.py -o dist
```

produces `dist/index.html` -- plain, dependency-free HTML.

## Status

**v0.002 — CSS.** The compiler now runs both an HTML backend and a CSS
backend over the same Website IR, so every generated site ships with a
sensible default look (typography, spacing, buttons, nav, cards) with
zero CSS written by hand. `arklight build` also opens the result in
your browser automatically, and internal links (`Link(..., href="/about")`)
are compiled to real relative file paths, so pages actually link to
each other correctly whether you open the file directly or deploy it
to a subdirectory. See [`PROGRESS.md`](./PROGRESS.md) for what's
implemented and what's next, and [`CHANGELOG.md`](./CHANGELOG.md) for
version history.

## Install

```bash
pip install -e .
```

This installs the `arklight` package and the `arklight` CLI command
(defined in `pyproject.toml`).

## CLI

```bash
arklight build <entry.py> [-o OUTPUT_DIR] [--open | --no-open]
```

- `entry.py` -- your site file (must define `site = Site()` and at
  least one `@site.page("/route")`-decorated function).
- `-o, --output` -- output directory, default `dist/`.
- `--open` (default) -- opens `index.html` in your default browser
  after building. `--no-open` disables this.

Try the bundled example -- this builds the site AND opens it in your
browser:

```bash
arklight build examples/hello_site/site.py -o dist
```

## Compiler pipeline

ARKlight compiles a site in clearly separated stages, each in its own
part of the package:

```
Python Source
    |
    v
Python AST            arklight/parser/discover.py
    |                  (static analysis via the stdlib `ast` module:
    |                   finds Site()/@site.page(...) without executing
    |                   user code)
    v
ARK AST               arklight/parser/loader.py + arklight/api.py
    |                  (the module is executed; calling Heading(...),
    |                   Text(...), etc. builds a tree of ARKNode objects
    |                   -- that tree IS the ARK AST)
    v
Normalization         arklight/ir/normalize.py
    |                  (flattens nested lists, drops None/False,
    |                   wraps bare strings as Text nodes where needed)
    v
Validation            arklight/ir/validate.py
    |                  (schema check: known component types, required
    |                   props, valid text-only nesting)
    v
Website IR            arklight/ir/build.py
    |                  (backend-independent IRNode tree: type/props/children
    |                   -- models website *intent*, not HTML)
    v
Backend Interface     arklight/backend/base.py
    |                  (abstract `Backend.render(ir) -> {path: contents}`)
    v
HTML Backend          arklight/backend/html/render.py
    |                  (maps IR node types to HTML tags, rewrites internal
    |                   Link/Image hrefs to relative file paths, links the
    |                   generated stylesheet)
    v
CSS Backend           arklight/backend/css/render.py
    |                  (v0.002: generates a global default stylesheet;
    |                   both backends run over the same IR and their
    |                   outputs are merged)
    v
index.html, about.html, styles.css, ...
```

`arklight/compiler/pipeline.py` orchestrates all of the above into a
single `build(entry_path, output_dir)` call, which is what the CLI
uses. By default it runs `[HTMLBackend(), CSSBackend()]` -- pass your
own `backends=[...]` list to customize which backends run.

### Internal links are relative, not root-absolute

`Link("About", href="/about")` refers to the *route* `"/about"`, the
same string you'd pass to `@site.page(...)`. The HTML backend resolves
this to the correct relative file path at build time (`about.html`,
`../about.html`, etc., depending on where the linking page lives), so
navigation works whether you open the file directly from disk or
deploy the `dist/` folder as-is. External URLs, `#fragments`, and
`mailto:`/`tel:` links are left untouched.

### Styling components

Any component accepts two extra props for styling, on top of the
default stylesheet:

```python
Text("Careful now", class_name="muted")
Container(..., style={"background": "#f5f5ff", "padding": "1rem"})
```

`class_name` renders as the HTML `class` attribute (avoiding the
`class` keyword clash); `style` accepts a dict of CSS properties and
is rendered as an inline `style` attribute. Built-in utility classes
from the default stylesheet: `.nav`, `.card`, `.muted`, `.page`.

## Public API (v0.001)

Components -- every one of these is a plain Python function that
returns an `ARKNode`:

| Component   | Notes                                              |
|-------------|-----------------------------------------------------|
| `Page`      | Root node every page function must return           |
| `Container` | Generic grouping element (renders as `<div>`)        |
| `Heading`   | Text-only. `level=1..6` prop controls `<h1>`-`<h6>`  |
| `Text`      | Text-only. Renders as `<p>`                          |
| `Button`    | Text-only. Renders as `<button>`                     |
| `Link`      | Text-only. Requires `href` prop. Renders as `<a>`    |
| `Image`     | No children allowed. Requires `src` prop             |
| `List`      | Renders as `<ul>`                                    |
| `Item`      | Text-only. Renders as `<li>`                         |

"Text-only" components may only contain plain strings, not other
components -- this is enforced by the Validation stage.

`Site`:

```python
site = Site()

@site.page("/some/route")
def page_fn():
    return Page(...)
```

Any keyword prop passed to a component that isn't recognized (e.g.
`id`, `class`, `href`, `src`, `style`, ...) is emitted as a `data-*`
HTML attribute, so nothing you write is silently dropped.

## Repository layout

```
arklight-framework/
  arklight/
    api.py            Public component functions + Site class
    ast/               ARK AST node type (ARKNode)
    parser/            Python Source -> Python AST -> (loaded) ARK AST
    ir/                Normalization, Validation, Website IR
    backend/
      base.py          Backend interface
      html/            HTML backend (the only backend in v0.001)
    compiler/          Pipeline orchestration
    cli/               `arklight` command-line entry point
  examples/
    hello_site/        Example site matching this README
  tests/               Unit + end-to-end tests for every pipeline stage
  docs/                Additional design notes
  PROGRESS.md          What's done, what's next
  CHANGELOG.md         Version history
```

## Running tests

```bash
pip install pytest
pytest
```

## Non-goals (v0.001 and for the foreseeable future)

- Browser-side Python
- Virtual DOM
- Runtime Python execution in the browser
- Feature creep beyond the milestone roadmap below

## Roadmap

- [x] v0.001 -- Python → HTML
- [x] v0.002 -- CSS
- [ ] v0.003 -- JavaScript helpers
- [ ] v0.010 -- Components (user-defined, reusable)
- [ ] v0.100 -- Alternate backends (Vue, Svelte)
- [ ] v1.0 -- Stable compiler
# ARKlight
