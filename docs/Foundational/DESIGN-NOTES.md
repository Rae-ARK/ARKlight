# Design Notes

Working notes on ARKlight's current ceiling and where it honestly sits
relative to other tools. Not a spec -- a record of reasoning, kept so
future milestone decisions don't re-litigate the same questions from
scratch. Fold new discussions in here as they happen.

## What `style={...}` can and can't reach (as of v0.003)

There's real headroom in the `style={...}` escape hatch that isn't
obvious at a glance: gradient text, `box-shadow` depth on `.card`-style
containers, and decorative inline SVG icons via
`Image(src="data:image/svg+xml...")` all work today, because they're
just CSS values or a data URI -- legal inside a plain `style="..."`
string or an `src="..."` attribute. No engine change needed to use any
of that.

**The real ceiling** is structural, not a matter of trying harder with
props:

- **No `:hover`/`:focus` styling on your own elements.** Inline
  `style=` has no pseudo-classes. You only get the free hover ARKlight's
  own stylesheet already puts on real `<a>`/`<button>` tags -- and even
  that gets clobbered if you also set an inline `color`.
- **No `@media` queries, `@keyframes` animations, or custom
  `@font-face`.** All of these need a `<style>` block or an additional
  `<link>` in `<head>`, and `Page` never renders anything into `<head>`
  except the title and the one fixed stylesheet (see
  `arklight/backend/html/render.py::_render_page`).
- **No JavaScript beyond the fixed `on_click` behavior vocabulary.**
  This isn't a gap to be closed casually -- it's the project's explicit
  non-goal ("the browser never executes Python," and nothing
  user-authored runs either). v0.003 added a *named, closed* set of
  behaviors (`toggle`, `scroll-to`) for exactly this reason: real
  interactivity without reopening that door to arbitrary strings.

None of these are hard blockers on any current milestone, but they're
the honest boundary of what a `style=`/`class_name=` prop can reach.
Custom fonts and responsive breakpoints in particular would need a real
`<head>` extension point on `Page` -- a plausible, scoped addition, not
yet on the roadmap.

## Vocabulary extension addendum: closing the vocabulary gap, not the structural ceiling

This addendum (folded into v0.003, not a new version) added ~46 component types (semantic layout, text-level
semantics, forms, tables, media) and two more closed JS behaviors
(`copy`, `dismiss`). It's worth being precise about what that does and
doesn't change against the ceiling described above, since it would be
easy to overstate:

**What it closes:** the earlier schema (`Page`, `Container`, `Heading`,
`Text`, `Button`, `Link`, `Image`, `List`, `Item`) couldn't express a
form, a table, a `<nav>`/`<header>`/`<footer>` landmark, an accordion,
or a code block without abusing `Container`/`Text`. That's a real gap
for "production grade" static sites -- a landing page with a contact
form or a docs page with a table couldn't be built at all. It's closed
now, and it's closed the way everything in this schema is: data added
to `arklight.ir.schema.SCHEMA`, not new compiler logic. Normalize,
validate, and build didn't change.

**What it doesn't close, confirmed against the v0.003 source, not
guessing:**

- **Still no `@media`/`@container` queries.** The new `.stack`,
  `.cluster`, `.sidebar`, `.switcher`, `.grid`, `.center`, `.reel`
  utility classes in the CSS backend are all *intrinsic* -- built from
  `minmax()`, `auto-fit`, `clamp()`, and `flex-basis` arithmetic that
  reads the container's own available width, never the viewport's.
  That's a genuine, well-established answer to "no breakpoints" (the
  pattern predates ARKlight -- see Every Layout's Stack/Cluster/
  Sidebar/Switcher/Grid primitives), but it is not the same feature as
  an explicit `@media (max-width: 600px) { ... }` rule, and there are
  real layouts (e.g. "hide this entirely on mobile," not just "let it
  reflow") that only an actual media query can express. `Page` still
  renders nothing into `<head>` beyond title + the one fixed
  stylesheet, so there's still no place to put one even if a user
  hand-wrote the CSS.
- **`copy`/`dismiss` are still closed-vocabulary, not "more state."**
  They extend the same fixed dispatch table `toggle`/`scroll-to`
  already used (`arklight.backend.js`'s `behaviors` object) -- no
  `eval`, no `new Function`, nothing user-authored ever executes. This
  is more surface area on the existing non-goal boundary, not a
  loosening of it.
- **`<details>`/`<summary>` sidesteps the JS ceiling rather than
  raising it.** It's a genuine, valuable addition (an accordion needs
  zero `on_click` wiring now), but it works because the *browser*
  ships the interactivity natively, not because ARKlight's runtime
  grew a new capability.

Net effect: v0.003 makes ARKlight capable of authoring the kind of page
a small business site or docs section actually needs (nav, forms,
tables, disclosure widgets, code samples), and gives it an honest,
non-hacky story for "responsive" within the no-breakpoints constraint.
It does not move the needle on the "who needs this" section below, and
it does not touch the reactivity/IR-state gap discussed later in this
document -- those remain the real forks in the road for v0.010/v0.100.

## Who actually needs this

A narrow but real slice of people, worth stating plainly rather than
overselling:

**Good fit:**
- Python developers who need a handful of static pages and don't want
  to touch HTML/CSS/JS directly -- internal tools, docs stubs, a
  landing page for a Python project, pages templated out of a script
  from data already in Python.
- People who value "boring and predictable" over "capable" -- no
  template language, no build toolchain, no npm, just functions
  returning functions.
- Teaching/learning contexts -- the compiler pipeline (AST -> IR ->
  backends) is small and readable enough to be a genuinely good "how
  does a compiler work" example, independent of whether anyone ships a
  real site with it.

**Not a fit today:**
- Anyone who needs interactivity beyond a closed, small behavior
  vocabulary (menus, toggles, scroll-to, copy-to-clipboard, dismiss --
  as of v0.003, `<form>`/`<input>` etc. can be *authored*, but there is
  still no client-side validation or submit handling; a `Form` posts
  like a plain HTML form always has, or goes nowhere without a real
  backend to receive it).
- Anyone who needs more than one page layout shape -- everything is
  still capped at a fixed-width column by default (the v0.003 `.stack`/
  `.cluster`/`.sidebar`/`.grid`/etc. utilities are opt-in per
  `class_name`, not a different default `Page` shape).
- Anyone who needs an explicit `@media` breakpoint rule (e.g. "hide
  entirely on mobile," not "reflow based on width") -- v0.003's
  intrinsic layout utilities cover a lot of the same ground without
  one, but they're not a substitute for every use of a real media
  query (see the v0.003 section above).
- Teams -- there's no component reuse mechanism yet beyond "write a
  Python function" (v0.010 on the roadmap), which is fine solo and gets
  messy with more than one contributor.

The honest positioning: a hobby-project-shaped tool at a
hobby-project-shaped maturity level. Legitimately pleasant for small,
personal, Python-only static sites; not a Jekyll/Hugo/Astro competitor
yet, and not trying to be at this stage.

## Is this "early Svelte"? No -- and being precise about why matters

Structurally, the origin story rhymes: a small, mostly-solo project.
But two things mattered more to Svelte's actual trajectory than "it
started small":

1. It sat mostly unnoticed for roughly two and a half years. What
   changed at v3 wasn't polish, it was a genuinely new technical
   insight -- compiling the framework away entirely (no virtual DOM,
   dramatically less shipped JS than React/Vue for equivalent UI) --
   that solved a pain the entire frontend world was actively feeling.
2. Svelte's author already had an audience and credibility from a
   previous framework and a bundler most of the JS ecosystem already
   used. That's not a repeatable ingredient by force of will.

ARKlight's pitch -- "write Python, get HTML, no template language" --
is a real ergonomic choice, but it isn't new. `htpy` already offers
plain-Python HTML construction with no template language. FastHTML
does the same and *already ships the JS-interactivity story* (via
HTMX) that ARKlight only started sketching in v0.003. Both are mature
in a niche ARKlight is only just entering.

**Where ARKlight might actually differentiate:** styled-by-default
output. None of htpy/FastHTML ship an opinionated default stylesheet
the way ARKlight's CSS backend does -- "beautiful with zero CSS
written" is a real, currently-unclaimed angle worth protecting as the
roadmap continues, more than trying to out-feature FastHTML on JS.

## Does reaching v0.010 (user components) change the comparison?

Only partially, and in a way that sharpens the distinction rather than
closing it. v0.010 would replace "write a Python function and call it"
(today's `nav()` pattern in the example site) with real composable,
reusable components -- closing real ergonomic ground with htpy/FastHTML,
and possibly bundling default per-component styling as a genuine
differentiator neither of those tools has.

What it does **not** touch: the actual reason Svelte broke out, which
is reactive UI with a minimal runtime. ARKlight's explicit non-goal is
no client-side runtime executing user logic at all. These aren't
different maturity points on the same axis -- they're different
categories of tool. Even fully built out per the current roadmap,
ARKlight's ceiling looks like a well-designed **Python-native static
site generator** (a Jekyll/Hugo analog), not a **UI framework**
(a Svelte/React/Vue analog). Reaching that second category would
require reintroducing exactly the kind of client-side state and
reactivity the whole project is currently built around avoiding.

## The "authoring layer that compiles to real frameworks" reframe

A sharper, and legitimate, alternative framing: ARKlight isn't trying
to be the frontend -- it's the Python-authoring layer in front of
*other* frontend frameworks, via `v0.100`'s planned Vue/Svelte
backends. There's real precedent: **Mitosis** (Builder.io) compiles one
component definition to React, Vue, Angular, Svelte, Solid, Alpine,
Qwik, and more, and is used in production for design-system syncing and
Figma-to-code pipelines. So "single authoring layer, many framework
targets" is a proven category, not a fantasy -- and it's a much better
answer to "who needs this" than competing with static-site generators
on static output alone.

**Why this changes difficulty, not just destination.** Mitosis's own
source components carry state (`useState`), event handlers
(`onChange`), and reactive bindings (`bind:value`) -- because that's
the substance that actually gets translated into each target
framework's own reactivity primitive (React's hooks, Vue's `ref()`,
Svelte's `let` assignments, Angular's `[attr.value]`). That reconciliation
across reactivity models is the hard part of a project like that, not
reformatting tags.

ARKlight's `IRNode` today is `type / props / children` -- full stop.
No state, no event bindings, no notion of "this changes." A
hypothetical `VueBackend` or `SvelteBackend` written against the
*current* IR could only emit `.vue`/`.svelte` files with a static
`<template>` and an empty `<script>` -- static HTML wearing a different
file extension, not "hooking into Vue or Svelte." Zero reactivity in,
zero reactivity out.

**The honest state of the architecture:** the Backend Interface itself
is genuinely ready for this -- `Backend.render(ir) -> {path: contents}`
doesn't care what the target is, and multiple backends already run over
the same IR today (HTML + CSS + JS, as of v0.003). **The IR is not
ready.** Before "v0.100 alternate backends" can mean more than a
novelty, the roadmap needs a milestone it doesn't have yet: adding
state and event semantics to both the Python API and the IR itself
(something like `State(0)`, `on_click=increment` referring to a real
state mutation rather than a fixed behavior name, and
runtime-aware conditional/list rendering instead of Python-side-only
control flow). That's plausibly a bigger lift than everything shipped
through v0.003 combined -- it's the same cross-framework
reactivity-model reconciliation that makes Mitosis's own codebase
non-trivial, and Mitosis starts from JSX, already one hop from any JS
framework. ARKlight would be doing that reconciliation starting from
Python semantics, which is a bigger conceptual jump.

This doesn't make the reframe not worth pursuing -- it means "assuming
this reaches v0.010" doesn't get meaningfully closer to it by itself.
The missing piece for that vision isn't component reuse, it's
reactivity, and that deserves its own named milestone rather than being
assumed inside v0.100.

## v0.0035 / v0.048 design: stateful JS, CLI scaffolding, responsive + head extension (v0.0035 + v0.004a DONE, v0.048 PLANNING)

This section is a design doc, written before any of it is built, so the
shape gets agreed on before code exists (same discipline as the
Alpine/htmx-vs-Reflex research that preceded v0.003). Status has moved
on since it was written -- see PROGRESS.md for what's actually landed
(v0.0035 and the CLI-scaffolding half of what was originally called
"v0.004" are both DONE; the CSS `@media`/`<head>` half is renumbered
v0.048 and still PLANNING).

Three initiatives, originally staged as two named milestones so this
didn't land as one undifferentiated grab-bag:

- **v0.0035 -- Stateful JS (DONE).** The breadcrumb for this already
  exists in the v0.003 commit history ("Next is adding states in
  V0.0035"). This is the reactivity/IR-state milestone this document
  has been calling the real prerequisite for v0.100 (alternate
  backends) to mean anything.
- **v0.004a -- CLI scaffolding (DONE).** Shipped independently of
  state landing first.
- **v0.048 -- responsive/head extension (PLANNING).** The other half
  of the original "v0.004" grouping; renumbered once v0.004a shipped
  ahead of it. Still not implemented.

### v0.0035: stateful JS -- capability, not vocabulary

Explicit constraint from the person requesting this: don't add new
*named* behaviors (no `increment`, no `fetch-submit`, etc. yet) --
make the **compiler** capable of arbitrary future client-side behavior,
so new vocabulary later is additive data, not a compiler rewrite. Two
separate refactors accomplish this:

**1. Behaviors become a registry, not a hardcoded dispatch table.**
Today `KNOWN_BEHAVIORS` (`arklight/ir/schema.py`) is a flat
`frozenset`, and `RUNTIME_JS` (`arklight/backend/js/render.py`) is one
hand-written JS string with an if/else-shaped `behaviors` object
inside it. Both become data:

- `KNOWN_BEHAVIORS: frozenset[str]` -> `BEHAVIOR_REGISTRY: dict[str,
  BehaviorSpec]`, where `BehaviorSpec` names optional extra props
  (e.g. `toggle_class`) the same way `NodeSpec` already documents
  required props for HTML components. `KNOWN_BEHAVIORS` stays as a
  derived `frozenset(BEHAVIOR_REGISTRY)` so Validation's existing
  check doesn't need to change shape.
- The JS runtime is assembled from small per-behavior fragments
  (`arklight/backend/js/behaviors/*.py`, one dict entry each: name ->
  JS function body as a string) instead of one monolithic
  hand-maintained string. `JSBackend.render()` concatenates only the
  fragments actually referenced by the site's IR (a real, if small,
  step towards the "future pass emitting only used behaviors" already
  flagged as a follow-up in PROGRESS.md).
- This alone adds zero user-facing vocabulary. It's the refactor that
  makes "add one more behavior later" a one-file, additive change
  instead of touching a hand-maintained JS string and its Python
  dispatch in lockstep.

**2. A real `State` primitive in the IR, with a closed *action*
vocabulary instead of a closed *behavior name* vocabulary.**

- New API: `State("count", 0)` -- declared inside `Page(...)`, becomes
  a `state: dict[str, Any]` field on the IR's `Page` node (not a prop
  on some other node; state belongs to the page, same way `title`
  does today).
- New API: `Bind("count")` -- usable anywhere a literal prop value is
  accepted today (`Text(Bind("count"))`, later `class_name=Bind(...)`
  for conditional classes). Marks "this value tracks state `count`" in
  the IR instead of being a static string. Validation checks every
  `Bind(...)` references a `State(...)` actually declared on that
  page, same "catch it at compile time" guarantee the rest of
  Validation already provides.
- New API: `Action.set(name, value)`, `Action.increment(name,
  delta=1)`, `Action.toggle_bool(name)` -- structured objects, not
  strings, passed to `on_click=` (or a future `on_change=`, etc.)
  alongside or instead of today's behavior names. Still a **closed,
  described vocabulary** -- never an arbitrary JS/Python string, so
  "the browser never executes anything ARKlight didn't ship" stays
  true. What's different from today's `KNOWN_BEHAVIORS` is that
  actions are driven from `ACTION_REGISTRY` (same registry pattern as
  behaviors above), so *this* project can add `Action.append_to_list`,
  `Action.set_from_input`, etc. later as pure data, without whoever
  writes those later needing to touch `JSBackend`'s generation logic.
- `JSBackend` emits, only for pages that declare `state`, one small
  fixed reactive core: a `createState(initial)` closure, a
  `data-ark-bind="count"` -> re-render wiring pass, and an action
  dispatcher that walks `ACTION_REGISTRY` the same way the existing
  behavior dispatcher walks `BEHAVIOR_REGISTRY`. Still one static,
  fully-readable runtime file. Still no `eval`, no `new Function`, no
  string ever executed as code -- the extensibility is in the
  registries being open to new *data*, not in the runtime becoming a
  general-purpose interpreter.
- Net result, matching the actual ask: "any kind of JS API which can
  be built in the future" becomes possible by adding registry entries
  (new `BehaviorSpec` / `ActionSpec` + a JS fragment), not by changing
  `normalize.py`/`validate.py`/`build.py`/the `Backend` interface --
  exactly the same "grow as data" discipline the two vocabulary
  addenda already established for HTML components, applied to JS for
  the first time.

### v0.0035: stateful-JS vocabulary addendum I

Once the registry/capability refactor above landed, growing the
*vocabulary* itself is meant to be additive data -- same discipline as
the two HTML vocabulary addenda already applied to `SCHEMA`. This is
the first time that's been exercised for `ACTION_REGISTRY`: two new
entries, picked for being the gaps real usage hits almost immediately
rather than a speculative full list.

- **`Action.decrement(name, delta=1)`.** `increment` shipped without
  its natural counterpart. Routing a `-1` button through
  `Action.increment(name, delta=-1)` works, but it's a footgun by
  omission (nothing stops the sign from being wrong, and it's not the
  obvious way to decrement) -- a counter demo needs both buttons about
  as often as it needs either one.
- **`Action.reset(name)`.** Puts a state key back to the value it was
  declared with in `State(...)`, without the call site hardcoding that
  value a second time (and needing an edit at every call site if the
  initial value ever changes). Implemented as a `reset(key)` method on
  the reactive core's `createState` closure -- it reads the store's own
  captured `initial` snapshot, not a value threaded through from
  Python -- so the action fragment itself (`arklight/backend/js/actions/reset.py`)
  is a one-line call into the core, same shape as every other action.

Both are additive: new `ACTION_REGISTRY` entries, new
`arklight/backend/js/actions/*.py` fragment modules, new `Action.*`
static methods on `arklight.api.Action`. No change to
`normalize.py`/`validate.py`/`build.py`/`JSBackend`'s generation logic,
confirming the registry refactor's actual point.

**Deliberately left for a future version, not included here** (this
addendum is intentionally the *most commonly needed* two, not an
exhaustive pass):

- List actions (`Action.append`, `Action.remove`) -- addressed in
  addendum II directly below.
- Derived/computed state (a value computed from other state keys,
  re-evaluated on every change) -- changes what `createState` *is*,
  not just what actions exist.
- `Action.set_from_input` / binding a state key directly to a form
  control's value on `input`/`change` (not just `click`) -- needs an
  `on_change=`-shaped prop family, not just a new action name.
- Debounced/throttled actions -- a timing concern orthogonal to what
  an action does, better solved once as a wrapper than duplicated per
  action.

### v0.0035: stateful-JS vocabulary addendum II

Second growth pass on `ACTION_REGISTRY`, same mechanism as addendum I
above. Where addendum I filled the two most obvious gaps in *scalar*
state actions, addendum II is the first to touch **list-valued**
state -- `State("items", ["milk", "eggs"])` -- rather than assume
every state key is a number/bool/string.

- **`Action.append(name, value)`.** Appends one value to a
  list-valued state key. Implemented as `store.set(key,
  list.concat([args.value]))` -- goes through the existing `set`
  mechanism on the store, not a new store method, so the change stays
  inside the action fragment (`arklight/backend/js/actions/append.py`)
  rather than touching `createState` itself.
- **`Action.remove(name, index)`.** Removes the element at `index`
  from a list-valued state key, via `list.filter(...)`. Deliberately
  index-based, not value-based: a value-based `remove` would need an
  equality rule for objects/lists (reference equality? deep equality?)
  that index-based removal sidesteps entirely, and "remove the Nth
  item in a rendered list" is the actual common case (e.g. a rendered
  list where each item already knows its own index).

**What made this scoped-and-shippable rather than the "needs its own
design pass" addendum I deferred it as:** the *rendering* half turned
out to need zero new work. `renderBindings`'s `el.textContent =
store.get(key)` was written assuming a scalar, but handing it an array
just invokes JS's own `Array.prototype.toString()` (elements joined by
commas) -- not pretty, but a real, working display for something like
a tag list or an item count, with no change to `Bind`, `data-ark-bind`,
or `renderBindings` at all. That's what kept this a same-shape
registry-entry addendum instead of a rendering-pipeline redesign.

**What's still explicitly out of scope, and why it stays that way:**

- **Per-item list rendering/templating** -- one `<li>` per item, each
  with its own wired-up remove button referencing its own index. This
  is the real remaining gap for a production todo-list/tag-editor
  style UI, and it's a materially different feature: it needs the
  compiler to emit a template *per item* and re-render that template
  set on every change, not just re-run `renderBindings` over a single
  bound element. Comma-joined display is a stopgap, not the end state.
- **Derived/computed state, `Action.set_from_input`,
  debounced/throttled actions** -- unchanged from addendum I's
  reasoning above; still bigger-than-a-registry-entry design work.

### v0.004a: CLI scaffolding (`arklight new`) -- DONE

```
arklight new <name> [--template simple|production] [--dir PATH]
```

- **`simple` (default).** Beginner-shaped: a single `site.py` with one
  or two inline pages, mirroring `examples/hello_site/` almost
  exactly. Goal: zero-thinking path from `arklight new my-site` to a
  working `arklight build` with nothing to wire up.
- **`production`.** Mirrors Product-Showcase's proven layout --
  `site.py` + `components/` + `pages/` + `content/` + `assets/` -- and
  bakes in fixes for the real gotchas that project's `architecture.md`
  documented from actually building a six-page site, rather than
  re-documenting them in a README for the next person to hit:
  - `site.py` is generated with every page wrapped in a real
    `@site.page("/route")` decorator (never the equivalent call form),
    since static discovery only recognizes the decorator.
  - Scaffolded `components/__init__.py` / `pages/__init__.py` /
    `content/__init__.py` exist up front so the package-shaped layout
    imports cleanly from line one.
  - The generated README documents the `cp -r assets dist/assets` step
    -- *and*, as a companion fix independent of scaffolding (this is a
    real gap, not a template-only concern): `arklight build` itself
    should auto-copy a top-level `assets/` folder into `dist/assets`
    when one exists, so the 404-images gotcha stops being possible by
    default instead of merely being documented.
  - Fold in the other real bug Product-Showcase's `architecture.md`
    found: `arklight/__init__.py` is missing the second vocabulary
    addendum from its `from arklight import *` surface (`Picture`,
    `OrderedList`, `Dialog`, etc. importable only via
    `arklight.api`). This is a pre-existing correctness bug, not new
    scope -- worth fixing alongside scaffolding since a fresh
    `production`-template project would hit it immediately.
- No templating dependency -- an in-package dict of relative path ->
  file contents (f-strings), consistent with "no runtime dependencies
  beyond the build backend."

**Update -- both now implemented as v0.042, see the "v0.042" section
below for the final design (which differs slightly from what's
sketched here: this is left in place per this file's own convention of
correcting in place rather than deleting):** two CLI helpers oriented
at discoverability once the component vocabulary is ~80+ names deep (a
real problem `arklight new` alone doesn't solve -- scaffolding gets
someone started, it doesn't help them remember `Picture`'s required
props six months later):

- `arklight --help` -- standard CLI usage/help text (subcommands,
  flags, short description of each).
- `arklight --search <name>` -- looks up a component by name in
  `arklight.ir.schema.SCHEMA` (the single source of truth every stage
  already reads from) and prints its schema back: required props,
  whether it allows children, text-only-children rule, and (once
  v0.0035 lands) whether it's a `Bind`-able target. A read-only
  reflection tool over data that already exists -- no new schema
  format, no new source of truth, just a formatter over `SCHEMA`.

Both are additive CLI surface only; neither touches the compiler
pipeline, the IR, or any backend.

### v0.048: CSS media queries + `<head>` extension (Stage A IN PROGRESS)

(Renumbered from the original "v0.004" combined heading once the CLI
scaffolding piece of that heading shipped separately as v0.004a --
see `PROGRESS.md`/`CHANGELOG.md`. Design below is unchanged from when
it was first written.)

Implementation started ahead of v0.044 in the announced roadmap order
(README/ARCHITECTURE previously said v0.044 next) -- same
out-of-sequence precedent as v0.0438 being cross-referenced rather
than strictly ordered; see `PROGRESS.md` ("v0.048 -- Stage A") for the
narrative record of why. Landing as two independent stages, each its
own tagged sub-version, so "structured `<head>` extension" and
"`@media` responsive styling" can each be reviewed/tested/shipped on
their own rather than as one large patch:

- **Stage A -- structured `<head>` extension (`meta`/`links` on
  `Page(...)`).** IN PROGRESS.
- **Stage B -- `@media` responsive styling (`responsive_style` prop +
  `CSSBackend` compilation).** DONE -- see `PROGRESS.md` ("v0.048 --
  Stage B") for the implementation record. Landed independently of
  Stage A as planned; sequenced second in this document only to keep
  each patch reviewable in isolation, not because it depended on
  Stage A landing first.

- `Page(...)` gains optional, *structured* extension points --
  deliberately not a raw HTML-injection escape hatch, to avoid
  reopening the "no arbitrary strings" boundary the rest of the
  project holds: `meta: dict[str, str] | None` (name/content pairs)
  and `links: list[dict] | None` (for `<link rel="preconnect">`,
  webfonts, icons -- each dict is attribute name -> value, rendered as
  a `<link ...>` tag). `head_html`-as-raw-string is explicitly
  rejected for the same reason arbitrary `on_click` JS strings were
  rejected in v0.003.
- Responsive styling extends the existing `style={...}` convention
  instead of a new component type: an optional `responsive_style:
  dict[str, dict[str, str]]` prop, where each key is a raw media
  condition (e.g. `"(max-width: 600px)"`) and each value is a normal
  CSS-property dict. `CSSBackend` compiles each into a real `@media
  (...) { .arkgen-N { ... } }` rule, auto-generating a scoped class
  per node the same way today's inline `style=` handling already
  needs a per-node identity. This finally allows a real breakpoint
  ("hide entirely on mobile"), which `docs/DESIGN-NOTES.md` has
  flagged since v0.003 as something the intrinsic-layout utilities
  cannot substitute for.
- Explicitly deferred, not silently dropped: `@keyframes` animations
  and `@font-face` custom fonts. Both are bigger design questions
  (asset handling for font files, keyframe-name collision rules) with
  no concrete ask yet -- noted here so they don't get assumed-in-scope
  later.

### v0.049: CSS selector algebra + at-rule vocabulary (IMPLEMENTED)

Closes the remaining structural gaps a user audit of the CSS backend
turned up against the ceiling described at the top of this file and in
v0.048's "explicitly deferred" note just above: pseudo-elements,
parameterized pseudo-classes (`:not()`, `:has()`, `:is()`, `:where()`,
`:nth-child()`), attribute selectors, combinators, grouped selectors,
bare tag-selector overrides, `@keyframes`, `@font-face`, `@container`,
`@supports`, and `@page`. `@import` (raised in the same audit as
"reachable indirectly via `Page(links=[...])`, but no direct
mechanism") is included too, for the case that indirection doesn't fit.

Every one of these lands the same way v0.048 Stage A/B and the two
stateful-JS vocabulary addenda above already do: **a closed grammar or
a closed registry, never a raw-CSS-string escape hatch.** That's worth
being explicit about, since "close the remaining CSS gaps" could
easily have meant "add an `Site.raw_css(text: str)` passthrough" --
the fastest way to get 100% parity, and exactly the kind of shortcut
this project has consistently declined elsewhere (`on_click`'s closed
behavior registry instead of `eval`; `meta`/`links` instead of
`head_html`; `ALLOWED_PSEUDO_CLASSES` instead of accepting any pseudo-
class string). Two new closed-vocabulary mechanisms do the actual work:

- **A real (if intentionally small) selector parser**
  (`arklight/backend/css/selectors.py`). `Site.style(name, rules)`
  stays exactly as it was -- one flat `.name { }` block, unchanged --
  because it's still the right tool for "give this class some rules."
  The new **`Site.style_selector(selector: str, rules: dict) -> None`**
  is for everything `style()` structurally can't express: combinators
  (`.a > .b`, `.a + .b`, `.a ~ .b`, `.a .b`), grouped selectors (`h1,
  h2, h3`), a bare tag override (`blockquote { ... }`, no
  `class_name=` needed on every node), attribute selectors
  (`[type="email"]`), pseudo-elements (`::before`, `::after`,
  `::placeholder`, `::selection`, `::marker`, `::first-line`,
  `::first-letter`), and parameterized pseudo-classes (`:not(.a)`,
  `:is(...)`, `:where(...)`, `:has(...)` -- including `:has()`'s
  CSS-spec-sanctioned relative form, `:has(> .icon)` -- and the
  `:nth-child()` family with real An+B micro-syntax validation, not
  just a regex ban-list). `selector` is parsed into a validated AST by
  `parse_selector_list`, which raises `CSSSelectorSyntaxError` (a
  `ValueError` subclass, same posture as `api.CSSSyntaxError`) for
  anything outside the grammar -- a bare tag must be a real tag
  ARKlight's HTML backend can emit (`KNOWN_HTML_TAGS`, kept in sync
  with `arklight.backend.html.render.TAG_MAP`'s values by hand, copied
  rather than imported to avoid a load-order cycle between the two
  backends), an attribute value must be quoted and free of injection
  characters, and a pseudo-class/pseudo-element name must be in one of
  the fixed sets. `render_selector_list` then turns that AST back into
  canonical CSS text, so the stylesheet only ever contains what was
  actually validated -- never the caller's original string verbatim.
  One deliberate, documented simplification: CSS's real `&` nesting
  syntax isn't emitted; instead, a `&`-prefixed key in `rules`
  (`"&:hover"`, `"& .child"`, `"& > .child"`, `"&.active"`,
  `"&[data-open]"`) is desugared at author time into its own
  fully-resolved selector, which keeps the generated CSS working in
  browsers that predate real nesting support, at the cost of only
  supporting one level of "parent" (a grouped base selector like `"h1,
  h2"` can't be nested against -- register each branch separately, the
  same "ambiguity forces a scope line" call `:has()`'s relative-form
  restriction to functional pseudo-classes makes on the parser side).
- **Five new closed-vocabulary `Site` methods for the at-rules
  `style()`/`style_selector()` can't reach**, all in `arklight/api.py`,
  all rendered by new pure functions in the new
  `arklight/backend/css/at_rules.py` (same "structured data in, CSS
  text out, no re-validation of its own" contract
  `custom_styles.py`'s `render_*` functions already keep):
  - **`Site.keyframes(name: str, frames: dict[str, dict[str, str]])`**
    -- a real `@keyframes name { ... }` block. `name` is a CSS
    custom-ident; each `frames` key is `"from"`/`"to"`/a percentage,
    validated against a fixed pattern, and stops are always re-sorted
    (from -> ascending % -> to) regardless of dict insertion order, so
    output is deterministic. `transition`/`animation` themselves
    already worked as plain `style=` values -- this only adds the
    missing "define what to animate *through*" half.
  - **`Site.font_face(family: str, src: str | list[dict], **descriptors)`**
    -- a real `@font-face { ... }` block, for a self-hosted webfont
    (an external one was already reachable indirectly via
    `Page(links=[{"rel": "stylesheet", "href": ...}])`, which still
    stays the better option for that case). `src` is a url string or a
    list of `{"url": ..., "format": ...}` dicts for a fallback chain;
    `format`, when given, must be one of `ALLOWED_FONT_FACE_FORMATS`
    (the real `format(...)` keywords browsers recognize). Extra
    keyword args become other descriptors (`font_weight=`,
    `font_display=`, ...), underscore-to-hyphen same as
    `style={...}`'s existing convention.
  - **`Site.container_query(condition: str, selector: str, rules: dict, *, name: str | None = None)`**
    -- a real `@container name? (condition) { selector { ... } }`
    block. Deliberately **not** flagged EXPERIMENTAL the way
    `site.media_query(...)` is: a container query is keyed to an
    ancestor's size, not the viewport, so it doesn't carry the same
    "assumes a phone-vs-desktop breakpoint intuition instead of
    intrinsic layout" caution that `media_query` does -- it's often
    used *alongside* intrinsic layout, not instead of it. The container
    context itself (`container-type`/`container-name`) needs no new
    mechanism -- it's just a `style={...}` prop on the ancestor, which
    was already unrestricted for property values.
  - **`Site.supports(condition: str, selector: str, rules: dict)`** --
    a real `@supports (condition) { selector { ... } }` feature-query
    block, previously not reachable at all. Like `media_query`'s
    condition, the feature-query text itself isn't parsed beyond
    "non-empty, no injection characters" -- the valid-syntax space is
    large, and a malformed condition just produces broken (not unsafe)
    generated CSS, the same failure mode a hand-written `@supports`
    would have.
  - **`Site.page_rule(rules: dict, *, pseudo: str | None = None)`** --
    a real `@page { ... }` / `@page :pseudo { ... }` print-layout
    rule. `pseudo` is one of `ALLOWED_PAGE_PSEUDOS` (`first`, `left`,
    `right`, `blank`) -- same fixed-set discipline as
    `ALLOWED_PSEUDO_CLASSES`.
  - **`Site.import_style(url: str)`** -- a real `@import url("...");`
    statement. Emitted first in the generated stylesheet, ahead of
    even `BASE_CSS_HEADER`, because the CSS spec requires `@import` to
    precede every other rule (aside from `@charset`, which ARKlight
    doesn't emit) -- see `CSSBackend.render`'s ordering comment.
    EXPERIMENTAL (see `docs/EXPERIMENTAL-APIS.md`, `css-import`):
    unlike every other addition in this section, the imported file's
    contents can't be validated by ARKlight -- it's fetched and
    applied by the browser at request time -- so this is gated behind
    the same experimental-feature mechanism `media_query` uses, not a
    plain passthrough.

All seven additions are pure passthrough data on `WebsiteIR`
(`selector_rules`, `keyframes`, `font_faces`, `container_queries`,
`supports_rules`, `page_rules`, `style_imports`), forwarded unchanged
from `Site` through `arklight.compiler.pipeline` into
`build_website_ir` -- no change to `normalize.py`/`validate.py`'s
tree-walking logic, confirming (same as the stateful-JS addenda) that
this really was closed-vocabulary growth, not a structural rework of
the compiler pipeline. Cascade placement in `CSSBackend.render`: the
new selector/at-rule blocks are ordered *after* `custom_styles`/
`media_queries`/`responsive_rules`, on the reasoning that a structural
selector or at-rule is usually the more specific/newer thing targeting
an element another mechanism already touches, and should get the final
say.

**What's still explicitly out of scope, and why:**

- **`@container` queries against an *unnamed* nearest container with
  no `container-type` declared anywhere** aren't validated at the
  `Site.container_query(...)` call site -- like `@supports`'s feature
  condition, a missing `container-type` produces a query that silently
  never matches, not unsafe output; catching it would mean tracking
  which ancestor nodes declared a container context, which is
  tree-shape analysis this addendum's "grow the registry, don't touch
  the compiler" scope deliberately avoids.
- **`:nth-child(An+B of <selector>)`** (the CSS4 form that scopes the
  count to a sub-selector, not just every child) -- the plain An+B form
  covers the overwhelmingly common case; the `of <selector>` extension
  is a real but rare need, deferred rather than guessed at.
- **Multi-level `&` nesting beyond what a single `_resolve_nested_selector`
  pass already covers** (e.g. a `&`-nested key whose own value is
  *another* `&`-nested dict) *is* supported -- `_expand_style_selector_rules`
  recurses -- but each level still only resolves against a single base
  selector, so a nested branch under a grouped selector still isn't
  reachable in one call.

### Staging

Land as two tagged milestones, not one commit: **v0.0035** (state +
behavior/action registries) lands first and independently; **v0.048**
(scaffolding + responsive/head -- scaffolding itself already shipped
as v0.004a) does not depend on it and could technically land first if
that's preferred once implementation starts.

### v0.049: pseudo-class vocabulary addendum III (IMPLEMENTED)

Addendum-shaped, same sense as the two stateful-JS vocabulary addenda
above: no new mechanism, just growing an existing closed set. Every
*parameterless* pseudo-class -- `:focus-within`, `:target`, `:empty`,
`:required`, `:invalid`, `:in-range`, `:only-child`, and so on -- is a
single word with no `(...)` argument, the same shape `hover`/`focus`/
`disabled` already had in `ALLOWED_PSEUDO_CLASSES`. Adding one is a
one-line set extension, not a regex or pipeline change, so this pass
adds the rest of the commonly-used CSS UI/structural/logical
pseudo-classes that fit that shape and weren't already in the set:
`focus-within`, `link`, `target`, `enabled`, `indeterminate`,
`default`, `required`, `optional`, `valid`, `invalid`, `in-range`,
`out-of-range`, `read-only`, `read-write`, `placeholder-shown`,
`root`, `empty`, `only-child`, `first-of-type`, `last-of-type`,
`only-of-type` -- 20 more, alongside the 9 already there.

Both existing call sites read the same set unchanged, so no other code
moved: `site.style(...)`'s `:pseudo:property` shorthand (`arklight/api.py`)
and the general selector parser backing `Site.style_selector(...)`
(`arklight/backend/css/selectors.py`). Functional/parameterized
pseudo-classes (`:not()`, `:nth-child()`, ...) and pseudo-elements
(`::before`, ...) are unaffected -- they're validated by the separate
`SELECTOR_LIST_PSEUDO_CLASSES`/`NTH_PSEUDO_CLASSES`/`PSEUDO_ELEMENTS`
sets the v0.049 selector algebra work above already added, and stay
out of scope for this addendum on purpose: growing *those* means
deciding on a new argument grammar per pseudo-class, not just adding a
name to a flat set, so it's a different-shaped change than this one.

## Reactive-core vdom staging: Stage 1 of 8 (Stages 1-3 IMPLEMENTED, Stages 4-8 PLANNING)

A separate, narrower initiative from `v0.044` below, tracked with its
own "Stage N" numbering rather than a `v0.0XX` id because it isn't new
page-facing capability -- it's staged work on the *mechanism*
underneath the existing `State`/`Bind`/`Action.*` runtime, done ahead
of (and in support of) `v0.044`'s registries actually needing a real
diff/patch algorithm once list rendering and conditional show/hide
land. Each stage is independent and additive, same discipline as every
other section in this file.

**Stage 1 -- vdom core (IMPLEMENTED).** Vendored
[snabbdom](https://github.com/snabbdom/snabbdom) 3.6.4's bare core
(`init`, `h`, `vnode`, `htmlDomApi` -- none of its optional
`attributes`/`class`/`dataset`/`eventlisteners`/`props`/`style`
modules) into `arklight/backend/js/vdom.py`, MIT-attributed. The
state runtime's `renderBindings` pass, which previously did a raw
`el.textContent = ...` on every `store.subscribe` notification, now
constructs a text vnode via `snabbdom.h` and calls a vendored
`patch()` instead. No page-facing API changed -- `State`/`Bind`
behave identically from a site author's point of view -- and pages
that declare no `State(...)` still ship zero vdom code, same
only-ship-what's-used guarantee `v0.003`'s named-behavior runtime
established. This exists purely to give the stages below (and
`v0.044`'s eventual list-rendering/conditional-rendering registries) a
real diffing engine to build on instead of each hand-rolling one.

**Stage 2 -- reactive class binding (IMPLEMENTED).** The first of
`v0.044`'s seven planned sub-systems, pulled forward because it
directly exercises Stage 1's vdom-adjacent machinery rather than only
text-node patching. New API:

```python
State("active", False)
Container(class_name="card", bind_class=Bind.when("active", "is-active"))
```

`Bind.when(state_key, class_name)` produces a `ClassBindSpec` (mirrors
`ActionRef`'s shape), validated the same way `Bind`/`Action.*` already
are: the referenced state key must exist on that page, and
`class_name` must be non-empty. The HTML backend pre-fills the class
at build time from the state's initial value (same
progressive-enhancement guarantee `Bind`'s text gives), and emits
`data-ark-bind-class="<class>"` + `data-ark-bind-class-state="<key>"`
for the runtime to pick up.

On the JS side this deliberately does *not* go through the vendored
vdom `patch()`: the bare core carries none of snabbdom's optional
modules (no `classModule`), and folding the class into an element's
vdom *selector* would make `patch()` see a different vnode on every
toggle (`sameVnode` compares `sel`) and remount the element, silently
dropping any listener already wired to it (e.g. an `on_click=Action.*`
on that same element). Instead, `renderClassBindings` is a small,
separate, hand-written pass doing a direct `el.classList.toggle(...)`
-- correct, and honest about the vendored core's actual scope rather
than pretending a bare core can do everything a full framework can.

**Stage 3 -- event modifiers (IMPLEMENTED).** New builder methods on
`ActionRef`:

```python
Action.set("saved", True).debounce(300)
Action.remove("items", 0).with_modifiers("prevent", "stop", "once")
```

`.with_modifiers(*names)` attaches bare boolean tokens
(`prevent`/`stop`/`once`); `.debounce(ms)`/`.throttle(ms)` attach a
param-carrying token (`"debounce:300"`/`"throttle:300"`). All tokens
are drawn from a new closed `MODIFIER_REGISTRY`
(`arklight/ir/schema.py`) -- same registry discipline
`ACTION_REGISTRY`/`BEHAVIOR_REGISTRY` already established, so this
stays "grow as data," not a compiler rewrite. Validation
(`arklight/ir/validate.py`) rejects unknown modifier names and
enforces that `debounce`/`throttle` carry a positive integer value
while `prevent`/`stop`/`once` don't take one.

The HTML backend renders the full set as a single
`data-ark-modifiers="prevent,debounce:300"` attribute, omitted
entirely for an `ActionRef` with no modifiers attached (same
only-ship-what's-used discipline as everywhere else in this file).
The JS runtime adds one small wrapper, `arkApplyModifiers`, that
reads that attribute once per element and wraps the action dispatcher
with `stop`/`once` short-circuiting and debounce/throttle timing,
instead of duplicating that logic into every action fragment. `prevent`
is honored by construction -- the existing click listener already
calls `event.preventDefault()` unconditionally -- so
`.with_modifiers("prevent")` mostly documents intent rather than
changing runtime behavior. Named behaviors (`on_click="toggle"`, etc.)
have no modifier-attaching API yet; deliberately out of scope here,
since this stage only touches `ActionRef`-based `on_click`.

Deliberately does *not* route through Stage 1's vendored vdom
`patch()`: modifiers are a dispatch-timing concern on the listener
itself, not a DOM-diffing concern, so there's nothing here for the
vdom core to do. 17 tests (`tests/test_event_modifiers.py`); no
change to `State`/`Bind`/existing `Action.*` behavior.

Computed/derived state, two-way input binding, watch effects,
conditional show/hide, and per-item list rendering remain -- same
designs already written up in `v0.044` below; landing them as Stage 4
through 7 here means they get built directly against Stage 1's vdom
rather than the old textContent pass.

**Stage 8 -- `State` persistence to browser storage (PLANNING).**
Opt-in `localStorage` persistence for individual state keys --
`State("count", 0, persist=True)` -- so a value survives a page
reload. Sketched here, not yet built: `initState()` would read a
`localStorage["ark:<page-path>:<key>"]` value (if present and
JSON-parseable) as an override on top of the server-rendered initial
value, and `store.subscribe` would gain one more fixed subscriber that
writes persisted keys back out on every change, wrapped in its own
`try/catch` (private-browsing/quota errors must degrade to "state
just doesn't persist," never a hard failure) -- same defensive
discipline `arkNotify` already applies elsewhere in this runtime.

## v0.0438: Android backend -- androidx.webkit.WebViewAssetLoader packaging (PLANNING)

Internal design doc only -- deliberately not summarized in `README.md`
until (if) implementation actually lands, same "design complete,
implementation not started" discipline every other PLANNING section
in this file follows. Placed here, right after Stage 8 above rather
than near `v0.044`, because the real dependency this milestone has is
on Stage 8's persistence work, not on anything in `v0.044` proper --
see "Why this sits after Stage 8, not after v0.044" below. Per the
current roadmap table (`docs/ARCHITECTURE.md`), this milestone is
`v0.080`; the Desktop backend is `v0.100` -- see that file's
"Renumbered" note for why the two swapped order.

### Updated direction: promote the existing Viewer repo, don't start from zero

An external, standalone project already exists --
`ARKlight-Viewer-for-Android-Devices` -- and it is much closer to this
milestone's end state than the "generate everything from a template"
plan below originally assumed. It is already an Android `.ark`-bundle
viewer built on AndroidX `WebView`, works offline, handles multi-page
bundles, and already separates the bundle/sealing concerns into their
own files (`ArkBundle.kt`, `ArkSeal.kt`) rather than mixing them into
the activity. It is Apache-2.0 licensed, which gives a clean basis for
folding its code into ARKlight proper (subject to preserving the
required license/notice text) rather than treating it as a separate
product to keep in sync by hand.

The plan this section now describes is **evolve that repo into the
Android backend's runtime**, not write a second Android project from
scratch:

```text
ARKlight Android Runtime
│
├── Viewer mode                    (what the repo already does today)
│   ├── bundle picker
│   ├── navigation UI
│   ├── open arbitrary .ark files
│   └── debugging/exploration
│
└── Application mode               (what this milestone adds)
    ├── one fixed compiled bundle, baked in at build time
    ├── no viewer chrome (no bundle picker, no nav UI)
    ├── WebView fills the window
    └── app-level metadata (icon, splash, name, package ID, ...)
```

Both modes share the same underlying runtime (asset loading, bundle
unpacking, seal verification, `WebView` configuration). "Viewer mode"
stays a genuinely useful standalone app for opening any `.ark` file on
a device -- it's what ships today. "Application mode" is the new,
thin, single-purpose shell that `arklight android build` generates:
same runtime, but the bundle is fixed at build time and every piece of
UI that exists only because "this used to be a viewer" is stripped
out. The rule of thumb carried over from this decision: if a visible
element exists solely because the app used to be a browser for
arbitrary bundles, it doesn't belong in application mode; if Android
itself requires or benefits from it (icons, splash, status-bar
handling), it stays in the runtime both modes share.

This also reframes what the *compiler* needs to hand the Android
backend. Rather than the backend needing to render Android UI itself,
its job narrows to: take an `arklight build` output directory (or a
packed `.ark`), drop it into the runtime's `assets/` folder as either
a `site.ark` or an unpacked `index.html` + `pages/` + `assets/` tree,
and configure the thin native shell (manifest, icon, splash, package
ID) around it. The heavy lifting -- unpacking, seal verification,
serving assets under a real origin -- is exactly what the promoted
Viewer runtime already does.

### App identity metadata this milestone now needs to accept

Once the output is a single-purpose app rather than a generic viewer,
it needs application-level metadata the Viewer never had to ask for.
Rather than inventing a new config file for this, it belongs in the
`CONFIG` dict `arklight.config.py` (`arklight.config`) already loads
from next to the site's entry file -- the same mechanism
`live_streaming` already uses for its `host`/`port`/`poll_interval`
settings, kept out of the Python `Site(...)` call since none of this
is application logic either:

    # arklight.config.py
    CONFIG = {
        "android": {
            "app_name": "ARKfolio",
            "package_id": "com.example.arkfolio",
            "version_name": "1.0.0",
            "version_code": 1,
            "icon": "assets/icon.png",
            "splash": "assets/splash.png",
            "orientation": "portrait",
            "edge_to_edge": False,
        },
    }

This milestone adds `"android"` to `arklight.config._KNOWN_SECTIONS`
and reads it the same way `arklight.cli.live_streaming` reads
`"live_streaming"` -- via `arklight.config.section(config, "android",
defaults)`, so every key above has a built-in default and a project
with no `arklight.config.py` at all (or one that doesn't set an
`"android"` section) still gets a buildable, if generically named and
iconed, app. Concretely, the metadata this section owns:

- App name, package/application ID, version name/code.
- Icon -- adaptive icon (foreground/background layers), not a single
  flat PNG, plus an optional monochrome variant for themed launchers.
- Splash screen (image only -- see "explicitly out of scope" below).
- Orientation and edge-to-edge vs. conventional system-bar handling,
  both configurable per app rather than hard-coded one way, since the
  right choice genuinely differs between something like a portfolio
  site and a utility app.

This also gives the eventual Desktop backend (`v0.100`) a precedent to
follow rather than a second config surface to invent: a `"desktop"`
section in the same `CONFIG` dict, read the same way, for whatever
app-identity metadata that backend turns out to need (window
title/size, icon, ...) -- one config file per project, one section per
backend, not a config file per platform.

### Explicitly out of scope, including one thing ruled out on purpose

Everything the original "explicitly out of scope" list below already
excludes still applies. One more is added by this update: **splash-
screen audio.** A splash *screen* is a reasonable, common ask; a
splash screen that plays sound is not something this backend should
default to, since it ties app startup to audio-permission/lifecycle
concerns most sites have no reason to need. If a specific app wants
startup audio, that's an application-level feature the site author
wires up themselves, not a platform default this backend ships.

Also explicitly deferred, not ruled out -- a generalized, capability-
based JS-to-native bridge (`ark.fs`, `ark.db`, `ark.clipboard`,
`ark.notify`, ...) that would let the *same* ARKlight JS-facing API
be backed differently per platform (IndexedDB/OPFS on web, Android
storage/SQLite here, native OS APIs on desktop), with a site
declaring only the capabilities it actually needs so the shipped
runtime doesn't carry unused native surface. That is a substantially
larger design (security review, a versioned platform ABI, an
implementation per backend) with no concrete forcing use case yet --
worth a future PLANNING section of its own once the Desktop backend
gives a second real data point for what such a bridge would need to
support, not something to speculatively scope into this milestone.

### What this is, in one line

A new `arklight android` CLI backend that packages an existing
`arklight build` output directory into a minimal native Android
project shell (Kotlin + Gradle, evolved from the existing Viewer
runtime described above), so the same static site that already runs
standalone in a browser or as a `.ark` polyglot can also be built into
an installable, Play-Store-shippable APK -- without ARKlight ever
executing JavaScript, running a JVM, or becoming a general-purpose
native-app framework.

### Why this needs to exist at all: the `file://` problem

`arklight build` output is plain static files. The obvious "just wrap
it in a WebView" approach -- point a `WebView` at
`file:///android_asset/index.html` -- works for a trivial single-page
site, but breaks down for exactly the features ARKlight's JS runtime
already has or is building toward:

- `file://` pages get a **null or opaque origin** in most WebView
  implementations. `fetch()`/XHR to relative paths, and some storage
  APIs, behave inconsistently or are blocked outright against opaque
  origins -- this is a real platform restriction, not an ARKlight
  bug.
- Stage 8 above (`State(..., persist=True)` -> `localStorage`) needs
  a **stable, real origin** to be reliable: `localStorage` under a
  null/opaque origin is unreliable to nonexistent depending on
  WebView version, and any origin computed per-load rather than
  per-app defeats the entire point of "survives a reload."

`androidx.webkit`'s `WebViewAssetLoader` (a Jetpack/AndroidX
component, not a solo-maintainer convenience wrapper) exists
specifically to solve this: it intercepts a `WebViewClient`'s resource
requests and serves an app's local `assets/` folder under a real,
stable `https` origin (conventionally
`https://appassets.androidx.domain/...`) instead of `file://` --
without a server, a socket, or network access at runtime. That real
origin is what makes Stage 8's persistence, and any future
`fetch()`-based feature, actually reliable inside a packaged app,
which is why this section is cross-referenced from Stage 8 rather
than from `v0.044`.

### Why `WebViewAssetLoader` specifically, not a random GitHub WebView wrapper

The maintenance-risk axis that matters here is **who maintains the
dependency**, not "Kotlin vs. Java" or "which wrapper has more
stars." `WebViewAssetLoader` ships as part of AndroidX/Jetpack --
Google's own release train, the same one every other `androidx.*`
artifact ARKlight would otherwise have zero relationship to rides on
-- rather than a single maintainer's personal repository. Depending
on it is depending on Google's AndroidX support commitment, not on
one person's continued interest in their own side project. This is
the deciding factor; it would be the wrong choice on solo-maintainer
grounds even if it were the more feature-rich or more popular option,
and it would still be the right choice even if a solo-maintainer
alternative were technically nicer.

### The toolchain is unavoidable -- corrected from an earlier, too-optimistic take

An earlier pass at this design assumed a "templating-only, zero
build-step" version could ship without asking the user to install
anything. That was wrong, and it's worth being explicit about why, so
nobody re-proposes it later: `WebViewAssetLoader` is not a `.js` file
that a WebView can load the way a browser loads a script tag -- it is
a compiled Kotlin/Java class that only exists as bytecode inside a
built APK. There is no "skip Gradle" version of this feature. Getting
`WebViewAssetLoader` into a running app unavoidably requires:

1. A `build.gradle` declaring `implementation
   "androidx.webkit:webkit:1.16.0"`, resolved from Google's Maven
   repository.
2. The Android Gradle Plugin + Android SDK (`compileSdk`/`targetSdk`,
   platform-tools) to compile Kotlin/Java that imports
   `androidx.webkit.WebViewAssetLoader` down to dex bytecode.
3. A JDK, for Gradle/AGP/`kotlinc` themselves to run at all.
4. Network access on first build, since Gradle/AGP/AndroidX artifacts
   are fetched from Maven, not vendored into ARKlight.

**What genuinely stays zero-dependency:** *generating* the Android
project's source files (Kotlin, `build.gradle`, `AndroidManifest.xml`)
from ARKlight's existing IR/build output is pure templating --
identical in kind to how `arklight new`'s scaffold templates or the
HTML/CSS/JS backends already work, no new runtime dependency on
ARKlight's own side. What is **not** zero-dependency, no matter how
minimally this feature is scoped, is turning those generated files
into anything runnable -- that step always needs JDK + Android SDK +
Gradle installed on the user's machine. Templating the source is
genuinely free; building it never can be. This is the corrected
framing this section replaces the earlier one with.

### Why `subprocess`, and why not PyJNIus/JPype/Jython

Given the toolchain above is unavoidable, the tempting-sounding next
question is "does ARKlight need a Python-to-JVM bridge to drive it?"
No -- and it's worth ruling the alternatives out explicitly, because
they solve a different problem than the one ARKlight actually has:

- **PyJNIus** and **JPype** are JNI bridges: they let Python code call
  into Java *classes* and *objects* directly, in-process, via the
  Java Native Interface. That's the right tool if ARKlight needed to,
  say, invoke a JVM API and get a live Java object back. It does not
  need that here.
- **Jython** is a separate, alternative *implementation* of the
  Python language itself, written in and running on the JVM -- not a
  feature or mode of CPython. Depending on it would mean ARKlight's
  own interpreter story forks depending on this one feature, which is
  a far larger commitment than this milestone calls for.

What `arklight android build` actually needs to do is **shell out to
an already-built external tool and check whether it succeeded** --
run `./gradlew assembleDebug` (the wrapper script the generated
project itself carries, per Gradle convention, so no Gradle install
is assumed beyond the JDK), wait for it to exit, and read its
exit code / stdout-stderr. That is precisely what the stdlib
`subprocess` module is for, and it is the *only* tool actually needed
here -- no JNI bridge, no alternate interpreter, no new third-party
dependency of any kind on ARKlight's own side. This keeps the same
"stdlib only, no new dependency" discipline the ARK Bundle sealing
code (`hmac`/`hashlib`/`secrets`) already established for a different
feature.

### Graceful failure when no JDK is present

Running `./gradlew` via `subprocess` on a machine with no JDK
installed does not raise a Java-flavored error -- it raises Python's
own `FileNotFoundError` (or platform-equivalent `OSError`), because
the OS itself cannot locate an executable for the wrapper script's
shebang/launcher to hand off to. Left uncaught, that surfaces as a
raw Python traceback, which is exactly the failure mode `main()`'s
v0.041 catch-all was built to eliminate for every other subcommand.
`arklight android build` should catch this specifically (not just
fall through to the generic catch-all) and print a clear, actionable
message -- "no Java installation found; `arklight android` needs a
JDK to build the generated project -- see
https://adoptium.net/ (or your OS package manager) to install one" --
then exit `1`, the same "clear message over raw traceback" contract
every other command in this CLI already honors.

### A staged CLI ladder, not one all-or-nothing command

Rather than ARKlight deciding how far a user has to go, `arklight
android` is proposed as a small ladder of increasingly toolchain-
dependent subcommands, so someone who only wants the generated
project (to open in Android Studio themselves, or commit to their own
CI) never needs a JDK on *this* machine at all, while someone who
wants a device-ready build in one command can ask for that instead:

1. **`arklight android scaffold <build-dir> -o <project-dir>`** --
   templating only, no toolchain required. Generates the Kotlin/
   Gradle/manifest project shell, wires a `MainActivity` that
   registers a `WebViewAssetLoader` pointed at the build output copied
   into `app/src/main/assets/`, and stops there. This is the
   genuinely zero-dependency stage described above.
2a. **CI build verification, no local toolchain at all** -- stage 1's
   scaffold also writes a GitHub Actions workflow
   (`.github/workflows/android-build.yml`) into the generated project,
   which builds a debug APK on GitHub-hosted runners (JDK + Android
   SDK already provisioned there) on every push/PR. This is the
   "someone who only wants the generated project ... to commit to
   their own CI" case named above, just delivered as a ready-made
   workflow file instead of left for that person to write themselves.
   Genuinely zero-dependency on the user's own machine, same as stage
   1 -- see `docs/Backends/ANDROID-BACKEND-IMPLEMENTATION.md`'s
   "Why split Stage 2 into 2a/2b" note.
2b. **`arklight android build <build-dir> -o <project-dir>`** -- runs
   stage 1, then shells out to the generated project's Gradle
   *locally* via `subprocess`, per the JDK-detection handling above.
   Produces a debug APK. First run needs JDK + Android SDK + network
   (for Gradle/AGP/AndroidX resolution) -- on the *user's own*
   machine this time, unlike 2a; nothing about ARKlight's own install
   grows to support this -- the toolchain lives entirely in the
   generated project, same way a `node_modules` folder would live in
   a project ARKlight itself has nothing to do with.
3. **`arklight android build --install <build-dir>`** -- stage 2b,
   then `adb install` onto a connected device/emulator if `adb` is
   found on `PATH` (same graceful-`FileNotFoundError` handling if
   not).
4. **`arklight android build --release`** -- stage 2b targeting
   `assembleRelease` instead of `assembleDebug`; signing
   configuration (keystore path/passwords) is the user's own concern,
   passed through to Gradle rather than ARKlight inventing its own
   credential-handling story -- explicitly out of scope for this
   milestone to manage on the user's behalf.

Each rung is additive and independently useful, mirroring the
`.ark` bundle's own "`--plain` vs. sealed" and "`arklight pack` runs
after `build`, never touching the compiler internals" precedents:
`arklight.packer` reads already-built output and never imports the
parser/ir/backend internals; `arklight android` would follow the same
shape, reading an existing `build-dir` and never touching the
HTML/CSS/JS backends it's packaging.

### Why this sits after Stage 8, not after `v0.044`

An earlier pass at this cross-reference guessed the relevant
intersection was `v0.044`'s Stage 3 (event modifiers) or general JS
capability growth. Tracing it through the actual stage list above,
that's not right: none of `v0.044`'s planned sub-systems (computed
state, two-way binding, list rendering, etc.) care what origin a page
is served from -- they operate purely on the in-memory `store` and
the DOM already in front of them. The one and only place origin
*does* matter is Stage 8, because `localStorage` is scoped per-origin
by the browser/WebView itself. That is the actual, narrow reason this
milestone is worth doing *before or alongside* Stage 8 rather than
after `v0.044` generally: shipping Stage 8 against a `file://`-served
page would give persistence that's unreliable in exactly the
environment (a packaged native app) where "survives a reload" matters
most to a user. Everything else in this file's roadmap is indifferent
to which of `file://` / `https://appassets.androidx.domain` /
plain browser HTTP a page is served from.

### Explicitly out of scope for this milestone

- **iOS.** `WKWebView` has its own analogous mechanism
  (`WKURLSchemeHandler`) but a different toolchain (Xcode, Swift,
  Apple's provisioning/signing model) and a different enough set of
  gotchas that it deserves its own PLANNING section rather than being
  folded into this one as "and also iOS."
- **Push/deep-link/native-plugin bridging of any kind.** This
  milestone's `MainActivity` hosts a `WebView` and nothing else -- no
  Capacitor-style native-plugin bridge, no JS-to-native message
  channel beyond what's needed to serve assets. A generalized native-
  bridge layer is a substantially larger surface (security review,
  plugin API design, ongoing maintenance of the bridge itself) with
  no concrete forcing use case identified yet; noted here as a
  candidate for a future, separate design rather than speculatively
  scoped now.
- **Play Store signing/publishing automation.** Stage 4 above passes
  signing config through to Gradle; it does not manage keystores,
  Play Console API integration, or release-track promotion on the
  user's behalf.
- **Any change to the HTML/CSS/JS backends themselves.** This is a
  packaging backend, not a template/codegen backend like the future
  `v0.100` Vue/Svelte target -- it consumes an existing `build-dir`
  as opaque input, same as `arklight.packer` already does for `.ark`
  bundles.

### Staging

Land as five independently-shippable sub-stages, each individually
useful on its own and gated behind the maintainer choosing to proceed
past design -- consistent with every other PLANNING section in this
file, nothing here is scheduled to a version number yet:

0. **Promote the Viewer repo into `arklight`'s Android runtime.**
   Split the existing `ARKlight-Viewer-for-Android-Devices` code into
   a shared runtime (bundle/seal handling, `WebView` + asset-loader
   configuration) and a thin Viewer-mode shell that keeps today's
   bundle-picker/navigation UI on top of it. This is the prerequisite
   the four CLI stages below build on -- it's what turns "an
   independent Android app that happens to read `.ark` files" into
   "the Android backend's runtime, with a Viewer-mode app as one
   consumer of it."
1. **`arklight android scaffold`** -- templating only, no toolchain
   required, per the CLI ladder above.
2. **`arklight android build`** -- adds the Gradle build step.
3. **`arklight android build --install`** -- adds `adb install`.
4. **`arklight android build --release`** -- adds release signing
   pass-through.

Tracked with status/dependencies per stage in
`docs/Backends/ANDROID-BACKEND-IMPLEMENTATION.md`, the same
routing-table role `REFACTOR-INDEX.md` plays for the HTML/HTMX/JS
refactor track -- that file also gives Stage 0 a file-by-file
breakdown of what in `ARKlight-Viewer-for-Android-Devices` (linked
there) carries over unchanged vs. needs splitting.

## v0.044: JS backend capability expansion -- reactive core parity with Vue 3 (PLANNING)

Requested directly by the maintainer: "add all kinds [of] cool JS
ability to the pkg... more capable of handling so much more
reactivity... to match Vue 3's breadth." This section is the design
doc for that, written before any of it is built, same discipline as
every other PLANNING section in this file. Status: design complete,
implementation not started.

This section assumes the reader has `v0.0035`'s section above in
mind: `State`/`Bind`/`Action.*`, the `BEHAVIOR_REGISTRY`/
`ACTION_REGISTRY` pattern, and the closed-vocabulary-over-arbitrary-JS
constraint. v0.044 is a direct continuation, not a new foundation --
it grows the same registries-as-data discipline into the specific
gaps that section's own "deliberately left for a future version"
notes already named (derived/computed state, `set_from_input`,
debounced actions, per-item list rendering).

### The one constraint that shapes everything else

**Anything CSS or HTML can already do doesn't belong here.** Per the
maintainer's own framing: CSS has its dedicated pipeline
(`arklight/backend/css/`), HTML has its dedicated pipeline
(`arklight/backend/html/` + `arklight.ir.schema.SCHEMA`), and JS's job
is reactivity -- *whether* and *what* changes, never *how it looks*.
Concretely:

- Conditional rendering decides *if* an element is shown. It does not
  define a fade/slide/animation for the transition -- that's a
  `Site.style`/CSS-class concern, unaffected by this milestone.
- Reactive class binding toggles an *existing* class the CSS backend
  (or `v0.042`'s `Site.style`) already defines. It does not define
  new classes or rules -- that would be reopening the CSS pipeline
  from the JS side, which is exactly the layering violation the
  maintainer flagged.
- List rendering decides *how many* copies of a template render and
  with *what bound values*. The template's own tags/props are
  ordinary `SCHEMA` components already validated by the existing
  HTML/CSS pipelines -- v0.044 doesn't add new component types.

### Why "Vue 3 parity" needs a different mechanism than Vue 3 uses

Vue 3's breadth comes from a real **expression evaluator**: template
directives (`v-if="user.age > 18 && user.active"`) compile down to
arbitrary JavaScript expressions embedded in generated render
functions. ARKlight's non-negotiable constraint -- no arbitrary
JS/Python string is ever handed to the browser to execute, no `eval`,
no `new Function` -- rules that mechanism out categorically, not as a
matter of degree. This isn't a gap to design around quietly; it's the
one part of "Vue 3 parity" this project cannot and should not chase,
and it needs to be said plainly rather than discovered later as a
disappointing surprise.

**What's achievable instead: breadth of closed, named primitives
covering the common cases**, the same trade Vue *itself* made at a
different layer -- Vue's own `<script setup>` macros
(`defineProps`, `defineEmits`) are themselves a closed, compiler-
recognized vocabulary, not "any JS goes." ARKlight pushes that same
idea one level further down, into the expression position itself:
where Vue writes `v-if="count > 5"`, ARKlight writes
`Show(Predicate.gt("count", 5))` -- a real Python call the Validation
stage can check against a registry at compile time, not a string
parsed at runtime. The result covers the large majority of realistic
template-expression usage (comparisons, membership, simple arithmetic
combinations, string formatting) without ever parsing or executing a
user-supplied expression. What it *cannot* cover -- an arbitrary,
unanticipated expression shape -- stays uncovered on purpose. That's
a real, permanent ceiling, not a temporary one this project intends
to close later by finally adding an evaluator.

### Seven additive sub-systems

Each follows the exact shape `v0.0035`'s `BehaviorSpec`/`ActionSpec`
established: a new `*Spec` dataclass, a new `*_REGISTRY` dict in
`arklight/ir/schema.py`, small per-entry JS fragments in a new
`arklight/backend/js/<kind>/` directory, and new `arklight.api`
surface that produces structured data (never a string of code).
Nothing here changes `normalize.py`/`validate.py`/`build.py`'s
*shape* -- it's the same registries growing as data, applied to six
new kinds of registry instead of just behaviors/actions.

**1. Computed/derived state** (closes the "derived/computed state"
gap named in both `v0.0035` addenda). New API:

```python
State("price", 9.99)
State("qty", 3)
Computed("total", deps=("price", "qty"), derive=Derive.multiply("price", "qty"))
Text(Bind("total"))
```

`DerivationSpec`/`DERIVATION_REGISTRY` (mirrors `ActionSpec`/
`ACTION_REGISTRY`): `Derive.sum(*names)`, `Derive.multiply(*names)`,
`Derive.join(*names, sep=" ")`, `Derive.count(name)` (list length),
`Derive.format(template, **names)` (fixed `{name}`-style substitution
over named state values only -- not a general string-eval, just
`str.format` over a closed mapping), `Derive.compare(a, b, op)` where
`op` is itself a closed choice (`"eq"`/`"gt"`/`"lt"`/...), never a
raw operator string executed as code. `IRPage` gains a `computed:
dict[str, ComputedSpec]` field alongside today's `state`. Validation
checks every `deps` name resolves to a real `State`/other `Computed`
on the same page (catching typos/forward-reference mistakes at build
time, same guarantee `Bind` validation already gives).

**2. Watch effects** (the reactive-effect / `watch()` equivalent).
New API:

```python
State("celsius", 0)
State("fahrenheit", 32)
Watch("celsius", then=Action.set("fahrenheit", Derive.format("...")))  # illustrative
```

More realistically, `Watch` is most useful paired with `Computed`
covering the "derive a value" half and `Watch` covering the "when X
changes, also do Y" side-effect half -- e.g. clamping a value back
into range, or dispatching a `dismiss`/`toggle` *behavior* (not just
an action) in response to a state change rather than only a click.
Declared as a `watch: list[WatchSpec]` on `IRPage`; the runtime's
existing `store.subscribe` mechanism (already used by
`renderBindings`) gains one more kind of subscriber. No new dispatch
mechanism -- watch effects reuse the exact same `ACTION_REGISTRY`
dispatcher `on_click=Action.*` already uses, just invoked from a
state-change subscription instead of a click listener.

**3. Two-way input binding** (the `v-model` equivalent; closes
`set_from_input`, named in the `v0.0035` addendum I "left for a
future version" list). New API:

```python
State("email", "")
Input(type="email", bind_value="email", bind_as="string")
```

Compiles to `data-ark-model="email"` (+ `data-ark-model-as` for the
closed coercion vocabulary: `"string"`/`"number"`/`"bool"`). The
runtime wires one `input`/`change` listener per bound element calling
`store.set(key, coerce(el.value))` -- the *coercion* function is
fixed vocabulary (four cases: string passthrough, `Number(...)`,
checkbox-checked boolean, nothing else), not user-suppliable code.

**4. Per-item list rendering** (the `v-for` equivalent -- the single
biggest lift here, and explicitly flagged as such back in the
`v0.0035` addendum II section: "the real remaining gap for a
production todo-list/tag-editor style UI... a materially different
feature"). New API:

```python
State("items", ["milk", "eggs"])

def row(item, index):
    return Item(
        Bind.item(),
        Button("Remove", on_click=Action.remove("items", Bind.index())),
    )

List(Repeat("items", template=row))
```

- `Repeat(state_name, template)` is a new `ARKNode`/IR concept (not a
  new HTML component -- `Repeat` never renders a tag itself, it
  wraps whatever `template(item, index)` returns, which must already
  be valid, schema-checked children of its parent the same as any
  other list of children today).
- Compiles to a `<template data-ark-repeat="items">...</template>`
  block (the real HTML `<template>` element -- inert, never rendered
  directly, exactly what it's for) wrapping one instance of the
  compiled template markup, with `Bind.item()`/`Bind.index()`
  positions marked as substitution points.
- One new, fixed, general runtime function -- `renderRepeats(store)`
  -- clones the `<template>` content once per array element on every
  relevant `store.set`, substituting the marked positions. This is
  one function shipped once, not per-list generated code: the
  "generality" lives in walking the DOM template + substitution
  markers, the same way `renderBindings` already generalizes over
  every `data-ark-bind` element today rather than having one
  hand-written function per bound key.
- `Action.remove(name, index)` already exists (`v0.0035` addendum
  II); `Bind.index()` inside a `Repeat` template is what makes
  "remove *this* item" wireable without new action vocabulary.

**5. Conditional show/hide** (the `v-show`/`v-if` equivalent). New
API:

```python
State("is_open", False)
Show(Predicate.truthy("is_open"), Container(Text("Details...")))
```

`PredicateSpec`/`PREDICATE_REGISTRY`: `Predicate.truthy(name)`,
`Predicate.equals(name, value)`, `Predicate.gt(name, value)`,
`Predicate.lt(name, value)`, `Predicate.in_list(name, values)`.
Compiles to `data-ark-show-if="<predicate-id>"` on the wrapped
element; the runtime evaluates the fixed predicate function against
current state on every relevant change and toggles the standard HTML
`hidden` attribute -- `v-show` semantics (stays in the DOM, display
toggled) rather than `v-if` (added/removed from the DOM). True
`v-if`-style removal is a plausible later addition on the same
predicate mechanism, deliberately not bundled in here to keep this
sub-system's first version to "toggle visibility," matching how
`v0.0035`'s `toggle` behavior already only toggles a class rather
than removing elements.

**6. Event modifiers** (`.prevent`/`.stop`/`.once`/debounce/throttle
-- named in `v0.0035` addendum I's "left for a future version" list
as "a timing concern orthogonal to what an action does, better solved
once as a wrapper than duplicated per action"). New API:

```python
Button("Save", on_click=Action.set("saved", True).debounce(300))
Link("Delete", href="#", on_click=Action.remove("items", 0).with_modifiers("prevent", "once"))
```

`ModifierSpec`/`MODIFIER_REGISTRY`: `prevent`, `stop`, `once`,
`debounce:<ms>`, `throttle:<ms>`. Implemented as one small wrapper
function in the dispatcher (`arklight/backend/js/render.py`'s
`wireActions`/`wireBehaviors`) that wraps the existing
click-handler-building logic, checked once per element from a new
`data-ark-modifiers="prevent,debounce:300"` attribute -- not
duplicated into every individual action/behavior fragment.

**7. Reactive class binding** (the `:class` equivalent; the "later
`class_name=Bind(...)` for conditional classes" note explicitly left
open in the original `v0.0035` design section above). New API:

```python
State("is_open", False)
Container(..., class_name=Bind.class_if("is_open", "expanded"))
```

`Bind.class_if(state_name, class_name, else_class_name=None)`
compiles to a `data-ark-class-if="is_open:expanded"` attribute (or
`"is_open:expanded:collapsed"` with an else-class); the runtime
adds/removes `class_name` on relevant state changes. The class itself
(`"expanded"`) must already exist in the site's stylesheet -- via the
default utility classes or `v0.042`'s `Site.style(...)` -- this
sub-system only ever toggles membership in an existing class, it does
not define one, keeping it strictly on the reactivity side of the
CSS/JS boundary.

### Generalizing the reactive core

All seven sub-systems above put more consumers on the same underlying
mechanism `v0.0035` introduced with one store and one flat
`listeners` array. That flat structure means every sub-system so far
would re-render *everything* on any `store.set` -- correct, but
wasteful once `Computed`/`Watch`/`Repeat`/`Show`/class-binding are all
independently subscribing. `createState` (`arklight/backend/js/
render.py`) grows a real, if small, **dependency graph**: each state
key tracks which computed keys, watchers, bound elements, repeat
blocks, and show-if/class-if predicates depend on it, so `store.set`
recomputes and re-renders only what actually depends on the changed
key. This is still one static, fully-readable runtime file, still
assembled from only the registry fragments a given site's IR actually
references (the existing "ship only what's used" discipline from
`v0.0035` applies unchanged), and still has zero `eval`/`new
Function` anywhere -- the dependency graph is a plain JS object built
from IR data at page-load time (`data-ark-deps="..."` or equivalent),
not a fundamentally different execution model.

### Compiler pipeline touch points

- `arklight/ir/schema.py` -- four new registries
  (`DERIVATION_REGISTRY`, `PREDICATE_REGISTRY`, `MODIFIER_REGISTRY`)
  plus their `*Spec` dataclasses, same shape as `BehaviorSpec`/
  `ActionSpec` today.
- `arklight/api.py` -- `Computed`, `Watch`, `Show`, `Repeat`,
  `Derive.*`, `Predicate.*`, `Bind.item`/`Bind.index`/`Bind.class_if`,
  `Input(bind_value=...)`, `.debounce(...)`/`.with_modifiers(...)` on
  `ActionRef`.
- `arklight/ir/build.py` / `arklight/ir/normalize.py` /
  `arklight/ir/validate.py` -- `IRPage` gains `computed`/`watch`
  fields alongside today's `state`; validation checks `Computed.deps`,
  `Watch` targets, `Repeat` template shape, and every `Derive.*`/
  `Predicate.*`/modifier's args against its registry spec, same
  discipline `Action.*` validation already applies.
- `arklight/backend/js/render.py` -- the dependency-graph
  generalization above; new fragment directories
  `arklight/backend/js/derivations/`, `.../predicates/`,
  `.../modifiers/`, one file per registry entry, mirroring
  `actions/`/`behaviors/` exactly.
- `arklight/backend/html/render.py` -- renders `Repeat`'s `<template>`
  wrapper, `Show`'s `data-ark-show-if`, `Input`'s `data-ark-model`,
  and the `data-ark-class-if`/`data-ark-modifiers` attributes.

### Explicitly out of scope for v0.044

Named here so none of it gets assumed-in-scope later, same convention
this file already uses for `v0.048`:

- A real JS/template-expression evaluator, `eval`, or `new Function`
  -- permanent non-goal (see "Why 'Vue 3 parity' needs a different
  mechanism" above), not a temporary gap.
- Component props/slots/`provide`/`inject`, or anything assuming
  `v0.010` (user-defined components) has landed -- it hasn't, and
  this milestone's registries are deliberately page-scoped, not
  component-scoped, so they don't need to be redesigned once v0.010
  does land.
- CSS transitions/animations/`@keyframes`/`@font-face` for anything
  `Show`/class-binding toggles -- squarely `v0.048`-and-beyond
  territory; this milestone only flips attributes/classes, never
  defines what a change looks like.
- New HTML component types or semantic vocabulary -- unchanged
  territory of `SCHEMA`/the vocabulary addenda, not touched here.
- Lifecycle hooks (`onMounted`/`onUpdated`) -- no concrete forcing
  use case identified yet; noted as a candidate for a future
  addendum rather than spec'd speculatively now.
- Alternate framework backends (`v0.100`) -- this milestone is
  a step toward the state/event-semantics prerequisite
  `docs/DESIGN-NOTES.md`'s "authoring layer" section above already
  names for that milestone, but does not itself complete it (no
  Vue/Svelte codegen ships as part of v0.044).

### Staging

One milestone, landed as registry additions the same way `v0.0035`'s
addenda were -- each of the seven sub-systems above is independently
shippable and additive (a page using none of them renders
byte-for-byte unchanged, same guarantee `v0.043`'s optional props
gave), so they can land as `v0.044a`/`v0.044b`/etc. sub-versions in
any order, rather than requiring one large all-or-nothing patch.
Suggested order, easiest/most-requested first: reactive class binding
(1) -> event modifiers (2) -> computed/derived state (3) -> two-way
input binding (4) -> watch effects (5) -> conditional show/hide (6)
-> per-item list rendering (7, the largest lift, last).

## v0.042: extra CSS features + CLI discoverability (IMPLEMENTED)

Two initiatives that were originally raised alongside the `@media`/
`<head>` request (v0.048 above) but scoped out of it as a distinct,
smaller problem: not reaching new capability ARKlight lacks (that's
v0.048), but cutting boilerplate/repetition in capability that already
sort of exists, plus closing the two CLI-discoverability gaps noted
above. Both are now implemented.

### Custom CSS class authoring

Before this, every class a site could use (`.nav`, `.card`, `.stack`,
...) came from the one fixed `BASE_CSS` constant in
`arklight/backend/css/render.py` -- there was no per-node CSS
generation, so a site author couldn't define a brand-new class with
its own rules, only opt into ones ARKlight already shipped. Of the two
options this file originally weighed -- (a) a way to pass a dict of
custom rules in that get emitted as real classes, or (b) collecting
repeated `style={...}` props into auto-generated classes behind the
scenes -- **(a) shipped; (b) was not pursued** (it addresses output
duplication, not authoring boilerplate, and was judged a smaller win
for the complexity added).

Final shape: **`Site.style(name: str, rules: dict[str, str]) -> None`**
(`arklight/api.py`). `name` must be a valid, single CSS class
identifier (letters/digits/hyphens/underscores, no leading digit) --
validated at call time via a compiled regex, raising `ValueError` with
a specific message otherwise (matching this project's "clear error
over raw traceback" ethos elsewhere in the CLI/pipeline). `rules` must
be a non-empty `{css-property: value}` dict of non-empty strings --
same shape as the existing per-node `style={...}` prop, so nothing new
to learn, and still a plain dict rather than a raw CSS string, keeping
the "no arbitrary CSS/HTML strings" boundary intact (same shape as the
`@media`/`<head>` design in v0.048 above). Calling `site.style()` again
with a name already registered overwrites it (last call wins) rather
than erroring or silently merging -- lets a site redefine a class as
it's built up without a separate "update" method.

Plumbing: `Site.custom_styles: dict[str, dict[str, str]]` is threaded
through `build_website_ir()` (new optional `custom_styles=` keyword,
backward-compatible with every existing call site) onto a new
`WebsiteIR.custom_styles` field, which `CSSBackend.render()` reads and
renders as real `.name { prop: value; }` blocks -- sorted by class
name, and by property name within each class, for deterministic output
across builds -- appended after `BASE_CSS` so custom classes can
override base rules purely by cascade order (last-defined-wins, no
extra specificity tricks needed). `class_name="name"` then just works
for a custom name the same way it already did for `.nav`/`.card`,
since the HTML backend's `class_name` handling was already a generic
prop-to-attribute passthrough with no knowledge of which class names
are "real."

Not pursued in this pass, left as a possible follow-up: `arklight
search` (below) currently only searches component schema, not
`BASE_CSS`'s or a site's registered custom class names.

### `arklight search <name>`

Implemented in a new `arklight/cli/search.py`, wired into
`arklight/cli/main.py` as a `search` subcommand. Matches the original
design almost exactly: read-only reflection over `SCHEMA`, no new data
format. Case-insensitive exact match wins outright and prints required
props, whether children are allowed, and whether the component is a
`Bind(...)`-able target (surfaced as "children: text only (Bind(...)
is also allowed here)" -- the same condition the validator checks:
`spec.text_only_children`).

When there's no exact match, falls back to typo-tolerant "did you
mean" suggestions (up to 5) instead of just failing -- not in the
original design note above, added because a schema-lookup tool that
only works when you already remember the exact name solves less of the
"~80+ names deep, hard to recall" problem than a fuzzy one does.
Implementation is stdlib-only (`difflib.get_close_matches`-style
`SequenceMatcher` ratio scoring, blended with a small camelCase-aware
tokenizer for multi-word matches like `"tbl-row"` -> `TableRow`) -- no
new runtime dependency, consistent with the rest of ARKlight. The
technique was adapted from a similar stdlib-only fuzzy-search utility
in the `ARKlight-Playground` companion repo's dev-tooling backend, not
copied verbatim (different corpus -- component names here, file paths
there -- so the scoring was retuned rather than reused as-is). A
genuinely unrelated query (no close whole-name match and no shared
token) returns a plain "nothing close enough to suggest" message
rather than forcing a guess.

### `arklight --help` / bare `arklight`

`--help` itself needed no new code -- argparse already generates it
from each subcommand's existing `help=` string. The actual gap: running
`arklight` with **no** subcommand used to hit argparse's `required=True`
constraint on the subparsers and print a terser `error: the following
arguments are required: command` instead of the same usage/help text.
Fixed by dropping `required=True` and explicitly checking `args.command
is None` in `main()`, printing `parser.print_help()` and returning `0`
in that case -- a first-time user typing just `arklight` now sees how
to get started instead of a bare error.

### Not part of this pass

`@keyframes`/`@font-face` (still explicitly deferred under v0.048
above), and searching utility/custom class names alongside component
schema in `arklight search` (noted above as a possible follow-up).

## v0.036: ARK Bundle spec v1 (IMPLEMENTED)

This section was originally written up front (same discipline as the
v0.0035/v0.048 design above) before any code existed. v1 is now
implemented as `arklight pack` (`arklight/packer/bundle.py`) -- the
packing algorithm below matches what's shipped, with one
simplification noted inline: stdlib `zipfile` turned out to handle the
offset math itself (see "Packing algorithm" below), so no manual ZIP
header patching was needed after all.

**v1 archive scope, confirmed at implementation time:** only `.html`/
`.css`/`.js` files are read as text (needed to inline the entry page).
Everything else in the build directory -- most notably `assets/` -- is
still carried into the archive, just as raw bytes; see "v0.037: sealed
bundles" below for when that carry-over, plus sealing, shipped.

### Problem this solves

`arklight build` already produces a working static site
(`index.html`, `styles.css`, `arklight.js`, `assets/`), but it's a
*folder* -- sharing it means zipping it by hand, hosting it somewhere,
or walking someone through opening `index.html` from a specific
relative path so its sibling `styles.css`/`arklight.js` resolve
correctly. There's no single artifact someone can be handed, double-
click, and get the exact same page a normal deploy would show, on
either a desktop OS or Android, with nothing installed.

### Format: an HTML/ZIP polyglot, not a new file format

A `.ark` bundle is:

```
[ 1. Self-contained entry page                                    ]
   A single HTML document -- the compiled entry page (index.html),
   but with its <link rel="stylesheet"> and <script src="arklight.js">
   replaced by the actual CSS/JS content inlined directly in <style>/
   <script> tags. Ends in a normal </html>.
[ 2. ZIP payload                                                   ]
   A standard ZIP archive containing the *original, unmodified* build
   output: index.html, styles.css, arklight.js, assets/... -- exactly
   what `arklight build` already writes to disk, byte-for-byte.
```

This works because the two formats each tolerate the other's presence
in a specific, well-documented way:

- **HTML parsers** stop at `</html>` and ignore anything after it (the
  same reason a saved webpage with trailing junk bytes still renders
  correctly).
- **ZIP readers** don't scan from byte 0 -- they seek to the End Of
  Central Directory record near the end of the file and follow offsets
  from there, and the format explicitly permits the first entry to
  start at a nonzero offset (this is exactly how self-extracting
  `.exe` archives already work: arbitrary bytes before the ZIP data,
  ignored by the ZIP reader).

Concatenate part 1 directly before part 2, and the result is
simultaneously a fully valid, renderable HTML document *and* a fully
valid ZIP archive -- not a disguised extension, not a custom container
format ARKlight invents, just two existing, widely-supported formats
occupying the same bytes. This is not a novel trick: the SingleFile
web-archiving tool already ships this exact technique in production as
its `--self-extracting-archive` output format.

### What "raw files inside the zip acting as a single frontend application" means

The ZIP payload is not a separate, alternate copy of the site -- it's
the same `index.html`/`styles.css`/`arklight.js`/`assets/` files
`arklight build` already produces, unmodified. Extracting the bundle
with any archive tool reproduces exactly the folder a normal build
already gives you: open `index.html` from that extracted folder and
it works precisely as it does today, because nothing about how the
HTML/CSS/JS backends generate those files changes for this milestone.
The "single frontend application" framing describes the *bundle's*
behavior (one file, two equally valid ways to consume it), not a new
runtime or a new IR concept -- there is no JSON intermediate
representation shipped inside the bundle, and no code, embedded or
otherwise, that ARKlight didn't already generate for a normal build.

### Why there's no "extraction" step to reason about for normal use

Opening a `.ark` bundle in a browser (double-click, or `Open With ->
Browser`, on desktop or Android) never invokes anything zip-related:
the browser's HTML tokenizer reads from the start of the file and
simply never reaches the ZIP bytes trailing after `</html>`. No temp
directory is created, nothing is written to disk, and there is nothing
to clean up afterwards -- behaviorally identical to how a video player
reads an `.mp4` container directly rather than unpacking frames to
disk first, or how opening a `.png` doesn't "extract" the image.

The ZIP payload only becomes relevant if a person deliberately opens
the same file with an archive tool instead of a browser (`unzip`,
7-Zip, a phone's file-manager "Extract" action). That extraction is
performed by *that* tool, on the user's terms, to a location of their
choosing -- ARKlight isn't running any code at that point and has
nothing to clean up either way.

### Packing algorithm (for the future implementation)

1. Run the existing build pipeline unchanged; obtain the entry page's
   final rendered HTML plus the CSS/JS backend outputs already
   produced.
2. Render a variant of the entry page with `<link
   rel="stylesheet" href="styles.css">` and `<script src="arklight.js"
   defer>` replaced by their inlined contents (`<style>...</style>` /
   `<script>...</script>`). Every other file (other routes, other
   assets) is untouched.
3. Write that inlined HTML document's bytes first.
4. Write ZIP local file headers + data for every file in the build
   output (including the *original*, non-inlined `index.html`), with
   each entry's offset shifted by the length of step 3's HTML bytes.
5. Write the ZIP central directory and End-Of-Central-Directory
   record last, with offsets pointing at the shifted positions from
   step 4.

Python's stdlib `zipfile` module doesn't support "write arbitrary bytes
before the archive" via its high-level API, but it doesn't need to:
opening the *same* already-open file handle with
`zipfile.ZipFile(handle, mode="a")` after writing the prefix bytes to
that handle directly is enough. `zipfile` computes every offset it
writes (local file headers, central directory, End-Of-Central-
Directory record) from the handle's current file position rather than
assuming the archive starts at byte 0, so the entries land correctly
after the prefix with no manual header patching required. Verified
against both Python's own `zipfile` reader and the system `unzip`
binary -- both read the resulting file's ZIP contents correctly,
ignoring the HTML prefix.

### Scope and non-goals for v1

- **Only `.html`/`.css`/`.js` files are read as text.** Even though a
  normal `arklight build` may also produce an `assets/` folder (images,
  audio, video, or anything else copied in from a top-level `assets/`
  next to the entry file), those files are handled as opaque bytes,
  not text -- `arklight pack` never opens, parses, or transforms them.
  (v1's original draft deferred asset carry-over entirely and reported
  those files as skipped; that carry-over shipped in v0.037 -- see
  below -- so this bullet now just documents the byte-vs-text
  distinction, not an exclusion.)
- **Packaging only, over already-built output.** No changes to
  `normalize.py`/`validate.py`/`build.py`/the `Backend` interface/the
  IR. This is not a new backend in the `Backend.render(ir) ->
  {path: contents}` sense -- it runs *after* all backends have already
  produced their files.
- **A separate module, not new logic inside the compiler pipeline** --
  explicit requirement from the person requesting this, matching how
  `arklight build`'s output is the input to this step rather than a
  new pipeline stage fused into it. Implemented as `arklight/packer/`,
  a module that only ever reads already-written build output and never
  imports the parser/ir/backend internals, exposed as a CLI subcommand
  (`arklight pack <build-dir> -o site.ark`) rather than a separate
  binary, to match the existing single-entry-point `arklight build ...`
  CLI style.
- **No native player app, on Android or elsewhere.** The browser
  already installed on the device is the only runtime this format
  needs. No embedded JSON IR, no server-driven-UI renderer, no
  Jetpack Compose bridge, no embedded Python -- all of that would
  reintroduce exactly the "runtime Python execution" and "feature
  creep beyond the milestone roadmap" non-goals this project already
  rejects (see "Non-goals" in `README.md`).
- **Single entry page for v1.** The polyglot/inlining treatment
  applies to one page (the bundle's "front door"); a multi-page site's
  other routes ship inside the ZIP payload as ordinary linked HTML
  files, same as a normal build, reachable once extracted. Whether a
  future version inlines *every* route as its own polyglot, or adds
  some other multi-page bundling scheme, is explicitly deferred --
  not assumed in scope here.
- **File-association / double-click behavior on a given OS is out of
  scope.** Whether `.ark` opens in a browser by default depends on
  that OS's file-type associations, same as any other extension;
  shipping the bundle as `.html` instead sidesteps this entirely with
  zero configuration, at the cost of the branded extension. This
  spec doesn't attempt to register file associations on the user's
  behalf.

### Known caveats

- macOS's built-in Archive Utility has a documented bug decompressing
  these polyglot archives directly (double-click "Extract"); the
  `unzip` CLI (or most third-party archive tools) handles them
  correctly. Worth a one-line note in user-facing docs once this
  ships.
- Some mobile browsers (documented for iOS Safari specifically) open
  locally-provided HTML files in a restricted viewer that disables
  JavaScript -- irrelevant to this project's stated Android target,
  but worth re-checking against whichever Android browsers/versions
  get tested before calling this done.

## v0.037: sealed bundles (IMPLEMENTED)

### Problem this solves

v1's `.ark` bundle carries a real, standard ZIP as its archive half --
by design, for maximum tool compatibility. The flip side: *any*
archive tool, a "rename to `.zip`", or a hex editor can open it,
inspect every page/asset inside, and splice in modified files before
handing the bundle to someone else, with nothing detecting the change.
For a bundle meant to be handed out as a single trusted artifact (a
demo build, a client deliverable, a kiosk build), that's a real gap:
nothing stops casual copying or tampering.

### What changed

`arklight pack` now **seals the archive half by default**: the ZIP
bytes are encrypted (see `arklight/packer/seal.py`) before being
appended after the inlined front-matter page, so the polyglot's second
half is no longer a parseable ZIP to a generic tool at all -- just
opaque bytes. `arklight unpack` (new command) reverses this. The
original v1 plain-ZIP-tail behavior is kept as an explicit opt-out
(`sealed=False` / `--plain`), not removed -- some use cases genuinely
want the extracted build freely re-editable without ARKlight
installed, and that should stay one flag away, not lost.

### Cipher construction (stdlib only, no new dependency)

This project ships zero runtime dependencies (`pyproject.toml` has no
`[project] dependencies` at all) -- pulling in `cryptography` or
`pyzipper` just for this one feature would break that invariant for
every user of the package, not just people who seal bundles. The
construction instead uses only `hmac`/`hashlib`/`secrets`:

- **Keystream:** HMAC-SHA256 counter mode -- block *i* is
  `HMAC-SHA256(key, salt || i)`, blocks concatenated and trimmed to the
  plaintext's length, then XORed against it. This is a standard,
  minimal way to turn a MAC into a stream cipher when a dedicated AEAD
  primitive isn't available in the stdlib.
- **Authentication:** `HMAC-SHA256(key, salt || ciphertext)`, checked
  with `hmac.compare_digest` (constant-time) *before* the decrypted
  bytes are ever handed to `zipfile` -- a wrong passphrase or a
  tampered/corrupted archive is rejected outright, not silently
  half-decrypted into garbage that `zipfile` then chokes on with a
  confusing error.
- **Key derivation, passphrase mode:** PBKDF2-HMAC-SHA256, 200,000
  iterations, random 16-byte salt per bundle.

### Two key modes -- and being honest about what each actually protects

- **Embedded-key mode (default, no `--passphrase`).** A fresh random
  32-byte key is generated per bundle and stored, unencrypted, inside
  the sealed blob, so `arklight unpack` always works with zero extra
  input -- the common case (share a demo, prevent casual poking)
  doesn't require anyone to manage a secret. **This is not
  encryption-grade confidentiality.** The key ships with the file by
  construction; anyone who has (or writes) an ARKlight-compatible
  unsealer can always open it. What it *does* provide: a generic
  archive tool, a "rename to `.zip`", or a hex-editor guess can't read
  or splice the contents, and the random salt/key mean there's no
  fixed byte pattern to fingerprint or strip in bulk. Framed
  accurately in both the README and the CLI's own pack output
  ("SEALED (embedded key) -- opaque to generic archive tools... For
  real secrecy... use --passphrase") rather than oversold as
  "encrypted" without qualification.
- **Passphrase mode (`--passphrase`).** The key is derived from the
  passphrase and never stored anywhere in the file. This *is* real
  confidentiality -- nobody without the passphrase, including someone
  running ARKlight's own `unpack` code, can recover the plaintext. The
  same passphrase must be supplied to `arklight unpack` later; there is
  deliberately no recovery mechanism (a backdoor here would defeat the
  point).

### What sealing does *not* protect, and why that's inherent, not a bug

The inlined front-matter page -- the actual page a browser renders
when the `.ark` file is opened -- is always plain HTML/CSS/JS,
sealed or not. This can't be otherwise: the polyglot only works
*because* an HTML parser can read that half directly, and a browser
has no decryption step in its page-load path to give it a key to. Only
the *archive* half (other routes, `assets/`, and a second, un-inlined
copy of the entry page) is protected. In other words: sealing stops
someone from opening the bundle file and pulling out its other
pages/assets/originals -- it was never going to stop view-source on the
one page currently on screen, and nothing marketed here claims it
does.

### Boundary detection: locating the archive half without a shared offset

`unpack` has to find where the front-matter page ends and the
archive (sealed or plain) begins, given only the bundle's raw bytes --
it doesn't have `pack()`'s in-memory `prefix_bytes` to compare against.
It locates this by searching for the literal `</html>\n` the HTML
backend always emits to close every page (`arklight/backend/html/
render.py`) -- exactly matching `pack()`'s `prefix_bytes` byte-for-byte,
including the trailing newline that's easy to miss (an off-by-one here
silently corrupts every unseal by one byte, since HMAC/keystream output
is position-sensitive; caught by round-trip tests before this shipped,
not after).

### Tests

`tests/test_seal.py` -- the cipher/MAC primitives in isolation: round-
trip (embedded-key and passphrase modes), empty payload, tamper
detection, wrong-passphrase detection, missing-passphrase detection,
and that two seals of the same payload differ (no fixed byte pattern).
`tests/test_pack.py` -- sealed-by-default pack/unpack round-trips
(including with `assets/`), `--plain` opt-out still produces a real
ZIP, CLI wiring for both `pack` and the new `unpack` subcommand,
tampered-bundle rejection end-to-end.



Python's raw proficiency advantage for LLM-assisted coding is well
documented (HumanEval, MBPP, and most standard coding benchmarks are
Python-specific by design, and "unspecified language -> Python" is a
consistent default), but that's a general Python argument, not an
ARKlight-specific one -- HTML is at least as represented in training
data.

**The ARKlight-specific mechanism is different:** it's not that AI
writes good Python, it's that ARKlight gives an AI-in-the-loop workflow
something raw HTML never gives -- a hard compile-time check with a
precise, localized error message. A nesting mistake, a missing required
prop, an unclosed tag written directly in HTML sits there silently
until someone renders the page and looks at it. The equivalent mistake
in ARKlight -- nesting a component inside a text-only component,
omitting `Link`'s required `href`, using an unknown `on_click` behavior
name -- is caught at the Validation stage immediately, with an exact
location and reason, before any file is written. That tighter feedback
loop (validate against a precise error vs. "does this look right in a
browser") is a real, mechanism-level advantage for AI-assisted
iteration, independent of Python's general popularity.
