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
  vocabulary (menus, toggles, scroll-to -- not forms, not client-side
  validation, not anything stateful across more than one class flip).
- Anyone who needs more than one page layout shape -- everything is
  capped at a fixed-width column with no override hook yet.
- Anyone who needs real responsive design -- no `@media` hook (see
  above).
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
