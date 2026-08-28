# HTMX Integration

## What this document is

A design proposal for adopting HTMX as ARKlight's primary client-side
interaction runtime, replacing portions of the hand-rolled JavaScript
ARKlight currently generates in `arklight/backend/js/render.py`.

This is not a proposal to add server-backed behavior to ARKlight, and
it is not a proposal to expose HTMX to ARKlight users. It is a proposal
to use HTMX as an **internal implementation dependency** — the same way
ARKlight already vendors snabbdom's bare core for vdom diffing without
exposing snabbdom's API to anyone writing a site.

---

## The problem this solves

ARKlight's JS backend currently hand-rolls a client-side interaction
runtime from scratch:

- `wireBehaviors()` — a `DOMContentLoaded` wiring pass over
  `[data-ark-on-click]` elements, dispatching to a `behaviors` object
  (`toggle`, `scroll-to`, `copy`, `dismiss`).
- `wireActions()` — a parallel pass for `Action.*` state mutations,
  reading `data-ark-on-click` / `data-ark-action-state` /
  `data-ark-action-args` attributes and dispatching into the reactive
  store.
- `wireModifiers()` — event modifier handling (`prevent`, `stop`,
  `once`, `debounce:<ms>`, `throttle:<ms>`), a non-trivial piece of
  plumbing that HTMX ships battle-tested.
- `renderBindings()` / `renderClassBindings()` — DOM update passes
  driven by store subscriptions, currently routed through a vendored
  snabbdom core for diffing.

Each of these solves a problem HTMX has already solved — event
triggering, target selection, modifier handling, fragment
insertion — and solved it more thoroughly than ARKlight's bespoke
implementation can match without significant ongoing maintenance. The
goal of this proposal is to delegate that plumbing to HTMX, so
ARKlight's JS backend shrinks to only the things HTMX cannot and should
not do: the closed `STATE_REGISTRY` / `ACTION_REGISTRY`, the reactive
store, and class binding.

---

## What HTMX is, and what it is not here

HTMX is a MIT-licensed client-side library (< 15 kB minified + gzip)
best known for its `hx-get` / `hx-post` attributes that issue HTTP
requests and swap HTML fragments into the DOM. That is the use case
most people associate with HTMX. It is **not** what this proposal is
about.

HTMX also ships a complete, general-purpose client-side event and
interaction model:

- `hx-trigger` — declarative event triggering with modifiers (`once`,
  `throttle`, `debounce`, `prevent`, `stop`, `target`, `consume`).
- `hx-swap` — target selection and DOM update strategies.
- `hx-on:*` — declarative event handler wiring without inline JS.
- Custom event dispatch and inter-element communication via
  `htmx.trigger()`.
- A JavaScript API (`htmx.on`, `htmx.off`, `htmx.trigger`,
  `htmx.process`) usable entirely without HTTP requests.

This is the part of HTMX this proposal adopts. HTMX as a
**declarative interaction bus**, not as an HTTP client.

In this model, `hx-get` and friends are simply never emitted by
ARKlight's compiler. No HTTP requests are made unless a future,
explicitly opt-in milestone introduces them. The generated output
remains ordinary static files deployable without a server.

---

## Architecture

### Current

```
ARKlight Python API
        |
        v
    Compiler / IR
        |
        v
  arklight.js (hand-rolled)
  ├── wireBehaviors()
  ├── wireActions()
  ├── wireModifiers()
  ├── createState()
  ├── renderBindings()        ← via vendored snabbdom
  └── renderClassBindings()
        |
        v
      Browser
```

### Proposed

```
ARKlight Python API
        |
        v
    Compiler / IR
        |
        v
  HTML attributes (HTMX + data-ark-*)
        |
        +---------------------------+
        |                           |
        v                           v
  htmx.js (vendored, MIT)     arklight.js (slimmed)
  ├── event triggering         ├── createState()
  ├── modifier handling        ├── renderBindings()
  ├── target selection         ├── renderClassBindings()
  └── DOM update dispatch      └── ACTION_REGISTRY dispatch
        |                           |
        +---------------------------+
                    |
                  Browser
```

`htmx.js` handles the interaction plumbing. `arklight.js` handles
only what is specific to ARKlight's closed-registry reactive model.

---

## What HTMX replaces, concretely

### `wireBehaviors()` and `wireActions()`

Both are `DOMContentLoaded` wiring passes that read custom `data-ark-*`
attributes and attach click listeners. HTMX's `hx-trigger` and
`hx-on:click` declarative model replaces the manual wiring loop. ARKlight's
compiler emits HTMX attributes; HTMX processes them at load time. The
manual `document.querySelectorAll` / `forEach` / `addEventListener`
boilerplate goes away.

### `wireModifiers()`

HTMX's `hx-trigger` modifier syntax (`once`, `throttle:300ms`,
`debounce:300ms`) directly maps to ARKlight's `MODIFIER_REGISTRY`
entries. The hand-rolled modifier parsing and dispatcher wrapper in
`render.py` is replaced by HTMX's already-tested implementation.
`prevent` and `stop` map to standard HTMX trigger modifiers.

### Event dispatch between elements

Where ARKlight currently uses `CustomEvent` dispatch to coordinate
between a trigger element and a target, HTMX's `htmx.trigger()` and
`hx-trigger="custom-event from:body"` provide a cleaner, declarative
coordination model without hand-rolled event bus code.

### What stays in `arklight.js`

- `createState()` — ARKlight's reactive store. No HTMX equivalent;
  HTMX is stateless by design.
- `renderBindings()` — store-driven DOM text updates, routed through
  snabbdom for diffing. No HTMX equivalent for client-local state
  rendering.
- `renderClassBindings()` — `classList.toggle()` pass driven by store
  subscriptions. No HTMX equivalent.
- `ACTION_REGISTRY` dispatch — the closed `Action.set` /
  `Action.increment` / `Action.toggle_bool` / etc. logic. HTMX
  triggers the action; ARKlight's store executes it.

---

## HTMX as a client-local interaction target

HTMX's primary use case routes requests to a remote server. In
ARKlight's static use case, the same trigger/swap model routes to
**client-local targets** — elements already in the page, in-memory
state, or ARKlight's own action dispatcher — without any HTTP request.

The mechanism: `hx-trigger` fires; ARKlight registers an `htmx:beforeRequest`
handler that intercepts the event, dispatches into the `ACTION_REGISTRY`
or behavior handler, and cancels the network request. The DOM update is
performed by ARKlight's store subscription / `renderBindings` pass, not
by HTMX's swap machinery. HTMX contributes the triggering and modifier
infrastructure; ARKlight contributes the state and update logic.

For named behaviors (`toggle`, `scroll-to`, `copy`, `dismiss`) that
don't involve state, HTMX's `hx-on:click` wires directly to a small
behavior function without any custom event plumbing.

---

## Static build guarantee

HTMX must not appear in the generated output of a site that declares
no behaviors and no `State(...)`. The "only ship what's used" discipline
ARKlight already applies to `ACTION_REGISTRY` fragments and the snabbdom
core applies equally here.

Sites with no interactive features produce output with no HTMX, no
`arklight.js`, and no JavaScript of any kind beyond what the HTML
backend already emits. This is unchanged from the current behavior.

Sites with interactive features include a vendored `htmx.js` alongside
the slimmed `arklight.js`. Both are static assets; neither requires a
server.

---

## The optional server-backed path

Nothing in this proposal requires or introduces a server. The static
build is the default and remains the default.

If a future milestone introduces server-backed interaction (a feature
a site author must explicitly opt into), HTMX's `hx-get` / `hx-post`
attributes are already the correct mechanism — they are generated by
ARKlight's compiler, not written by the site author. ARKlight's IR
represents the intent; the web backend generates the HTMX attributes;
the site author never writes HTMX syntax directly.

That path is explicitly out of scope for this proposal. It is noted
here only to confirm that adopting HTMX now does not foreclose it
later — it enables it cleanly, at a future milestone that deserves its
own design.

Flask and FastAPI are not mentioned anywhere in this proposal's
implementation scope for the same reason: they belong to a future
opt-in milestone, not to the static interaction story.

---

## Dependency model

HTMX is MIT licensed. The MIT license permits vendoring, modification,
and redistribution provided the copyright notice and license text are
preserved. ARKlight already applies this discipline to snabbdom (MIT,
vendored, attributed in `arklight/backend/js/vdom.py`).

HTMX would be vendored under `arklight/backend/js/htmx.py` (the
minified source embedded as a Python string, same pattern as the
snabbdom vendor) with the MIT copyright notice preserved verbatim and
attributed in a module-level comment. ARKlight does not fork HTMX,
does not modify it, and does not redistribute it separately — the
vendored copy is emitted into the generated `arklight.js` output only
when a site's feature set requires it.

The version vendored is pinned by ARKlight's release. Updating the
pinned version is an intentional ARKlight maintenance act, not an
automatic resolution. This matches the project's general dependency
discipline (zero runtime dependencies in `pyproject.toml`;
anything vendored is a deliberate, auditable choice).

---

## Implementation ladder

Matching ARKlight's existing convention of staged, independently
reviewable work:

**Stage 1 — Vendor HTMX, replace `wireBehaviors()`.**
Vendor the HTMX minified source. Emit `hx-on:click` / `hx-trigger`
attributes from the HTML backend for named behaviors (`toggle`,
`scroll-to`, `copy`, `dismiss`). Delete `wireBehaviors()` from
`render.py`. All existing behavior tests pass against the new output.
No change to `wireActions()`, `createState()`, or the reactive core.

**Stage 2 — Replace `wireModifiers()`. -- IMPLEMENTED**
Map `MODIFIER_REGISTRY` entries to HTMX `hx-trigger` modifier syntax
at compile time. Delete the hand-rolled modifier parsing and dispatcher
wrapper. Modifier tests pass. `"prevent"` maps to no token (honored by
construction, unchanged from before this stage); `"stop"` maps to
HTMX's `consume` modifier. `wireActions()` itself no longer wraps its
dispatch through a modifier-aware function -- it now fires directly on
every click, so `debounce`/`throttle`/`once`/`stop` are compiled into
the page's markup but not yet functionally enforced until `htmx-3`'s
`htmx:beforeRequest` interceptor reads `hx-trigger` for real.

**Stage 3 — Replace `wireActions()` wiring loop. -- IMPLEMENTED**
Register an `htmx:beforeRequest` interceptor in `arklight.js` that
catches HTMX-triggered events, dispatches into `ACTION_REGISTRY`, and
cancels the network request. Delete the `wireActions()` loop. Action
tests pass. The reactive store and `renderBindings()` are untouched.

**Stage 4 — Audit and remove remaining hand-rolled plumbing.**
Review what remains in `arklight.js` after Stages 1-3. Remove any
plumbing that duplicates HTMX behavior. Document what stays and why.

Each stage is a standalone diff. No stage changes the ARKlight Python
API. No stage changes what a site author writes. The change is entirely
internal to the JS backend.

---

## What this is not

- Not a proposal to expose HTMX attributes in the ARKlight Python API.
  Site authors never write `hx-get`, `hx-trigger`, or any HTMX syntax.
  ARKlight's compiler generates those attributes from the IR.

- Not a proposal to add server-backed behavior. Static sites remain
  static. No Flask, no FastAPI, no server required.

- Not a fork of HTMX. ARKlight vendors the unmodified upstream release,
  attributes it correctly, and pins a version.

- Not a change to ARKlight's public API, component vocabulary, IR
  shape, or deployment story. The only thing that changes is what
  `arklight.js` contains and how the HTML backend annotates interactive
  elements.

---

## Design principles, stated explicitly

1. ARKlight is an SSG by default. HTMX does not change that.
2. Static builds must not require a server. HTMX must not introduce one.
3. HTMX is an implementation detail. The Python API describes intent;
   the compiler decides how to implement it.
4. The browser never executes Python. The browser never executes
   ARKlight. HTMX does not change either constraint.
5. Only ship what the site uses. A site with no interactive features
   includes no HTMX.
6. Vendor deliberately. Pin the version. Preserve the license notice.
7. The server-backed path is a future opt-in milestone. This proposal
   does not design it, and does not preclude it.

---

## JavaScript backend changes

A precise account of what changes inside `arklight/backend/js/render.py`
and adjacent modules, and what does not.

### Unchanged

The following remain untouched after all four implementation stages:

- `createState()` — ARKlight's reactive store. HTMX has no equivalent;
  HTMX is stateless by design.
- `renderBindings()` — store-driven DOM text updates routed through the
  vendored snabbdom core. No HTMX equivalent for client-local state
  rendering.
- `renderClassBindings()` — `classList.toggle()` pass driven by store
  subscriptions. No HTMX equivalent.
- `initState()` — reads `data-ark-state` from `<body>` and bootstraps
  the store. Unchanged.
- `_collect_usage()` — IR inspection determining which runtime features
  to ship. Gains HTMX detection (whether any behaviors or actions are
  present) but its existing logic is untouched.
- `_NAV_HIGHLIGHT_JS` — zero-configuration nav link highlighting.
  Unchanged.
- `_NOTIFY_JS` — runtime error notification. Unchanged.
- `ACTION_FRAGMENTS` — the closed `Action.set` / `Action.increment` /
  `Action.toggle_bool` / etc. implementations. Only the wiring
  boilerplate that connects click events to these functions is removed;
  the action logic itself is untouched.

### Removed by HTMX

**`wireBehaviors()` and `_behaviors_block()`**

The `behaviors` dispatch object and its `querySelectorAll` /
`forEach` / `addEventListener` wiring loop are removed. The
`_behaviors_block()` Python function that generates this JavaScript
string is removed alongside it.

The HTML backend instead emits HTMX attributes (`hx-on:click`,
`hx-trigger`) that HTMX processes declaratively at load time. The
manual wiring boilerplate is gone. `BEHAVIOR_FRAGMENTS` retains the
behavior logic (the actual `toggle`, `scroll-to`, `copy`, `dismiss`
implementations) but loses any wiring-specific scaffolding no longer
needed.

**`wireActions()` and its `addEventListener` loop**

The `querySelectorAll('[data-ark-on-click^="action:"]')` loop and its
per-element `addEventListener` / `data-ark-action-*` attribute reading
are removed. HTMX triggers the event; an `htmx:beforeRequest`
interceptor registered once in `arklight.js` reads the
`data-ark-action-*` attributes, dispatches into
`actions[name](store, stateKey, args)`, and cancels the request. The
per-element wiring loop becomes a single interceptor registration.

**`arkApplyModifiers()`**

The entire 60-line hand-rolled debounce / throttle / once / stop
implementation is removed. These map directly to HTMX `hx-trigger`
modifier syntax, compiled in at build time by the HTML backend:

| ARKlight `MODIFIER_REGISTRY` | HTMX `hx-trigger` syntax    |
|------------------------------|-----------------------------|
| `once`                       | `click once`                |
| `debounce:<ms>`              | `click debounce:<ms>ms`     |
| `throttle:<ms>`              | `click throttle:<ms>ms`     |
| `stop`                       | `click[...]` + HTMX default |
| `prevent`                    | honored by construction     |

This is the largest single reduction in hand-maintained code in the
file.

### Added

**HTMX vendored source inclusion**

`_build_runtime_js()` gains a conditional HTMX source block, emitted
before `arklight.js` content when `_collect_usage()` determines that
behaviors or state are present. Vendored under
`arklight/backend/js/htmx.py`, same pattern as
`arklight/backend/js/vdom.py`.

**`_htmx_interceptor`**

A small, static JavaScript block registered once via
`htmx.on('htmx:beforeRequest', ...)`. Reads `data-ark-action-*`
attributes from the event target, dispatches into the `actions` object,
updates the store, and calls `event.preventDefault()` to cancel the
outbound HTTP request. Replaces the per-element `addEventListener` loop
that `wireActions()` previously generated.

### `_build_runtime_js()` after

The runtime assembly order becomes:

```python
parts = [
    htmx_vendored_source,    # new — only when behaviors or state present
    _NOTIFY_JS,              # unchanged
    _SNABBDOM_CORE_JS,       # unchanged — only when has_state
    _actions_object,         # ACTION_FRAGMENTS unchanged
    _STATE_CORE_JS,          # createState / renderBindings /
                             # renderClassBindings / initState — unchanged
    _htmx_interceptor,       # new — single beforeRequest handler
    _NAV_HIGHLIGHT_JS,       # unchanged
    DOMContentLoaded block,  # simplified: initState, renderBindings,
                             # renderClassBindings only
]
```

The `DOMContentLoaded` block loses the `wireBehaviors()` and
`wireActions()` calls. `initState()`, `renderBindings()`, and
`renderClassBindings()` remain.

### HTML backend changes (`arklight/backend/html/render.py`)

The attribute emission logic changes shape. Currently emitted:

```html
data-ark-on-click="toggle"
data-ark-modifiers="debounce:300"
```

Replaced with generated HTMX attributes:

```html
hx-on:click="htmx.trigger(this, 'ark:toggle')"
hx-trigger="click debounce:300ms"
```

Modifier semantics are compiled into HTMX trigger syntax at build
time, not parsed at runtime. This change is entirely within the HTML
backend; the ARKlight Python API and the IR are untouched.

### Bundle size

| Condition              | Before         | After                        |
|------------------------|----------------|------------------------------|
| No interactivity       | No JS shipped  | No JS shipped — unchanged    |
| Behaviors only         | ~3–4 kB        | ~14 kB (HTMX) + smaller glue |
| State + actions        | ~3–4 kB + snabbdom | ~14 kB (HTMX) + snabbdom + smaller glue |

Interactive builds are somewhat larger. The runtime is substantially
simpler, more correct, and carries no ongoing maintenance burden for
modifier handling or event wiring. Non-interactive builds are
unaffected.

### Expected net reduction in `render.py`

Approximately 150 lines removed (`wireBehaviors`, `wireActions`,
`arkApplyModifiers`, `_behaviors_block`, associated comments). The
file gains a smaller HTMX inclusion block and the interceptor
registration. Net file length decreases; the remaining code is more
directly readable as "what ARKlight owns" rather than "general-purpose
event plumbing."

### Runtime responsibility boundary, stated explicitly

| Responsibility                        | Owner after HTMX    |
|---------------------------------------|---------------------|
| Event triggering                      | HTMX                |
| Modifier handling (debounce/throttle) | HTMX                |
| Target selection                      | HTMX                |
| Request interception                  | HTMX + interceptor  |
| State creation and mutation           | ARKlight            |
| DOM text binding (snabbdom)           | ARKlight            |
| Reactive class binding                | ARKlight            |
| Action dispatch                       | ARKlight            |
| Navigation highlighting               | ARKlight            |
| Runtime error notification            | ARKlight            |
| Compile-time validation               | ARKlight (unchanged)|

---

## Implementation structure and atomicity

### The matched-pair constraint

The HTML backend and the JS backend are not independent here. They form
matched pairs around every attribute they share:

- `html/render.py` emits `data-ark-on-click="toggle"`.
- `js/render.py`'s `wireBehaviors()` reads `[data-ark-on-click]`.

These two are a matched pair. Changing one without the other breaks the
site silently:

- Change the HTML backend to emit `hx-on:click` but leave
  `wireBehaviors()` in place → `wireBehaviors()` queries for
  `[data-ark-on-click]` elements that no longer exist and wires
  nothing. Behaviors stop working with no error.
- Delete `wireBehaviors()` but leave the old attributes → HTMX has
  nothing to trigger on. Same result.

The same constraint applies to modifiers: `data-ark-modifiers` and
`arkApplyModifiers()` are a matched pair. Neither can change without
the other.

This means the atomic unit of work is not per-file. It is per-pair.

### Revised stage atomicity

**Stage 1 — Behaviors (HTML backend + JS backend + HTMX vendor, together) -- IMPLEMENTED** (see CHANGELOG.md `[0.0497]`; `docs/Backends/REFACTOR-INDEX.md` row 4 `htmx-1`)

Three changes that must land in the same diff:

1. `html/render.py` emits `hx-on:click` / `hx-trigger` for string
   `on_click` behaviors instead of `data-ark-on-click`.
2. `wireBehaviors()` and `_behaviors_block()` deleted from
   `js/render.py`.
3. HTMX vendored in `arklight/backend/js/htmx.py` and included by
   `_build_runtime_js()` when behaviors or state are present.

Cannot be split. The HTML backend behavior attribute change *is* the
JS backend Stage 1 change, viewed from the other side.

**Stage 2 — Modifiers (HTML backend + JS backend, together) -- IMPLEMENTED** (see CHANGELOG.md; `docs/Backends/REFACTOR-INDEX.md` row 5 `htmx-2`)

Two changes that must land in the same diff:

1. `html/render.py` serialises `value.modifiers` as HTMX `hx-trigger`
   modifier syntax (`click debounce:300ms`) instead of
   `data-ark-modifiers="debounce:300"`.
2. `arkApplyModifiers()` deleted from `js/render.py`.

Cannot be split. Same matched-pair constraint as Stage 1.

**Stage 3 — Actions (JS backend only) -- IMPLEMENTED**

`data-ark-action-*` attributes on the HTML side are not changing —
the interceptor still reads them from the event target. The change is
entirely in `js/render.py`/`runtime/dispatch.py`: the `wireActions()`
loop is replaced by a single interceptor registration. This stage is
genuinely independent and can land on its own.

**Deviation from the design above, discovered during implementation:**
landed as a delegated native `click` listener (`wireActionInterceptor`,
`arklight/backend/js/runtime/dispatch.py`) rather than the
`htmx:beforeRequest` interceptor described earlier in this document.
`htmx:beforeRequest` is only dispatched by HTMX's own request path,
which requires a request-verb attribute (`hx-get`/`hx-post`/etc) --
something `Action.*(...)` buttons deliberately never carry, being
client-local state mutations rather than server requests. Wiring only
through that event would leave every action with no attached
modifiers (the common case, which also gets no compiled `hx-trigger`
from `htmx-2`) with no click handling at all. The delegated `click`
listener preserves both the "single registration, not a per-element
wiring pass" outcome and correctness for the unmodified-action case,
at the cost of not (yet) routing modifier timing through HTMX's own
trigger-spec parsing -- see `dispatch.py`'s module docstring for the
full reasoning and what remains a documented gap.

**Stage 4 — Audit and cleanup (independent)**

Dead code removal, comment updates, generated file header update.
Independent.

### Relationship to the HTML backend refactor

`docs/HTML-BACKEND-REFACTOR.md` and this document describe overlapping
work. The HTML backend refactor is not a prerequisite for HTMX
integration — the behavior and modifier attribute changes it covers
*are* HTMX Stages 1 and 2, from the HTML backend's perspective.

These two documents should be read together when planning Stage 1 and
Stage 2 implementation. Any diff that touches behavior or modifier
attribute emission in `html/render.py` is simultaneously an HTML
backend refactor change and an HTMX integration change. They are the
same commit.

### Realistic effort

| Stage | Scope | Estimate |
|-------|-------|----------|
| Stage 1 | Vendor HTMX, HTML behavior attrs, delete `wireBehaviors()` | 2–3 days |
| Stage 2 | HTML modifier attrs, delete `arkApplyModifiers()` | 1–2 days |
| Stage 3 | `htmx:beforeRequest` interceptor, delete `wireActions()` | 2–3 days |
| Stage 4 | Audit, cleanup, docs | 1 day |
| **Total** | | **6–9 days** |

The dominant cost is not the code changes — those are well-bounded.
The dominant cost is the test suite. 58 JS-related tests currently
pass. A significant subset assert on specific strings
(`wireBehaviors`, `wireActions`, `arkApplyModifiers`,
`data-ark-modifiers`) that will no longer exist after Stages 1 and 2.
Those tests are not wrong — they need to be rewritten to assert on the
new HTMX output shape while preserving the same behavioural guarantees.
That rewrite is the majority of the calendar time in each stage.

The fact that the rewrite cost is in the tests rather than the
implementation is a sign the existing coverage is thorough enough to
trust the refactor once they pass again.

---

## Native capability boundary

HTMX does not provide native Android or desktop capabilities itself.
Its role remains the client-side interaction layer. Native capabilities
are provided by ARKlight's optional Android and desktop backends.

The architecture is:

```text
ARKlight API
    |
    v
Compiler / IR
    |
    +-----------------------------+
    |                             |
    v                             v
HTML + CSS + HTMX          Native capability adapters
    |                             |
    v                             v
Web deployment              Android / Desktop
````

The same ARKlight application can therefore use a capability API without
requiring the site author to implement platform-specific JavaScript.

Examples of capabilities that may be provided by native backends:

* persistent application storage
* filesystem access
* native notifications
* system clipboard
* sharing
* camera and other device APIs
* background tasks
* application lifecycle events
* deep links
* desktop system-tray integration
* OS-level credential or secure-storage facilities

The web backend uses browser capabilities where available. Android and
desktop backends provide native implementations where browser APIs are
insufficient or unavailable.

### Capability abstraction

A future ARKlight API may describe capability intent rather than a
specific platform implementation:

```python
Share(...)
Notify(...)
Storage(...)
File(...)
Clipboard(...)
```

The compiler and selected backend determine how the capability is
implemented.

This keeps platform-specific functionality outside the core SSG model.
A normal static deployment remains ordinary HTML, CSS, and optional
HTMX. Packaging the same build through an Android or desktop backend
adds the corresponding native capability adapter.

HTMX therefore simplifies the interaction boundary without becoming the
native runtime. It handles declarative browser interaction and event
coordination; ARKlight's platform backends handle capabilities that only
exist or are substantially better implemented at the native layer.

### Optional local application bridge

For packaged Android and desktop applications, a future backend may
provide a local bridge between the generated page and the native
runtime.

```text
Generated ARKlight application
        |
        v
      HTMX
        |
        v
ARKlight capability interface
        |
        +------------------+
        |                  |
        v                  v
 Android adapter     Desktop adapter
        |                  |
        v                  v
 Android APIs          OS APIs
```

The bridge may operate entirely locally. It does not require the
application to become a conventional server-backed web application.

HTMX remains responsible for declaring and coordinating client-side
interaction. Native adapters handle operations that require platform
privileges or platform-specific APIs.

This preserves the primary ARKlight guarantee:

**Build for the web first. Package for native platforms when native
capabilities are actually required.**

The Android and desktop backends are therefore deployment targets and
capability providers, not alternative frontend frameworks.

```
