# JS Backend Refactor Plan, Staged

Status: **Design only -- not started.** Scope: `arklight/backend/js/`
(and, where the HTML backend must emit different attributes for it,
`arklight/backend/html/render.py` -- called out explicitly wherever
that's true, same discipline `docs/Backends/HTMX-INTEGRATION.md`
already follows).

## Why this doc exists

Three plans currently describe changes to the same JS runtime,
written independently and never reconciled into one execution order:

1. **Reactive-core vdom staging** (`docs/DESIGN-NOTES.md`) -- Stages
   1-3 DONE (vdom core, class binding, event modifiers), Stages 4-8
   PLANNING (computed/derived state, watch effects, two-way input
   binding, per-item list rendering, conditional show/hide,
   `localStorage` persistence).
2. **HTMX integration** (`docs/Backends/HTMX-INTEGRATION.md`) -- a
   4-stage plan to delegate `wireBehaviors()`/`wireModifiers()`/
   `wireActions()` to a vendored HTMX, shrinking the hand-rolled
   dispatch plumbing in `arklight/backend/js/render.py`.
3. **The packaging backends** (`docs/DESIGN-NOTES.md`'s Android
   section, `docs/Backends/KAIOS-BACKEND-IMPLEMENTATION.md`, and the
   `docs/Backends/NEUTRALINO-INTEGRATION.md` Desktop backend) -- all three wrap ARKlight's
   *existing* multi-page static output into a native shell, and all
   three implicitly assume that output behaves like an app once
   wrapped. It doesn't yet -- see below.

This doc reconciles those three into one staged order, and adds one
finding not previously written down anywhere in this repo: **HTMX
adoption isn't only an internal code-shrinking refactor -- inside a
packaged shell, it's the mechanism that makes ARKlight's output feel
like an app instead of a website loaded in a WebView.** That
reframes where in the sequence HTMX adoption belongs, and adds one
new stage HTMX-INTEGRATION.md didn't scope.

## The app-illusion problem, stated precisely

Checked directly against `arklight/backend/html/render.py`: ARKlight
today emits **real multi-page output**. Every route is a separate
static HTML file; `Link("About", href="/about")` compiles to a plain
`<a href="about.html">`; following it is a full browser navigation --
new document load, new `DOMContentLoaded`, the entire `arklight.js`
IIFE re-evaluated from scratch, and (critically) **any in-memory
`State(...)` on the page just navigated away from is gone**, because
`createState`'s store lives in that page's JS heap, not anywhere
persistent, unless that specific key opted into Stage 8's
`persist=True` -> `localStorage`.

For a plain static website opened in a normal browser tab, this is
completely fine -- it's how the web has always worked, and it's why
ARKlight is an SSG in the first place (see `HTMX-INTEGRATION.md`'s
own "Design principles": "ARKlight is an SSG by default"). The
problem only exists once that same output is wrapped in a shell whose
entire purpose is to *not* look like a browser:

- **Android** (`v0.0438`, PLANNING) packages the build into a
  `WebViewAssetLoader`-backed native app specifically to get a real
  origin and reliable storage -- see `docs/DESIGN-NOTES.md`'s own
  "why this sits after Stage 8, not after v0.044" reasoning. A user
  tapping between screens of that app and seeing a white-flash full
  reload on every tap is a worse experience than most native Android
  apps ship, and undermines the entire "installable, Play-Store-
  shippable" pitch.
- **KaiOS** (`docs/Backends/KAIOS-BACKEND-IMPLEMENTATION.md`) has this
  *more* acutely: §3 of that doc notes KaiOS's CSP already forces
  ARKlight's existing no-inline-script discipline, but full-page
  reloads on a Cortex-A7-class single/dual-core part (per
  `kaios-app-design-doc.md` §1) are not just a flash -- they're a
  real, felt multi-hundred-millisecond stall on hardware that
  document already establishes is GC-pause-sensitive at the
  200-300ms level for a single dropped frame. A KaiOS user expects
  D-pad-driven app navigation, not repeated document loads.
- **Desktop** (`v0.060`, not yet designed) has the same problem in
  spirit: wrapping static multi-page output in a desktop shell (Tauri
  or similar) and having every internal link cause a visible
  navigation defeats the point of shipping it as a desktop app rather
  than just telling the user to open a browser bookmark.

**None of the three packaging-backend docs currently propose fixing
this**, because it isn't their job to -- each of them, correctly,
only wraps an already-built `build-dir` (same "never touches
parser/ir/backend internals" boundary `arklight.packer` established).
The fix belongs in the JS backend, once, upstream of all three.

## Why HTMX adoption is the right mechanism for this, not a separate one

HTMX ships `hx-boost` specifically for this shape of problem:
attach it to a container (or `<body>`), and HTMX intercepts
same-origin link clicks, fetches the target page over AJAX, and swaps
the `<body>` in place with `history.pushState` -- from the user's
perspective, an in-app navigation with no full document reload, no
JS-runtime restart, and (this is the part that matters most for
ARKlight specifically) **no loss of any in-memory `State(...)` that
lives outside the swapped region** -- e.g. an app-shell header/nav
bar with its own state survives a "screen" change the way it would in
a real native app, exactly the gap identified above.

This is not a new dependency beyond what `HTMX-INTEGRATION.md`
already proposes vendoring for the interaction-bus work -- it's one
more attribute (`hx-boost="true"`) emitted by the same vendored copy.
That's the concrete reason this plan folds "fix the app-illusion
problem" into the HTMX track rather than treating it as a fourth,
independent initiative: the dependency is already paid for by
`HTMX-INTEGRATION.md`'s Stage 1, this just uses more of what that
stage already ships.

**Deliberately opt-in, not default.** `hx-boost` changes real,
observable behavior for a plain static website too (the URL bar still
updates via `pushState`, but network tooling, analytics-by-page-load,
and anyone relying on a genuinely fresh document per navigation would
see a difference). Proposed: a new `Site(app_shell=True)` (naming
placeholder) flag, defaulting to `False` -- unset, ARKlight's output
is byte-for-byte what it is today, real multi-page navigation, no
`hx-boost` anywhere. Set, the HTML backend emits `hx-boost="true"` on
`<body>` (or a designated shell container) and the packaging backends
(Android/KaiOS/Desktop) can each recommend --- but not require --- it
in their own scaffolding output, since it's specifically their use
case this exists for.

## Reconciled staged plan

Numbering kept deliberately loose (matching the existing `vdom-N`
convention in `PROGRESS.md`'s snapshot table, not a `v0.0XX` id) since
these are staged work on a shared mechanism, not new page-facing
milestones each deserving their own version number.

| Stage | What | Depends on | Status |
|---|---|---|---|
| refactor-0 | **Module split.** `arklight/backend/js/render.py`'s `_STATE_CORE_JS` (145+ lines: `createState`, `renderBindings`, `renderClassBindings`, `initState`, `arkApplyModifiers`, `wireActions`, all one triple-quoted string) splits into `arklight/backend/js/runtime/{state,bindings,modifiers,dispatch,nav,notify}.py`, mirroring the `actions/`/`behaviors/` per-file pattern already established. Pure refactor -- no output byte changes, no page-facing API change. Same "refactor before growing further" precedent the CSS and HTML backends already set at a comparable line count. | none | **Done** |
| htmx-1 | Vendor HTMX; replace `wireBehaviors()`. Per `HTMX-INTEGRATION.md` Stage 1. | refactor-0 | Not started |
| htmx-2 | Replace `wireModifiers()`/`arkApplyModifiers` with `hx-trigger` modifier syntax. Per `HTMX-INTEGRATION.md` Stage 2. | htmx-1 | Not started |
| htmx-3 | Replace `wireActions()`'s wiring loop with an `htmx:beforeRequest` interceptor into `ACTION_REGISTRY`. Per `HTMX-INTEGRATION.md` Stage 3. | htmx-2 | Not started |
| **htmx-4 (new)** | **App-shell navigation.** `Site(app_shell=True)` emits `hx-boost="true"`; HTML backend audited so shell-persistent regions (nav/header state) survive a boosted swap. This is the new stage this doc adds -- solves the app-illusion problem above. Each packaging backend doc gets a one-line cross-reference added once this lands. | htmx-3 | Not started |
| htmx-5 | Audit and remove remaining hand-rolled plumbing. Per `HTMX-INTEGRATION.md` Stage 4. | htmx-4 | Not started |
| vdom-4 | Computed/derived state (`Computed`/`DERIVATION_REGISTRY`). | refactor-0 | Not started |
| vdom-5 | Watch effects (`Watch(...)`, reuses the action dispatcher -- verify against whatever htmx-3 leaves that dispatcher looking like). | vdom-4, htmx-3 | Not started |
| vdom-6 | Two-way input binding (`bind_value=` -> `data-ark-model`). Touches the HTML backend too, same as htmx-4. | vdom-4 | Not started |
| vdom-7 | Per-item list rendering (`Repeat`) + conditional show/hide (`Show`). The two biggest remaining lifts per `docs/DESIGN-NOTES.md`'s own `v0.044` write-up; needs keyed-children routing through the vendored `patch()` (see `docs/new js backend proposal/ARCHITECTURE-VDOM.md` §6.2-6.3 for the keying/vnode-swap proposal this stage should implement against). | vdom-4, vdom-6 | Not started |
| vdom-8 | `localStorage` persistence for `State(..., persist=True)`. Real origin dependency -- blocks on nothing here directly, but is the reason the Android backend design is sequenced after it (`docs/DESIGN-NOTES.md`, "Why this sits after Stage 8"). | vdom-7 | Not started |

**Ordering rationale, stated explicitly:**

- `refactor-0` first because both tracks below touch the same file;
  splitting once avoids two large, unrelated diffs colliding in
  review.
- The `htmx-*` track runs before most of the `vdom-*` track because
  it *shrinks* `arklight.js` (deletes hand-rolled dispatch code) --
  landing it first means `vdom-4` onward is written against a smaller
  surface, not one that's about to have chunks deleted out from under
  it.
- `htmx-4` (app-shell navigation) is sequenced specifically before
  `vdom-6` (two-way input binding) because a boosted-swap region and
  a two-way-bound `<input>` both need the same answer to "what
  survives a partial DOM swap and what doesn't" -- solving it once at
  `htmx-4` means `vdom-6` inherits a settled answer instead of each
  needing to work it out independently.

## A later, separate, explicitly opt-in milestone: server-backed state streaming

Everything above is **local-only** -- no network request, no server,
matching every design principle `HTMX-INTEGRATION.md` already states
("Static builds must not require a server. HTMX must not introduce
one."). There is a genuinely different, larger capability worth
naming here so it doesn't get conflated with `htmx-4`'s app-shell
work: **server-driven state**, where a site's `State(...)` is updated
by a remote process rather than only by the user's own clicks.

This is informed by an external reference prototype --
[`State-Driven-UI-Streaming-Prototype`](https://github.com/Rae-ARK/State-Driven-UI-Streaming-Prototype)
-- built explicitly to de-risk this idea *before* ARKlight has to
implement it (its own `docs/reference/PROPOSAL.md` §13: "Prototype
the behavior before implementing the runtime"). It is a standalone
Vue 3 + Express project, not ARKlight code, and nothing from it is
proposed to be copied verbatim -- it's referenced here for its
validated architecture, not its implementation:

- **Two parallel paths fed from one server-side state object.** A
  "direct pipeline" (raw JSON over SSE, consumed reactively) and a
  "bus path" (per-field HTML fragments over SSE, swapped in by real
  htmx via `hx-ext="sse"` / `sse-swap`). Both read from the same
  state; neither is the source of truth for the other.
- **`ARKVM.js`: a per-field latency-driven promotion router.** Bus
  path is the default for every field (cheaper to wire, server does
  the rendering). The first time a given field's real swap latency
  crosses a fixed threshold, that field is detached from the bus and
  driven directly off the raw JSON stream instead -- a one-way valve,
  never demoted back, because in that cost model direct is never more
  expensive than bus per update. See that repo's `ARKVM.js` header
  comment for the full reasoning, and `PROPOSAL.md` §16 for what's
  actually implemented (Stage 1-2 of that project's own roadmap) vs.
  planned.
- **`FIELD_RENDERERS` is an explicit, named seam.** The prototype's
  own README states this hardcoded object is "a stand-in for what an
  ARKlight-style compiler would eventually emit from a state/intent
  contract" -- i.e., the prototype was built with ARKlight's eventual
  IR->runtime compilation step already in mind as the thing that
  would replace it, not as an incidental implementation detail.
- **§15 of that repo's proposal ("Application Runtime Hypothesis")**
  maps unusually well onto ARKlight's own Desktop backend (`v0.060`,
  undesigned): a packaged app that starts its own local state server
  and connects to it automatically is close to what "Desktop backend"
  could mean for anything beyond a static-file wrapper, and is worth
  reading before that backend's own design doc gets written, not
  after.

**What this milestone would need to be, if scoped for real:** the
`bus path` half maps directly onto `htmx-1`'s already-vendored HTMX
(`hx-ext="sse"`/`sse-swap` is the same dependency, more of it used);
the `direct pipeline` half maps onto ARKlight's existing
`createState`/`renderBindings`, pointed at a WebSocket/SSE source
instead of only local `Action.*` dispatch. Both are large enough, and
different enough in kind from everything above (they require a
*server*, which nothing in this doc's other stages do), that this
belongs as its own future milestone with its own version number and
its own design doc -- not silently folded into `vdom-*` or `htmx-*`
numbering. Flagged here as a validated direction, not committed
scope.

**Open questions this milestone would inherit from the prototype,
carried over rather than re-discovered:** the promotion threshold
(100ms in the prototype) is a placeholder, not a researched constant;
clock-skew (`Date.now()` vs. a server timestamp) is explicitly noted
there as unsafe across hosts without NTP; and per-field *render cost*
is not yet used as a routing signal, only per-field *churn/latency*
is -- cost-based static classification (which ARKlight, unlike the
prototype, could plausibly compute at compile time from the IR) is
future work the prototype's own doc names but doesn't attempt.

## Cross-cutting risk: KaiOS/Gecko engine compatibility

`docs/Backends/KAIOS-BACKEND-IMPLEMENTATION.md` §6 states ARKlight's
*current* hand-written `arklight.js` output runs on Gecko 48 (KaiOS
2.5) without transformation, verified against
`kaios-app-design-doc.md`'s engine notes. That verification does
**not** automatically extend to vendored HTMX -- HTMX's own minified
source is written and maintained against modern browser targets, and
has not been checked against a 2016-era SpiderMonkey build anywhere
in this repo. Before `htmx-1` ships as something the KaiOS packaging
backend recommends enabling, it needs its own compatibility pass
(either confirm HTMX's shipped build works unmodified on Gecko 48, or
document that `app_shell=True`/HTMX-dependent features are
Android/Desktop-only and KaiOS builds keep the pre-HTMX hand-rolled
dispatch path). Flagged here so it isn't discovered late, after
`htmx-*` has already landed as the only implementation.

## Testing discipline, carried over unchanged

Same convention every stage in this file inherits from the rest of
this codebase's history: one new test file per stage
(`tests/test_<stage>.py`), full existing suite green before a stage
is considered done, and no stage changes ARKlight's public Python API
unless explicitly noted (only `htmx-4`/`vdom-6` do, and only by adding
new optional constructor kwargs, never altering existing behavior for
sites that don't opt in).
