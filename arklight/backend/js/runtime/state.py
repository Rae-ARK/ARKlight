"""
Reactive state core: `createState` (the plain store: get/set/reset +
subscribe) and `initState` (reads `data-ark-state` off `<body>`, JSON
Notice-parses it, and wires the store's subscribers to the render
passes in `arklight.backend.js.runtime.bindings`).

Split out of `arklight/backend/js/render.py`'s old `_STATE_CORE_JS`
(`refactor-0`, see `docs/Backends/REFACTOR-INDEX.md`) -- pure move, no
JS output change. Mirrors the `actions/`/`behaviors/` per-file
pattern: `arklight.backend.js.runtime` reassembles these fragments in
the same order the monolithic string used to hold them.
"""

from __future__ import annotations

CREATE_STATE_JS = """  function createState(initial) {
    var state = Object.assign({}, initial);
    var listeners = [];
    return {
      get: function (key) { return state[key]; },
      set: function (key, value) {
        state[key] = value;
        listeners.forEach(function (fn) { fn(); });
      },
      reset: function (key) {
        state[key] = initial[key];
        listeners.forEach(function (fn) { fn(); });
      },
      subscribe: function (fn) { listeners.push(fn); }
    };
  }

"""

INIT_STATE_JS = """  function initState() {
    var raw = document.body.getAttribute("data-ark-state");
    if (!raw) return null;
    try {
      var store = createState(JSON.parse(raw));
      store.subscribe(function () { renderBindings(store); renderClassBindings(store); });
      return store;
    } catch (err) {
      arkNotify("This page's saved state couldn't be loaded -- interactive features on this page may not work.");
      return null;
    }
  }

"""
