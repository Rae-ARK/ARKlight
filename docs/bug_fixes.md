# ARKlight Philosophy Audit

**Scope:** `Rae-ARK/ARKlight`, `alpha` branch, commit `678a60d`
("Combined Refactoring Started~ Stage 11 done").

**Method:** grepped the codebase for the project's own stated invariants
(quoted below) and their known failure modes, then read every hit in
context against `docs/Backends/REFACTOR-INDEX.md`'s stage-status table
and the test suite to see which are still live and unfixed.

## The stated philosophy (for reference)

Pulled directly from the codebase's own docstrings, so the findings below
can be checked against ARKlight's own words rather than an outside
standard:

- **"The browser never executes Python."** (`arklight/__init__.py`) —
  output is plain HTML/CSS/vanilla JS; the compiler is the only thing
  that runs Python.
- **"No eval, no new Function, no string ever executed as code."**
  (`arklight/backend/js/render.py`, `runtime/dispatch.py`, `attrs.py`) —
  the shipped runtime never turns a string into executable code, even
  via a vendored dependency's optional feature.
- **"Fail loudly at build time, not silently in the browser."**
  (`ir/validate.py`, `config.py`, `experimental.py`) — anything wrong
  with a site should raise a `ValidationError` in Python during
  `arklight build`, never manifest as silent broken behavior after
  deployment.
- **"Only ship what's used."** (`js/htmx.py`, `js/render.py`, `attrs.py`)
  — the compiler emits the minimum HTML/CSS/JS a given site's IR
  actually needs; nothing bundled unconditionally.
- **Compiled markup should be honest about what it does** — the project
  repeatedly frames "inspectable, predictable" output as the point of
  compiling to plain HTML at all (`README.md`'s opening description).

## Findings

### 1. `Action.*` event modifiers (`debounce`/`throttle`/`once`/`stop`) are compiled but not enforced — violates "fail loudly, not silently" and "honest markup"

**Severity: should fix.** This is the one confirmed, currently-live gap.

**What's wrong:** `.debounce(300)` / `.throttle(...)` / `.with_modifiers("once", "stop")`
on an `Action.*` call compiles correctly to an `hx-trigger="click debounce:300ms"`
attribute (`arklight/backend/html/attrs.py::_modifiers_to_hx_trigger`), but
the shipped runtime's delegated click listener
(`arklight/backend/js/runtime/dispatch.py::wireClickInterceptor`) never
reads `hx-trigger` at all — it dispatches the action on *every* click,
immediately, regardless of any declared modifier. A page author who
writes `debounce=300` to collapse rapid double-clicks gets no debouncing;
`once` doesn't stop a second click from re-firing; `stop` doesn't call
`event.stopPropagation()`.

**Why it's a philosophy violation, specifically:** this is exactly the
failure mode `ir/validate.py`'s own docstring warns against — a case
where something is wrong with the site and the *only* place that shows
up is "silently in the browser," at runtime, invisible to the page
author unless they manually test the interaction. The HTML output looks
correct on inspection (the attribute is there, honest about *intent*)
but the compiled artifact doesn't do what it visibly claims to do. It
also produces genuinely dead code: HTMX's own attribute processing does
still wire a correctly-timed native listener for that `hx-trigger`
attribute and fires a bubbling `htmx:trigger` event — but nothing in
ARKlight's runtime listens for it, so that code path runs and produces
nothing, on every page that uses a modifier.

**Where:**
- `arklight/backend/html/attrs.py` (`_modifiers_to_hx_trigger`) — compiles correctly.
- `arklight/backend/js/runtime/dispatch.py` (`CLICK_INTERCEPTOR_JS` / `wireClickInterceptor`) — doesn't read what was compiled.
- Acknowledged in-repo: `arklight/backend/js/render.py` line ~134 ("a deliberate, documented, temporary gap"); `runtime/dispatch.py`'s module docstring calls it "a documented, deliberate scope boundary."

**Test coverage gap:** `tests/test_event_modifiers.py` only asserts the
*compiled attribute string* is correct
(`test_html_backend_emits_hx_trigger_for_modifiers`). No test anywhere
exercises actual debounce/throttle/once/stop timing in the JS runtime,
so this could regress further without anything failing.

**Roadmap status:** not tracked. `docs/Backends/REFACTOR-INDEX.md`'s
rows 1–11 (`htmx-1` through `html-6`) are all marked **Done**; the
remaining unstarted rows (`vdom-4`–`vdom-8`) are unrelated features
(computed state, watch effects, two-way binding, list rendering,
persistence). There is no numbered stage that closes this gap.

**Fix shape (not yet implemented):** give `wireClickInterceptor` its own
per-element debounce/throttle/once bookkeeping (timestamps or timers
keyed off the element, e.g. via a `WeakMap`) and an unconditional
`event.stopPropagation()` for the `stop` token — all read from the
already-compiled `hx-trigger` string (or a small dedicated
`data-ark-*` encoding of it), so it stays inside the existing "no eval,
no new Function" invariant. Alternatively, wire through HTMX's own
`htmx:trigger` event (which already fires correctly-timed) instead of
duplicating the timing logic by hand.

## Areas checked, no violation found

For completeness — these were checked against the same invariants and
are clean:

- **"No eval, no new Function"** — holds throughout the current runtime.
  The one place this was previously violated (`hx-on:click` building a
  `new Function` internally inside vendored HTMX) was already found and
  fixed at the `htmx-5` stage (`data-ark-on-click="behavior:<n>"` now
  routes through the same delegated listener as actions), plus
  defense-in-depth (`htmx.config.allowEval = false`) against any future
  stage accidentally emitting `hx-vals`/`hx-vars`/bracket-syntax
  `hx-trigger` filters.
- **`shell_persistent` inertness** (`ir/validate.py`) — the prop is a
  no-op on a site without `Site(app_shell=True)`, but this is validated
  and intentional, not a silent-in-the-browser case: nothing is
  compiled that implies behavior that then doesn't happen.
- **"Only ship what's used"** — spot-checked `needs_htmx` gating in
  `arklight/backend/js/render.py`; HTMX is correctly omitted for
  behavior-free, state-free pages, and the vendored bundle itself is
  shipped unmodified/unminified-further per its own sourcing note.
- No other `TODO`/`FIXME`/`NotImplementedError` markers exist outside
  `Backend.postprocess`'s intentional base-class stub.
- No other case was found where a compiler module's own docstring flags
  a "deliberate, documented gap" between compiled output and runtime
  behavior — the modifier-timing gap above appears to be the only
  instance of this specific pattern in the current tree.

## Bottom line

One real, confirmed issue: **`Action.*` event modifiers are markup
without teeth.** Everything else the project claims about itself
(no eval, fail-loudly validation, ship-only-what's-used, browser never
runs Python) checks out against the actual code as of this commit.
