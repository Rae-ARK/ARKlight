# ARKlight Progress

Living document tracking what's implemented, key decisions made along
the way, and what's queued up next. Update this file at the end of
every work session, not just at milestone boundaries.

## Current milestone: [Unreleased] -- JS runtime error-handling hardening

**Status: DONE**, version number not yet assigned. Follow-up to "CLI &
pipeline error-handling hardening" directly below -- that pass covered
the Python/CLI side and explicitly deferred the generated client-side
`arklight.js` runtime, which had **zero** `try`/`catch` anywhere in it
(confirmed by reading `arklight/backend/js/render.py` and every
behavior/action fragment directly). Full detail in `CHANGELOG.md`
("JS runtime error-handling hardening"). Short version:

- [x] New `arkNotify(message)` helper (`arklight/backend/js/render.py`)
      -- small, self-contained, inline-styled on-page notice, shipped
      only when a site actually uses a behavior or declares
      `State(...)` (same "only ship what's used" discipline as the
      rest of this runtime). Gives end users a visible signal instead
      of a console-only error nobody but a developer would ever see.
      Wrapped in its own `try`/`catch` so the notifier itself can
      never throw.
- [x] `initState()`'s `JSON.parse` is now guarded -- previously a
      malformed `data-ark-state` attribute threw inside the
      `DOMContentLoaded` handler and silently aborted `wireActions()`
      (and anything scheduled after it) for the whole page.
- [x] `wireActions()` and `wireBehaviors()` now guard each element's
      setup *and* its click dispatch independently -- previously one
      malformed element (bad JSON in `data-ark-action-args`, or a
      behavior/action throwing at click time) could abort the
      `forEach` loop for every other element on the page, not just the
      one at fault.
- [x] The `copy` behavior's clipboard promise
      (`arklight/backend/js/behaviors/copy.py`) now has a `.catch()`
      -- previously an unhandled rejection, notable because
      `arklight build --open` opens sites as `file://` URLs by
      default, exactly where clipboard permissions are likeliest to be
      denied.
- [x] `tests/test_js_error_handling.py` -- 8 new tests (212 total, all
      passing).

Deliberately left out: `renderBindings()` and `highlightActiveNavLink()`
have no plausible runtime failure mode given their inputs
(`store.get(key)` returning `undefined` just renders as the text
"undefined", not a throw; the nav-highlight loop only ever touches
`<a>` elements' own `.href`), so no guard was added to either.

## Previous milestone: [Unreleased] -- CLI & pipeline error-handling hardening

**Status: DONE**, version number not yet assigned. Prompted by a UX
audit comparing the CLI's error handling against how the generated
client-side JS runtime handles (or rather, doesn't handle) failures.
Full detail in `CHANGELOG.md` ("CLI & pipeline error-handling
hardening"). Short version:

- [x] `arklight/cli/main.py::main()` -- top-level `try/except` around
      subcommand dispatch. Every subcommand already caught its own
      typed error (`CompileError`/`PackError`/`PWAError`/
      `ScaffoldError`); anything outside those known, anticipated
      failure modes previously escaped as a raw traceback, which
      directly contradicted the CLI module docstring's own stated
      goal. Now prints a clear "outside ARKlight's known, handled
      failure modes" message and exits `1`.
- [x] `arklight/compiler/pipeline.py::build()` -- the output-file
      write loop and the `_copy_assets()` call are now each guarded
      with `try/except OSError`, reporting exactly how many files
      wrote successfully before a failure (permissions, disk full, a
      network drive dropping mid-write) rather than leaving a silently
      partial output directory that looks the same as a complete one.
- [x] `_cmd_pack` -- prints a runtime warning when `--passphrase` is
      passed on the command line (shell history / process-listing
      exposure), rather than leaving that risk documented only in
      `--help` text.
- [x] Fixed a real, pre-existing bug found while making the change
      above: `_cmd_pwa` was defined twice in `arklight/cli/main.py`
      (identical bodies, second silently shadowed the first). Removed
      the duplicate.
- [x] Fixed a version drift recurrence: `pyproject.toml` said `0.1.0`
      while `arklight/__init__.py` already said `0.038` -- same class
      of bug as the one fixed during the "v0.003 addendum" pass below,
      just recurred for a later version jump and went uncaught.

Deliberately out of scope for this pass, tracked as separate follow-up
work: the generated client-side `arklight.js` runtime has an
analogous gap -- zero `try`/`catch` anywhere in
`arklight/backend/js/render.py`'s output, an unhandled clipboard-
promise rejection in the `copy` behavior (`.writeText().then(...)`
with no `.catch()`, notable since `arklight build --open` opens sites
as `file://` URLs by default -- exactly where clipboard permissions
are likeliest to fail), and a single malformed
`data-ark-action-args` attribute able to abort `wireActions()`'s
`forEach` for every *other* element on the page, not just the bad one.

**Update:** this follow-up is now done -- see the "JS runtime
error-handling hardening" milestone directly above.

## Previous milestone: v0.0035 -- Stateful JS

**Status: DONE.** This entry was missing from PROGRESS.md/CHANGELOG.md
even though the code shipped -- `pyproject.toml` and
`arklight/__init__.py` both already read `0.0035`, and the README
"Status" section already described this milestone in the present
tense. Docs are being brought back in sync with the code here rather
than the other way around; nothing described below required new
implementation work.

### What's implemented

- [x] `KNOWN_BEHAVIORS` (a flat `frozenset`) replaced by
      `BEHAVIOR_REGISTRY: dict[str, BehaviorSpec]`
      (`arklight/ir/schema.py`) -- `KNOWN_BEHAVIORS` stays as a derived
      `frozenset(BEHAVIOR_REGISTRY)` so Validation's existing check
      didn't need to change shape.
- [x] `arklight/backend/js/behaviors/` -- one file per behavior
      (`toggle.py`, `scroll_to.py`, `copy.py`, `dismiss.py`), each a
      `JS_FRAGMENT` string; `JSBackend.render()` concatenates only the
      fragments a given site's IR actually references.
- [x] `arklight/backend/js/actions/` -- one file per closed action
      (`set.py`, `increment.py`, `toggle_bool.py`), driven by a new
      `ACTION_REGISTRY` (same registry pattern as behaviors), so a
      future `Action.append_to_list`/etc. is a new registry entry, not
      a `JSBackend` rewrite.
- [x] New API in `arklight/api.py`: `State(name, initial)` (declares
      page-scoped reactive state, stored on the IR's `Page` node),
      `Bind(name)` (references a declared `State(...)` wherever a
      literal prop value is accepted today, e.g. `Text(Bind("count"))`),
      and `Action.set`/`Action.increment`/`Action.toggle_bool`
      (structured `ActionRef` objects for `on_click=`, never an
      arbitrary JS/Python string).
- [x] Validation extended: every `Bind(...)`/`Action.*(...)` must
      reference a `State(...)` actually declared on that page, same
      "catch it at compile time" guarantee the rest of Validation
      already provides.
- [x] `JSBackend` emits, only for pages that declare `state`, a small
      fixed reactive core (`createState` closure, `data-ark-bind`
      re-render wiring, an action dispatcher walking
      `ACTION_REGISTRY`) -- still no `eval`, no `new Function`, no
      string ever executed as code.
- [x] `tests/test_stateful_js.py` -- 14 tests covering the new API,
      validation, and generated runtime (130 tests total, all
      passing).

### Deliberate design choices worth remembering later

- Explicit scope boundary honored: this milestone added **capability,
  not vocabulary** -- no new named behaviors, just the registry
  refactor plus the `State`/`Bind`/`Action` primitives, exactly as
  scoped in `docs/DESIGN-NOTES.md` ("v0.0035: stateful JS --
  capability, not vocabulary").
- This is the reactivity/IR-state milestone `docs/DESIGN-NOTES.md`
  named as the real prerequisite for v0.100 (alternate backends) to
  mean more than static HTML wearing a different file extension --
  worth revisiting that section before scoping v0.100 for real.

## Previous milestone: v0.003 -- JavaScript helpers

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

## Done: v0.036 -- ARK Bundle spec v1

Implemented. Full writeup in `docs/DESIGN-NOTES.md` ("v0.036: ARK
Bundle spec v1"). Short version: `arklight pack <build-dir> -o
site.ark` packages a site's existing build output into a single
`.ark` file, so it can be shared and opened like a native document --
no local server, no Python environment, no separate player app on
desktop *or* Android.

Key design decision: the bundle is an **HTML/ZIP polyglot** -- the raw
build files are stored untouched inside a standard ZIP, with a fully
self-contained, inlined rendering of the entry page placed *before*
the ZIP data. The same bytes are simultaneously a directly-renderable
HTML document (a browser stops parsing at `</html>` and never touches
the trailing ZIP data -- no extraction, no temp files, same as opening
a `.mp4` doesn't unpack it first) and a valid ZIP archive (any archive
tool can extract the original, unmodified build output). Prior art:
this is the same technique the SingleFile web-archiving tool ships in
production as `--self-extracting-archive`. Confirmed working against
both Python's own `zipfile` reader and the system `unzip` binary.

Explicit scope boundary for v1, as shipped: packaging only, over files
the existing pipeline already produces. No changes to `normalize.py`/
`validate.py`/`build.py`/the `Backend` interface/the IR, and a
separate module (`arklight/packer/`) rather than logic folded into
the compiler internals (per explicit request -- see
`docs/DESIGN-NOTES.md`). **Only `.html`/`.css`/`.js` files are
inlined/packed** -- an `assets/` folder (images/audio/video/anything
else) is detected and reported as skipped rather than packed; carrying
those over is the next planned version, not this one. An
`--encrypt`/password flag so the ZIP payload isn't inspectable without
a password is planned for the version after that.

One implementation note worth flagging for future work in this area:
the original design doc assumed manual ZIP-header offset patching
would be needed to prepend arbitrary bytes before the archive. It
wasn't -- opening the same already-open file handle with
`zipfile.ZipFile(handle, mode="a")` after writing the HTML prefix to
it directly is sufficient, since `zipfile` computes offsets from the
handle's current position rather than assuming a byte-0 start.

## Then: v0.004 -- CLI scaffolding (DONE) + responsive/head extension (PLANNING)

Originally three pieces, independent of v0.0035. Status as of this
update:

- [x] `arklight new <name> --template simple|production` --
  **implemented and wired into the CLI** (`arklight/cli/scaffold.py`,
  `arklight/cli/templates/simple.py` and `.../production.py`,
  `_cmd_new` in `arklight/cli/main.py`). The doc note below ("v0.0035
  -- done; v0.004 -- folder scaffolding only, logic not started") is
  now stale as a result and is being left in place with this
  correction rather than rewritten, per this file's own convention of
  not silently editing history.
- [ ] `responsive_style={...}` prop -> real `@media` blocks in the CSS
  backend. Still not implemented -- `arklight/backend/css/render.py`
  still emits one fixed stylesheet with no `@media`/`@container`
  blocks.
- [ ] `Page(meta=..., links=...)` -- a structured, non-arbitrary
  `<head>` extension point (no raw HTML injection). Still not
  implemented.

## Later: v0.010 -- Components (user-defined, reusable)

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

## v0.0035 -- done; v0.004 -- folder scaffolding only (logic not started)

`arklight/backend/js/behaviors/` and `arklight/backend/js/actions/`
were originally added as empty, docstring-only packages ahead of the
actual work; both are now fully populated (see "Current milestone:
v0.0035" above) -- `arklight/backend/js/render.py` assembles the
runtime from these fragments instead of one static `RUNTIME_JS`
string.

Still scaffold-only, logic not started:

- `arklight/cli/templates/` -- where the `simple`/`production`
  templates for `arklight new` (`docs/DESIGN-NOTES.md`, "v0.004: CLI
  scaffolding") will live, with `templates/simple/assets/` and
  `templates/production/assets/` placeholder directories (just a
  `.gitkeep` each -- deliberately not copied from Product-Showcase).
  Nothing is wired into `arklight/cli/main.py` yet; `arklight` still
  only has the `build` subcommand.

Also documented, not implemented, in `docs/DESIGN-NOTES.md`: two CLI
helpers (`arklight --help`, `arklight --search <name>`) for looking up
a component's schema by name once the vocabulary is large enough that
recall becomes the bottleneck. Explicitly held for a separate
go-ahead signal, independent of v0.0035/v0.004 above.

## v0.0035 addendum II -- list actions (append, remove) (done)

Not a new milestone/version -- second growth pass on
`ACTION_REGISTRY`, same mechanism as addendum I directly below. First
actions that assume a list-valued `State(...)` rather than a scalar
one:

- [x] `Action.append(name, value)` -- appends to a list-valued state
      key. `arklight/backend/js/actions/append.py`.
- [x] `Action.remove(name, index)` -- removes by index from a
      list-valued state key. `arklight/backend/js/actions/remove.py`.
- [x] `tests/test_stateful_js_vocabulary_addendum_2.py` -- 12 new
      tests (182 total, all passing).

No changes needed to `Bind`/`renderBindings` -- `el.textContent =
store.get(key)` already renders a list via JS's own
`Array.prototype.toString()`. Per-item templating (a real `<li>` per
item) is bigger scope and deliberately left for a future version, same
as derived/computed state, `Action.set_from_input`, and
debounced/throttled actions -- see `docs/DESIGN-NOTES.md`
("v0.0035: stateful-JS vocabulary addendum II").

## v0.0035 addendum I -- decrement, reset (done)

Not a new milestone/version -- same "addendum, not a full milestone"
treatment as the two v0.003 vocabulary addenda above, applied to
`ACTION_REGISTRY` for the first time. Added the two most commonly
needed state actions, purely as new registry entries + JS fragment
modules (no changes to normalize.py/validate.py/build.py/`JSBackend`'s
generation logic):

- [x] `Action.decrement(name, delta=1)` -- `-1` counterpart to
      `Action.increment`. `arklight/backend/js/actions/decrement.py`.
- [x] `Action.reset(name)` -- resets a state key back to its declared
      initial value, via a new `reset(key)` method on the reactive
      core's `createState` closure. `arklight/backend/js/actions/reset.py`.
- [x] `tests/test_stateful_js_vocabulary_addendum.py` -- 10 new tests
      (170 total, all passing).

Deliberately left for a future version at the time (see
`docs/DESIGN-NOTES.md`, "v0.0035: stateful-JS vocabulary addendum"):
list actions -- addressed in addendum II directly above --
derived/computed state, `Action.set_from_input` (binding state to
`input`/`change` events, not just `click`), and debounced/throttled
actions.

## Milestone checklist (from ARCHITECTURE.md)

- [x] v0.001 Python → HTML
- [x] v0.002 CSS
- [x] v0.003 JavaScript helpers (+ two vocabulary extension addenda above)
- [x] v0.0035 Stateful JS (registry-driven behaviors + actions,
      `State`/`Bind`/`Action.*`), plus addenda I & II (decrement,
      reset, append, remove)
- [x] v0.004a `arklight new` CLI scaffolding (simple + production
      templates) -- implemented and wired in
- [ ] v0.004b CSS `@media` support + structured `<head>` extension --
      still design-only
- [ ] v0.010 Components
- [x] v0.036 ARK Bundle spec v1 (single-file `.ark` packaging via
      `arklight pack`; html/css/js carry-over only)
- [x] v0.037 Sealed ARK Bundles (`assets/` carried into the archive,
      encrypted by default, `--passphrase`/`--plain`, `arklight unpack`)
      -- previously missing from this checklist despite shipping; added
      here for accuracy
- [x] [Unreleased] CLI, pipeline & JS runtime error-handling
      hardening (top-level catch-all in `main()`, `OSError` guards in
      `build()`, passphrase warning, `arkNotify()` + `try`/`catch`
      guards throughout the generated `arklight.js` runtime; version
      number not yet assigned -- see `CHANGELOG.md`)
- [ ] v0.100 Alternate backends -- Backend interface ready; IR needs a
      state/event-semantics milestone first (see `docs/DESIGN-NOTES.md`)
- [ ] v1.0 Stable compiler
