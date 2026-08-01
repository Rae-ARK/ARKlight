# ARKlight Progress

Living document tracking what's implemented, key decisions made along
the way, and what's queued up next. Update this file at the end of
every work session, not just at milestone boundaries.

## Current milestone: v0.003 -- JavaScript helpers

**Status: DONE.** Also folded in a round of research (Alpine.js/htmx,
Reflex, Mitosis) and a written positioning/design-notes doc, per
request, before committing to the JS design.

### Research performed

- Compared Alpine.js/htmx's "attributes describe behavior, a small
  shipped runtime does the rest, no build step" model against Reflex's
  "Python state class + live WebSocket backend" model. Reflex requires
  a running Python server and compiles the *frontend* to React while
  keeping state/logic server-side -- fundamentally incompatible with
  ARKlight being a static, backend-independent compiler with no runtime
  Python anywhere. Alpine/htmx's model -- ship a tiny fixed runtime,
  describe behavior via HTML attributes -- is the correct fit and is
  what v0.003 follows.
- Looked at Mitosis (Builder.io) as prior art for "one authoring layer,
  many framework backends" (the v0.100 vision). Confirmed the Backend
  interface is already shaped correctly for this, but that ARKlight's
  IR (`type/props/children`, no state or event semantics) isn't yet --
  see `docs/DESIGN-NOTES.md` for the full reasoning. This is now an
  explicit, named gap in the roadmap rather than an implicit one.
- Wrote up honest positioning against htpy/FastHTML (mature Python
  "no template language" tools; FastHTML already has an HTMX-based JS
  story) and against the Svelte comparison (structurally similar small
  beginning, but Svelte's breakout came from a genuinely new technical
  insight solving an acutely-felt problem, not just "started small").
  Captured in `docs/DESIGN-NOTES.md`.

### What's implemented

- [x] `KNOWN_BEHAVIORS` added to the shared schema
      (`arklight/ir/schema.py`) -- a closed, documented set of
      client-side behavior names (`toggle`, `scroll-to`). Closed
      deliberately: components accept a fixed behavior *name*, never
      an arbitrary JS string, keeping "the browser never executes
      Python" true in spirit (nothing runs that ARKlight didn't ship)
      and "one obvious way" true in practice.
- [x] Validation stage extended: any node with `on_click` must name a
      known behavior and must carry a `behavior_target` (CSS selector)
      prop, or the build fails with a specific message -- same
      "catch it at compile time, not silently in the browser"
      guarantee the rest of Validation already provides.
- [x] `JSBackend` (`arklight/backend/js/render.py`) -- generates a
      single static `arklight.js`: a `behaviors` dispatch object
      (`toggle`, `scroll-to`), a `DOMContentLoaded` wiring pass over
      `[data-ark-on-click]` elements, and automatic current-page nav
      link highlighting (`is-active` on any `.nav a` matching the
      current URL) with zero props required.
- [x] HTML backend updated: `on_click`/`behavior_target`/`toggle_class`
      props render as `data-ark-on-click` / `data-ark-target` /
      `data-ark-toggle-class` (not real HTML attributes), and every
      page now includes `<script src="...arklight.js" defer></script>`
      with the same relative-path resolution styles.css already gets.
- [x] **Renamed the behavior-selector prop to `behavior_target`,
      not `target`**, specifically because `target` is already a real
      HTML attribute (`<a target="_blank">`) and reusing it would have
      been a silent footgun the moment someone wanted both on one
      element. Caught and fixed before shipping, not after.
- [x] CSS backend: added `.nav a.is-active` styling and a `.hidden`
      utility class (`display: none`) that pairs with `toggle_class`
      for the common "hidden by default, revealed by a button" pattern.
- [x] `default_backends()` now returns `[HTMLBackend(), CSSBackend(),
      JSBackend()]`.
- [x] Example site updated: the shared `nav()` gets automatic active-
      link highlighting for free, and the home page gained a real
      "Show details" button using `on_click="toggle"` -- a working
      interactive element with no hand-written JavaScript anywhere in
      the example.
- [x] `docs/DESIGN-NOTES.md` added: styling ceiling (`style=`'s real ceiling
      is no pseudo-classes/`@media`/`@keyframes`/custom fonts, all of
      which need a `<head>` hook `Page` doesn't expose yet), audience
      positioning, the Svelte-comparison writeup, the Mitosis-reframe
      writeup (state/event semantics as the real blocker for v0.100),
      and why compile-time validation is a sharper AI-assisted-coding
      advantage than "Python is popular" alone.
- [x] 9 new tests (66 total, all passing): JS backend output content,
      behavior-prop validation (valid/unknown/missing target), HTML
      rendering of `data-ark-*` attributes and the script tag.
- [x] **Verified interactively with Playwright**, not just by reading
      generated HTML: served the built example over a local HTTP
      server, loaded it in real headless Chromium, confirmed the nav
      link for the current page gets `is-active`, confirmed
      `#more-details` starts hidden, clicked the "Show details" button,
      and confirmed it becomes visible. Screenshotted the result.

### Verification performed

```bash
arklight build examples/hello_site/site.py -o /tmp/dist_v3 --no-open
python3 -m http.server 8934 --directory /tmp/dist_v3 &
python3 -c "<playwright script: goto, check .is-active, click 'Show details', assert #more-details visible>"
# -> home link class: 'is-active' / about link class: '' (on index.html)
# -> details visible before click: False / after click: True
python3 -m pytest -q
# -> 66 passed
```

### Deliberate design choices worth remembering later

- **Closed behavior vocabulary, not arbitrary JS.** The obvious
  "easier" path would have been an `on_click="alert(1)"`-style raw JS
  string prop. Rejected because it reopens exactly the door "the
  browser never executes Python" is meant to keep shut (arbitrary
  code, just JS instead of Python), breaks Validation's ability to
  catch mistakes at compile time (a typo in a JS string isn't
  checkable), and turns every site into a slightly different JS
  dialect -- the opposite of "one obvious way."
- **`behavior_target` instead of `target`** to avoid colliding with the
  real HTML anchor `target` attribute. Small, but exactly the kind of
  naming collision that's cheap to avoid now and expensive once sites
  depend on it.
- **Static, constant `arklight.js` for v0.003**, mirroring the CSS
  backend's v0.002 scope cut: `JSBackend.render(ir)` doesn't yet
  inspect which behaviors a given site actually uses. A future pass
  emitting only the referenced behaviors is a natural, non-breaking
  follow-up.

## Previous milestone: v0.002 -- CSS

**Status: DONE.** Along with real CSS support, this pass also fixed
three "wrinkles" reported after v0.001 landed: the CLI didn't open
anything in a browser, the example site's nav links were broken once
you actually clicked them, and the example looked unstyled.

### What's implemented

- [x] `CSSBackend` (`arklight/backend/css/render.py`) -- a second
      backend that runs over the same Website IR as the HTML backend
      and contributes `styles.css`: a single default stylesheet
      (typography, spacing, buttons, links, nav/card utility classes)
      so a freshly generated site looks intentional with zero CSS
      written by the user. This is the literal "Backend Interface fans
      out to multiple backends" design the architecture doc gestured
      at under "Future: CSS, JavaScript, Vue, Svelte."
- [x] `arklight/compiler/pipeline.py` now runs a *list* of backends by
      default (`default_backends() -> [HTMLBackend(), CSSBackend()]`)
      and merges their output file dicts before writing. `build(...,
      backends=[...])` lets callers customize this.
- [x] Style props on any component: `class_name="..."` (renders as the
      HTML `class` attribute; named to dodge the `class` keyword) and
      `style={...}` (a dict of CSS properties, rendered as an inline
      `style` attribute, e.g. `{"font_weight": "bold"}` ->
      `style="font-weight: bold"`).
- [x] **Internal links now compile to real relative file paths.**
      `Link("About", href="/about")` is resolved against the site's
      route table at render time and rewritten to `about.html`,
      `../about.html`, etc., depending on the linking page's location.
      External URLs (`https://...`), protocol-relative URLs (`//...`),
      fragments (`#section`), and `mailto:`/`tel:` links are left
      untouched. Same handling applies to the generated `<link
      rel="stylesheet">` tag, so it resolves correctly for nested
      routes too.
- [x] CLI auto-opens the built site in the default browser
      (`webbrowser.open` on a `file://` URI to `index.html`) after a
      successful `arklight build`, controlled by `--open` (default)
      /`--no-open`. Browser-launch failures (e.g. headless CI) are
      swallowed rather than failing the build.
- [x] Example site (`examples/hello_site/site.py`) rewritten: a shared
      `nav()` helper function (plain Python composition) is called
      from both pages so Home and About actually link to each other;
      `class_name="nav"`/`"card"`/`"muted"` used to lean on the new
      default stylesheet.
- [x] 15 new tests (57 total, all passing): CSS backend output,
      relative-link resolution (same-level, nested, unknown routes,
      externals/fragments untouched), `class_name`/`style` rendering,
      stylesheet link path correctness, and CLI browser-open behavior
      (mocked -- no real browser launched in tests).

### Verification performed

```bash
arklight build examples/hello_site/site.py -o /tmp/dist_v2 --no-open
# inspected output HTML directly: hrefs are "index.html"/"about.html", not "/about"
# rendered both pages with wkhtmltoimage --enable-local-file-access to confirm
# the stylesheet loads and the page is visually styled, not "hot garbage"
python3 -m pytest -q
# -> 57 passed
```

### Bugs found and fixed during this milestone

1. **The actual cause of "index and about aren't linked."** It wasn't
   a missing feature -- the example already had a `Link(..., href="/")`
   -- it was that root-absolute hrefs (`/about`) only resolve correctly
   once a site is deployed at a domain root. Opening `dist/index.html`
   directly via `file://` (exactly what a beginner does on "first
   setup") sends `href="/about"` to the filesystem root, not
   `dist/about.html`. Root-caused and fixed by making the HTML backend
   route-aware: it now knows every page's output path and rewrites
   internal hrefs to correct relative paths at compile time.
2. **Nothing ever opened a browser.** `arklight build` only wrote
   files and printed paths. Added `open_in_browser()` in the CLI,
   wired to run by default after a successful build.

### Deliberate design choices worth remembering later

- **One static, global stylesheet for v0.002**, not per-node CSS
  generation. `CSSBackend.render(ir)` currently ignores `ir` and
  returns a constant `styles.css`. This was a deliberate scope cut --
  collecting `style=` props into real generated CSS rules (instead of
  inline `style` attributes) is a natural v0.002-follow-up but wasn't
  needed to fix the reported problems or ship a good default look.
- **`class_name` instead of `class`** as the prop name, matching how
  most Python-to-HTML tools (JSX's `className`, Django templates via
  `class_`, etc.) dodge the same keyword collision. Kept consistent
  with "AI-friendly API": one obvious, greppable name.
- **Backends now form a list, not a single object**, in both
  `build()`'s signature and internally. This was the smallest change
  that matches the architecture doc's "Future: CSS, JavaScript, Vue,
  Svelte" framing literally -- multiple backends consuming the same IR
  -- rather than treating CSS as a special case bolted onto the HTML
  backend.

## Previous milestone: v0.001 -- Python → HTML

**Status: DONE.** Full pipeline implemented, tested, and verified
end-to-end against the example from ARCHITECTURE.

### What's implemented

- [x] `ARKNode` (`arklight/ast/nodes.py`) -- the ARK AST node type, plus
      the `node(type_name)` factory used to define every built-in
      component as a plain function.
- [x] Public API (`arklight/api.py`) -- `Site`, `Page`, `Heading`,
      `Text`, `Button`, `Container`, `Link`, `Image`, `List`, `Item`.
- [x] Static Python AST discovery (`arklight/parser/discover.py`) --
      uses the stdlib `ast` module to find `Site()` and
      `@site.page(...)` registrations **without executing user code**.
      This is a real, standalone pipeline stage, not just a comment.
- [x] Module loader (`arklight/parser/loader.py`) -- executes the site
      file in an isolated namespace to get the live `Site` object, with
      errors wrapped in `SiteLoadError` (bad file path, syntax error,
      no `Site()`, no pages, runtime error during module exec).
- [x] Normalization (`arklight/ir/normalize.py`) -- flattens nested
      list children (from comprehensions), drops `None`/`False`
      (conditional rendering pattern), and wraps bare strings as `Text`
      nodes -- *except* inside components that are themselves
      text-only, where a bare string is already correct.
- [x] Validation (`arklight/ir/validate.py`) -- schema-driven: unknown
      component types, missing required props (`Link.href`,
      `Image.src`), disallowed children (`Image`), and disallowed
      nesting (component inside a text-only component) all raise a
      specific `ValidationError` with a path to the offending node.
- [x] Shared schema (`arklight/ir/schema.py`) -- single source of truth
      for per-component rules, used by both normalize and validate so
      they can never disagree (this fixed a real bug -- see "Bugs
      found and fixed" below).
- [x] Website IR (`arklight/ir/build.py`) -- `IRNode` / `IRPage` /
      `WebsiteIR`, deliberately kept as a separate type from `ARKNode`
      even though v0.001's shapes are similar, so future milestones can
      let IR diverge from the public API's ergonomics.
- [x] Backend interface (`arklight/backend/base.py`) -- abstract
      `Backend.render(ir) -> {relative_path: contents}`. Backends never
      touch the filesystem directly, which keeps them trivially
      testable in isolation.
- [x] HTML backend (`arklight/backend/html/render.py`) -- maps IR node
      types to HTML tags, `Heading(level=N)` to `h1`-`h6`, known props
      to real HTML attributes, unknown props to `data-*` attributes,
      HTML-escapes all text content, and maps routes to output file
      paths (`/` -> `index.html`, `/about` -> `about.html`, `/blog/post`
      -> `blog/post.html`).
- [x] Compiler pipeline (`arklight/compiler/pipeline.py`) --
      orchestrates every stage above into `compile_site_file()` (source
      -> IR) and `build()` (source -> files written to disk). Every
      failure mode from every stage is caught and re-raised as a single
      `CompileError` with a clear message, so CLI users never see a raw
      internal traceback for an ordinary mistake (missing prop, unknown
      component, undefined name, etc.).
- [x] CLI (`arklight/cli/main.py`) -- `arklight build <entry.py> [-o
      OUTPUT_DIR]`, `arklight --version`.
- [x] Example site (`examples/hello_site/site.py`) -- two pages (`/`
      and `/about`), matching and extending the ARCHITECTURE.md sample.
- [x] Packaging (`pyproject.toml`) -- installable via `pip install -e
      .`, registers the `arklight` console script.
- [x] Test suite (`tests/`) -- 42 tests covering every stage in
      isolation plus full end-to-end builds. All passing.

### Verification performed

```bash
pip install -e .
arklight build examples/hello_site/site.py -o /tmp/dist_test
# -> valid index.html and about.html produced
python3 -m pytest -q
# -> 42 passed
```

### Bugs found and fixed during this milestone

1. **Double-wrapping strings inside text-only components.**
   Normalization originally wrapped every bare string child in a `Text`
   node unconditionally. This is correct for `Container`-like nodes
   (`Container("hi")` should become `Container(Text("hi"))` so
   container children are a uniform list of nodes) but wrong for
   components that are *themselves* text-only, like `Heading("hi")` --
   wrapping there produced `Heading(Text("hi"))`, which Validation then
   correctly rejected as "a Heading can't contain a nested component."
   Fixed by extracting a shared `arklight/ir/schema.py` with
   `TEXT_ONLY_TYPES`, consulted by both `normalize.py` (to decide
   whether to wrap) and `validate.py` (to decide whether nesting is
   allowed), so the two stages can't drift out of sync again.

2. **Page-function errors not surfaced as `CompileError`.** Because
   `@site.page(...)` only *registers* a function (it isn't called at
   module-exec time), a `NameError` or other exception raised **inside**
   a page function wasn't being caught by the loader's
   exec-time try/except -- it only appeared later, when
   `site.build_ark_ast()` actually calls each page function during
   pipeline execution. Fixed by wrapping the `build_ark_ast()` call
   (and the subsequent `normalize_ark_ast()` call) in the pipeline with
   their own try/except, so *every* stage's failure becomes a
   `CompileError` for CLI/API consumers, not just exec-time errors.

### Deliberate design choices worth remembering later

- **Execution vs. pure static analysis for the ARK AST.** The
  architecture doc's "Python AST" stage is implemented as genuine
  static analysis (via the stdlib `ast` module) for *discovery*
  (finding routes/pages), but the ARK AST itself is still produced by
  *executing* the module, because components are ordinary function
  calls and Python's full semantics (loops, conditionals, imports,
  helper functions) are needed to build real trees. Reimplementing a
  Python interpreter over the AST to avoid execution entirely was
  judged out of scope and against "Flask-like simplicity" for v0.001.
  If sandboxing untrusted site files ever becomes a requirement, this
  is the place to revisit.
- **IR kept structurally distinct from ARK AST**, even though in
  v0.001 `IRNode` and `ARKNode` look almost identical. This was a
  deliberate hedge for v0.100 (alternate backends) and v0.010
  (user-defined components), where the IR may need to diverge from
  whatever shape is most ergonomic for the Python API.
- **Route -> file path mapping** uses the simple convention `/` ->
  `index.html`, `/x` -> `x.html`, `/x/y` -> `x/y.html`. "Pretty URL"
  output (`/x/index.html`) was considered but deferred -- easy to add
  as a backend option later without touching earlier stages.

## Next up: v0.010 -- Components (user-defined, reusable)

Not started. Per `docs/DESIGN-NOTES.md`, this is where "write a plain
Python function" (today's `nav()` pattern) becomes a real, first-class
reusable unit -- likely with its own default styling bundled in, which
would be a genuine differentiator versus htpy/FastHTML (neither ships
opinionated per-component CSS). Rough questions to resolve first:

- What distinguishes a "component" from a plain helper function like
  `nav()` today? If the answer is "nothing, syntactically" the
  milestone may be more about a registration/discovery mechanism (so
  the compiler *knows* about reusable components, e.g. for future
  tooling) than a new runtime concept.
- Should components be able to carry their own default `style=`/CSS
  rules, shipped alongside the component definition rather than
  relying entirely on the global stylesheet?
- Note from the design-notes doc: this milestone does **not** by
  itself move ARKlight toward "Svelte-like." The next real fork in the
  road is whether a future milestone introduces state/event semantics
  into the IR (a prerequisite this doc names for v0.100 to mean
  anything beyond static output) -- worth deciding explicitly before
  v0.100, not assuming it falls out of v0.010 or v0.100 automatically.

## v0.003 addendum -- vocabulary extension (done)

Not a new milestone/version -- this stays v0.003. Added ~46 more
built-in components (semantic layout, text-level semantics, forms,
tables, media) and two more closed JS behaviors (`copy`, `dismiss`) on
top of the original v0.003 JavaScript-helpers work, entirely as data
in `arklight.ir.schema.SCHEMA` / `arklight.ir.schema.KNOWN_BEHAVIORS`
-- no changes to normalize.py, validate.py, or build.py. See
`CHANGELOG.md` for the full list and `docs/DESIGN-NOTES.md` ("v0.003:
closing the vocabulary gap, not the structural ceiling") for what this
does and doesn't change about the ceiling (still no
`@media`/`@container`, still a closed JS vocabulary).

Also fixed a pre-existing version drift: `pyproject.toml` said
`0.001` while `arklight/__init__.py` said `0.003`; both now correctly
read `0.003`.

## v0.003 addendum 2 -- even more vocabulary (done)

Still v0.003, same mechanism as addendum 1: 33 more built-in
components, purely as data in `arklight.ir.schema.SCHEMA` (+
`TAG_MAP`/`PASSTHROUGH_ATTRS`/`VOID_TAGS` in the HTML backend, +
default CSS rules) -- normalize.py/validate.py/build.py untouched
again. This batch closes the "long tail" gaps a production
responsive static site still hits after addendum 1: a numbered list
(`OrderedList` -- addendum 1 could only ever produce `<ul>`),
description lists, art-directed responsive images
(`Picture`/`PictureSource` + `loading`/`decoding`, the image half of
"responsive design" that addendum 1's CSS-only utilities didn't
cover), native progress/gauge/autocomplete/output widgets, a
`Dialog` that opens and closes with zero JS via
`Form(method="dialog")`, the rest of text-level semantics including
bidi (`Bdi`/`Bdo`) and ruby (`Ruby`/`Rt`/`Rp`) annotations, table
column grouping, video/audio caption tracks, image maps, `IFrame`
embeds, and a `NoScript` fallback. 22 new tests in
`tests/test_vocabulary_addendum_2.py` (109 total). Full list and
per-group rationale in `CHANGELOG.md`.

Deliberately left out (see CHANGELOG.md "Notes" for why):
`<canvas>`/`<template>` (meaningless without JS driving them, out of
scope for the closed-behavior model), the new `<search>` landmark
(too new/unsettled), `<object>`/`<embed>` (redundant with `IFrame`
for this project's use cases).

## Milestone checklist (from ARCHITECTURE.md)

- [x] v0.001 Python → HTML
- [x] v0.002 CSS
- [x] v0.003 JavaScript helpers (+ two vocabulary extension addenda above)
- [ ] v0.010 Components
- [ ] v0.100 Alternate backends -- Backend interface ready; IR needs a
      state/event-semantics milestone first (see `docs/DESIGN-NOTES.md`)
- [ ] v1.0 Stable compiler
