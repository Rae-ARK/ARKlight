# Changelog

All notable changes to ARKlight are tracked here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/); versions
follow the milestone scheme from ARCHITECTURE.md rather than strict
SemVer.

## [0.0436] - Unreleased

**`arklight pwa` can now register manifest icons via `--icon`.**
`enable_pwa(icons=...)` already accepted a list of manifest icon
dicts, but the CLI had no way to pass them -- every `arklight pwa`
run shipped an empty `icons` list, which is enough for some browsers
to decline to prompt an install. Added a repeatable `--icon
SRC:SIZES[:TYPE]` flag (e.g. `--icon assets/icon-192.png:192x192`);
`SRC` is a path relative to the build directory (same as an icon
already copied into `assets/` by a normal build), `SIZES` is
`WIDTHxHEIGHT` or `any`, and `TYPE` is optional, inferred from `SRC`'s
extension via `mimetypes` when omitted. Malformed values (bad `SIZES`,
an extension `mimetypes` can't resolve without an explicit `TYPE`)
report a normal CLI error rather than a traceback or a silently wrong
manifest.

## [0.0435] - Unreleased

**`arklight new --template production` now recommends the layout it
already scaffolds.** The `production` template's `site.py` +
`components/` + `pages/` + `content/` split was already
service-oriented and separated by concern, but a first-time user got
no explanation of *why* the files were laid out that way -- just a
file list. A short note now prints after every `production` scaffold
(`arklight new` output for `simple` is unchanged, since there's
nothing to explain there). Added `arklight new --explain-architecture`
to print the full guide -- concrete to this template's actual
directories, not generic advice -- either standalone (`arklight new
--explain-architecture`, no project name needed) or right after a
`--template production` scaffold. `name` is now an optional positional
on `new` (only to allow the standalone form); omitting it without
`--explain-architecture` still errors exactly as before.

## [0.0434] - Unreleased

**`<html lang="...">` is no longer hardcoded to `"en"` with zero
override path.** Every page of every ARKlight site, regardless of
actual content language, rendered `lang="en"` -- wrong for any
non-English site, and consequential: `lang` drives screen-reader
pronunciation, browser auto-translate prompts, and search engines'
language signal, not just cosmetics. Added `WebsiteIR.lang` (default
`"en"`, unchanged), `Site(lang=...)` for a sitewide default, and a
per-page `Page(lang=...)` override read the same way `title`/
`favicon`/`description` already are -- a page-level override wins over
the sitewide default, which wins over the `"en"` stock default. Also
added `arklight build --lang TAG`, which overrides `Site(lang=...)`
(but not an explicit `Page(lang=...)`) without a site-file edit.
Verified the emitted value is HTML-escaped (no injection risk from an
untrusted `lang` string).

**Button text color decoupled from accent, silently.** `button`'s
`color: #ffffff` was a literal, independent of `background:
var(--ark-accent)` -- harmless while the stock accent stayed a dark
indigo, but a real usability trap for any site now setting a *light*
accent (via the override paths added in 0.0432/0.0433): white text on
a light button background, unreadable, with no var to fix it through.
Added `--ark-button-text` (default `#ffffff`, unchanged) and
`Site(button_text=...)` / `arklight build --button-text VALUE`.

## [0.0433] - Unreleased

**`body`'s `font-family` is no longer unreachable.** Same bug class as
the container-width fix, just not caught in that pass: `body` read a
literal font stack directly (no `--ark-*` var at all), so there was no
way -- sitewide *or* per-instance -- for a site author to change the
font. Added `--ark-font-family` (universal `"*"` `@property` syntax,
since font stacks don't fit a typed CSS syntax component) and
`Site(font_family=...)` + `arklight build --font-family "..."`,
mirroring `max_width`/`bg`. Default unchanged from BASE_CSS's existing
system-font stack.

**PBKDF2 iterations raised from 200,000 to 600,000 (`ARKSEAL2`),
without breaking any bundle already sealed at the old count.**
`_PBKDF2_ITERATIONS` was a fixed module constant with no version
attached to it in the blob format -- bumping it in place would have
made `unseal()` silently derive the wrong key (and report a misleading
"wrong passphrase") for every `.ark` bundle sealed by an older
ARKlight release. Fixed by making the format self-describing about its
own iteration count instead of assuming one: `ARKSEAL2` embeds a
4-byte iteration count in passphrase mode; `unseal()` still recognizes
`ARKSEAL1` bundles and falls back to the old fixed 200,000 for them.
Every bundle sealed by every past release still opens unchanged; only
newly-sealed bundles get the stronger, current-OWASP-guidance count.
`arklight.packer.bundle`'s sealed-bundle detection (`was_sealed = ...`)
updated to recognize both magics (`SEALED_MAGICS`) instead of hardcoding
`ARKSEAL1`.

## [0.0432] - Unreleased

**`--max-width`/`--bg` CLI flags on `arklight build`.** The site-file
API (`Site(max_width=..., bg=...)`) already existed, but there was no
way to set either without editing the site file itself. `arklight
build site.py --max-width 90rem --bg "#0f0f1a"` now overrides those
design tokens at build time, taking precedence over whatever the site
file sets; leaving both flags off changes nothing. Threaded through
`compile_site_file()`/`build()` as an optional `css_var_overrides`
merge, layered *over* `site.css_var_overrides` rather than replacing
it.

**Layout-primitive tokens (`Stack`/`Cluster`/`Sidebar`/`Switcher`/
`Grid`/`Reel`) are now sitewide-configurable via `Site(...)`.**
Previously `--ark-stack-space`, `--ark-grid-min`,
`--ark-switcher-threshold`, `--ark-sidebar-width`,
`--ark-cluster-space`, `--ark-sidebar-space`, `--ark-switcher-space`,
`--ark-grid-space`, `--ark-center-gutter`, and `--ark-reel-space` each
had a `var(--ark-x, fallback)` at their point of use in `BASE_CSS`, so
a *per-instance* wrapper `style="--ark-grid-min: 20rem"` already
worked -- but there was no sitewide override path the way
`max_width`/`bg` have, a gap `design_tokens.py` flagged in its own
comments as "tracked as a follow-up." `Site(stack_space=..., grid_min=...,
switcher_threshold=..., sidebar_width=..., cluster_space=...,
sidebar_space=..., switcher_space=..., grid_space=..., center_gutter=...,
reel_space=...)` are now real constructor kwargs, all defaulting to
`None` (unset) -- an unconfigured site's rendered layout is unchanged,
byte-identical apart from these values now also being declared
explicitly at `:root` (needed for the `@property` typing and the
override path to work at all).

## [Unreleased]

**Documentation fix: the container-width bug fix itself was never
documented.** `arklight/api.py`'s own `Site.__init__` comment has
pointed at `docs/CONTAINER-WIDTH-BUG.md` since the fix landed in
`7aabfb5` ("CSS Backend is being refactored for predictability. Stage
1 done.") -- but that file never existed in this repo (only in a
downstream site's own repo, which independently diagnosed the same
bug from the outside). Added `docs/CONTAINER-WIDTH-BUG.md` here,
documented `Site(max_width=..., bg=...)` in `README.md`'s "Styling
components" section (previously undocumented anywhere despite being
live, working public API), and this entry. No code change -- the fix
itself already shipped; only the paper trail was missing.

**Stage 2 of the vdom staging: reactive class binding.**
`Bind.when("active", "is-active")` + `bind_class=` toggles a CSS class
as a `State(...)` value's truthiness changes (`ClassBindSpec`,
validated the same way `Action.*`/`Bind` already are). HTML backend
pre-fills the class from the initial state value; the JS runtime uses
a small direct `classList.toggle` pass (`renderClassBindings`) rather
than routing through Stage 1's vdom `patch()`, since the vendored bare
core has no class module and doing so would remount the element on
every toggle. 10 new tests (`tests/test_class_binding.py`); no
page-facing change to `State`/`Bind`/`Action.*`.

**Stage 1 of a staged reactive-core expansion: vendored vdom core.**
Pages that declare `State(...)` now re-render their `data-ark-bind`
elements through a vendored [snabbdom](https://github.com/snabbdom/snabbdom)
core (`init` + `h` + `vnode` + `htmlDomApi`, MIT licensed, no optional
modules -- see `arklight/backend/js/vdom.py`) instead of a raw
`el.textContent = ...` assignment. This is a mechanism swap only: no
new page-facing Python API, no change to `State`/`Bind`/`Action.*`
behavior, and pages without `State(...)` still ship none of it (only
ship what's used, unchanged). It exists to give later stages (list
rendering, conditional show/hide, attribute/class binding, and a
planned "Stage 8": `localStorage` persistence for `State`) a real
diff/patch algorithm to build on rather than each hand-rolling one.

Next up is **v0.044** (JS backend capability
expansion -- computed/derived state, watch effects, two-way input
binding, per-item list rendering, conditional show/hide, event
modifiers, reactive class binding), with **v0.048** (CSS `@media`
queries + structured `<head>`/`<header>` extension) queued right
behind it -- see the "Planned" section of [`PROGRESS.md`](./PROGRESS.md)
and [`docs/DESIGN-NOTES.md`](./docs/DESIGN-NOTES.md) ("v0.044: JS
backend capability expansion -- reactive core parity with Vue 3" and
"v0.048: CSS media queries + `<head>` extension") for both designs.

## [0.0431] -- Emergency patch: unrouted-reference build warning

Out-of-band alpha maintenance release (numbered inside the v0.043 ->
v0.0438 gap, ahead of v0.044). Addresses one finding from an external
HTML-backend audit: `ROUTE_AWARE_ATTRS` covers only `href`/`src`, while
`Picture`/`PictureSource`'s `srcset`, `Video`'s `poster`, and `Form`'s
`action`/`formaction` are all emitted verbatim -- a route-shaped value
(`/assets/preview.png`) silently 404s once the site is deployed outside
the domain root.

**Detection only, not a fix yet.** `arklight.backend.html.render` now
warns at build time (`warnings.warn`, build still succeeds) whenever
one of those four attributes is given a route-shaped value, naming the
node/attribute/value and pointing at this patch series. Real
route-rewriting for these four attributes -- splitting/rejoining
`srcset`'s comma-separated list, and deciding whether `action`/
`formaction` should warn-and-skip instead of rewrite -- is tracked as a
follow-up, not shipped here.

Also confirmed **not** an issue on this branch: the audit's other
finding, an unrecognized `on_click` value silently no-opping, doesn't
reproduce -- `arklight/ir/validate.py` already hard-errors on any
`on_click` outside `KNOWN_BEHAVIORS`.

Three further findings (`<html lang="en">` hardcoded, `--ark-max-width`
unreachable from any prop, untyped `--ark-*` custom properties) were
open at the time but aren't build-time-detectable -- no prop existed
yet for a site author to trigger them. `--ark-max-width` was fixed by
the CSS backend refactor (`docs/CONTAINER-WIDTH-BUG.md`); `<html
lang="en">` was fixed above, in `[0.0434]`. Untyped `--ark-*` custom
properties remains open. These were tracked as "against the CSS/HTML
backend refactor in `docs/DESIGN-NOTES.md`" -- that section was never
written; the design doc that promise pointed to is now
`docs/HTML-BACKEND-REFACTOR.md` (HTML side) and
`docs/CSS-BACKEND-REFACTOR.md` (CSS side, already landed).

`0.043` -> `0.0431` version bump only; no page-facing API change;
existing builds produce byte-for-byte identical HTML/CSS/JS. See
[`PROGRESS.md`](./PROGRESS.md) ("v0.0431 -- Emergency patch") for the
full narrative.

## [0.043] -- Optional `<head>` metadata props + backend `postprocess` hook

Two independent, additive changes: five new optional `Page(...)` props
for common `<head>` metadata (filling part of the gap ahead of
v0.048's full `<head>`/`<header>` extension), and a new extension
point on `Backend` for adding a backend that depends on another
backend's already-rendered output, without editing that backend's
source.

### Added

- **`description`, `favicon`, `og_title`, `og_description`,
  `og_image`** (`arklight/backend/html/render.py`) -- optional
  `Page(...)` props rendering `<meta name="description">`, `<link
  rel="icon">`, and Open Graph `<meta property="og:*">` tags,
  following the same `page.root.props.get(...)` pattern `title`
  already used. All five are additive: a page that sets none of them
  renders byte-for-byte identically to before this change. Open Graph
  tags specifically are opt-in -- they only render once `description`
  or any `og_*` prop is supplied, so `title`-only pages don't get an
  unsolicited `og:title`. `favicon`/`og_image` resolve to a relative
  path the same way the stylesheet/script links already do.
- **`Backend.postprocess(output_files) -> output_files`**
  (`arklight/backend/base.py`, `arklight/compiler/pipeline.py`) --
  optional second pass, called once per backend (same order as
  `backends=[...]`) after every backend's `render()` has finished,
  over the *combined* `{path: contents}` dict from all of them.
  Default implementation is a no-op identity, so `HTMLBackend`,
  `CSSBackend`, and `JSBackend` needed no changes. Lets a new backend
  (analytics injection, build stamps, sitemap generation, ...) see and
  transform what other backends already produced without editing
  their source -- see `tests/test_pipeline_end_to_end.py` for a
  worked example.

## [0.042] -- Extra CSS features: custom classes, `arklight search`, `arklight --help`

Goal was cutting boilerplate/nesting in the styling API and closing
two long-open CLI discoverability gaps -- not new `@media`/`<head>`
capability (that's still v0.048). Full design context in
[`docs/DESIGN-NOTES.md`](./docs/DESIGN-NOTES.md) ("v0.042: extra CSS
features").

### Added

- **`Site.style(name, rules)`** (`arklight/api.py`) -- registers a
  real, named, reusable CSS class from a plain `{css-property: value}`
  dict. `class_name="name"` anywhere in the site then picks up the
  rules from the generated stylesheet, instead of repeating a
  `style={...}` dict on every node that needs it. Validated at
  registration time: `name` must be a safe, single CSS class
  identifier (letters/digits/hyphens/underscores, no leading digit);
  `rules` must be a non-empty dict of non-empty string
  properties/values. Deliberately **not** a raw CSS string -- same
  "no arbitrary CSS/HTML strings" boundary the rest of the project
  holds. Calling `site.style()` again with a name already registered
  overwrites it (last call wins).
- **`WebsiteIR.custom_styles`** (`arklight/ir/build.py`) -- threads
  `Site.custom_styles` through `build_website_ir()` (new optional
  keyword arg, backward-compatible) so `CSSBackend` can see what a
  site registered.
- **`CSSBackend`** (`arklight/backend/css/render.py`) now renders
  `ir.custom_styles` as real `.name { prop: value; }` blocks, sorted
  by class name (and by property within each class) for deterministic
  output, appended after the fixed `BASE_CSS` stylesheet so custom
  classes can override base rules by cascade order.
- **`arklight search <name>`** (`arklight/cli/search.py`,
  `arklight/cli/main.py`) -- read-only schema lookup against
  `arklight.ir.schema.SCHEMA`: required props, whether children are
  allowed, and whether the component is a `Bind(...)`-able target
  (i.e. `text_only_children`). Exact match (case-insensitive) wins
  outright; otherwise falls back to typo-tolerant "did you mean"
  suggestions via stdlib `difflib` + a camelCase-aware tokenizer --
  no external dependency, no new data format, no compiler-pipeline
  changes.
- **`arklight --help` / bare `arklight`** (`arklight/cli/main.py`) --
  `--help` already worked via argparse's built-in flag (every
  subcommand already carried a `help=` description), but running
  `arklight` with **no** subcommand used to print argparse's terser
  "error: the following arguments are required: command" instead of
  the same usage/help text. Subparsers are no longer `required=True`;
  a bare `arklight` now prints full help and exits `0`.

### Notes

- Custom classes and the fixed `BASE_CSS` utility classes (`.nav`,
  `.card`, `.stack`, ...) share the same `class_name=` mechanism --
  nothing new needed on the HTML backend side, since `class_name` was
  already a generic prop-to-`class`-attribute passthrough.
  `arklight search` does not currently search `BASE_CSS`'s utility
  class names, only component schema -- noted as a possible follow-up,
  not scoped for this pass.
- Test coverage: `tests/test_api_style.py` (new),
  `tests/test_css_backend.py` (extended),
  `tests/test_pipeline_end_to_end.py` (extended),
  `tests/test_search.py` (new), `tests/test_cli.py` (extended) --
  251 tests passing.

## [0.041] -- CLI, pipeline & JS runtime hardening + stateful JS vocabulary addenda

Four change sets that landed together and are released as one version.
Each keeps its own "Added"/"Notes" detail below; this line is only
here so the version-history reader doesn't have to guess why 0.041
covers four unrelated-sounding headings.

## [0.041] -- JS runtime error-handling hardening

Follow-up to "CLI & pipeline error-handling hardening" directly below
-- that pass covered the Python/CLI side; this covers the generated
client-side `arklight.js` runtime, which previously had **zero**
`try`/`catch` anywhere in it (confirmed by reading
`arklight/backend/js/render.py` and every behavior/action fragment
directly).

### Added

- **`arkNotify(message)`** (`arklight/backend/js/render.py`) -- a
  small, self-contained, inline-styled on-page notice, shipped only
  when a site actually uses a behavior or declares `State(...)` (same
  "only ship what's used" discipline as everything else in this
  runtime). Gives end users a visible signal when the runtime hits a
  case its closed vocabulary didn't anticipate, instead of a
  console-only error nobody but a developer would ever see. Wrapped in
  its own `try`/`catch` so the notifier itself can never throw.
- **`try`/`catch` around `initState()`'s `JSON.parse`** -- a malformed
  `data-ark-state` attribute previously threw inside the
  `DOMContentLoaded` handler and silently aborted `wireActions()` (and
  anything scheduled after it) for the entire page. Now caught,
  notified via `arkNotify`, and the page degrades to non-reactive
  instead of partially broken with no explanation.
- **`try`/`catch` around each element's setup *and* click dispatch**
  in both `wireActions()` and `wireBehaviors()` -- previously a single
  malformed `data-ark-action-args` attribute (or a behavior/action
  throwing at click time) could abort the `forEach` loop for every
  *other* element on the page, not just the one at fault. Each element
  now fails independently.
- **`.catch()` on the `copy` behavior's clipboard promise**
  (`arklight/backend/js/behaviors/copy.py`) -- `navigator.clipboard
  .writeText(...).then(...)` had no rejection handler, notable because
  `arklight build --open` opens sites as `file://` URLs by default,
  exactly the context where clipboard permissions are likeliest to be
  denied. A copy failure now notifies the user instead of silently
  doing nothing when clicked.
- `tests/test_js_error_handling.py` -- 8 new tests (212 total, all
  passing) covering `arkNotify` shipping conditions, the new guard
  structure in `initState`/`wireActions`/`wireBehaviors`, the clipboard
  `.catch()`, and re-confirming no `eval`/`new Function` was
  introduced.

### Notes

- No changes to `normalize.py`/`validate.py`/`build.py`/the IR --
  this is purely a `JSBackend` generation change, same class of
  change as every behavior/action addendum before it.
- Deliberately did not add error handling to `renderBindings()` or
  `highlightActiveNavLink()` -- neither has a plausible runtime
  failure mode given their inputs (`store.get(key)` returning
  `undefined` just renders as the text "undefined", not a throw; the
  nav-highlight loop only ever touches `<a>` elements' own `.href`).

## [0.041] -- CLI & pipeline error-handling hardening

A UX audit of the CLI's error handling (comparing it against how the
generated client-side JS runtime handles -- or doesn't handle --
failures) found that every subcommand only ever caught its *own*
typed error (`CompileError`/`PackError`/`PWAError`/`ScaffoldError`).
Anything outside those specific, anticipated failure modes propagated
as a raw Python traceback, contradicting the CLI's own stated design
goal ("error messages that point at exactly what went wrong... rather
than a raw traceback" -- `arklight/cli/main.py` module docstring).

### Added

- **Top-level catch-all in `main()`** (`arklight/cli/main.py`) --
  wraps subcommand dispatch. Anything not already handled by a
  subcommand's own typed `except` clause now prints a clear,
  clearly-labeled "outside ARKlight's known, handled failure modes"
  message (which command was running, the underlying exception type
  and message, an explicit note that this isn't a documented/
  recommended failure path) instead of a raw traceback, and returns
  exit code `1` like every other failure mode. Points at
  https://github.com/Rae-ARK/ARKlight/issues for reporting.
- **`OSError` guards around `build()`'s file-write loop and asset
  copy** (`arklight/compiler/pipeline.py`) -- previously neither step
  was guarded against filesystem failures (permissions, disk full, a
  network drive disconnecting mid-write), so a failure there escaped
  as a raw `OSError` instead of the `CompileError` every other pipeline
  stage raises. Both paths now report exactly how much of the build
  completed before the failure (e.g. "3/6 file(s) written before the
  failure"), so a partially-written output directory is never
  mistaken for a clean one.
- **Runtime warning for `--passphrase` on the command line**
  (`_cmd_pack`) -- previously this risk (shell history / process-
  listing exposure) was only documented in `--help` text, easy to
  never see. Now prints at the moment the flag is actually used.

### Fixed

- **Removed a duplicate `_cmd_pwa` definition** in `arklight/cli/main.py`
  -- found while adding the catch-all above. Two identical copies of
  the function existed; the second silently shadowed the first at
  import time. Harmless today since the bodies matched exactly, but
  exactly the kind of latent bug the new catch-all exists to guard
  against if they'd ever drifted apart.
- **`pyproject.toml` / `arklight/__init__.py` version mismatch**
  (`0.1.0` vs. `0.038`) -- a second recurrence of the same class of
  drift already fixed once during the "v0.003 addendum" pass (see
  below); `pyproject.toml` now correctly reads `0.038`. This is a
  distinct issue from the previously-documented `arklight --version`
  vs. `pip show arklight` mismatch, which is about the *published*
  PyPI package's own reported version, not this repo's internal
  build-metadata sync.

### Notes

- Scope was deliberately kept to the CLI's own dispatch/build path --
  the generated client-side `arklight.js` runtime has an analogous
  gap (no `try`/`catch` anywhere in `arklight/backend/js/render.py`'s
  output, an unhandled clipboard-promise rejection in the `copy`
  behavior, one malformed `data-ark-action-args` attribute able to
  abort `wireActions()` for every other element on the page) --
  tracked as separate, follow-up work, not addressed in this pass.
  **Update:** this follow-up is now done -- see "JS runtime
  error-handling hardening" above.

## [0.041] -- Stateful JS vocabulary addendum II

Full writeup in `docs/DESIGN-NOTES.md` ("v0.0035: stateful-JS
vocabulary addendum II"). Second growth pass on `ACTION_REGISTRY`,
same "additive data" discipline as addendum I directly below -- this
batch is the first to assume a **list-valued** `State(...)` rather
than a scalar one.

### Added

- `Action.append(name, value)` -- appends `value` to a list-valued
  `State(...)`. New `arklight/backend/js/actions/append.py` fragment
  and `ACTION_REGISTRY["append"]` entry.
- `Action.remove(name, index)` -- removes the element at `index` from
  a list-valued `State(...)`. Index-based on purpose (unambiguous,
  unlike a value-based removal, which would need an equality rule for
  objects). New `arklight/backend/js/actions/remove.py` fragment and
  `ACTION_REGISTRY["remove"]` entry.
- `tests/test_stateful_js_vocabulary_addendum_2.py` -- 12 new tests
  (182 total).

### Notes

- No changes to `renderBindings`/`Bind` were needed: `el.textContent =
  store.get(key)` already renders a list via JS's own
  `Array.prototype.toString()` (comma-joined elements) -- enough for a
  simple tag list or count display. Per-item templating (a real
  `<li>` per item, with per-item remove buttons wired individually) is
  materially bigger scope -- would need the compiler to emit a
  template per list item and re-render *that*, not just re-run
  `renderBindings` -- and is deliberately left for a future version.

### Deliberately deferred to a future version

Still not an exhaustive vocabulary pass -- see `docs/DESIGN-NOTES.md`:

- Per-item list rendering/templating (see note above).
- Derived/computed state.
- `Action.set_from_input` / binding state to `input`/`change` events.
- Debounced/throttled actions.

## [0.041] -- Stateful JS vocabulary addendum I

Full writeup in `docs/DESIGN-NOTES.md` ("v0.0035: stateful-JS
vocabulary addendum"). Grows `ACTION_REGISTRY` (added in v0.0035) with
the two most commonly needed actions real usage hits right away,
following the same "additive data, not a compiler change" discipline
the v0.0035 registry refactor was built for.

### Added

- `Action.decrement(name, delta=1)` -- the `-1` counterpart to
  `Action.increment`. New `arklight/backend/js/actions/decrement.py`
  fragment and `ACTION_REGISTRY["decrement"]` entry.
- `Action.reset(name)` -- resets a state key to the value it was
  declared with in `State(...)`, without hardcoding that value again
  at the call site. Backed by a new `reset(key)` method on the
  reactive core's `createState` closure (reads its own captured
  `initial` snapshot), plus a new
  `arklight/backend/js/actions/reset.py` fragment and
  `ACTION_REGISTRY["reset"]` entry.
- `tests/test_stateful_js_vocabulary_addendum.py` -- 10 new tests
  (170 total).

### Deliberately deferred to a future version

Not an exhaustive vocabulary pass -- see `docs/DESIGN-NOTES.md` for
the reasoning behind leaving these out of this addendum:

- List actions (`Action.append` / `Action.remove`) -- addressed in
  addendum II directly above.
- Derived/computed state.
- `Action.set_from_input` / binding state to `input`/`change` events.
- Debounced/throttled actions.

## [0.037] -- Sealed ARK Bundles

Full writeup in `docs/DESIGN-NOTES.md` ("v0.037: sealed bundles").

### Added

- `arklight.packer.seal` -- new stdlib-only (`hmac`/`hashlib`/
  `secrets`) sealing primitive: `seal(payload, *, passphrase=None)` /
  `unseal(blob, *, passphrase=None)`, an HMAC-SHA256 counter-mode
  stream cipher with an HMAC-SHA256 authentication tag
  (encrypt-then-MAC). `SealError` on missing/wrong passphrase or a
  failed integrity check.
- `arklight pack` now **seals the archive half by default**. Without
  `--passphrase`, a random embedded key travels with the bundle (blocks
  generic archive tools, not a secret from ARKlight itself -- see
  DESIGN-NOTES for the honest framing); with `--passphrase`, the key is
  derived via PBKDF2-HMAC-SHA256 and never stored, for real
  confidentiality.
- `--plain` flag on `arklight pack` -- opts back into the original v1
  plain-ZIP-tail behavior.
- `arklight unpack <bundle.ark> -o OUTPUT_DIR [--passphrase ...]` --
  new CLI subcommand and `arklight.packer.bundle.unpack()` Python API,
  reversing `pack()`. Auto-detects sealed vs. plain bundles.
- `arklight.packer.bundle.UnpackResult` -- `output_dir`,
  `extracted_paths`, `was_sealed`.
- `PackResult` gained `sealed` and `passphrase_protected` fields.
- `tests/test_seal.py` (new) and expanded `tests/test_pack.py` --
  round-trips for both key modes, tamper/wrong-passphrase rejection,
  `--plain` opt-out, CLI wiring for `pack`/`unpack`.

### Changed

- **`assets/` (and any other non-html/css/js file) is now carried into
  the archive**, closing the v1 scope gap `docs/DESIGN-NOTES.md`
  explicitly flagged as deferred. `PackResult.skipped_paths` is always
  empty now; kept on the dataclass for backward compatibility rather
  than removed.
- The archive is now built entirely in memory (`io.BytesIO`) before a
  single `write_bytes()` call, rather than writing prefix bytes to disk
  and appending to that same file handle -- needed so the sealing step
  has a complete in-memory ZIP blob to encrypt; produces byte-identical
  plain bundles to before.

## [0.036] -- ARK Bundle spec v1

Full writeup in `docs/DESIGN-NOTES.md` ("v0.036: ARK Bundle spec v1").

### Added

- `arklight pack <build-dir> -o site.ark` -- a new CLI subcommand
  (`arklight/packer/bundle.py`) that packages an existing
  `arklight build` output directory into a single `.ark` file: an
  HTML/ZIP polyglot. A fully self-contained, inlined rendering of the
  entry page is prepended before a standard ZIP archive of the
  original build output, so the same bytes are both a directly-
  renderable HTML document (double-click / open in a browser, no
  unzip step, no temp files, no local server) and a valid ZIP archive
  (any archive tool extracts the original build output untouched).
- `arklight.packer.bundle.pack(build_dir, output_path) -> PackResult`
  -- the underlying Python API, importable independently of the CLI.
  `PackResult` exposes `packed_paths` and `skipped_paths`.
- `arklight.packer.bundle.PackError` -- raised with a specific message
  when `build_dir` isn't an `arklight build` output directory (missing
  `index.html`/`styles.css`/`arklight.js`, or missing the expected
  `<link>`/`<script src>` tags to inline).

### Scope (v1)

- Only `.html`/`.css`/`.js` files are inlined/packed. Any other file in
  the build directory -- most notably an `assets/` folder with images,
  audio, video, or anything else -- is intentionally left out of the
  bundle and reported as skipped (`PackResult.skipped_paths`, printed
  by the CLI) rather than silently dropped. Asset carry-over is planned
  for a follow-up version, not included here.
- Packaging only, over already-built output: no changes to
  `normalize.py`/`validate.py`/`build.py`/the `Backend` interface/the
  IR. `arklight/packer/` only reads already-written build files and
  never imports the parser/ir/backend internals.
- stdlib `zipfile` turned out to handle writing entries after an
  arbitrary byte prefix correctly (`zipfile.ZipFile(handle, mode="a")`
  on a handle that already has the HTML prefix written to it computes
  every offset from the handle's current position) -- no manual ZIP
  header patching was needed, simplifying the original design's
  assumption on this point.

## [0.0035] -- Stateful JS

This entry documents what actually shipped in the commits titled "v0.0035
is done" -- it was missing from this file even though
`pyproject.toml`/`arklight/__init__.py` already read `0.0035` and the
README's "Status" section already described it. See
`docs/DESIGN-NOTES.md` ("v0.0035: stateful JS -- capability, not
vocabulary") for the full design rationale.

### Added

- `arklight.ir.schema.BEHAVIOR_REGISTRY: dict[str, BehaviorSpec]`,
  replacing the flat `KNOWN_BEHAVIORS` frozenset from v0.003 as the
  source of truth (`KNOWN_BEHAVIORS` is now a derived view over it, so
  Validation's existing check didn't need to change shape).
- `arklight/backend/js/behaviors/` -- `JSBackend`'s runtime is now
  assembled from small per-behavior JS fragments (`toggle.py`,
  `scroll_to.py`, `copy.py`, `dismiss.py`) instead of one hand-written
  string; only the fragments a given site's IR actually references are
  emitted.
- `arklight.ir.schema.ACTION_REGISTRY` and `arklight/backend/js/actions/`
  (`set.py`, `increment.py`, `toggle_bool.py`) -- the same registry
  pattern applied to a new closed *action* vocabulary for state
  mutation.
- New public API in `arklight.api`: `State(name, initial)` (page-scoped
  reactive state, stored on the IR's `Page` node), `Bind(name)`
  (references a declared `State(...)` from anywhere a literal prop
  value is accepted, e.g. `Text(Bind("count"))`), and
  `Action.set(name, value)` / `Action.increment(name, delta=1)` /
  `Action.toggle_bool(name)` (structured `ActionRef` objects for
  `on_click=` -- never an arbitrary JS/Python string).
- Validation: every `Bind(...)`/`Action.*(...)` must reference a
  `State(...)` actually declared on that page, or the build fails at
  compile time with a specific message.
- `JSBackend`: pages that declare `state` get one additional small
  fixed reactive core (a `createState` closure, a `data-ark-bind`
  re-render wiring pass, and an action dispatcher walking
  `ACTION_REGISTRY`) appended to the runtime. Pages with no
  `State(...)` get none of this. Still no `eval`, no `new Function`, no
  string ever executed as code.
- `tests/test_stateful_js.py` -- 14 new tests (130 total).

### Notes

- Explicit scope boundary honored: capability, not vocabulary -- no
  new named behaviors were added in this milestone, only the registry
  refactor plus the `State`/`Bind`/`Action` primitives.

## [0.003] -- JavaScript helpers (+ two vocabulary extension addenda)

### Addendum 2: even more vocabulary

Still not a version bump -- this stays v0.003, same as addendum 1
below. Extends the same `arklight.ir.schema.SCHEMA` dict with the
"long tail" of standard, production-grade static-site HTML that
addendum 1 left out: numbered/description lists, art-directed
responsive images, native form/progress widgets, a zero-JS dialog,
the rest of HTML's text-level semantics (bidi + ruby included), table
column grouping, video captions, image maps, iframes, and a
`<noscript>` fallback. Same guarantee as before: zero changes to
normalize.py, validate.py, or build.py -- every addition below is
data only, in `SCHEMA` (+ `TAG_MAP`/`PASSTHROUGH_ATTRS`/`VOID_TAGS` in
the HTML backend, + default CSS rules in the CSS backend).

#### Added

- **33 new built-in components:**
  - Lists: `OrderedList` (`<ol>`, with `start`/`reversed`) --
    genuinely missing before this: v0.003's first pass could only ever
    produce `<ul>` via `List`, with no numbered list at all.
    `DescriptionList`/`DescriptionTerm`/`DescriptionDetails`
    (`<dl>`/`<dt>`/`<dd>`) for key/value and glossary content (specs,
    FAQs, metadata blocks) a `<ul>` can't express semantically.
  - Responsive images: `Picture`/`PictureSource` (`<picture>` +
    `srcset`/`sizes`/`media` art-direction) -- the image half of
    "responsive design", which addendum 1's CSS-only intrinsic-layout
    utilities didn't touch at all. `PictureSource` is a distinct type
    from the existing `Source` (used by `Video`/`Audio`, which
    requires `src`) since a `<picture>`'s `<source>` takes `srcset`
    instead. Also added `loading`/`decoding` as generic passthrough
    attributes, so `Image(..., loading="lazy")` gets native
    lazy-loading with zero JS.
  - Native, zero-JS widgets: `Progress`, `Meter`, `Datalist`, `Output`
    -- progress bars, gauges, input autocomplete, and calculation
    output are all built into the browser already.
  - `Dialog` (`<dialog open>`): renders open with zero JS, and
    `Form(method="dialog")` closes it natively (a real browser
    behavior, not a script) -- a static confirmation/FAQ modal needs
    no JS at all with this pairing. Opening it programmatically from
    an arbitrary trigger would need JS and stays out of scope, same as
    the rest of v0.003's "no arbitrary JS" boundary.
  - More text-level semantics: `Kbd`, `Samp`, `Var`, `Data`
    (`required_props=("value",)`), `Ins`, `Del`, `Q`, `Dfn`,
    `Address`, `Wbr`, plus bidirectional-text isolation/override
    (`Bdi`, `Bdo`) for real production i18n needs (mixed LTR/RTL
    content), and ruby annotations (`Ruby`/`Rt`/`Rp`) for East-Asian
    typography -- a genuine gap nothing above could express at all.
  - Table extras: `ColGroup`/`Col` for column-level styling without
    repeating a rule on every cell in the column.
  - Media: `Track` (`required_props=("src",)`) for caption/subtitle
    tracks -- accessibility, not decoration.
  - Image maps: `Map` (`required_props=("name",)`) / `Area` for
    multiple clickable regions on one image.
  - Embeds: `IFrame` (`required_props=("src",)`, no children) --
    arguably the single most common piece of "extra functionality" a
    static site reaches for that plain markup alone can't provide
    (embedding a map, a video host's player, or another site's
    widget), while staying pure declarative HTML.
  - `NoScript`: fallback content for the visitor with JavaScript
    disabled, pairing naturally with ARKlight's own small JS runtime
    -- anything gated behind `toggle`/`copy`/`dismiss` can have a
    `NoScript` sibling.
- New passthrough HTML attributes: `start`, `reversed` (`<ol>`);
  `srcset`, `sizes`, `media`, `loading`, `decoding` (responsive
  images); `low`, `high`, `optimum` (`<meter>`); `dir` (bidi text);
  `span` (`<colgroup>`/`<col>`); `kind`, `srclang`, `default`
  (`<track>`); `shape`, `coords` (`<area>`); `allow`,
  `allowfullscreen`, `sandbox`, `referrerpolicy` (`<iframe>`).
- Four new void tags in the HTML backend (`wbr`, `col`, `area`,
  `track`), alongside the existing `img`/`hr`/`br`/`input`/`source`.
- Default styling for every new tag in the generated stylesheet
  (`ol`/`dl`/`dt`/`dd`, `progress`/`meter`, `dialog`, `kbd`/`samp`/
  `var`, `dfn`, `address`, `ruby`/`rt`, `iframe`, `map`/`area`).
- 22 new tests (109 total) in `tests/test_vocabulary_addendum_2.py`
  covering every new component, its required props, and its rendered
  HTML.

#### Notes

- `DescriptionDetails`, `Ins`, `Del`, `Ruby`, and `Address` are real
  containers (like `TableCell`/`Blockquote`), not text-only -- a
  definition, an edit, a ruby base, or an address block routinely
  holds a `Link`/`Strong`/`Span`, not just a bare string. As with
  `Blockquote(Text("..."))` elsewhere, wrap plain text explicitly
  (e.g. `Ruby(Span("漢"), Rt("kan"))`) rather than relying on the
  auto-wrap, since a bare string in a non-text-only container becomes
  a block-level `Text`/`<p>` node, which isn't what an inline element
  like `<ruby>` wants.
- `DescriptionTerm`, `Progress`, `Meter`, `Output`, `Kbd`, `Samp`,
  `Var`, `Data`, `Q`, `Dfn`, `Bdi`, `Bdo`, `Rt`, `Rp` stay text-only,
  matching how `Item`/`Caption`/`Label` already work.
- Considered and deliberately left out: `<canvas>`/`<template>` (both
  are meaningless without JS driving them, which is out of scope for
  v0.003's closed-behavior model); a brand-new `<search>` landmark
  (too new/unsettled for a "production-grade" vocabulary claim); and
  `<object>`/`<embed>` (redundant with the new `IFrame` for the static
  use cases this project targets, with worse fallback-content
  ergonomics).

### Addendum 1: vocabulary extension

Not a version bump and not a new pipeline stage -- this stays v0.003.
Every addition below is data, not new compiler logic:
`arklight.ir.schema.SCHEMA` is the single source of truth every stage
(normalize/validate/build/backends) already reads from, so extending
it is how this addendum adds ~46 new component types without touching
normalize.py, validate.py, or build.py at all.

#### Added

- **46 new built-in components**, grouped the same way HTML groups
  them:
  - Semantic layout: `Header`, `Footer`, `Main`, `Nav`, `Section`,
    `Article`, `Aside`, `Figure`, `FigCaption`, `Details`, `Summary`
    (the last two are a *native* browser disclosure widget -- an
    accordion/expand-collapse that needs zero JS, not even the
    `toggle` behavior).
  - Text-level semantics: `Strong`, `Em`, `Small`, `Mark`, `Code`,
    `Cite`, `Abbr`, `Sub`, `Sup`, `Span`, `Time`, `HorizontalRule`,
    `LineBreak`, `Pre`, `Blockquote`.
  - Forms: `Form`, `Input`, `Textarea`, `Select`, `Option`,
    `OptGroup`, `Label`, `FieldSet`, `Legend`.
  - Tables: `Table`, `TableHead`, `TableBody`, `TableFoot`,
    `TableRow`, `TableHeaderCell`, `TableCell`, `Caption`.
  - Media: `Video`, `Audio`, `Source`.
- **Two new closed JS behaviors**, alongside `toggle`/`scroll-to`:
  `copy` (clipboard copy with button-text feedback) and `dismiss`
  (one-way hide, e.g. closing a banner/alert for good). Both are
  stateless in the same sense the original two are -- a pure reaction
  to one click, nothing retained in JS across events.
- **A generic `aria_*` prop convention** (`aria_label`, `aria_hidden`,
  `aria_expanded`, ...) mapping straight to the real `aria-*`
  attribute, plus `role`/`tabindex` and a `for_`/`html_for` alias for
  `<label for>` (since `for` is a Python keyword).
- **Intrinsic responsive layout utility classes** in the default
  stylesheet -- `.stack`, `.cluster`, `.sidebar`, `.switcher`, `.grid`,
  `.center`, `.reel`, `.fluid-heading` -- built entirely from flexbox/
  grid sizing keywords (`minmax`, `auto-fit`, `clamp`, `flex-basis`
  math), with **no `@media`/`@container` query anywhere**, addressing
  the structural ceiling recorded in `docs/DESIGN-NOTES.md`: `Page`
  still has no `<head>` hook for a breakpoint-based rule, so
  responsiveness has to come from the browser reflowing content from
  available width alone.
- Default styling for every new tag (forms, tables, `<details>`,
  `<code>`/`<pre>`, media, etc.) in the generated stylesheet, plus an
  `.alert` utility that pairs with the new `dismiss` behavior.
- 34 new tests (87 total) covering the new components, behaviors, and
  CSS utilities across `test_html_backend.py`, `test_css_backend.py`,
  `test_js_backend.py`, and `test_validate.py`.

#### Notes

- `TableHeaderCell`/`TableCell` are real containers (like `Container`),
  not text-only -- a real table cell routinely holds a `Link` or
  `Strong`, not just plain text. This means a bare string child gets
  wrapped in a `Text` node the same way it would inside a `Container`
  (consistent with existing normalization behavior, not new).
  `FigCaption`, `Summary`, `Legend`, `Caption`, `Label`, `Option`,
  `Textarea` stay text-only, matching how `Heading`/`Text`/`Button`
  already work.
- `pyproject.toml`'s version was still `0.001` while
  `arklight/__init__.py` said `0.003` -- both now correctly read
  `0.003`.

### Added

- `JSBackend` (`arklight.backend.js`) generating a static
  `arklight.js`: a fixed, closed vocabulary of client-side behaviors
  (`toggle`, `scroll-to`) plus automatic current-page nav-link
  highlighting. No arbitrary JavaScript is ever accepted from user
  code.
- `on_click` / `behavior_target` / `toggle_class` props on any
  component, validated against `arklight.ir.schema.KNOWN_BEHAVIORS` at
  build time and rendered as `data-ark-*` attributes.
- `default_backends()` now returns `[HTMLBackend(), CSSBackend(),
  JSBackend()]`.
- `.nav a.is-active` and `.hidden` added to the default stylesheet.
- `docs/DESIGN-NOTES.md`: styling ceiling, audience positioning,
  Svelte-comparison, and Mitosis-reframe (state/event semantics as the
  real prerequisite for v0.100) writeups.
- 9 new tests (66 total): JS backend content, behavior validation, and
  HTML attribute/script-tag rendering. Also verified interactively with
  Playwright against a real headless browser (nav highlighting + toggle
  click), not just by inspecting generated HTML.
- Example site: home page gained a working "Show details" toggle using
  `on_click="toggle"`, with no hand-written JavaScript.

### Changed

- CLI/package version bumped to 0.003.

## [0.002] -- CSS

### Added

- `CSSBackend` (`arklight.backend.css`) generating a default
  `styles.css` (typography, spacing, buttons, links, `.nav`/`.card`/
  `.muted` utility classes) -- every generated site is styled with zero
  CSS written by hand.
- `arklight.compiler.pipeline.build()` now runs a list of backends by
  default (`default_backends() -> [HTMLBackend(), CSSBackend()]`) and
  merges their output; customizable via `build(..., backends=[...])`.
- `class_name` and `style` (dict) props on any component, rendered as
  the HTML `class` attribute and an inline `style` attribute
  respectively.
- CLI: `arklight build` now opens the built site in the default
  browser automatically (`--open`, the default) or can be disabled
  (`--no-open`).
- 15 new tests (57 total): CSS backend output, relative-link
  resolution, `class_name`/`style` rendering, stylesheet link
  correctness, CLI browser-open behavior.

### Fixed

- **Internal links (`Link(..., href="/about")`) now compile to real
  relative file paths** instead of root-absolute routes. Previously,
  opening `dist/index.html` directly (the normal "first setup"
  experience) sent `href="/about"` to the filesystem root instead of
  `dist/about.html` -- pages appeared linked in the Python source but
  the links didn't actually work once rendered. The HTML backend is
  now route-aware and rewrites internal hrefs based on each page's
  actual output location; external URLs, fragments, and `mailto:`/
  `tel:` links are left untouched.
- The bundled example site now actually links Home and About to each
  other (via a shared `nav()` helper function) and uses the new
  styling props, instead of looking unstyled.

## [0.001] -- Python → HTML

First working compiler pipeline: a Python site file compiles all the
way to static HTML files, matching the full pipeline described in
ARCHITECTURE.md.

### Added

- `ARKNode` ARK AST node type and `node()` component factory.
- Public API: `Site`, `Page`, `Heading`, `Text`, `Button`, `Container`,
  `Link`, `Image`, `List`, `Item`.
- Static Python AST discovery stage (`arklight.parser.discover`) using
  the stdlib `ast` module.
- Site-file loader (`arklight.parser.loader`) that executes a site file
  in isolation and returns the live `Site` object.
- Normalization stage: flattens nested list children, drops
  `None`/`False`, wraps bare strings as `Text` nodes where appropriate.
- Validation stage: schema-checked component types, required props,
  and text-only nesting rules, with precise error messages.
- Shared component schema (`arklight.ir.schema`) used by both
  normalization and validation.
- Website IR (`IRNode` / `IRPage` / `WebsiteIR`), kept structurally
  distinct from the ARK AST.
- Backend interface (`Backend.render(ir) -> {path: contents}`).
- HTML backend: component-to-tag mapping, heading levels, prop-to-HTML
  attribute mapping (including a `data-*` fallback for unknown props),
  HTML escaping, and route-to-file-path mapping.
- Compiler pipeline (`compile_site_file`, `build`) unifying every
  stage behind a single `CompileError` for any failure.
- CLI: `arklight build <entry.py> [-o OUTPUT_DIR]`, `arklight --version`.
- Example site (`examples/hello_site/site.py`) with two pages.
- 42 tests covering every stage in isolation and end-to-end.
- Packaging via `pyproject.toml` (`pip install -e .`).

### Fixed

- Normalization no longer double-wraps strings inside text-only
  components (e.g. `Heading("hi")` no longer became an invalid
  `Heading(Text("hi"))`).
- Errors raised inside a page function (e.g. referencing an undefined
  component) are now caught by the pipeline and surfaced as
  `CompileError`, not left to propagate as raw exceptions.
