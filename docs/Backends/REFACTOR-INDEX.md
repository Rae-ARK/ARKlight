# Backend Refactor Index: HTML + HTMX + JS, One Staged Order

Status: **Design only -- not started**, except where noted. This file
does not restate the reasoning already written in the three documents
it reconciles -- it exists only to answer "what order do I actually do
these in," because the three source docs were written independently,
each staged *within itself*, but never sequenced *against each other*
even though several of their stages touch the same files:

1. **`HTML-BACKEND-REFACTOR.md`** -- splits
   `arklight/backend/html/render.py` (~580 lines) into
   `tag_map.py` / `routing.py` / `attrs.py` / `head_meta.py` /
   `page_render.py`. Stage 1 (`tag_map.py`) is **done**; this index
   only sequences Stages 2-6.
2. **`HTMX-INTEGRATION.md`** -- delegates
   `wireBehaviors()` / `wireModifiers()` / `wireActions()` in
   `arklight/backend/js/render.py` to a vendored HTMX, and is explicit
   that its Stage 1/2 attribute changes are matched pairs spanning
   *both* the HTML and JS backends at once (see that doc's
   "Implementation structure and atomicity").
3. **`JS-BACKEND-REFACTOR-PLAN.md`** -- already reconciles HTMX
   integration against the reactive-core `vdom-*` staging in
   `docs/DESIGN-NOTES.md` and adds one new stage (`htmx-4`, app-shell
   navigation) neither older doc scoped. It does not, however,
   reconcile against the HTML backend's own module split -- it only
   notes in prose that Stages 1/2 "also" touch
   `arklight/backend/html/render.py`, without saying when that file's
   *other* four extraction stages should happen relative to them.

That gap -- HTML Stages 2-6 vs. the `refactor-0`/`htmx-*`/`vdom-*`
table -- is what this document closes. Everything below is a single
merge of the three staging tables into one dependency order; every row
links back to the source doc/section that actually specifies the work,
because this file is a routing layer, not a third copy of the design.

## Why the HTML split and the HTMX attribute changes collide

`HTMX-INTEGRATION.md`'s Stage 1 and Stage 2 rewrite exactly the
attribute-emission logic that `HTML-BACKEND-REFACTOR.md`'s own target
shape assigns to `attrs.py`:
`BEHAVIOR_PROP_ATTRS` (behavior/action attrs) and `_attr_string`
(where `data-ark-modifiers` gets serialized) both live there per that
doc's module table. Landing the HTMX attribute rewrite *before* the
`attrs.py` extraction means writing `hx-on:click`/`hx-trigger`
emission into the 580-line `render.py`, then moving it a few commits
later -- extra churn for no reason, the same "don't bake in today's
gaps" logic `HTML-BACKEND-REFACTOR.md` already applies to itself.
Landing the extraction first means the HTMX changes land directly in
`attrs.py`, once. Same reasoning applies to `htmx-4`'s app-shell
`hx-boost` audit and `page_render.py` (Stage 5) -- `_render_page` is
exactly where a shell-persistent-region audit has to happen, so that
extraction should land first there too.

## Merged staged order

| # | Stage | What | Source | Depends on | Status |
|---|---|---|---|---|---|
| 1 | `html-2` | Extract routing/asset-path resolution into `routing.py`; land the `UNROUTED_REFERENCE_ATTRS` reachability fix (`srcset`/`poster`/`action`/`formaction`) here or as an immediate follow-up commit. | `HTML-BACKEND-REFACTOR.md` "Staging" -> Stage 2 | none | **Done** |
| 2 | `refactor-0` | Split `arklight/backend/js/render.py`'s `_STATE_CORE_JS` into `arklight/backend/js/runtime/{state,bindings,modifiers,dispatch,nav,notify}.py`. Pure refactor, no output change. | `JS-BACKEND-REFACTOR-PLAN.md` staged table -> `refactor-0` | none | **Done** |
| 3 | `html-3` | Extract `PASSTHROUGH_ATTRS`/`PROP_ALIASES`/`BEHAVIOR_PROP_ATTRS`/`_style_dict_to_css`/`_attr_string` into `attrs.py`. **Sequenced here, ahead of `htmx-1`, so the HTMX attribute rewrite below lands directly in the new module** (see "Why the HTML split and the HTMX attribute changes collide" above) rather than in the file being split out from under it. | `HTML-BACKEND-REFACTOR.md` "Staging" -> Stage 3 | `html-2` (ordering convenience only, not a hard file dependency) | **Done** |
| 4 | `htmx-1` | Vendor HTMX; `attrs.py` emits `hx-on:click`/`hx-trigger` for named behaviors instead of `data-ark-on-click`; JS backend deletes `wireBehaviors()`/`_behaviors_block()`. Matched-pair change -- HTML and JS halves land in the same diff. | `HTMX-INTEGRATION.md` "Revised stage atomicity" -> Stage 1, and "Implementation ladder" -> Stage 1; `JS-BACKEND-REFACTOR-PLAN.md` staged table -> `htmx-1` | `html-3`, `refactor-0` | **Done** |
| 5 | `htmx-2` | `attrs.py` serializes `value.modifiers` as `hx-trigger` modifier syntax instead of `data-ark-modifiers`; JS backend deletes `arkApplyModifiers()`. Matched-pair change, same-diff constraint as `htmx-1`. | `HTMX-INTEGRATION.md` "Revised stage atomicity" -> Stage 2, "Implementation ladder" -> Stage 2; `JS-BACKEND-REFACTOR-PLAN.md` -> `htmx-2` | `htmx-1` | **Done** |
| 6 | `htmx-3` | JS-only: replace the `wireActions()` wiring loop with a single delegated interceptor dispatching into `ACTION_REGISTRY`. HTML-side `data-ark-action-*` attributes are unchanged, so no `attrs.py` work here. **Landed as a delegated native `click` listener (`wireActionInterceptor`), not the literally-described `htmx:beforeRequest` interceptor** -- see `arklight/backend/js/runtime/dispatch.py`'s module docstring for why that event doesn't fire for non-AJAX action buttons. | `HTMX-INTEGRATION.md` "Revised stage atomicity" -> Stage 3, "Implementation ladder" -> Stage 3; `JS-BACKEND-REFACTOR-PLAN.md` -> `htmx-3` | `htmx-2` | **Done** |
| 7 | `html-4` | Extract `_render_head_meta` into `head_meta.py`. Independent of the `htmx-*` track (no shared surface with behavior/modifier/action attrs) -- can be scheduled in parallel with rows 4-6 if convenient, but is listed here in file order. | `HTML-BACKEND-REFACTOR.md` "Staging" -> Stage 4 | `html-3` (ordering convenience) | **Done** |
| 8 | `html-5` | Extract `_render_bind`/`_render_children`/`_render_node`/`_render_page` into `page_render.py`. **Sequenced ahead of `htmx-4`**, for the same reason `html-3` precedes `htmx-1`: `_render_page` is where the app-shell/`hx-boost` audit below has to look. | `HTML-BACKEND-REFACTOR.md` "Staging" -> Stage 5 | `html-3`, `html-4` | **Done** |
| 9 | `htmx-4` | App-shell navigation. `Site(app_shell=True)` (the naming placeholder was kept -- no better name turned up) emits `hx-boost="true"` on `<body>`/shell container; `page_render.py` audited so shell-persistent regions (nav/header) survive a boosted swap via a new `shell_persistent=True` prop -> `hx-preserve="true"` (Validation requires a matching `id`, htmx's own requirement for `hx-preserve` to correlate old/new elements). The audit also surfaced and fixed two gaps a boosted swap opens that no prior stage had to consider: `needs_htmx` now also ships HTMX for `app_shell` alone (a plain nav-only page needs HTMX loaded for `hx-boost` to do anything, independent of behaviors/state), and page init (`highlightActiveNavLink`/`initState`/`renderBindings`/`renderClassBindings`) is extracted into a re-callable `arkInitPage()` wired to both `DOMContentLoaded` (unchanged) and htmx's own `htmx:afterSettle` (app_shell sites only), since a boosted navigation never refires `DOMContentLoaded`. A third, HTML-side gap: `hx-boost`'s default swap never updates `<body>`'s own attributes (confirmed against htmx's docs), so a state page's `data-ark-state` blob moves off `<body>` and into a swappable marker element when `app_shell=True` -- `initState()` (`runtime/state.py`) checks for it first, falls back to the `<body>` attribute otherwise. Solves the "app illusion" problem for the Android/KaiOS/Desktop packaging backends. | `JS-BACKEND-REFACTOR-PLAN.md` "The app-illusion problem, stated precisely" + staged table -> `htmx-4` (new stage, not in `HTMX-INTEGRATION.md`) | `htmx-3`, `html-5` | **Done** |
| 10 | `htmx-5` | Audit and remove any remaining hand-rolled plumbing in `arklight.js` that now duplicates HTMX. Document what stays (`createState`, `renderBindings`, `renderClassBindings`, `ACTION_REGISTRY`) and why. **The audit's actual finding cuts the other way**: `htmx-1`'s `hx-on:click="arkRunBehavior('<name>', this)"` turned out to route every named-behavior click through HTMX's own `Function`-from-string dispatch (`new Function("event", attributeValue)`, gated only by `htmx.config.allowEval`) -- an eval-equivalent operation this project's own stated invariant ("no eval, no new Function, no string ever executed as code" -- `arklight/backend/js/render.py`'s module docstring) doesn't permit, regardless of whether the string-executing code lives in ARKlight's own source or a vendored dependency's optional attribute-processing feature. Fixed by removing `hx-on:click` from ARKlight's output entirely: named behaviors now compile to `data-ark-on-click="behavior:<name>"` and dispatch through the same delegated `click` listener `htmx-3` built for `Action.*(...)` (`wireActionInterceptor` renamed `wireClickInterceptor`, gains a `behavior:` branch). `arkBehaviors`/`arkRunBehavior` (window-attached) are gone. Side effect: a behavior-only page (no `State(...)`) now ships no HTMX at all, since `hx-on:click` processing was the only reason it ever needed to. Defense-in-depth: `htmx.config.allowEval = false` is set whenever HTMX does ship, closing the remaining vendored-HTMX code paths (`hx-vals`/`hx-vars`, bracket-syntax `hx-trigger` filters) that construct a function from a string, none of which ARKlight's compiler emits into. See `arklight/backend/js/runtime/dispatch.py`'s module docstring for the full finding and `tests/test_htmx_5.py` for dedicated coverage. | `HTMX-INTEGRATION.md` "Implementation ladder" -> Stage 4; `JS-BACKEND-REFACTOR-PLAN.md` -> `htmx-5` | `htmx-4` | **Done** |
| 11 | `html-6` | Confirm (don't assume) whether `README.md`'s "Compiler pipeline" HTML Backend line still describes only external behavior, after rows 1-10 have changed what that backend actually does. Sequenced last on purpose -- it's a check against the *finished* state of the HTML backend, not the mid-refactor one. | `HTML-BACKEND-REFACTOR.md` "Staging" -> Stage 6 | `html-2`, `html-3`, `html-4`, `html-5` | **Done** |
| 12 | `vdom-4` | Computed/derived state (`Computed`/`DERIVATION_REGISTRY`). **Landed:** `arklight.api.Computed`/`Derive.*` (Python side already shipped in the prior commit -- `api.py`/`ast/nodes.py`/`ir/schema.py`/`ir/build.py`/`ir/validate.py`/`backend/html/page_render.py`) is completed on the JS side by a new `arklight/backend/js/derivations/` package (mirrors `actions/`: one `NAME`/`JS_FRAGMENT` module per `Derive.*` kind), `createState`/`initState` (`runtime/state.py`) recomputing every `Computed(...)` value -- in the dependency order `arklight.ir.build` already sorted at build time -- after every `set`/`reset` and once more at construction, and `render.py`'s `_collect_usage`/`_build_runtime_js` shipping only the derivation fragments a site's IR actually references (same "only ship what's used" discipline as `ACTION_FRAGMENTS`/`BEHAVIOR_FRAGMENTS`). No new markup pass: a `Computed(...)` value lives in the same state object a `State(...)` value does, so `Bind(...)`/`bind_class=` read it through the unmodified `renderBindings`/`renderClassBindings` passes. See `tests/test_vdom_4.py` for dedicated coverage. | `JS-BACKEND-REFACTOR-PLAN.md` staged table -> `vdom-4`; `docs/DESIGN-NOTES.md` `v0.044` | `refactor-0` | **Done** |
| 13 | `vdom-5` | Watch effects (`Watch(...)`). **Landed:** `arklight.api.Watch` (`then=Action.*(...)`) added alongside `Computed`/`Derive`; Validation (`_validate_watch_declaration`) requires a direct `Page(...)` child whose `name` resolves to a bindable `State(...)`/`Computed(...)` and whose `then` passes the exact same `_validate_action` check `on_click=Action.*(...)` already does (so `then` can only ever target a real `State(...)`); IR build (`_extract_page_state`) pulls `Watch(...)` nodes into a new declaration-ordered `IRPage.watch` field, each entry a JSON-serializable mirror of its `ActionRef` (`_action_ref_to_spec`); the HTML backend emits a sibling `data-ark-watch` attribute alongside `data-ark-state`/`data-ark-computed` on the same marker; and a new `arklight/backend/js/runtime/watch.py` (`wireWatchers`) is wired into `initState()` (guarded with `typeof wireWatchers === "function"` so a stateful page with no `Watch(...)` isn't broken by an undefined-function call) -- confirms this stage's own "verify against whatever htmx-3 leaves that dispatcher looking like" note: `wireWatchers` dispatches through the exact same `actions[...]` object `wireClickInterceptor` (`runtime/dispatch.py`, post-`htmx-5`) already reads, just from a `store.subscribe` callback instead of a click listener -- no new dispatch mechanism. `render.py`'s `_collect_usage`/`_build_runtime_js` fold a `Watch(...)`'s `then.action` into the same `used_actions` set an `on_click=` reference would (so the fragment ships whenever either needs it), while keeping `needs_actions_object` (ships `actions`) separate from `needs_click_interceptor` (ships the click listener) -- a watch-only page with no `on_click=`/named behavior anywhere ships `actions` without an unused click interceptor. The snapshot-before-dispatch ordering in `wireWatchers` keeps a self-referential `Watch(...)` (the "clamp a value back into range" case) bounded rather than an infinite loop -- see `tests/test_vdom_5.py`'s dedicated Node-subprocess coverage for both the dispatch-on-change and boundedness checks. | `JS-BACKEND-REFACTOR-PLAN.md` -> `vdom-5`; `docs/Foundational/DESIGN-NOTES.md` "Watch effects" | `vdom-4`, `htmx-3` | **Done** |
| 14 | `vdom-6` | Two-way input binding (`bind_value=` -> `data-ark-model`). **Landed:** `arklight.api.Bind.model(name)` (a thin, explicit spelling for a `State(...)` name -- `bind_value=` also accepts a plain string) added alongside `Bind.when(...)`; Validation (`_validate_model_bind`) requires the target to be a real `State(...)` name declared on the page, same restriction `_validate_action` already enforces for `Action.*(...)` targets (a `Computed(...)` has no independent value to write back into); the HTML backend (`attrs.py`) pre-fills `value=` from initial state the same way `bind_class` pre-fills `class_name` (an explicit `value=` prop wins), and compiles `bind_value=` to `data-ark-model="name"`; and a new `arklight/backend/js/runtime/model.py` ships `renderModelBindings(store)` (one more `store.subscribe` render pass, alongside `renderBindings`/`renderClassBindings`, comparing against the element's current `.value` first so a user's own keystroke doesn't get its cursor reset) and `wireModelBinding(getStore)` (one delegated `input` listener on `document`, same `Element.closest()` event-delegation pattern `wireClickInterceptor` uses for `click`, taking a zero-argument getter for the same "registered exactly once, survives an `app_shell` boosted navigation" reason `wireClickInterceptor` documents). `render.py`'s `_collect_usage`/`_build_runtime_js` gained a `has_model_binding` flag so both fragments are only shipped on a page that actually declares `bind_value=` somewhere -- same "only ship what's used" discipline `WIRE_WATCHERS_JS` already follows. Deliberately not routed through the vendored snabbdom core, same reasoning `renderClassBindings` already documents for `bind_class`: `.value` is DOM element state, not a vnode's own rendered children. Touches `attrs.py` too, same cross-backend shape as `htmx-1`/`htmx-2`. Sequenced after `htmx-4` deliberately: both a boosted-swap region and a two-way-bound `<input>` need the same answer to "what survives a partial DOM swap," and `htmx-4` settles that answer first. See `tests/test_vdom_6.py`'s dedicated Node-subprocess coverage for the state->value and value->state sync checks. | `JS-BACKEND-REFACTOR-PLAN.md` -> `vdom-6` and "Ordering rationale, stated explicitly" | `vdom-4`, `htmx-4` | **Done** |
| 15 | `vdom-7` | Per-item list rendering (`Repeat`) + conditional show/hide (`Show`); keyed-children routing through the vendored `patch()`. | `JS-BACKEND-REFACTOR-PLAN.md` -> `vdom-7`; `docs/new js backend proposal/ARCHITECTURE-VDOM.md` SS6.2-6.3 | `vdom-4`, `vdom-6` | Not started |
| 16 | `vdom-8` | `localStorage` persistence for `State(..., persist=True)`. | `JS-BACKEND-REFACTOR-PLAN.md` -> `vdom-8`; `docs/DESIGN-NOTES.md` Stage 8 | `vdom-7` | Not started |

## Gating condition, not a numbered stage: KaiOS/Gecko compatibility

Before `htmx-1` ships as something the KaiOS packaging backend
recommends enabling, it needs its own compatibility pass against
Gecko 48 -- vendored HTMX has not been checked against that engine
anywhere in this repo, unlike ARKlight's current hand-written
`arklight.js`. This does not block `htmx-1` itself (Android/Desktop
have no such constraint); it blocks *recommending* `app_shell=True`/
HTMX-dependent output to KaiOS builds specifically, which otherwise
keep the pre-HTMX hand-rolled dispatch path. See
`JS-BACKEND-REFACTOR-PLAN.md` "Cross-cutting risk: KaiOS/Gecko engine
compatibility" for the full reasoning, and
`docs/Backends/KAIOS-BACKEND-IMPLEMENTATION.md` SS6 for the existing
Gecko 48 verification this does *not* automatically extend to.

## Explicitly out of scope here

**Server-backed state streaming** (SSE/WebSocket-driven `State(...)`,
informed by the external `State-Driven-UI-Streaming-Prototype`
reference) is a later, separate, explicitly opt-in milestone with its
own version number and design doc -- not part of this merged order.
See `JS-BACKEND-REFACTOR-PLAN.md` "A later, separate, explicitly
opt-in milestone: server-backed state streaming" for what it would
need to be if scoped for real.

## Testing discipline

Unchanged from every source doc: `tests/test_html_backend.py` (HTML
rows) and the full JS-related suite (JS/HTMX/vdom rows) pass after
every stage, with one new test file per stage
(`tests/test_<stage>.py`), except where a stage is explicitly
documented as changing behavior (`html-2`'s `UNROUTED_REFERENCE_ATTRS`
fix; `htmx-1`/`htmx-2`'s attribute-shape change, which rewrites
assertions rather than leaving them "unchanged" per
`HTMX-INTEGRATION.md`'s own note on the 58 JS-related tests).
