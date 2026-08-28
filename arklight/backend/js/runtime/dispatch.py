"""
`wireActions`: wires every `[data-ark-on-click^="action:"]` element to
its `ACTION_FRAGMENTS` entry, resolving `data-ark-action-state` /
`data-ark-action-args`.

Split out of `arklight/backend/js/render.py`'s old `_STATE_CORE_JS`
(`refactor-0`). Pure move, no JS output change at that stage.

`htmx-2` (see `docs/Backends/HTMX-INTEGRATION.md` "Stage 2 --
Modifiers" / `docs/Backends/REFACTOR-INDEX.md` row 5) removed the
`arkApplyModifiers(el, ...)` wrapper this used to dispatch through:
`arklight/backend/html/attrs.py` now compiles an `ActionRef`'s
modifier tokens into an `hx-trigger` attribute instead of
`data-ark-modifiers`, and `arkApplyModifiers()` (the runtime parser
that read the old attribute) is deleted along with it. This loop does
*not* yet read `hx-trigger` itself -- it still fires the action
directly on every native `click`, so `debounce`/`throttle`/`once`/
`stop` are compiled into the page's markup but not yet functionally
enforced. `htmx-3` (`docs/Backends/REFACTOR-INDEX.md` row 6) replaces
this whole `querySelectorAll`/`forEach` loop with a single
`htmx:beforeRequest` interceptor, at which point `hx-trigger` is what
actually governs when the interceptor fires and this gap closes.
`"prevent"` was never affected either way: the `event.preventDefault()`
call below is unconditional, independent of any modifier.
"""

from __future__ import annotations

WIRE_ACTIONS_JS = """  function wireActions(store) {
    if (!store) return;
    document.querySelectorAll('[data-ark-on-click^="action:"]').forEach(function (el) {
      try {
        var actionName = el.getAttribute("data-ark-on-click").slice("action:".length);
        var stateKey = el.getAttribute("data-ark-action-state");
        var argsRaw = el.getAttribute("data-ark-action-args");
        var args = argsRaw ? JSON.parse(argsRaw) : {};
        var action = actions[actionName];
        if (!action) return;
        el.addEventListener("click", function (event) {
          event.preventDefault();
          try {
            action(store, stateKey, args);
          } catch (err) {
            arkNotify("Something went wrong updating this page -- an unsupported or unexpected case was hit.");
          }
        });
      } catch (err) {
        // One malformed element (e.g. bad data-ark-action-args JSON)
        // must not abort wiring for every other element in this loop.
        arkNotify("One of this page's interactive elements couldn't be set up.");
      }
    });
  }"""
