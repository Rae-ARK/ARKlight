"""
`wireClickInterceptor`: the single, delegated `click` listener that
dispatches both `Action.*(...)` state mutations and named-behavior
runs (`toggle`, `scroll-to`, `copy`, `dismiss`). Through `htmx-4` these
were two separate mechanisms: actions dispatched through this file's
own delegated listener (`wireActionInterceptor`, landed at `htmx-3`,
replacing the old `wireActions()` -- the `querySelectorAll('[data-ark-
on-click^="action:"]')`/`forEach`/per-element-`addEventListener` loop
this module held through `htmx-2`; see git history / CHANGELOG.md
`[0.0492]` onward for that shape); behaviors dispatched through
vendored HTMX's own `hx-on:click="arkRunBehavior('<name>', this)"`
attribute processing (landed at `htmx-1`).

**`htmx-5`** (see `docs/Backends/HTMX-INTEGRATION.md` "Stage 4 --
Audit and remove remaining hand-rolled plumbing" / `docs/Backends/
REFACTOR-INDEX.md` row 10) removes the `hx-on:click` mechanism
entirely and folds behavior dispatch into this one function, renamed
from `wireActionInterceptor` to `wireClickInterceptor` accordingly.

**Why, precisely -- this is the actual finding of the htmx-5 audit,
not a style preference:** HTMX's `hx-on:click` attribute processing
does not call the named function directly. It builds a new function
from the attribute's string value with the `Function` constructor
(`new Function("event", attributeValue)`) and calls that -- an
eval-equivalent operation, gated only by `htmx.config.allowEval`
(`true` by default in the vendored release). Every named-behavior
click on every ARKlight site using `on_click="toggle"` (or
`"scroll-to"`/`"copy"`/`"dismiss"`) was, through `htmx-4`, routing
through that path -- directly contradicting this project's own stated
invariant (see `arklight/backend/js/render.py`'s module docstring:
"there is no eval, no new Function, no string ever executed as code").
`arkRunBehavior`'s own body was always a small, fixed,
statically-readable function; the eval-equivalent step was HTMX's
attribute-processing machinery *getting there*, not anything ARKlight
wrote -- which is exactly the case where this stage's "remove
hand-rolled plumbing that HTMX already duplicates" mandate cuts the
other way: here, HTMX's own machinery duplicated something ARKlight's
delegated-listener pattern (already proven out for actions at
`htmx-3`) does perfectly well without ever constructing a function
from a string.

The fix folds behavior dispatch into the existing delegated `click`
listener: `data-ark-on-click` now carries `"behavior:<name>"` for a
named behavior, matched-pair with the `"action:<name>"` shape it
already carried for `Action.*(...)` (see `arklight/backend/html/
attrs.py`'s module docstring for the compiled-attribute side of this
change). One `addEventListener("click", ...)` call still handles both
shapes, branching on the attribute's prefix -- so this remains exactly
the "single registration, not a per-element wiring pass" outcome
`htmx-3` established, just with one more case in the branch.

**Side effect, not the goal, but real:** a page that uses named
behaviors and nothing else (no `State(...)`, no `Action.*(...)`) no
longer needs HTMX loaded at all -- see `arklight/backend/js/
render.py`'s `_build_runtime_js`, `needs_htmx`. Through `htmx-4`,
`hx-on:click` processing was the *only* reason a behavior-only page
shipped HTMX; with that gone, the common "toggle a menu, nothing
else" site ships a smaller runtime. `hx-boost`/`hx-preserve`
(`app_shell`) and `hx-trigger` (`Action.*` modifiers, which require
`State(...)`) are unaffected by this stage -- neither exercises the
eval-equivalent paths this stage removes ARKlight's reliance on, so
both keep working exactly as `htmx-2`/`htmx-4` left them. As further,
defense-in-depth hardening (belt-and-suspenders, not required for
correctness given the above), `arklight/backend/js/render.py` also
sets `htmx.config.allowEval = false` whenever HTMX ships, so that even
a future stage accidentally emitting `hx-vals`/`hx-vars`/bracket-
syntax `hx-trigger` filters -- the other paths inside vendored HTMX
that construct a function from a string -- fails safely instead of
silently executing.

Split out of `arklight/backend/js/render.py`'s old `_STATE_CORE_JS`
(`refactor-0`). Pure move at that stage, no JS output change.

**Deviation from the design doc's literal wording, documented here
because it matters:** `HTMX-INTEGRATION.md` describes this stage as
"Register an `htmx:beforeRequest` interceptor... that catches
HTMX-triggered events". Taken literally, that doesn't work for every
`Action.*(...)` button on a real HTMX build: `htmx:beforeRequest` is
only ever dispatched by HTMX's own `he()` request path, which only
runs for an element carrying a request-verb attribute (`hx-get`/
`hx-post`/etc) -- something `Action.*(...)` buttons deliberately never
have, being client-local state mutations, not server requests (see
`HTMX-INTEGRATION.md`'s "HTMX as a client-local interaction target").
An `ActionRef` *with* modifiers does get a compiled `hx-trigger`
attribute (`htmx-2`), and HTMX's own attribute processing *does* wire
a debounce/throttle/once/consume-aware native listener for that case
even without a request verb (its `hx-trigger`-only branch, dispatching
a bubbling `htmx:trigger` -- not `htmx:beforeRequest` -- event) -- but
an `ActionRef` with *no* modifiers, the common case, gets no compiled
attribute from `htmx-2` at all, so HTMX's attribute processing does
nothing with it whatsoever. Wiring only through an HTMX-dispatched
event would silently drop every unmodified `Action.*(...)` button's
click handling -- not an acceptable regression for a "JS-only,
independent" stage per `REFACTOR-INDEX.md` row 6's own framing.

The fix that preserves both the "single interceptor registration,
not a per-element wiring pass" outcome the design calls for *and*
correctness for the unmodified-action case: register one delegated
listener on `document` for the plain native `click` event (event
delegation via `Element.closest()`), which fires for every
`[data-ark-on-click^="action:"]` element regardless of whether HTMX's
own attribute processing touched it. This is still exactly one
`addEventListener` call for the whole page, still deletes the old
per-element `querySelectorAll`/`forEach` loop, and still needs no
`attrs.py` changes -- `data-ark-action-*` are read exactly as before,
unmodified by this stage, matching `REFACTOR-INDEX.md` row 6's "HTML-
side `data-ark-action-*` attributes are unchanged" note. `"prevent"`
remains honored by construction (the `event.preventDefault()` call
below is unconditional, independent of any modifier, same as every
prior stage). `debounce`/`throttle`/`once`/`stop`'s *compiled*
`hx-trigger` tokens still describe intent in the page's markup (kept
for a future stage that wires this interceptor through HTMX's own
trigger-spec parsing directly, once `htmx-4`'s app-shell audit settles
what survives a boosted swap) -- this stage closes the "no listener at
all" gap `htmx-2` left open, not the "modifier timing" gap; that
remains a documented, deliberate scope boundary of this stage.

`htmx-4` (docs/Backends/REFACTOR-INDEX.md row 9) changed this
function's signature (then still named `wireActionInterceptor`) from
`wireActionInterceptor(store)` to `wireActionInterceptor(getStore)`,
taking a zero-argument getter instead of a fixed store value. This is
the audit `htmx-3`'s docstring above already flagged as deferred here,
for a reason specific to app-shell navigation: `DOMContentLoaded` only
ever fires once per real document load, but a page carrying
`State(...)` under `Site(app_shell=True)` needs its store re-created
on every boosted navigation to a *different* page (see
`arklight/backend/js/render.py`'s `arkInitPage`) -- each with its own
initial values. The interceptor itself, though, is registered exactly
once, at `DOMContentLoaded`, and must never be registered again
(`document` itself is never replaced by a boosted swap, so a second
`addEventListener("click", ...)` call would stack a second listener
closing over a now-stale store, double-firing every click and acting
on outdated state). Passing a getter instead of a value lets the one
registered listener always read whatever `arkInitPage` most recently
assigned, without re-registering. On a non-app_shell site this is a
no-op difference -- `getStore` is called once per click either way,
and there's only ever one store to return. `htmx-5` keeps this exact
`getStore` contract on the renamed `wireClickInterceptor` -- a
behavior dispatch never calls `getStore()` at all (behaviors are
stateless by design; see `arklight/backend/js/behaviors/`), so a
behavior-only page (no `State(...)` anywhere) simply passes a getter
that always returns `null`, which the action branch's existing
`if (!store) return;` guard already handles correctly -- see
`arklight/backend/js/render.py`'s `_build_runtime_js`.
"""

from __future__ import annotations

CLICK_INTERCEPTOR_JS = """  function wireClickInterceptor(getStore) {
    document.addEventListener("click", function (event) {
      var el = event.target.closest("[data-ark-on-click]");
      if (!el) return;
      var raw = el.getAttribute("data-ark-on-click");
      if (raw.indexOf("action:") === 0) {
        var store = getStore();
        if (!store) return;
        event.preventDefault();
        try {
          var actionName = raw.slice("action:".length);
          var stateKey = el.getAttribute("data-ark-action-state");
          var argsRaw = el.getAttribute("data-ark-action-args");
          var args = argsRaw ? JSON.parse(argsRaw) : {};
          var action = actions[actionName];
          if (!action) return;
          action(store, stateKey, args);
        } catch (err) {
          arkNotify("Something went wrong updating this page -- an unsupported or unexpected case was hit.");
        }
      } else if (raw.indexOf("behavior:") === 0) {
        event.preventDefault();
        try {
          var behaviorName = raw.slice("behavior:".length);
          var behavior = behaviors[behaviorName];
          if (!behavior) return;
          behavior(el);
        } catch (err) {
          arkNotify("Something went wrong running this action -- an unsupported or unexpected case was hit.");
        }
      }
    });
  }"""
