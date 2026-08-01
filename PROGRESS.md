# ARKlight Progress

Living document tracking what's implemented, key decisions made along
the way, and what's queued up next. Update this file at the end of
every work session, not just at milestone boundaries.

## Current milestone: v0.002 -- CSS

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

## Next up: v0.003 -- JavaScript helpers

Not started. Rough shape to evaluate first:

- What's the smallest useful JS surface that doesn't violate "the
  browser never executes Python"? Likely candidates: a `JSBackend`
  emitting a small `site.js` for things like nav-toggle/interactivity
  helpers, plus a way for a component to declare "attach this behavior"
  without hand-writing inline `onclick` strings.
- Should JS behaviors be named, reusable helpers (`Button("Go",
  on_click="toggle_menu")`) resolved against a small built-in behavior
  library, rather than letting users embed arbitrary JS strings? Leaning
  towards yes, to keep the "AI-friendly", "one obvious way" principles
  intact and avoid quietly becoming a JS templating engine.
- This is also a good time to revisit "per-node style generation" noted
  as deferred in the v0.002 section above, since JS behaviors and CSS
  classes often want to be declared together (e.g. a collapsible nav).

## Milestone checklist (from ARCHITECTURE.md)

- [x] v0.001 Python → HTML
- [x] v0.002 CSS
- [ ] v0.003 JavaScript helpers
- [ ] v0.010 Components
- [ ] v0.100 Alternate backends
- [ ] v1.0 Stable compiler
