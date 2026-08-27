"""
`wireActions`: wires every `[data-ark-on-click^="action:"]` element to
its `ACTION_FRAGMENTS` entry, resolving `data-ark-action-state` /
`data-ark-action-args`, and running the dispatch through
`arklight.backend.js.runtime.modifiers.arkApplyModifiers`.

Split out of `arklight/backend/js/render.py`'s old `_STATE_CORE_JS`
(`refactor-0`). Pure move, no JS output change.
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
        var dispatch = arkApplyModifiers(el, function () {
          try {
            action(store, stateKey, args);
          } catch (err) {
            arkNotify("Something went wrong updating this page -- an unsupported or unexpected case was hit.");
          }
        });
        el.addEventListener("click", function (event) {
          event.preventDefault();
          dispatch(event);
        });
      } catch (err) {
        // One malformed element (e.g. bad data-ark-action-args JSON)
        // must not abort wiring for every other element in this loop.
        arkNotify("One of this page's interactive elements couldn't be set up.");
      }
    });
  }"""
