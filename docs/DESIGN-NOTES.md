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

## v0.0035 / v0.004 design: stateful JS, CLI scaffolding, responsive + head extension (PLANNING -- not yet implemented)

This section is a design doc, written before any of it is built, so the
shape gets agreed on before code exists (same discipline as the
Alpine/htmx-vs-Reflex research that preceded v0.003). Nothing below is
implemented yet -- see PROGRESS.md for what's actually landed.

Three initiatives, staged as two named milestones so this doesn't land
as one undifferentiated grab-bag:

- **v0.0035 -- Stateful JS.** The breadcrumb for this already exists in
  the v0.003 commit history ("Next is adding states in V0.0035"). This
  is the reactivity/IR-state milestone this document has been calling
  the real prerequisite for v0.100 (alternate backends) to mean
  anything.
- **v0.004 -- CLI scaffolding + responsive/head extension.** Two
  independent, smaller features that don't depend on state landing
  first.

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

### v0.004: CLI scaffolding (`arklight new`)

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
explicitly signaled, independent of the state of v0.0035/v0.004 above.

### v0.004: CSS media queries + `<head>` extension

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
behavior/action registries) lands first and independently; **v0.004**
(scaffolding + responsive/head) does not depend on it and could
technically land first if that's preferred once implementation starts.

## Why Python specifically, independent of popularity

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
