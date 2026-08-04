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
arklight build site.py -o ARK
```

produces `ARK/index.html` -- plain, dependency-free HTML.

## Status

**Current release: v0.0431 -- emergency patch, build-time warning for
unrouted `srcset`/`poster`/`action`/`formaction`.** Alpha maintenance
release: those four attributes aren't route-rewritten yet (only
`href`/`src` are), so a route-shaped value now gets a clear, non-fatal
build warning instead of silently 404ing when the site is deployed
outside the domain root -- the build still succeeds and the site still
gets written either way. Full write-up, including what was checked and
found *not* to be a problem, in [`CHANGELOG.md`](./CHANGELOG.md) and
[`PROGRESS.md`](./PROGRESS.md) ("v0.0431 -- Emergency patch").

**Previous release: v0.043 -- optional `<head>` metadata props +
backend `postprocess` hook.** `Page(...)` gains five optional props
beyond the existing `title`: `description`, `favicon`, `og_title`,
`og_description`, `og_image` (see "Head metadata" below) -- all
additive, so a page using none of them renders byte-for-byte
unchanged. Separately, every `Backend` now has an optional
`postprocess(output_files)` hook, called after all backends'
`render()` finish, so a *new* backend can transform the combined
output of `HTMLBackend`/`CSSBackend`/`JSBackend` (build stamps,
sitemaps, injected analytics, ...) without editing any of their
source (see "Compiler pipeline" below). v0.042 (extra CSS features +
CLI discoverability) shipped just before this -- full detail in
[`CHANGELOG.md`](./CHANGELOG.md); narrative/decision log in
[`PROGRESS.md`](./PROGRESS.md).

**Next up: v0.044 -- JS backend capability expansion.** Computed/
derived state, watch effects, two-way input binding, per-item list
rendering, conditional show/hide, event modifiers, and reactive class
binding -- all via closed, described registries (no arbitrary JS, no
`eval`), same discipline as the existing `State`/`Bind`/`Action.*`
system. Design complete, implementation not started. See
[`docs/DESIGN-NOTES.md`](./docs/DESIGN-NOTES.md) ("v0.044: JS backend
capability expansion -- reactive core parity with Vue 3").

**In progress alongside it: reactive-core vdom staging (Stage 2 of
8).** A narrower, separately-tracked initiative on the *mechanism*
under `State`/`Bind` rather than new page-facing capability -- Stage 1
(vendoring a real diff/patch engine, [snabbdom](https://github.com/snabbdom/snabbdom)'s
bare core, in place of the old `textContent`-overwrite re-render pass)
and Stage 2 (`Bind.when(...)`/`bind_class=` reactive class binding)
are both done; Stage 3 (event modifiers) is next, feeding into
`v0.044` above. See [`docs/DESIGN-NOTES.md`](./docs/DESIGN-NOTES.md)
("Reactive-core vdom staging").

**Queued right behind it: v0.048 -- CSS `@media` queries +
`<head>`/`<header>` extension.** Design complete, implementation not
started. See [`docs/DESIGN-NOTES.md`](./docs/DESIGN-NOTES.md) ("v0.048:
CSS media queries + `<head>` extension").

See [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) for the full
milestone roadmap.

## Install

```bash
pip install -e .
```

This installs the `arklight` package and the `arklight` CLI command
(defined in `pyproject.toml`).

## CLI

```bash
arklight build <entry.py> [-o OUTPUT_DIR] [--open | --no-open] [--verbose] [--debug]
```

- `entry.py` -- your site file (must define `site = Site()` and at
  least one `@site.page("/route")`-decorated function).
- `-o, --output` -- output directory, default `ARK/`.
- If a top-level `assets/` folder sits next to `entry.py`, it is
  copied (recursively) into `<output>/assets` automatically.
- `--open` (default) -- opens `index.html` in your default browser
  after building. `--no-open` disables this.
- `--verbose` -- prints a `[ARKlight] ...` line as each pipeline stage
  starts (discovering the site, normalizing, validating, building the
  IR, each backend's render/postprocess, writing files, copying
  assets), e.g.:

  ```
  [ARKlight] Discovering site and compiling AST trees...
  [ARKlight] Normalizing AST...
  [ARKlight] Running validation...
  [ARKlight] Building website IR...
  [ARKlight] Rendering backend 'html'...
  ...
  [ARKlight] Build complete -> ARK/index.html
  ```

  Useful for seeing exactly which stage a build reached before it
  failed or hung.
- `--debug` -- implies `--verbose`, and on failure prints the full
  chained Python traceback instead of the short one-line error
  message, so you can trace a compiler error back to the exact file
  and line that raised it.

Both flags are off by default -- a plain `arklight build` is
unchanged.

Try the bundled example -- this builds the site AND opens it in your
browser:

```bash
arklight build examples/hello_site/site.py -o ARK
```

```bash
arklight pack <build-dir> [-o OUTPUT.ark] [--plain] [--passphrase PASSPHRASE]
```

- `build-dir` -- an existing `arklight build` output directory (e.g.
  `ARK`).
- `-o, --output` -- output bundle path, default `site.ark`.
- Packs the build directory into a single `.ark` file: an HTML/archive
  polyglot (see "ARK Bundle" below), carrying over every file in
  `build-dir` including `assets/`.
- **Sealed by default** -- the archive half is encrypted, opaque to
  generic archive tools. `--passphrase PASSPHRASE` derives the key from
  a passphrase instead of an embedded one, for real confidentiality
  (the same passphrase is then required to unpack). `--plain` skips
  sealing entirely and produces a plain, freely-openable ZIP tail
  (the original v1 behavior).

```bash
arklight unpack <bundle.ark> [-o OUTPUT_DIR] [--passphrase PASSPHRASE]
```

- `bundle.ark` -- a `.ark` file produced by `arklight pack`.
- `-o, --output` -- output directory, default `ARK`.
- Extracts the archive half back into a normal build directory.
  Auto-detects sealed vs. plain bundles; `--passphrase` is only needed
  if the bundle was sealed with one.

```bash
arklight build examples/hello_site/site.py -o ARK --no-open
arklight pack ARK -o hello_site.ark
arklight unpack hello_site.ark -o restored
```

```bash
arklight search <name>
```

- `name` -- a built-in component name, e.g. `Picture`.
- Prints that component's schema: required props, whether it allows
  children, and whether it's a `Bind(...)`-able target (i.e.
  `text_only_children`). Case-insensitive exact match wins; if nothing
  matches, prints up to 5 typo-tolerant "did you mean" suggestions
  (or says plainly that nothing was close enough).

```bash
arklight search Picture
arklight search pictur   # -> "Did you mean: Picture, PictureSource?"
```

`arklight --help` (or a bare `arklight` with no subcommand) prints the
full list of subcommands with a short description of each.

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

Each backend can also implement `postprocess(output_files) ->
output_files`, called once per backend (same order as `backends=[...]`)
*after* every backend's `render()` has run, over the combined
`{path: contents}` dict from all of them. The default `Backend`
implementation is a no-op identity, so existing backends need no
changes. This is the extension point for adding a new backend that
depends on what other backends already produced (analytics snippets,
build stamps, sitemap generation, ...) without editing that backend's
source -- see `tests/test_pipeline_end_to_end.py` for a worked example.

### Internal links are relative, not root-absolute

`Link("About", href="/about")` refers to the *route* `"/about"`, the
same string you'd pass to `@site.page(...)`. The HTML backend resolves
this to the correct relative file path at build time (`about.html`,
`../about.html`, etc., depending on where the linking page lives), so
navigation works whether you open the file directly from disk or
deploy the `ARK/` folder as-is. External URLs, `#fragments`, and
`mailto:`/`tel:` links are left untouched.

### Head metadata (title, description, favicon, Open Graph)

`Page(...)` already accepted `title` (falls back to the site name if
omitted). Five more optional props extend the same pattern -- read
straight off `Page`'s props, nothing new to import:

```python
Page(
    Heading("ARKlight"),
    title="ARKlight",
    description="A Python-first compiler for building static websites.",
    favicon="assets/favicon.ico",
    og_image="assets/social.png",
)
```

| Prop              | Renders as                                    |
|-------------------|------------------------------------------------|
| `title`           | `<title>` (already existed)                    |
| `description`     | `<meta name="description">`                    |
| `favicon`         | `<link rel="icon">` -- resolved relative, same as the stylesheet/script links |
| `og_title`        | `<meta property="og:title">` -- defaults to `title` |
| `og_description`  | `<meta property="og:description">` -- defaults to `description` |
| `og_image`        | `<meta property="og:image">` -- resolved relative, like `favicon` |

All six are optional and additive: a page that sets none of them
renders identically to before this feature existed. Open Graph tags
specifically only appear once `description` or any `og_*` prop is
supplied, so `title`-only pages (the common case) don't get an
unsolicited `og:title`.

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

### Custom CSS classes

`style={...}` is per-node and `class_name="..."` alone only reaches
the fixed utility classes above -- neither lets you define a *new*,
reusable class. `site.style(name, rules)` does:

```python
site = Site()
site.style("pull-quote", {"font-style": "italic", "border-left": "4px solid purple"})

@site.page("/")
def home():
    return Page(Text("A quote worth repeating.", class_name="pull-quote"))
```

`rules` is a plain `{css-property: value}` dict -- the same shape as
the per-node `style={...}` prop, never a raw CSS string, so this
doesn't reopen the "no arbitrary CSS/HTML strings" boundary the rest
of ARKlight holds. Registered classes are appended to the generated
stylesheet after the fixed defaults, so they can override base rules
by cascade order. Calling `site.style()` again with an already-used
name overwrites its rules (last call wins).

### Responsive layout, without `@media` (platform-independent by construction)

`Page` never gets a `<head>` hook (see
[`docs/DESIGN-NOTES.md`](./docs/DESIGN-NOTES.md)), so a generated site
has no `@media`/`@container` query available to it at all -- there is
no "desktop breakpoint" or "mobile breakpoint" to hand-tune, and
nothing keyed to a specific screen width, device, or platform. Layouts
still adapt, but from the *content's own* available width using plain
flexbox/grid sizing keywords (`minmax`, `auto-fit`, `flex-wrap`,
`clamp`) -- the same technique goes by "intrinsic web design." Opt in
with `class_name`, same mechanism as `.nav`/`.card` above:

| Class             | What it does                                                                 |
|-------------------|-------------------------------------------------------------------------------|
| `.stack`          | Consistent vertical rhythm between block children                            |
| `.cluster`        | A row of items that wraps as a group once it runs out of width                |
| `.sidebar`        | Two panels side-by-side once there's room, stacked when there isn't           |
| `.switcher`       | Children stay in a row until each would drop below a minimum width, then stack |
| `.grid`           | An auto-filling card/tile grid with no explicit column count                  |
| `.center`         | Constrains and horizontally centers content, with optional gutters            |
| `.reel`           | A horizontally-scrolling row that never wraps or overflows the page           |
| `.fluid-heading`  | Font size scales smoothly with available width via `clamp()`                  |

For a layout that's three columns on a wide viewport and a single
column on a narrow one -- the classic "desktop vs. mobile" case --
`.switcher` is usually the right tool: give it three children and it
lays them out in a row as long as each stays above a minimum width
(`--ark-switcher-threshold`, default `30rem`), and stacks them
vertically the moment they'd drop below that, with no device or
browser ever queried:

```python
Container(
    Container(Heading("Fast"), Text("...", class_name="muted"), class_name="card"),
    Container(Heading("Simple"), Text("...", class_name="muted"), class_name="card"),
    Container(Heading("Portable"), Text("...", class_name="muted"), class_name="card"),
    class_name="switcher",
)
```

This adapts identically on any platform that renders CSS at all --
desktop browser, phone browser, embedded webview -- because the
decision is made from the container's own measured width, not from
`user-agent`, viewport metadata, or a hard-coded pixel breakpoint.
`.grid` is the equivalent choice when the number of items is open-ended
rather than a fixed three (a card feed, a tag list), auto-filling as
many `minmax()`-wide columns as the available width allows. All
`--ark-*` custom properties above (space, thresholds, widths) can be
overridden per-instance via the `style` prop shown earlier.

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

## ARK Bundle (`.ark`) -- v0.037 (sealed by default, implemented)

A build's output (`index.html`, `styles.css`, `arklight.js`, `assets/`)
is a folder of separate files. `arklight pack` (see CLI section above)
packages that output as a single `.ark` file:

- The raw build files -- including an `assets/` folder, if present --
  are stored as-is inside an archive; no new file format, no
  re-encoding, nothing about how the HTML/CSS/JS backends generate
  files changes for this feature.
- The bundle is a **polyglot**: a fully self-contained, inlined
  rendering of the entry page is placed *before* the archive data, so
  the same file opens directly as a rendered page in a browser (no
  unzip step, no temp files, no server -- the same way an image viewer
  doesn't "extract" a `.png` before displaying it) regardless of what
  the archive half contains.
- **Sealed by default.** The archive half is encrypted (see
  `arklight.packer.seal`, stdlib `hmac`/`hashlib`/`secrets` only, no
  crypto dependency) so a generic archive tool, "rename to `.zip`", or
  hex editor sees only opaque bytes -- it can't be casually opened,
  inspected, or spliced/tampered with. `arklight unpack site.ark -o
  ARK` reverses this. Without a `--passphrase`, the encryption key
  travels embedded in the bundle so `arklight unpack` always works with
  no extra input -- this blocks generic tools, but is **not** secrecy
  from someone who also has ARKlight (the key is right there in the
  file). Pass `--passphrase` for real confidentiality: the key is then
  derived from it (PBKDF2-HMAC-SHA256) and never stored, and the same
  passphrase is required to unpack.
- **`--plain` opts back into the original v1 behavior**: a real,
  generically-openable ZIP tail, freely inspectable/re-editable by any
  archive tool without ARKlight installed at all.
- This is a packaging step that runs *after* `arklight build`, over
  files the existing pipeline already produces -- `arklight.packer`
  only reads already-written build output and never imports the
  parser/ir/backend internals.
- **Known limit, sealed or not:** only the *archive* half is protected.
  The *inlined front-matter page* -- what a browser actually renders --
  is always plain HTML/CSS/JS, because that's what makes the polyglot
  openable as a web page at all; view-source on the page you're
  currently looking at was never in scope to hide. Sealing protects the
  *other* pages/assets bundled alongside it, not the one on screen.

See [`docs/DESIGN-NOTES.md`](./docs/DESIGN-NOTES.md) ("v0.036: ARK
Bundle spec v1" and "v0.037: sealed bundles") for the full byte layout,
packing algorithm, cipher construction, and known caveats.

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
        behaviors/     v0.0035 behavior fragments (toggle, scroll-to,
                        copy, dismiss) -- one file per
                        BEHAVIOR_REGISTRY entry
        actions/       v0.0035 action fragments (set, increment,
                        toggle_bool) -- one file per ACTION_REGISTRY
                        entry
    compiler/          Pipeline orchestration
    cli/               `arklight` command-line entry point
      templates/       `simple`/`production` scaffolds for
                        `arklight new` (v0.004a; see docs/DESIGN-NOTES.md)
    packer/            `arklight pack` -- ARK Bundle (.ark) packaging,
                        reads already-built output only, never touches
                        the compiler pipeline
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

Full milestone table (with status) lives in
[`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) -- kept as the single
canonical copy rather than duplicated here, in `PROGRESS.md`, and in
`CHANGELOG.md`. Short version: v0.001 through v0.043 are done; v0.044
(JS backend capability expansion) is next, with v0.048 (CSS `@media` +
`<head>`/`<header>` extension) queued right behind it; v0.010
(components) and v0.100 (alternate backends) are further out.
