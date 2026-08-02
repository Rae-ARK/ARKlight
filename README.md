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

**v0.003 — JavaScript helpers.** The compiler now runs three backends
(HTML, CSS, JS) over the same Website IR. Any component can opt into a
small, closed set of built-in client-side behaviors --
`on_click="toggle"` and `on_click="scroll-to"` -- via a tiny, fixed
vanilla-JS runtime ARKlight ships automatically; no JavaScript is ever
written by hand, and no arbitrary JS strings are accepted (see
[`docs/DESIGN-NOTES.md`](./docs/DESIGN-NOTES.md) for why that boundary
is deliberate). The nav bar in the example site also gets its current
page highlighted automatically, with zero wiring. See
[`PROGRESS.md`](./PROGRESS.md) for what's implemented and what's next,
and [`CHANGELOG.md`](./CHANGELOG.md) for version history.

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
    |                   generated stylesheet and behavior runtime)
    v
CSS Backend           arklight/backend/css/render.py
    |                  (v0.002: generates a global default stylesheet)
    v
JS Backend            arklight/backend/js/render.py
    |                  (v0.003: generates a tiny fixed behavior runtime;
    |                   all three backends run over the same IR and their
    |                   outputs are merged)
    v
index.html, about.html, styles.css, arklight.js, ...
```

`arklight/compiler/pipeline.py` orchestrates all of the above into a
single `build(entry_path, output_dir)` call, which is what the CLI
uses. By default it runs `[HTMLBackend(), CSSBackend(), JSBackend()]`
-- pass your own `backends=[...]` list to customize which backends run.

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
from the default stylesheet: `.nav`, `.card`, `.muted`, `.page`,
`.hidden` (pairs with the `toggle` behavior below).

### Behaviors (client-side interactivity, no JS written by hand)

Any component accepts `on_click` + `behavior_target` (a CSS selector)
to opt into a small, closed set of built-in behaviors, implemented by
the tiny runtime the JS backend generates:

```python
Button(
    "Show details",
    on_click="toggle",              # or "scroll-to"
    behavior_target="#more-details",
    toggle_class="hidden",          # optional, default "is-open"
)
Container(Text("..."), id="more-details", class_name="hidden")
```

| Behavior     | What it does                                                   |
|--------------|-------------------------------------------------------------------|
| `toggle`     | Toggles a CSS class (`toggle_class`, default `is-open`) on every element matching `behavior_target` |
| `scroll-to`  | Smooth-scrolls the element matching `behavior_target` into view    |

`on_click` is validated against this fixed vocabulary at the
Validation stage -- an unknown behavior name (or a missing
`behavior_target`) fails the build with a clear message rather than
silently doing nothing in the browser. There is deliberately no way to
pass arbitrary JavaScript: see
[`docs/DESIGN-NOTES.md`](./docs/DESIGN-NOTES.md) for why that boundary
is a design choice, not a gap.

The current page's nav link is also highlighted automatically (an
`is-active` class added to any `<a>` inside `.nav` whose target matches
the current page) -- no props needed for that one.

## Public API (v0.003)

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

The table above is the original v0.001 core. Two vocabulary
addenda (still v0.003, no new pipeline stage -- see CHANGELOG.md) add
~79 more components on top of it, purely as data in
`arklight.ir.schema.SCHEMA` (the single source of truth every stage
reads from):

- **First addendum:** semantic layout (`Header`, `Footer`, `Main`,
  `Nav`, `Section`, `Article`, `Aside`, `Figure`/`FigCaption`,
  `Details`/`Summary`), text-level semantics (`Strong`, `Em`, `Small`,
  `Mark`, `Code`, `Cite`, `Abbr`, `Sub`, `Sup`, `Span`, `Time`,
  `HorizontalRule`, `LineBreak`, `Pre`, `Blockquote`), forms (`Form`,
  `Input`, `Textarea`, `Select`, `Option`, `OptGroup`, `Label`,
  `FieldSet`, `Legend`), tables (`Table`, `TableHead`, `TableBody`,
  `TableFoot`, `TableRow`, `TableHeaderCell`, `TableCell`, `Caption`),
  and media (`Video`, `Audio`, `Source`).
- **Second addendum ("even more vocabulary"):** numbered/description
  lists (`OrderedList`, `DescriptionList`/`DescriptionTerm`/
  `DescriptionDetails`), art-directed responsive images (`Picture`/
  `PictureSource`, plus `loading`/`decoding` attributes), native
  widgets (`Progress`, `Meter`, `Datalist`, `Output`), a zero-JS
  `Dialog`, more text semantics including bidi and ruby (`Kbd`,
  `Samp`, `Var`, `Data`, `Ins`, `Del`, `Q`, `Dfn`, `Address`, `Wbr`,
  `Bdi`, `Bdo`, `Ruby`, `Rt`, `Rp`), table column grouping
  (`ColGroup`, `Col`), video/audio captions (`Track`), image maps
  (`Map`, `Area`), `IFrame` embeds, and a `NoScript` fallback.

See [`CHANGELOG.md`](./CHANGELOG.md) for the rationale behind each
group and `arklight.ir.schema.SCHEMA` for the authoritative list of
every component's required props, text-only-children rule, and
whether it allows children at all.

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
      js/
        behaviors/     Reserved for v0.0035 (empty scaffold; see
                        docs/DESIGN-NOTES.md)
    compiler/          Pipeline orchestration
    cli/               `arklight` command-line entry point
      templates/       Reserved for v0.004 `arklight new` (empty
                        scaffold; see docs/DESIGN-NOTES.md)
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
- [x] v0.003 -- JavaScript helpers
- [ ] v0.0035 -- Stateful JS (registry-driven behaviors + actions;
      design complete, see `docs/DESIGN-NOTES.md`, implementation not
      started)
- [ ] v0.004 -- `arklight new` CLI scaffolding (simple + production
      templates), CSS `@media` support, structured `<head>` extension
      (design complete, implementation not started)
- [ ] not yet scheduled -- `arklight --help` / `arklight --search
      <name>` (schema lookup for a component by name); design sketched
      in `docs/DESIGN-NOTES.md`, explicitly waiting on a go-ahead
      before implementation starts
- [ ] v0.010 -- Components (user-defined, reusable)
- [ ] v0.100 -- Alternate backends (Vue, Svelte) -- **note:** the
      Backend interface is ready for this today; the IR isn't yet.
      See [`docs/DESIGN-NOTES.md`](./docs/DESIGN-NOTES.md) for why a
      state/event-semantics milestone likely needs to land before this
      one means more than static HTML wearing a different file
      extension.
- [ ] v1.0 -- Stable compiler
# ARKlight
