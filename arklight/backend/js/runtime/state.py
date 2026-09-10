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

`vdom-4` (docs/Backends/REFACTOR-INDEX.md row 12): `createState` gains
a second, optional `computed` argument -- the same dependency-ordered
`(name, spec)` pairs `IRPage.computed` carries (see
`arklight/ir/build.py`), JSON-round-tripped as plain 2-element arrays
(`[["total", {"kind": "multiply", "names": [...], "args": {...}}],
...]`). A new `recomputeAll()` closure walks that list in order --
already a valid recompute order because `arklight.ir.build`'s
`_topological_order_computed` sorted it once at build time, so the
client never re-derives that ordering itself -- looking each entry's
`kind` up in the `derivations` object (`arklight/backend/js/
derivations/`, assembled into scope by `arklight/backend/js/
render.py`'s `_derivations_object_js`, the same "only ship what's
used" pattern `actions`/`behaviors` already follow) and writing the
result straight into `state` under that `Computed(...)`'s own `name`
-- so a `Computed(...)` value is readable through the exact same
`store.get(key)` every `Bind(...)`/`renderBindings` call already uses,
with no separate lookup path for computed vs. plain state.
`recomputeAll()` runs once at construction (so a value is already
present before the first render) and again at the end of every `set`/
`reset`, *before* that call's subscriber notification -- so a
subscriber (`renderBindings`/`renderClassBindings`) always sees
already-fresh computed values, never a stale one from before the
triggering mutation. `computed` defaults to an empty array on a page
with no `Computed(...)` declarations, in which case `recomputeAll()`
is a no-op and `derivations` (whose declaration is itself gated on
`has_computed` in `_build_runtime_js`) is never dereferenced.
`initState()` below reads the sibling `data-ark-computed` attribute
the same way it already reads `data-ark-state`, and passes it through.

`vdom-5` (docs/Backends/REFACTOR-INDEX.md row 13): `initState()` also
reads a sibling `data-ark-watch` attribute (`IRPage.watch`, the same
marker/`<body>`-attribute duality `data-ark-state`/`data-ark-computed`
already use) and, once the store is constructed, hands it to
`wireWatchers` (`arklight/backend/js/runtime/watch.py`) alongside the
existing `renderBindings`/`renderClassBindings` subscriber -- one more
kind of `store.subscribe` listener, per that module's docstring. The
call is guarded with `typeof wireWatchers === "function"` rather than
called unconditionally: `STATE_CORE_JS` (this fragment) ships on
*every* stateful page, but `WIRE_WATCHERS_JS` only ships on a page
that actually declares `Watch(...)` (see `arklight/backend/js/
render.py`'s `_build_runtime_js`) -- an unconditional call would throw
a `ReferenceError` on any stateful page with no watch effects at all,
`typeof` is the standard safe way to probe for a maybe-undeclared
identifier without that risk.

`vdom-6` (docs/Backends/REFACTOR-INDEX.md row 14): the `store.subscribe`
callback also calls `renderModelBindings(store)`
(`arklight/backend/js/runtime/model.py`), same `typeof`-guarded,
only-shipped-when-used pattern as `wireWatchers` just above -- a page
with no `bind_value=` anywhere never declares that function.
"""

from __future__ import annotations

CREATE_STATE_JS = """  function createState(initial, computed) {
    var state = Object.assign({}, initial);
    var listeners = [];
    function recomputeAll() {
      (computed || []).forEach(function (entry) {
        var name = entry[0];
        var spec = entry[1];
        var derive = derivations[spec.kind];
        if (derive) { state[name] = derive(state, spec.names, spec.args); }
      });
    }
    recomputeAll();
    return {
      get: function (key) { return state[key]; },
      set: function (key, value) {
        state[key] = value;
        recomputeAll();
        listeners.forEach(function (fn) { fn(); });
      },
      reset: function (key) {
        state[key] = initial[key];
        recomputeAll();
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
    var rawComputed = marker
      ? marker.getAttribute("data-ark-computed")
      : document.body.getAttribute("data-ark-computed");
    var rawWatch = marker
      ? marker.getAttribute("data-ark-watch")
      : document.body.getAttribute("data-ark-watch");
    try {
      var computed = rawComputed ? JSON.parse(rawComputed) : [];
      var watch = rawWatch ? JSON.parse(rawWatch) : [];
      var store = createState(JSON.parse(raw), computed);
      store.subscribe(function () {
        renderBindings(store);
        renderClassBindings(store);
        if (typeof renderModelBindings === "function") { renderModelBindings(store); }
      });
      if (typeof wireWatchers === "function") { wireWatchers(store, watch); }
      return store;
    } catch (err) {
      arkNotify("This page's saved state couldn't be loaded -- interactive features on this page may not work.");
      return null;
    }
  }

"""
