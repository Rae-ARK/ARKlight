# Changelog

All notable changes to ARKlight are tracked here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/); versions
follow the milestone scheme from ARCHITECTURE.md rather than strict
SemVer.

## [Unreleased] -- `head_meta.py` favicon/og_image root-relative path bugfix

**Bug:** a root-relative `favicon`/`og_image` value (leading `/`, e.g.
`/assets/favicon.ico`) was passed straight into
`_relative_asset_path`, which resolves via `posixpath.relpath()`.
With one argument absolute, `relpath` resolves it against the build
process's `os.getcwd()` instead of the site's route structure --
every page ended up with the wrong number of `../` segments (matching
the *build directory's* path depth, not the page's route depth)
instead of the correct site-relative path.

`routing.py`'s `_resolve_src_ref` already hit and fixed this exact
failure mode for `src`-shaped attributes (Image/Source/Track/IFrame/
`poster`/`srcset`) by stripping a leading `/` before calling
`_relative_asset_path` -- see `HTML-BACKEND-REFACTOR.md` / the
`UNROUTED_REFERENCE_ATTRS` fix in `[0.0491]` below. That fix never
made it to `head_meta.py`'s `favicon`/`og_image` handling, which
predates it.

**Fix (`arklight/backend/html/head_meta.py`):** both `favicon` and
`og_image` now go through `.lstrip("/")` before `_relative_asset_path`,
matching `_resolve_src_ref`'s existing treatment. A root-relative path
now resolves identically to the same path written without the leading
`/`, regardless of the directory `arklight build` is invoked from.

**Tests (`tests/test_html_head_meta.py`):** two new regression tests
assert a leading-`/` favicon/og_image renders identically to the same
path with no leading `/`, from a nested route.

## [0.0501] -- Combined refactor, Stage 11 of 16 (HTMX integration, `htmx-5`: audit and remove remaining hand-rolled plumbing)

**Scope:** `docs/Backends/REFACTOR-INDEX.md` row 10 / `docs/Backends/
HTMX-INTEGRATION.md` "Implementation ladder" Stage 4. Audit what's
left in `arklight.js` after `htmx-1` through `htmx-4` and remove
anything that duplicates HTMX. The audit's actual finding cuts the
other way from what the stage description implies: the plumbing worth
removing turned out to be a piece of *HTMX's own* attribute
processing, not anything hand-rolled.

**The finding:** `htmx-1`'s `hx-on:click="arkRunBehavior('<name>',
this)"` (the mechanism every named behavior -- `toggle`, `scroll-to`,
`copy`, `dismiss` -- used to wire a click) turns out to route through
HTMX's own `hx-on:*` attribute-processing internals, which build a
function from the attribute's *string value* with the `Function`
constructor (`new Function("event", attributeValue)`) before calling
it. This is an eval-equivalent operation, gated only by
`htmx.config.allowEval` (`true` by default in the vendored release).
Every named-behavior click on every ARKlight site was, through
`htmx-4`, routing through that path -- directly contradicting this
project's own stated invariant (`arklight/backend/js/render.py`'s
module docstring: "there is no eval, no new Function, no string ever
executed as code"). `arkRunBehavior`'s own body was always a small,
fixed, statically-readable function; the eval-equivalent step was
HTMX's attribute-processing machinery *getting there*, not anything
ARKlight wrote.

**HTML backend (`attrs.py`):**

- A named behavior now compiles to `data-ark-on-click="behavior:<name>"`,
  reverting `htmx-1`'s `hx-on:click` shape. Matched-pair with the
  `"action:<name>"` shape `on_click=Action.*(...)` already emitted --
  both are now read by the same delegated listener on the JS side.
  `behavior_target`/`toggle_class` (`data-ark-target`/
  `data-ark-toggle-class`) are unaffected.

**JS backend (`render.py` + `runtime/`):**

- `runtime/dispatch.py`'s `wireActionInterceptor` is renamed
  `wireClickInterceptor` and gains a `"behavior:"` branch alongside
  its existing `"action:"` one -- still exactly one
  `document.addEventListener("click", ...)` registration for the
  whole page, branching on the clicked element's
  `data-ark-on-click` prefix. Each branch has its own `try`/`catch`.
- `arkBehaviors`/`arkRunBehavior` (previously attached to `window` so
  HTMX's attribute evaluation could reach them) are gone. The closed
  behavior-dispatch object is now a plain local `behaviors` var, read
  by closure the same way `actions` already was.
- `STATE_CORE_JS` is reactive-state machinery only now
  (`createState`/`renderBindings`/`renderClassBindings`/`initState`)
  -- the click interceptor is pulled out of that bundle entirely,
  since it's no longer tied to `has_state` (a behavior-only page has
  no `State(...)` at all, but still needs the interceptor).
  `_build_runtime_js` ships `actions`/`behaviors`/
  `wireClickInterceptor` whenever a page uses an `Action.*(...)` or a
  named behavior, independent of `has_state`.
- `needs_htmx` drops the "or a named behavior is used" condition --
  named behaviors no longer touch any `hx-*` attribute, so a
  behavior-only page (the common "toggle a menu, nothing else" case)
  now ships no HTMX at all. `has_state` and `ir.app_shell` are
  unaffected and remain the only two conditions.
- Defense-in-depth, not required for correctness given the above:
  whenever HTMX does ship, `arklight.js` sets `htmx.config.allowEval =
  false` right after loading it, closing the other vendored-HTMX code
  paths that construct a function from a string
  (`hx-vals`/`hx-vars`, bracket-syntax `hx-trigger` event filters) --
  paths ARKlight's compiler never emits into, but which this stops
  relying on "never emits" alone to guarantee.
- A pure-display state page (`Bind(...)` only, no `Action.*(...)`, no
  named behavior) previously always shipped an unused
  `var actions = {};` alongside its reactive core. It no longer does
  -- a further "ship only what's used" tightening this audit turned up
  as a side effect, not the goal.

**Tests:** new `tests/test_htmx_5.py` covering the renamed
interceptor's two branches, the `data-ark-on-click="behavior:..."`
HTML shape, the dropped `needs_htmx` condition (a behavior-only page
now ships no HTMX), `htmx.config.allowEval = false` being present
whenever HTMX does ship, and -- the actual regression this stage
exists to prevent -- that no ARKlight-compiled HTML output ever
contains `hx-on:*`/`hx-vals`/`hx-vars` for any behavior/action/state
combination. The rename (`wireActionInterceptor` ->
`wireClickInterceptor`, `ACTION_INTERCEPTOR_JS` ->
`CLICK_INTERCEPTOR_JS`, `arkRunBehavior`/`arkBehaviors` removed)
updates literal-string assertions in `tests/test_htmx_3.py`,
`tests/test_htmx_4.py`, `tests/test_html_attrs.py`,
`tests/test_html_backend.py`, `tests/test_js_backend.py`,
`tests/test_js_error_handling.py`, `tests/test_class_binding.py`,
`tests/test_event_modifiers.py`,
`tests/test_stateful_js_vocabulary_addendum.py`, and
`tests/test_refactor_0.py`. Two of those updates reflect the actual
behavior changes above, not just the rename: `test_refactor_0.py`'s
`STATE_CORE_JS`-ordering test now checks four reactive-core pieces,
not five (the interceptor is no longer part of that bundle), and
`test_stateful_js_vocabulary_addendum.py`'s pure-display-state test
now asserts `actions`/`wireClickInterceptor` ship *neither*, not that
`actions` ships empty.

## [0.0500] -- Combined refactor, Stage 10 of 16 (HTMX integration, `htmx-4`: app-shell navigation)

**Scope:** `docs/Backends/REFACTOR-INDEX.md` row 9 / `docs/Backends/
JS-BACKEND-REFACTOR-PLAN.md` "The app-illusion problem, stated
precisely." App-shell navigation for sites wrapped in a packaging
backend (Android/KaiOS/Desktop), where a full document reload on every
internal link defeats the point of shipping ARKlight's output as an
installable app.

**`Site(app_shell=True)`** (naming placeholder kept -- no better name
turned up) is a new, single feature flag. Defaults to `False`, and
every existing site's output -- HTML and JS both -- is byte-for-byte
unaffected unless a site opts in. Threaded through the same
`Site` -> `build_website_ir` -> `WebsiteIR` -> backends plumbing every
other `Site(...)` flag already uses.

**HTML backend (`page_render.py`):**

- `<body hx-boost="true">` when `app_shell=True` -- htmx's own
  mechanism for turning same-origin link clicks into an in-place AJAX
  swap instead of a full document reload.
- New `shell_persistent=True` prop (any component) compiles to
  `hx-preserve="true"` -- htmx's mechanism for keeping an element
  untouched across a boosted swap, matched by `id` between the old and
  newly-fetched page. Validation now requires a non-empty `id`
  alongside `shell_persistent=True`, since a `hx-preserve` with no
  stable `id` for htmx to match on is silently useless. This is the
  actual fix for the "shell-persistent regions (nav/header) survive a
  boosted swap" half of the design doc.
- A state page's `data-ark-state` blob moves off `<body>` and into a
  hidden `<div id="ark-state" data-ark-state="...">` marker when
  `app_shell=True`. Verified directly against htmx's own docs: an
  `hx-boost`ed swap replaces `<body>`'s *innerHTML* only, never the
  `<body>` tag's own attributes -- so a `data-ark-state` attribute
  placed directly on `<body>` (the existing, non-app_shell shape,
  unchanged) would freeze at whatever page first loaded and never
  update across a boosted navigation. The marker, being part of the
  swapped content, updates correctly.

**JS backend (`render.py` + `runtime/`):**

- `needs_htmx` now also ships HTMX for `ir.app_shell` alone, not just
  "a named behavior or `State(...)` is used somewhere on the site."
  Closes a real gap the audit surfaced: `arklight.js` is one shared
  file across the whole site, so a plain nav-only page in an
  `app_shell` site with no behaviors or state used *anywhere* would
  previously have shipped without HTMX loaded at all, silently
  falling back to a real document navigation on every click.
- Page init (`highlightActiveNavLink()`/`initState()`/
  `renderBindings()`/`renderClassBindings()`) is extracted into a
  re-callable `arkInitPage()`. Closes a second gap: `DOMContentLoaded`
  only ever fires once per real document load, and a boosted
  navigation doesn't refire it, so nothing before this stage re-ran
  nav highlighting or state hydration after navigating to a
  *different* page via a boosted link. `arkInitPage()` is wired to
  `DOMContentLoaded` unconditionally (unchanged initial-load behavior)
  and, only for `app_shell` sites, to htmx's own `"htmx:afterSettle"`
  event too.
- `runtime/dispatch.py`'s `wireActionInterceptor(store)` becomes
  `wireActionInterceptor(getStore)` -- a zero-argument getter instead
  of a fixed value. The interceptor's one `document`-level `click`
  listener is still registered exactly once, at `DOMContentLoaded`,
  and must never be re-registered on a later boosted swap (`document`
  itself is never replaced by `hx-boost`, so a second registration
  would stack a second listener closing over a now-stale store,
  double-firing every click). The getter lets that one listener always
  read whatever `arkInitPage()` most recently assigned to the shared
  `arkStore` variable, without re-registering.
- `runtime/state.py`'s `initState()` checks for the `#ark-state`
  marker element first, falling back to the `<body>` attribute --
  handles both the `app_shell` and non-`app_shell` shapes without
  needing to know which one it's looking at.

**Tests:** new `tests/test_htmx_4.py` (23 tests) covering the
`Site`/IR plumbing, `hx-boost` emission, the state-marker relocation,
`shell_persistent`/`hx-preserve` (including the Validation
requirement), `needs_htmx`'s new condition, and the `arkInitPage()`/
`htmx:afterSettle` re-init wiring. `wireActionInterceptor`'s signature
change updates the literal-string assertions in
`tests/test_htmx_3.py`, `tests/test_class_binding.py`,
`tests/test_event_modifiers.py`, `tests/test_js_error_handling.py`,
and `tests/test_refactor_0.py` -- no behavioral assertion in any of
those files changed, only the function signature they check for.

## [0.0499] -- Combined refactor, Stage 9 of 16 (HTMX integration, `htmx-3`: action dispatch)

Full design in `docs/Backends/HTMX-INTEGRATION.md` ("Stage 3 --
Replace `wireActions()` wiring loop" / "Revised stage atomicity" ->
Stage 3) and `docs/Backends/REFACTOR-INDEX.md` row 6. Ninth stage of
the merged 16-row staged order, immediately following `htmx-2`.

JS-backend-only change (HTML-side `data-ark-action-*` attributes are
unchanged, per `REFACTOR-INDEX.md` row 6):

- **JS backend** (`arklight/backend/js/runtime/dispatch.py`): the
  `wireActions(store)` function -- a `document.querySelectorAll(
  '[data-ark-on-click^="action:"]')`/`forEach`/per-element-
  `addEventListener` wiring loop -- is deleted and replaced with
  `wireActionInterceptor(store)`: a single delegated `click` listener
  registered once on `document`, resolving the actual target element
  via `Element.closest('[data-ark-on-click^="action:"]')`. One
  `addEventListener` call for the whole page instead of one per
  action element, same "audit and remove hand-rolled plumbing" outcome
  `htmx-2` left queued for this stage.
- **Documented deviation from the design doc:** `HTMX-INTEGRATION.md`
  describes this stage as registering an `htmx:beforeRequest`
  interceptor. That event is only ever dispatched by HTMX's own
  request path (`he()`), which only runs for an element carrying a
  request-verb attribute (`hx-get`/`hx-post`/etc) -- something
  `Action.*(...)` buttons deliberately never have, being client-local
  state mutations rather than server requests (see
  `HTMX-INTEGRATION.md` "HTMX as a client-local interaction target").
  An `ActionRef` *with* modifiers does get a compiled `hx-trigger`
  attribute (`htmx-2`) that HTMX's own attribute processing wires a
  native listener for even without a request verb, but an `ActionRef`
  with *no* modifiers -- the common case -- gets no compiled attribute
  at all, so HTMX's own processing does nothing with it. Wiring only
  through an HTMX-dispatched event would silently drop click handling
  for every unmodified `Action.*(...)` button. `wireActionInterceptor`
  is a delegated native `click` listener instead, which is correct for
  both the modified and unmodified case and still satisfies the
  "single registration, not a per-element wiring pass" outcome the
  design calls for. See `dispatch.py`'s module docstring for the full
  reasoning.
- **`data-ark-on-click="action:..."`/`data-ark-action-state`/
  `data-ark-action-args` are unchanged** -- `wireActionInterceptor`
  reads them exactly as `wireActions()` used to, off the resolved
  target element instead of a pre-bound closure variable.
  `event.preventDefault()` is unconditional, same as before -- `
  "prevent"` remains honored by construction.
- **Guard shape changed**: `wireActions()` had two `try`/`catch`
  blocks (an outer per-element wiring guard, an inner per-click
  dispatch guard). `wireActionInterceptor` has one -- there is no
  separate wiring phase per element any more, so a single guard around
  the attribute reads + dispatch on each click covers the same
  "one malformed element/click can't break anything else" guarantee
  (each invocation of the delegated listener is independent).

### Changed

- `arklight/backend/js/runtime/dispatch.py`: `WIRE_ACTIONS_JS` ->
  `ACTION_INTERCEPTOR_JS`; `wireActions(store)` -> `wireActionInterceptor(store)`,
  rewritten as a delegated `click` listener. Module docstring rewritten
  to document the `htmx:beforeRequest` deviation above.
- `arklight/backend/js/runtime/__init__.py`: import/reassembly updated
  for the renamed export; module docstring updated.
- `arklight/backend/js/render.py`: `DOMContentLoaded` ready-call
  updated from `wireActions(store);` to `wireActionInterceptor(store);`;
  module docstring and the generated runtime's explanatory header
  comment both updated to describe `htmx-3`.
- `arklight/backend/html/attrs.py`: module docstring note pointing to
  `wireActions()`/`dispatch.py` updated to reflect that `htmx-3` has
  landed (attribute shape itself is unchanged).
- `docs/Backends/HTMX-INTEGRATION.md` / `docs/Backends/REFACTOR-INDEX.md`
  / `docs/Backends/JS-BACKEND-REFACTOR-PLAN.md`: Stage 3 / row 6 /
  `htmx-3` marked **Done**, with the delegated-`click`-listener
  deviation documented inline.
- `tests/test_refactor_0.py`, `tests/test_event_modifiers.py`,
  `tests/test_js_error_handling.py`, `tests/test_js_backend.py`
  updated to assert on `wireActionInterceptor`/`ACTION_INTERCEPTOR_JS`
  instead of `wireActions`/`WIRE_ACTIONS_JS`, and on the new
  single-try/catch guard shape, preserving the same underlying
  coverage (malformed-input isolation, action dispatch, "only ship
  what's used") rather than the old assertions verbatim.

### Added

- `tests/test_htmx_3.py`: this stage's dedicated coverage --
  `wireActions` is gone, `wireActionInterceptor` is present and
  registered via a single delegated `click` listener (not a
  `querySelectorAll`/`forEach` loop), dispatch still resolves
  `data-ark-action-state`/`data-ark-action-args` correctly, `"prevent"`
  remains honored by construction, and the guard shape holds.

### Removed

- `arklight/backend/js/runtime/dispatch.py`'s old `wireActions(store)`
  per-element wiring loop. No successor per-element loop -- the
  delegated listener replaces it outright.

### Not in this pass

Modifier *timing* (`debounce`/`throttle`/`once`/`stop`) is still not
functionally enforced by the shipped runtime: `wireActionInterceptor`
dispatches on every native click regardless of the compiled
`hx-trigger` attribute's contents, same as `wireActions()` did before
it. Routing this interceptor through HTMX's own trigger-spec parsing
(the `hx-trigger`-only branch of its attribute processing, which does
support debounce/throttle/once/consume without a request verb) is
deferred -- `htmx-4`'s app-shell audit settles what survives a boosted
DOM swap first, and that answer affects whether trigger-spec parsing
can be safely relied on here. This is a narrower, more honest version
of the gap `htmx-2` originally described as closing at this stage; see
`dispatch.py`'s module docstring for the full reasoning.

## [0.0498] -- Combined refactor, Stage 8 of 16 (HTMX integration, `htmx-2`: modifiers)

Full design in `docs/Backends/HTMX-INTEGRATION.md` ("Stage 2 --
Modifiers" / "Revised stage atomicity") and
`docs/Backends/REFACTOR-INDEX.md` row 5. Eighth stage of the merged
16-row staged order, immediately following `htmx-1`.

Matched-pair change spanning the HTML and JS backends, same atomicity
constraint `htmx-1` already established:

- **HTML backend** (`arklight/backend/html/attrs.py`): an `ActionRef`'s
  `.with_modifiers(...)`/`.debounce(...)`/`.throttle(...)` tokens now
  compile to an `hx-trigger="click debounce:300ms"`-shaped attribute
  via new `_modifiers_to_hx_trigger`, instead of the comma-joined
  `data-ark-modifiers="prevent,debounce:300"` attribute. `"once"` maps
  straight across; `"debounce"`/`"throttle"` gain an `ms` suffix;
  `"stop"` maps to HTMX's `consume` modifier (the closest built-in
  equivalent to `stopPropagation`); `"prevent"` produces no token at
  all -- `wireActions()`'s click listener already calls
  `event.preventDefault()` unconditionally, so it was "honored by
  construction" before this stage too. The attribute is omitted
  entirely when there's nothing left to say (no modifiers, or only
  `"prevent"`), same "only ship what's used" discipline as elsewhere.
  `data-ark-on-click="action:..."`/`data-ark-action-state`/
  `data-ark-action-args` are unaffected -- `htmx-3` scope.
- **JS backend** (`arklight/backend/js/runtime/`): `arkApplyModifiers`
  -- the ~60-line hand-rolled debounce/throttle/once/stop wrapper --
  and its sibling module (`runtime/modifiers.py`) are deleted.
  `wireActions()` (`runtime/dispatch.py`) no longer wraps its dispatch
  through it; it now calls the action directly on every native click,
  same as `event.preventDefault()` already ran unconditionally before.
  **Documented, temporary gap:** `hx-trigger` is compiled into the
  page's markup by this stage, but nothing reads it as an actual
  trigger yet, so `debounce`/`throttle`/`once`/`stop` have no runtime
  effect until `htmx-3` (`REFACTOR-INDEX.md` row 6) replaces
  `wireActions()`'s hand-rolled loop with an `htmx:beforeRequest`
  interceptor that HTMX's own trigger processing actually feeds.
  `STATE_CORE_JS` (`runtime/__init__.py`) is reassembled without the
  deleted piece; `_build_runtime_js`'s (`js/render.py`) explanatory
  header comment updated to match.

### Changed

- `arklight/backend/html/attrs.py`: new `_modifiers_to_hx_trigger` /
  `_HX_TRIGGER_MODIFIER_MAP`; `ActionRef` branch of `_attr_string`
  emits `hx-trigger` instead of `data-ark-modifiers`.
- `arklight/backend/js/runtime/dispatch.py`: `WIRE_ACTIONS_JS` no
  longer calls `arkApplyModifiers`; module docstring documents the
  `htmx-3` handoff.
- `arklight/backend/js/runtime/__init__.py`: `STATE_CORE_JS`
  reassembled without `APPLY_MODIFIERS_JS`; module docstring updated.
- `arklight/backend/js/render.py` / `arklight/backend/html/render.py`:
  module docstrings updated to describe the new attribute shape and
  the `htmx-3` dependency the temporary functional gap above resolves
  through.
- `docs/Backends/HTMX-INTEGRATION.md` / `docs/Backends/REFACTOR-INDEX.md`
  / `docs/Backends/JS-BACKEND-REFACTOR-PLAN.md`: Stage 2 / row 5 /
  `htmx-2` marked **Done**.
- `tests/test_html_attrs.py`, `tests/test_event_modifiers.py`,
  `tests/test_refactor_0.py` updated to assert on the new `hx-trigger`
  output shape and the deletion of `arkApplyModifiers`/
  `data-ark-modifiers`, preserving the same underlying coverage
  (which modifier combinations are accepted, which attribute shape
  each produces, that the runtime module split still reassembles
  correctly) rather than the old assertions verbatim.

### Removed

- `arklight/backend/js/runtime/modifiers.py` (`APPLY_MODIFIERS_JS`):
  deleted outright, per `HTMX-INTEGRATION.md`'s "Removed by HTMX"
  section. No successor module -- there is nothing left for a runtime
  modifier parser to do once modifiers are compiled at build time.

### Not in this pass

`htmx-3` (`REFACTOR-INDEX.md` row 6, `wireActions()`'s wiring loop
replaced by a single `htmx:beforeRequest` interceptor) is what
actually makes `hx-trigger` functionally govern dispatch timing --
until it lands, this stage's `hx-trigger` attribute is compiled but
inert, as documented above and in `runtime/dispatch.py`'s module
docstring.

## [0.0497] -- Combined refactor, Stage 7 of 16 (HTMX integration, `htmx-1`: behaviors)

Full design in `docs/Backends/HTMX-INTEGRATION.md` ("Stage 1 --
Behaviors" / "Revised stage atomicity") and
`docs/Backends/REFACTOR-INDEX.md` row 4. Seventh stage of the merged
16-row staged order, and the first of the `htmx-*` rows -- the ones
Stages 1-6 (the HTML backend module split) were sequenced ahead of
specifically so this landed directly in the new modules instead of
the 580-line `render.py` those stages had already split apart.

This is a matched-pair change spanning the HTML and JS backends at
once, per `HTMX-INTEGRATION.md`'s own atomicity note -- changing one
side without the other breaks named behaviors silently, so both land
in this single stage:

- **Vendored HTMX** (`arklight/backend/js/htmx.py`, new file): the
  real `htmx.org` npm package, version 2.0.10, Zero-Clause BSD
  licensed, `dist/htmx.min.js` included unmodified byte-for-byte --
  same "cite the vendored source" discipline
  `arklight/backend/js/vdom.py` already established for snabbdom.
  Unlike snabbdom's Stage 1 (a hand-picked "bare core" subset), HTMX
  ships as one self-contained bundle with no smaller subset to
  extract, so it's vendored whole.
- **HTML backend** (`arklight/backend/html/attrs.py`): a plain string
  `on_click` (a named behavior -- `toggle`/`scroll-to`/`copy`/
  `dismiss`) now compiles to `hx-on:click="arkRunBehavior('<name>',
  this)"` instead of `data-ark-on-click="<name>"`. `on_click` removed
  from `BEHAVIOR_PROP_ATTRS` accordingly (the generic dict-based
  dispatch it used to go through is now dead for this key --
  special-cased ahead of it instead, same shape as the pre-existing
  `ActionRef` special case). `behavior_target`/`toggle_class` are
  unaffected -- still `data-ark-target`/`data-ark-toggle-class`.
  `on_click=Action.*(...)` (`ActionRef`) is untouched; that's
  `htmx-3` scope.
- **JS backend** (`arklight/backend/js/render.py`): `wireBehaviors()`
  and its `DOMContentLoaded` query/`addEventListener` wiring loop over
  `[data-ark-on-click]` are gone -- HTMX's own `hx-on:click` attribute
  processing does the wiring now (and, unlike the old pass, keeps
  working on any DOM HTMX subsequently swaps in, not just once at
  page load). `_behaviors_block` now emits only the closed
  `arkBehaviors` dispatch object (still just the fragments a site's
  IR actually references) plus a one-line `arkRunBehavior(name, el)`
  lookup-and-call wrapper, both attached to `window` since HTMX
  evaluates `hx-on:click`'s value in normal global scope, not inside
  `arklight.js`'s own IIFE. `_build_runtime_js` ships vendored HTMX
  whenever a page uses a named behavior or declares state (state-only
  pages don't yet emit any `hx-*` attribute themselves, but are scoped
  in now per `REFACTOR-INDEX.md` row 4 so `htmx-2`/`htmx-3` landing
  later doesn't also have to touch this condition).

### Changed

- `arklight/backend/html/attrs.py`: string `on_click` special-cased
  to emit `hx-on:click`; `on_click` removed from `BEHAVIOR_PROP_ATTRS`.
- `arklight/backend/js/render.py`: `wireBehaviors()` deleted;
  `_behaviors_block` rewritten around `arkBehaviors`/`arkRunBehavior`;
  `_build_runtime_js` includes vendored `HTMX_JS` per `needs_htmx`.
- `docs/Backends/HTMX-INTEGRATION.md` / `docs/Backends/REFACTOR-INDEX.md`:
  Stage 1 / row 4 marked **Done**.
- Six test files updated to assert on the new `hx-on:click`/
  `arkRunBehavior` output shape instead of `data-ark-on-click`/
  `wireBehaviors` -- `tests/test_html_attrs.py`,
  `tests/test_html_backend.py`, `tests/test_js_backend.py`,
  `tests/test_js_error_handling.py`, `tests/test_event_modifiers.py`.
  Two of these also scope their pre-existing "no eval/no new Function"
  guarantee to ARKlight's own authored code, now that pages shipping
  vendored HTMX (a general-purpose third-party library) legitimately
  contain those tokens internally, unrelated to that guarantee.

### Added

- `arklight/backend/js/htmx.py`: vendored HTMX 2.0.10 (`HTMX_JS`) plus
  its upstream Zero-Clause BSD license text (`HTMX_LICENSE`).

## [0.0496] -- Combined refactor, Stage 6 of 16 (HTML backend refactor confirmation check, `html-6`)

Full design in `docs/Backends/HTML-BACKEND-REFACTOR.md` (Stage 6) and
`docs/Backends/REFACTOR-INDEX.md` row 11. Sixth stage of the merged
16-row staged order, and the last of the six HTML-side staging items
-- a confirmation check against the *finished* state of the HTML
backend split (Stages 1-5, all now done), not a code change: does
`README.md`'s "Compiler pipeline" HTML Backend bullet still describe
only external behavior, now that Stages 1-5 have moved every function
it could plausibly reference out of `render.py` and into
`tag_map.py`/`routing.py`/`attrs.py`/`head_meta.py`/`page_render.py`?

Confirmed, as the design doc predicted: no code or doc change needed.
`README.md`'s bullet describes what the backend does from the outside
-- maps IR node types to HTML tags, rewrites internal `Link`/`Image`
references to relative file paths, links the generated stylesheet and
behavior runtime -- none of which changed across Stages 1-5; only
*where* that logic lives internally changed. The bullet names
`arklight/backend/html/render.py` as the pipeline stage (not a
specific function inside it), and that's still exactly where
`HTMLBackend.render()` lives after the split, so the reference stays
accurate. `docs/ARCHITECTURE.md`'s pipeline diagram was checked for
the same reason (it names "HTML Backend" as a stage with no function-
level detail at all) and is unaffected for the same reason.

With this stage done, every row `HTML-BACKEND-REFACTOR.md` originally
staged (1-6) is complete; `docs/Backends/REFACTOR-INDEX.md`'s merged
order moves on to the not-yet-started `htmx-*`/`vdom-*` rows (12-16 in
that table), none of which are part of this document's own scope.

### Changed

- `docs/Backends/HTML-BACKEND-REFACTOR.md`: Stage 6 checkbox marked
  **Done** with the confirmation writeup above; Status line updated to
  reflect all six stages implemented.
- `docs/Backends/REFACTOR-INDEX.md`: row 11 (`html-6`) marked **Done**.

No source or test files touched -- this stage is a documentation
confirmation, not an extraction. 761 tests, unchanged from Stage 5.

## [0.0495] -- Combined refactor, Stage 5 of 16 (HTML backend page_render.py split, `html-5`)

Full design in `docs/Backends/HTML-BACKEND-REFACTOR.md` (Stage 5) and
`docs/Backends/REFACTOR-INDEX.md` row 8. Fifth stage of the merged
16-row staged order, and the last of the HTML-side module
extractions: splits `arklight/backend/html/render.py`'s per-page
composition -- `_render_bind`, `_render_children`, `_render_node`,
`_render_page` -- into a new `arklight/backend/html/page_render.py`,
mirroring the `tag_map.py`/`routing.py`/`attrs.py`/`head_meta.py`
per-concern split Stages 1-4 already established. With this stage
done, `render.py` holds only `HTMLBackend`, whose `render()` is a
short composition of the five sibling modules -- the target shape's
stated end state. Pure refactor -- no generated HTML output changes;
`render.py` now imports the moved functions from
`arklight.backend.html.page_render` instead of defining them inline,
and re-exports them for backward compatibility, same as Stages 1-4.
Sequenced ahead of the not-yet-started `htmx-4` (app-shell navigation)
deliberately, per `REFACTOR-INDEX.md` row 8: `_render_page` is exactly
where that stage's shell-persistent-region audit has to look, so this
extraction lands first -- the same reasoning `html-3` already applied
ahead of `htmx-1`.

### Added

- New `arklight/backend/html/page_render.py`: `_render_bind`,
  `_render_children`, `_render_node`, `_render_page` -- moved
  verbatim from `render.py`. Imports tag selection from `tag_map.py`
  (Stage 1), route/asset-path resolution from `routing.py` (Stage 2),
  attribute rendering from `attrs.py` (Stage 3), and `<head>`
  metadata assembly from `head_meta.py` (Stage 4) -- the same call
  graph `render.py` had before this split, just addressed through
  the sibling modules directly instead of re-exported names.
- New `tests/test_html_page_render.py` -- 17 tests: `_render_bind`
  (value rendering, missing-key default, escaping), `_render_node`/
  `_render_children` (simple containers, void tags, `Bind` dispatch,
  text/nested-node flattening, escaping, route-relative link
  resolution through recursion), and `_render_page` (full document
  shell, title/lang fallback and override, state hydration presence/
  absence, nested-route asset-path resolution, head-meta inclusion).
  761 tests total.

### Changed

- `arklight/backend/html/render.py`: rewritten to hold only
  `HTMLBackend` plus the Stages 1-5 backward-compatibility re-exports;
  every per-node/per-page rendering function now lives in
  `page_render.py`. Module docstring rewritten with a "module map"
  section pointing at where each Stage 1-5 concern actually lives, so
  "what does the HTML backend do" is answerable without a 580-line
  scroll -- the same goal the original design doc's "Cheap to read"
  bullet named for the finished split.
- `docs/Backends/HTML-BACKEND-REFACTOR.md`: Stage 5 checkbox and
  Status line marked **Done**.
- `docs/Backends/REFACTOR-INDEX.md`: row 8 (`html-5`) marked **Done**.

## [0.0494] -- Combined refactor, Stage 4 of 16 (HTML backend head_meta.py split, `html-4`)

Full design in `docs/Backends/HTML-BACKEND-REFACTOR.md` (Stage 4) and
`docs/Backends/REFACTOR-INDEX.md` row 7. Fourth stage of the merged
16-row staged order, and the fourth HTML-side extraction: splits
`arklight/backend/html/render.py`'s per-page `<head>` metadata
assembly -- `_render_head_meta` -- into a new
`arklight/backend/html/head_meta.py`, mirroring the `tag_map.py`/
`routing.py`/`attrs.py` per-concern split Stages 1-3 already
established. Pure refactor -- no generated HTML output changes;
`render.py` now imports `_render_head_meta` from
`arklight.backend.html.head_meta` instead of defining it inline, and
re-exports it for backward compatibility, same as Stages 1-3.
Independent of the not-yet-started `htmx-*` track per
`REFACTOR-INDEX.md` row 7's own note -- no shared surface with
behavior/modifier/action attribute emission, so this stage didn't need
to wait on or block anything in that track.

### Added

- New `arklight/backend/html/head_meta.py`: `_render_head_meta` --
  moved verbatim from `render.py`. Depends on `routing.py` (Stage 2)
  for `_relative_asset_path` (resolves `favicon`/`og_image` the same
  way `page_render.py` resolves the stylesheet/script paths); depends
  on nothing from `attrs.py` (Stage 3) or the not-yet-split
  `page_render.py` (Stage 5).
- New `tests/test_html_head_meta.py` -- 11 tests: the no-optional-
  props empty-string case, `description`/`favicon` rendering,
  Open-Graph opt-in behavior (no og_* prop supplied vs. `description`
  alone vs. an explicit `og_title` override), `og_image` asset-path
  resolution, `meta`/`links` dict/list rendering (ordering, multiple
  entries, `links`' verbatim-not-asset-resolved handling), and HTML
  escaping. 744 tests total.

### Changed

- `arklight/backend/html/render.py`: `_render_head_meta` is now
  imported from `arklight.backend.html.head_meta` instead of defined
  inline. Every other function in the file (`_render_bind`,
  `_render_children`, `_render_node`, `_render_page`, `HTMLBackend`) is
  unchanged; the `IRPage` import stays, still used by `_render_page`'s
  own signature.
- `docs/Backends/HTML-BACKEND-REFACTOR.md`: Stage 4 checkbox and
  Status line marked **Done**.
- `docs/Backends/REFACTOR-INDEX.md`: row 7 (`html-4`) marked **Done**.

## [0.0493] -- Combined refactor, Stage 3 of 16 (HTML backend attrs.py split, `html-3`)

Full design in `docs/Backends/HTML-BACKEND-REFACTOR.md` (Stage 3) and
`docs/Backends/REFACTOR-INDEX.md` row 3. Third stage of the merged
16-row staged order, and the third HTML-side extraction: splits
`arklight/backend/html/render.py`'s attribute-rendering concern --
`PASSTHROUGH_ATTRS`, `PROP_ALIASES`, `BEHAVIOR_PROP_ATTRS`,
`_style_dict_to_css`, `_attr_string` -- into a new
`arklight/backend/html/attrs.py`, mirroring the `tag_map.py`/
`routing.py` per-concern split Stages 1-2 already established. Pure
refactor -- no generated HTML output changes; `render.py` now imports
the moved names from `arklight.backend.html.attrs` instead of defining
them inline, and re-exports them for backward compatibility, same as
Stages 1-2. Sequenced ahead of the not-yet-started `htmx-1` stage
deliberately, per `REFACTOR-INDEX.md`'s "Why the HTML split and the
HTMX attribute changes collide": landing the HTMX attribute-emission
rewrite directly in `attrs.py` once that stage starts, rather than in
`render.py` a few commits before being moved out from under it.

### Added

- New `arklight/backend/html/attrs.py`: `PASSTHROUGH_ATTRS`,
  `PROP_ALIASES`, `BEHAVIOR_PROP_ATTRS`, `_style_dict_to_css`,
  `_attr_string` -- moved verbatim from `render.py`. Depends on
  `routing.py` (Stage 2) for the route/asset-path resolution
  `_attr_string` delegates to; depends on nothing from `head_meta.py`
  or `page_render.py` (Stages 4-5, not yet split out).
- New `tests/test_html_attrs.py` -- 24 tests: the moved data
  tables' exact contents, `_style_dict_to_css` conversion/joining/
  filtering, and `_attr_string` across passthrough attrs, aliases,
  inline styles, unknown-prop `data-*` fallback, `aria_*` mapping,
  boolean attrs, route-aware `href` rewriting, `ActionRef`/
  `ClassBindSpec` attribute emission (including modifiers and
  state-driven class pre-fill). 733 tests total.

### Changed

- `arklight/backend/html/render.py`: `PASSTHROUGH_ATTRS`/
  `PROP_ALIASES`/`BEHAVIOR_PROP_ATTRS`/`_style_dict_to_css`/
  `_attr_string` are now imported from `arklight.backend.html.attrs`
  instead of defined inline. The now-unused `ActionRef`/
  `ClassBindSpec` import was dropped from `render.py` (both are only
  referenced from `attrs.py` now); `json`/`html.escape` imports stay,
  still used by `_render_bind`/`_render_head_meta`/`_render_page`.
  Every other function in the file (`_render_bind`, `_render_children`,
  `_render_node`, `_render_head_meta`, `_render_page`, `HTMLBackend`)
  is unchanged.
- `docs/Backends/HTML-BACKEND-REFACTOR.md`: Stage 3 checkbox and
  Status line marked **Done**.
- `docs/Backends/REFACTOR-INDEX.md`: row 3 (`html-3`) marked **Done**.

## [0.0492] -- Combined refactor, Stage 2 of 16 (JS runtime module split, `refactor-0`)

Full design in `docs/Backends/JS-BACKEND-REFACTOR-PLAN.md` (`refactor-0`
row) and `docs/Backends/HTMX-INTEGRATION.md`; sequencing against the
HTML backend split and the `htmx-*`/`vdom-*` tracks in
`docs/Backends/REFACTOR-INDEX.md` row 2. Second stage of the merged
16-row staged order that document closes, and the first stage on the
JS-backend side of it: splits `arklight/backend/js/render.py`'s old
`_STATE_CORE_JS` (`createState`, `renderBindings`,
`renderClassBindings`, `initState`, `arkApplyModifiers`,
`wireActions`, one 145-line triple-quoted string) plus its
`_NOTIFY_JS`/`_NAV_HIGHLIGHT_JS` constants into
`arklight/backend/js/runtime/{state,bindings,modifiers,dispatch,nav,
notify}.py`, mirroring the `actions/`/`behaviors/` per-file pattern
already established for the per-name registries. Pure refactor -- no
generated JS output changes; `render.py` now imports the reassembled
fragments from `arklight.backend.js.runtime` instead of defining them
inline. Landed ahead of the `htmx-*` track deliberately, since both
that track and the not-yet-started `vdom-*` track touch this same
file -- splitting once first avoids two large, unrelated diffs
colliding in review (see `JS-BACKEND-REFACTOR-PLAN.md` "Ordering
rationale, stated explicitly").

### Added

- New `arklight/backend/js/runtime/` package:
  - `state.py` -- `CREATE_STATE_JS` (`createState`), `INIT_STATE_JS`
    (`initState`).
  - `bindings.py` -- `RENDER_BINDINGS_JS` (`renderBindings`),
    `RENDER_CLASS_BINDINGS_JS` (`renderClassBindings`).
  - `modifiers.py` -- `APPLY_MODIFIERS_JS` (`arkApplyModifiers`).
  - `dispatch.py` -- `WIRE_ACTIONS_JS` (`wireActions`).
  - `nav.py` -- `NAV_HIGHLIGHT_JS` (`highlightActiveNavLink`).
  - `notify.py` -- `NOTIFY_JS` (`arkNotify`).
  - `__init__.py` -- reassembles `STATE_CORE_JS` from the six modules
    above in the original `_STATE_CORE_JS` order, and re-exports
    `NOTIFY_JS`/`NAV_HIGHLIGHT_JS`.
- New `tests/test_refactor_0.py` -- 9 tests: each new module exposes
  the fragment it's supposed to, `STATE_CORE_JS` reassembles them in
  the original order, and `JSBackend.render()`'s output for both a
  plain and a stateful page is unaffected by the split. 709 tests
  total.

### Changed

- `arklight/backend/js/render.py`: `_STATE_CORE_JS` / `_NOTIFY_JS` /
  `_NAV_HIGHLIGHT_JS` are now imported from
  `arklight.backend.js.runtime` instead of defined inline; every
  other function in the file (`_collect_usage`, `_behaviors_block`,
  `_actions_block`, `_build_runtime_js`, `JSBackend`) is unchanged.
- `docs/Backends/REFACTOR-INDEX.md`: row 2 (`refactor-0`) marked
  **Done**.

## [0.0491] -- HTML backend refactor, Stage 2 of 6 (routing.py + UNROUTED_REFERENCE_ATTRS fix)

Full design in `docs/Backends/HTML-BACKEND-REFACTOR.md`; sequencing
against the JS backend/HTMX work in `docs/Backends/REFACTOR-INDEX.md`
row 1 (`html-2`). Second of six staged extractions splitting
`arklight/backend/html/render.py`'s five unrelated jobs into their own
modules. Unlike Stage 1, this stage is deliberately not
behavior-preserving in one respect: it also lands the
`UNROUTED_REFERENCE_ATTRS` reachability fix the design doc's audit
flagged as open, per that doc's own stated exception to "behavior
unchanged after every stage."

### Added

- New `arklight/backend/html/routing.py`: route/asset-path resolution
  -- `_output_path_for_route`, `_is_internal_route_ref`,
  `_resolve_route_ref`, `_resolve_src_ref`, `_relative_asset_path`, and
  the attribute-classification sets `ROUTE_AWARE_ATTRS`,
  `ASSET_OR_ROUTE_AWARE_ATTRS`, `SRC_ATTRS` -- moved out of `render.py`.
- New `_resolve_srcset_ref` in `routing.py`: `srcset` packs one or more
  comma-separated `url descriptor` pairs into a single value (e.g.
  `"wide.jpg 800w, narrow.jpg 400w"`), so it needed its own resolver
  rather than reusing `_resolve_route_ref`/`_resolve_src_ref` directly
  -- each URL is split out, resolved independently (same
  route-or-asset treatment `poster`/`src` get), and rejoined with its
  descriptor intact. New `SRCSET_ATTRS` set drives this in `_attr_string`.
- **The `UNROUTED_REFERENCE_ATTRS` fix**, per the design doc's audit:
  - `action`/`formaction` (Form, and any submit-capable Button/Input)
    join `ROUTE_AWARE_ATTRS` -- resolved exactly like `href`. The
    audit's flagged sub-question (whether these should warn-and-skip
    instead, since a form action is at least as likely to target an
    external API as an internal route) is resolved by
    `_resolve_route_ref`'s existing "unknown route left as-is" safety
    net: an external API URL never matches a registered route, so it's
    never rewritten either way -- no separate warn-and-skip path
    needed.
  - `poster` (Video) joins `ASSET_OR_ROUTE_AWARE_ATTRS` -- resolved
    exactly like `src` (route-checked first, asset-fallback
    otherwise), since a poster names an image asset, not a route.
  - `srcset` (PictureSource) resolved via the new `_resolve_srcset_ref`
    above.
- New `tests/test_html_routing.py` -- 31 tests exercising `routing.py`
  directly, independent of `HTMLBackend.render`/a full IR build (same
  "independent testability" goal `tests/test_html_tag_map.py`
  established for Stage 1). 700 tests total.
- 8 new end-to-end tests in `tests/test_html_backend.py` covering the
  `UNROUTED_REFERENCE_ATTRS` fix through real `Page(...)`/`render()`
  calls: known-route `action`/`formaction` rewriting (including across
  nested page depth), `poster` as both a known-route embed and a
  root-relative asset, and `srcset` with multiple entries, a density
  descriptor, and an external URL left untouched.

### Fixed

- A separate, pre-existing bug surfaced while wiring `formaction`
  through the fix above: `formaction` was missing from
  `PASSTHROUGH_ATTRS` entirely, so it always rendered as
  `data-formaction="..."` instead of a real HTML attribute, independent
  of routing. Added to `PASSTHROUGH_ATTRS` in the same commit --
  a route-rewritten `formaction` value isn't observable through a
  `data-formaction` fallback attribute, so shipping the routing half of
  the fix without this would have been silently incomplete.

### Removed

- `UNROUTED_REFERENCE_ATTRS` and `_warn_unrouted_reference` (the
  v0.0431 emergency-patch build-time warning) -- removed entirely, not
  deprecated. Once every attribute the warning covered is correctly
  resolved, there is nothing left for it to flag. The CLI's
  `[ARKlight ALPHA]`-marker warning-surfacing machinery
  (`arklight/cli/main.py`) is unaffected -- it's generic across every
  alpha-limitation warning, not specific to this one, and other
  `[ARKlight ALPHA]` warnings may still exist elsewhere.

### Changed

- `render.py` now imports the routing names from `routing.py` instead
  of defining them, and re-exports them so
  `from arklight.backend.html.render import ROUTE_AWARE_ATTRS` (etc.)
  keeps working unchanged -- same backward-compatibility discipline
  Stage 1 established for `TAG_MAP`/`VOID_TAGS`/`_tag_for`.
  `tests/test_html_backend.py`'s existing suite passes unchanged
  *except* for the one test the design doc's own staging notes as the
  expected exception (the build-time warning previously asserted via
  `pytest`'s captured-warnings summary for `test_form_elements_render_with_form_attrs`'s
  `action="/submit"` no longer fires, since `/submit` isn't a
  registered route and is correctly left untouched with no warning --
  the test's own assertions were already correct and needed no
  changes).

### Not in this pass

Stages 3-6 (`attrs.py`, `head_meta.py`, `page_render.py`, the
`README.md` compiler-pipeline description check) are unstarted -- see
`docs/Backends/HTML-BACKEND-REFACTOR.md`'s staging table and
`docs/Backends/REFACTOR-INDEX.md` for how they sequence against the JS
backend/HTMX work.

## [0.049] -- HTML backend refactor, Stage 1 of 6

Full design in `docs/Backends/HTML-BACKEND-REFACTOR.md`. First of six
staged, behavior-preserving extractions splitting
`arklight/backend/html/render.py`'s five unrelated jobs into their own
modules, mirroring the CSS backend refactor's earlier split.

### Added

- New `arklight/backend/html/tag_map.py`: `TAG_MAP` (IR node type ->
  HTML tag name), `VOID_TAGS` (tags with no closing tag/children), and
  `_tag_for(node)` (resolves `Heading`'s tag from its `level` prop,
  falls back to `TAG_MAP` otherwise) -- moved verbatim out of
  `render.py`. Pure data plus one tiny pure function, no dependency on
  anything else in the HTML backend.
- New `tests/test_html_tag_map.py` -- 8 tests exercising `tag_map.py`
  directly, independent of `HTMLBackend.render`/a full IR build (the
  refactor's "independent testability" goal). 661 tests total.

### Changed

- `render.py` now imports `TAG_MAP`/`VOID_TAGS`/`_tag_for` from
  `tag_map.py` instead of defining them, and re-exports all three
  names so `from arklight.backend.html.render import TAG_MAP` (etc.)
  keeps working unchanged. Zero behavior change: `tests/test_html_backend.py`
  passes unmodified, generated HTML is byte-for-byte identical.
- `docs/ARCHITECTURE.md`'s Backend Interface section updated to point
  at the refactor doc's real path (`docs/Backends/HTML-BACKEND-REFACTOR.md`,
  not `docs/HTML-BACKEND-REFACTOR.md`) and reflect Stage 1 landing.

### Not in this pass

Stages 2-6 (`routing.py`, `attrs.py`, `head_meta.py`, `page_render.py`,
the `README.md` compiler-pipeline description check) are unstarted --
see the design doc's staging table. Stage 2 in particular also carries
the `UNROUTED_REFERENCE_ATTRS` reachability fix (`srcset`/`poster`/
`action`/`formaction` not route-rewritten) flagged there; deliberately
not pulled forward into this stage.

## [0.049] -- Feedback-loop fix + `@import` made experimental

Two fixes, bundled together since both touch the same "Stage 8
compile-time feedback loop" and "at-rule vocabulary" areas from the
work directly below.

### Fixed

- **Stage 8's self-learning typo feedback loop never actually fired.**
  Every component (`Heading`, `Image`, ...) is a real Python
  function/name, so misspelling one (`Headingg(...)`) fails as a
  plain Python `NameError` inside `Site.build_ark_ast()` -- several
  pipeline stages before `validate_node()` ever runs -- so it never
  reached the `ValidationError` `arklight/search/feedback.py`'s
  `record_validation_feedback` was built to listen for. In ordinary
  use, that `ValidationError` path is essentially unreachable: all
  three `ARKNode(type=...)` construction sites in the codebase pass a
  fixed, correctly-spelled string, never one that round-trips through
  user input.
  - New `parse_undefined_component_name`/`record_name_error_feedback`
    in `arklight/search/feedback.py`, recognizing Python's own
    `NameError` message shape (`name 'X' is not defined`) -- the
    message a typo'd component call actually raises.
  - `compile_site_file` (`arklight/compiler/pipeline.py`) gains a new
    `except NameError` branch around `site.build_ark_ast()`, ahead of
    the existing catch-all `except Exception`, calling this new
    best-effort recorder. Same failure-swallowing, build-behavior-
    neutral contract as the existing `ValidationError` hook --
    recording a confusion never affects whether/how a build succeeds
    or fails.
  - `record_validation_feedback`/`parse_unknown_component_type` are
    unchanged and kept for the rarer path where an already-built
    `ARKNode` reaches `validate_node()` with an unknown `.type`
    directly (IR constructed by a lower-level caller that skips the
    documented component functions).
  - New `tests/test_search_feedback.py` -- 12 tests, including an
    end-to-end repro of the original bug report (scaffold a typo'd
    site, build it, confirm a `confusions` row is now actually
    recorded). 647 tests total, all passing.
  - Not fixed here, left as-is: `arklight search`'s undisclosed
    first-run creation of `~/.local/share/arklight/search.sqlite3`
    (or the platform equivalent) -- flagged in the same audit, but a
    documentation/disclosure gap, not a bug, and out of scope for this
    pass.

### Changed

- **`Site.import_style(url)` (`@import`) is now an EXPERIMENTAL API**
  (see `docs/EXPERIMENTAL-APIS.md`), gated through the same mechanism
  `site.media_query(...)` already uses. New `css-import` entry in
  `arklight/experimental.py`'s `FEATURES` registry: *"the imported
  file's contents can't be validated by ARKlight"* -- unlike every
  other rule this project generates, an `@import` URL is fetched and
  applied by the browser at request time, so nothing about it is
  checked. Every call now prints the inline `[EXPERIMENTAL FEATURE
  ACTIVE]` banner and an end-of-run summary block, same as
  `media_query`. `container_query` remains deliberately **not**
  flagged (unaffected by this change) -- it isn't request-time-opaque
  the way `@import`/`@media` are.
  - `tests/test_experimental_apis.py` and
    `tests/test_css_structural_addendum.py` extended with `css-import`
    coverage (registration, inline banner, IR threading, invalid-URL-
    doesn't-record, summary text).
  - `docs/EXPERIMENTAL-APIS.md` and `docs/DESIGN-NOTES.md` updated to
    list `css-import` alongside `css-media-queries`/
    `experimental-install-pwa`.

## [0.049] -- Pseudo-class vocabulary addendum III

Full writeup in `docs/DESIGN-NOTES.md` ("v0.049: pseudo-class
vocabulary addendum III"). Same mechanism as the CSS selector algebra
work directly below, just growing the set -- every parameterless
pseudo-class (single word, no `(...)` argument) is the same shape as
`hover`/`focus`/`disabled` already in `ALLOWED_PSEUDO_CLASSES`, so
adding more is a one-line set extension, not a regex or pipeline
change. No new mechanism, no new tests infrastructure -- just more
entries validated by the two call sites that already read this set
(`site.style(...)`'s `:pseudo:property` shorthand in `arklight/api.py`,
and the general selector parser in `arklight/backend/css/selectors.py`
used by `Site.style_selector(...)`).

### Added

- 20 more entries in `ALLOWED_PSEUDO_CLASSES`: `focus-within`, `link`,
  `target`, `enabled`, `indeterminate`, `default`, `required`,
  `optional`, `valid`, `invalid`, `in-range`, `out-of-range`,
  `read-only`, `read-write`, `placeholder-shown`, `root`, `empty`,
  `only-child`, `first-of-type`, `last-of-type`, `only-of-type`.
- `tests/test_api_style.py::test_style_accepts_every_supported_pseudo_class`
  extended to cover all 29 pseudo-classes (was 7).
- `tests/test_css_selectors.py::test_round_trips_a_valid_selector`
  extended with parameterless-pseudo-class and multi-pseudo-class
  cases (`:focus-within`, `:target`, `:empty`, `:required`,
  `:invalid`, `:in-range`, `:only-child`, `input:required:invalid`).
- 635 tests total (31 new test cases from the two parametrize
  extensions above), all passing.

### Notes

- Deliberately still a curated set, not "any `:whatever` the user
  types" -- functional/parameterized pseudo-classes (`:not()`,
  `:nth-child()`, etc.) and pseudo-elements (`::before`, etc.) are out
  of scope here; they're handled by the separate mechanisms added in
  the CSS selector algebra work directly below (`SELECTOR_LIST_PSEUDO_CLASSES`,
  `NTH_PSEUDO_CLASSES`, `PSEUDO_ELEMENTS`).

## [0.049] - Unreleased

**CSS selector algebra + at-rule vocabulary.** Closes the remaining
structural CSS gaps flagged in `docs/DESIGN-NOTES.md` ("CSS selector
algebra + at-rule vocabulary"): pseudo-elements, parameterized
pseudo-classes, attribute selectors, combinators, grouped selectors,
bare tag-selector overrides, `@keyframes`, `@font-face`, `@container`,
`@supports`, `@page`, and `@import`. Same discipline as every other
extension point in the project -- a closed grammar/registry, never a
raw-CSS-string escape hatch.

- New `arklight/backend/css/selectors.py`: a small recursive-descent
  selector parser. `parse_selector_list(text)` either returns a
  validated AST or raises `CSSSelectorSyntaxError`; `render_selector_list`
  turns that AST back into canonical CSS text.
- New `Site.style_selector(selector: str, rules: dict) -> None` --
  combinators (`.a > .b`, `.a + .b`, `.a ~ .b`, `.a .b`), grouped
  selectors (`h1, h2, h3`), bare tag overrides (`blockquote`),
  attribute selectors (`[type="email"]`), pseudo-elements
  (`::before`, `::after`, `::placeholder`, `::selection`, `::marker`,
  `::first-line`, `::first-letter`), and parameterized pseudo-classes
  (`:not()`, `:is()`, `:where()`, `:has()` -- including its relative
  form, `:has(> .icon)` -- and the `:nth-child()` family with real
  An+B validation). Supports one level of `&`-prefixed nesting
  (`"&:hover"`, `"& .child"`, `"& > .child"`), desugared at author
  time into fully-resolved selectors rather than emitted as real CSS
  nesting syntax. `Site.style(name, rules)` is unchanged.
- New `Site.keyframes(name, frames)`, `Site.font_face(family, src,
  **descriptors)`, `Site.container_query(condition, selector, rules,
  *, name=None)`, `Site.supports(condition, selector, rules)`,
  `Site.page_rule(rules, *, pseudo=None)`, and `Site.import_style(url)`
  -- new closed-vocabulary `Site` methods, each rendered by a new pure
  function in the new `arklight/backend/css/at_rules.py`.
  `container_query` is deliberately not flagged EXPERIMENTAL the way
  `media_query` is (a container query isn't viewport-keyed, so it
  doesn't carry the same caution). `import_style` output is placed
  first in the generated stylesheet, ahead of `BASE_CSS_HEADER`, per
  the CSS spec's `@import`-must-come-first requirement.
- All additions are pure passthrough data on `WebsiteIR`
  (`selector_rules`, `keyframes`, `font_faces`, `container_queries`,
  `supports_rules`, `page_rules`, `style_imports`) -- no change to
  `normalize.py`/`validate.py`'s tree-walking logic. 63 new tests
  (`tests/test_css_selectors.py`, `tests/test_css_structural_addendum.py`);
  604 tests total, all passing. Fully additive -- a site that never
  calls any of these methods renders byte-for-byte unchanged.

## [0.048] - Unreleased

**Stage A of v0.048: structured `<head>` extension.** `Page(...)`
gains two more optional, structured props: `meta: dict[str, str] |
None` (name/content pairs, each rendered as `<meta name="..."
content="...">`) and `links: list[dict[str, str]] | None` (each dict
an attribute -> value map rendered as one `<link ...>` tag, for
preconnect/webfonts/extra icon sizes beyond `favicon`). No raw
HTML-injection escape hatch -- same discipline as every other
extension point in the project. Validated in `arklight/ir/validate.py`
(`_validate_page_head_extensions`, `Page`-only); rendered in
`arklight/backend/html/render.py`'s `_render_head_meta`, appended
after the existing `description`/`favicon`/`og_*` tags. `links`
entries are emitted verbatim (not resolved as a relative build asset
the way `favicon`/`og_image` are), since a `links` entry is at least
as likely to point at an external origin as a local one. 10 new tests
in `tests/test_html_backend.py`; 541 tests total, all passing. Fully
additive -- a page that sets neither prop renders byte-for-byte
unchanged.

With this stage landing, **v0.048 (CSS `@media` queries + `<head>`
extension) is now DONE in full** -- Stage B (`responsive_style` +
`@media` compilation) shipped previously; see `PROGRESS.md` for both
stages' implementation records.

**Renumbered the milestones behind v0.048** now that it has shipped
(see `docs/ARCHITECTURE.md` for the full note): JS backend capability
expansion moves `v0.044` -> `v0.054`; user-defined components moves
`v0.100` -> `v0.060`; the Desktop backend moves `v0.060` -> `v0.080`;
the Android backend moves `v0.080` -> `v0.100`; and the KaiOS backend
-- previously designed but unnumbered -- is now `v0.120`. No scope or
design changes, sequencing only.

## [0.0436] - Unreleased

**Added `arklight live-streaming`, an alpha-only dev server: watch,
auto-rebuild, and auto-reload a project in the browser as you edit.**
`arklight live-streaming --subscribe site.py [-o ARK] [--host H]
[--port P]` blocks in the terminal it's run from, serves the build
output over stdlib `http.server`, and re-runs the normal
`arklight.compiler.pipeline.build()` pipeline (with full
`--verbose`-style stage narration) whenever a `.py` file or `assets/`
under the entry's directory changes on disk -- detected via a plain
mtime-polling loop, no third-party watcher dependency (ARKlight stays
zero-dependency). Reload is delivered over a Server-Sent-Events
endpoint (`/__arklight_live__/events`) to a small vendored client
script (`/__arklight_live__/client.js`), injected into every HTML page
*only* during a live-streaming build via a new, purely additive
`_LiveReloadBackend` (`Backend.postprocess`, same extension point
`arklight/backend/base.py` already documents for "injecting
analytics/OG tags... without editing that backend's source") -- a
plain `arklight build` is byte-for-byte unaffected. `arklight
live-streaming --unsubscribe [site.py]` and `--status [site.py]
[--status-pin]` run from another terminal and talk to the running
session via a small on-disk registry (`~/.arklight/live_streaming/
registry.json`) keyed by the entry file's absolute path, plus a
`SIGTERM` for shutdown; both are idempotent (`--unsubscribe` on a
session that isn't running, or a second `--subscribe` on one already
running, are no-ops rather than errors). `--status-pin` is a purely
per-invocation formatting flag -- it's never written into the
registry, so it has no effect on the running `--subscribe` session and
isn't remembered for the next `--status` call. Host/port/poll-interval
can also be pinned per-project via a new, deliberately small
`arklight.config.py` (see `arklight/config.py` and next entry) instead
of passed as flags every time. New regression tests in
`tests/test_live_streaming.py` cover reload-script injection, registry
read/write/corrupt-file recovery and stale-PID pruning, and session
lookup/disambiguation; manually verified end-to-end (idempotent
subscribe, live edit -> rebuild -> reload, clean `--unsubscribe`, and
graceful shutdown on an external `SIGTERM`).

**Added `arklight.config.py`, a minimal per-project config file.**
Currently the only reader is `arklight live-streaming` (see above),
which wants a place to pin `host`/`port`/`poll_interval` under a
`live_streaming` section without flags on every `--subscribe`. Rather
than design a full schema with no second consumer yet, `arklight/
config.py` defines just enough to load a project's
`arklight.config.py` (a plain Python file next to `site.py` containing
a top-level `CONFIG = {...}` dict), merge a named section over a
reader-supplied set of defaults, and fail loudly (`ConfigError`) on a
present-but-broken file rather than silently falling back -- extending
it later is a one-line addition to whichever module reads a new
section, not a rewrite of the loader. New regression tests in
`tests/test_config.py`.

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

**Stage 3 of the vdom staging: event modifiers.**
`Action.set("saved", True).debounce(300)` /
`Action.remove("items", 0).with_modifiers("prevent", "stop", "once")`
attach `prevent`/`stop`/`once`/`debounce:<ms>`/`throttle:<ms>` tokens
to an `ActionRef`, validated against a new closed `MODIFIER_REGISTRY`
(`arklight/ir/schema.py`) the same way `ACTION_REGISTRY` already is.
Compiles to a single `data-ark-modifiers="prevent,debounce:300"`
attribute (omitted when unused), read once per element by a new
`arkApplyModifiers` JS runtime wrapper that handles `stop`/`once`
short-circuiting and debounce/throttle timing around the existing
action dispatcher -- `prevent` was already honored unconditionally by
the click listener, so this stage mostly makes that intent explicit
and named. 17 new tests (`tests/test_event_modifiers.py`); no change
to `State`/`Bind`/existing `Action.*` behavior. Deliberately does not
route through Stage 1's vendored vdom -- this is a dispatch-timing
concern on the listener, not a DOM-diffing one.

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

**v0.048** (CSS `@media` queries + structured `<head>`/`<header>`
extension) has since shipped in full -- see the `[0.048]` entry above.
Next up is **v0.054** (renumbered from v0.044: JS backend capability
expansion -- computed/derived state, watch effects, two-way input
binding, per-item list rendering, conditional show/hide, event
modifiers, reactive class binding) -- see the "Planned" section of
[`PROGRESS.md`](./PROGRESS.md) and
[`docs/DESIGN-NOTES.md`](./docs/DESIGN-NOTES.md) ("v0.044: JS backend
capability expansion -- reactive core parity with Vue 3") for the
design.

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

**Fixed a real version-drift bug from the published PyPI release, and
bumped to `0.42.0`.** The shipped `0.37`/`0.038`-internal release had
`pyproject.toml`'s version and `arklight.__version__` disagreeing --
two hardcoded copies of the same number, nothing keeping them in
sync, and they'd drifted apart by release time. `arklight/__init__.py`
no longer hardcodes a second copy: `__version__` is now read back
from the installed package's own metadata
(`importlib.metadata.version("arklight")`), so `pyproject.toml` is the
single source of truth and there's no second place for it to drift
from. Also moved off the old two/three-digit "milestone number as a
decimal fraction" scheme (`0.037`, `0.041`, a future `0.100`) to a
proper three-part `MAJOR.MINOR.PATCH` string -- the old scheme is a
real PEP 440 hazard: `0.100` normalizes (trailing zeros stripped) to
`0.1`, which would have sorted *below* `0.048`'s `0.48` the moment a
`v0.100`-named milestone shipped. `0.100.0` compares each dotted
component as an integer instead, so this can't happen again. Staying
under `1.0` intentionally -- `1.0` is reserved for when ARKlight
actually reaches that milestone, not a general "looks more mature"
bump. New regression test (`tests/test_version.py`) locks
`arklight.__version__` to installed package metadata so this can't
silently drift apart again.

Next up is **v0.048** (CSS `@media` queries + structured
`<head>`/`<header>` extension) -- see the "Planned" section of
[`PROGRESS.md`](./PROGRESS.md) and [`docs/DESIGN-NOTES.md`](./docs/DESIGN-NOTES.md)
("v0.048: CSS media queries + `<head>` extension") for the design.
Custom CSS class authoring and an `arklight --search <name>` schema
lookup are sketched but not yet scheduled to a version -- also in
`PROGRESS.md`.

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
