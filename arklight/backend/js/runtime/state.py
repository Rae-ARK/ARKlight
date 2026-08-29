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

`htmx-4` (docs/Backends/REFACTOR-INDEX.md row 9) changes where
`initState()` reads its JSON blob from. Per htmx's own docs, an
`hx-boost`ed swap replaces `<body>`'s *innerHTML* only, never the
`<body>` tag's own attributes -- so a `data-ark-state` attribute
placed directly on `<body>` would never update across an app-shell
boosted navigation to a different page. `arklight/backend/html/
page_render.py`'s `_render_page` accounts for this: on an
`app_shell=True` page with state, the JSON blob is instead emitted as
a `<div id="ark-state" data-ark-state="...">` marker that *is* part of
the swapped content. `initState()` below checks for that marker first
and falls back to the `<body>` attribute (the non-app_shell shape,
unchanged), so the same function handles both without needing to know
`app_shell` was set.
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
    var marker = document.getElementById("ark-state");
    var raw = marker
      ? marker.getAttribute("data-ark-state")
      : document.body.getAttribute("data-ark-state");
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
