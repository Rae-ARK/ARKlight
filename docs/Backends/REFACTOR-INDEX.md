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
| 5 | `htmx-2` | `attrs.py` serializes `value.modifiers` as `hx-trigger` modifier syntax instead of `data-ark-modifiers`; JS backend deletes `arkApplyModifiers()`. Matched-pair change, same-diff constraint as `htmx-1`. | `HTMX-INTEGRATION.md` "Revised stage atomicity" -> Stage 2, "Implementation ladder" -> Stage 2; `JS-BACKEND-REFACTOR-PLAN.md` -> `htmx-2` | `htmx-1` | Not started |
| 6 | `htmx-3` | JS-only: replace the `wireActions()` wiring loop with a single `htmx:beforeRequest` interceptor dispatching into `ACTION_REGISTRY`. HTML-side `data-ark-action-*` attributes are unchanged, so no `attrs.py` work here. | `HTMX-INTEGRATION.md` "Revised stage atomicity" -> Stage 3, "Implementation ladder" -> Stage 3; `JS-BACKEND-REFACTOR-PLAN.md` -> `htmx-3` | `htmx-2` | Not started |
| 7 | `html-4` | Extract `_render_head_meta` into `head_meta.py`. Independent of the `htmx-*` track (no shared surface with behavior/modifier/action attrs) -- can be scheduled in parallel with rows 4-6 if convenient, but is listed here in file order. | `HTML-BACKEND-REFACTOR.md` "Staging" -> Stage 4 | `html-3` (ordering convenience) | **Done** |
| 8 | `html-5` | Extract `_render_bind`/`_render_children`/`_render_node`/`_render_page` into `page_render.py`. **Sequenced ahead of `htmx-4`**, for the same reason `html-3` precedes `htmx-1`: `_render_page` is where the app-shell/`hx-boost` audit below has to look. | `HTML-BACKEND-REFACTOR.md` "Staging" -> Stage 5 | `html-3`, `html-4` | **Done** |
| 9 | `htmx-4` | App-shell navigation. `Site(app_shell=True)` (naming placeholder) emits `hx-boost="true"` on `<body>`/shell container; `page_render.py` audited so shell-persistent regions (nav/header state) survive a boosted swap. Solves the "app illusion" problem for the Android/KaiOS/Desktop packaging backends. | `JS-BACKEND-REFACTOR-PLAN.md` "The app-illusion problem, stated precisely" + staged table -> `htmx-4` (new stage, not in `HTMX-INTEGRATION.md`) | `htmx-3`, `html-5` | Not started |
| 10 | `htmx-5` | Audit and remove any remaining hand-rolled plumbing in `arklight.js` that now duplicates HTMX. Document what stays (`createState`, `renderBindings`, `renderClassBindings`, `ACTION_REGISTRY`) and why. | `HTMX-INTEGRATION.md` "Implementation ladder" -> Stage 4; `JS-BACKEND-REFACTOR-PLAN.md` -> `htmx-5` | `htmx-4` | Not started |
| 11 | `html-6` | Confirm (don't assume) whether `README.md`'s "Compiler pipeline" HTML Backend line still describes only external behavior, after rows 1-10 have changed what that backend actually does. Sequenced last on purpose -- it's a check against the *finished* state of the HTML backend, not the mid-refactor one. | `HTML-BACKEND-REFACTOR.md` "Staging" -> Stage 6 | `html-2`, `html-3`, `html-4`, `html-5` | **Done** |
| 12 | `vdom-4` | Computed/derived state (`Computed`/`DERIVATION_REGISTRY`). | `JS-BACKEND-REFACTOR-PLAN.md` staged table -> `vdom-4`; `docs/DESIGN-NOTES.md` `v0.044` | `refactor-0` | Not started |
| 13 | `vdom-5` | Watch effects (`Watch(...)`), reuses the action dispatcher -- verify against whatever `htmx-3` leaves that dispatcher looking like. | `JS-BACKEND-REFACTOR-PLAN.md` -> `vdom-5` | `vdom-4`, `htmx-3` | Not started |
| 14 | `vdom-6` | Two-way input binding (`bind_value=` -> `data-ark-model`). Touches `attrs.py` too, same cross-backend shape as `htmx-1`/`htmx-2`. Sequenced after `htmx-4` deliberately: both a boosted-swap region and a two-way-bound `<input>` need the same answer to "what survives a partial DOM swap," and `htmx-4` settles that answer first. | `JS-BACKEND-REFACTOR-PLAN.md` -> `vdom-6` and "Ordering rationale, stated explicitly" | `vdom-4`, `htmx-4` | Not started |
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
