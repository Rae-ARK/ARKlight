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

**Also planned, not yet implemented, not yet scheduled to a specific
sub-version -- explicitly waiting on a go-ahead before implementation
starts:** two CLI helpers oriented at discoverability once the
component vocabulary is ~80+ names deep (a real problem `arklight new`
alone doesn't solve -- scaffolding gets someone started, it doesn't
help them remember `Picture`'s required props six months later):

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
pipeline, the IR, or any backend. Held back from implementation until
explicitly signaled, independent of the state of v0.0035/v0.004a/v0.048 above.

### v0.048: CSS media queries + `<head>` extension

(Renumbered from the original "v0.004" combined heading once the CLI
scaffolding piece of that heading shipped separately as v0.004a --
see `PROGRESS.md`/`CHANGELOG.md`. Design below is unchanged from when
it was first written.)

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

### Staging

Land as two tagged milestones, not one commit: **v0.0035** (state +
behavior/action registries) lands first and independently; **v0.048**
(scaffolding + responsive/head -- scaffolding itself already shipped
as v0.004a) does not depend on it and could technically land first if
that's preferred once implementation starts.

### Explicitly not part of v0.048: custom CSS class authoring (PLANNING -- not yet designed)

Raised alongside the `@media`/`<head>` request but a distinct, bigger
problem: today every class a site can use (`.nav`, `.card`, `.stack`,
...) comes from the one fixed `BASE_CSS` constant in
`arklight/backend/css/render.py` -- there is no per-node CSS
generation, so a site author cannot define a brand-new class with its
own rules, only opt into ones ARKlight already ships. Real support
would mean either (a) a way to pass a dict of custom rules into
`CSSBackend` that get emitted as real classes, or (b) collecting
`style={...}` props into generated classes instead of inline styles,
per the note already in `arklight/backend/css/render.py`'s module
docstring. Both keep the "no arbitrary CSS/HTML strings" boundary the
rest of the project holds -- structured input in, real CSS out, same
shape as the `@media`/`<head>` design above. No implementation
decision yet; noted here so it isn't silently folded into v0.048's
scope. Held for a separate go-ahead, same as `arklight --search`
above.

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
