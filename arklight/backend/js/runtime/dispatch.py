"""
`wireActionInterceptor`: a single, delegated listener that replaces
the old `wireActions()` -- the `querySelectorAll('[data-ark-on-click^=
"action:"]')`/`forEach`/per-element-`addEventListener` loop this
module held through `htmx-2` (see git history / CHANGELOG.md `[0.0492]`
onward for that shape).

Split out of `arklight/backend/js/render.py`'s old `_STATE_CORE_JS`
(`refactor-0`). Pure move at that stage, no JS output change.

`htmx-3` (see `docs/Backends/HTMX-INTEGRATION.md` "Stage 3 -- Replace
`wireActions()` wiring loop" / `docs/Backends/REFACTOR-INDEX.md` row 6)
is what actually rewrites this file's contents -- the wiring loop
above is gone, replaced with the single delegated listener below.

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
"""

from __future__ import annotations

ACTION_INTERCEPTOR_JS = """  function wireActionInterceptor(store) {
    if (!store) return;
    document.addEventListener("click", function (event) {
      var el = event.target.closest('[data-ark-on-click^="action:"]');
      if (!el) return;
      event.preventDefault();
      try {
        var actionName = el.getAttribute("data-ark-on-click").slice("action:".length);
        var stateKey = el.getAttribute("data-ark-action-state");
        var argsRaw = el.getAttribute("data-ark-action-args");
        var args = argsRaw ? JSON.parse(argsRaw) : {};
        var action = actions[actionName];
        if (!action) return;
        action(store, stateKey, args);
      } catch (err) {
        arkNotify("Something went wrong updating this page -- an unsupported or unexpected case was hit.");
      }
    });
  }"""
