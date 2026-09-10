"""
`vdom-6` (docs/Backends/REFACTOR-INDEX.md row 14): two-way input
binding. `bind_value=Bind.model("query")` (`arklight/api.py`) compiles
to `data-ark-model="query"` (`arklight/backend/html/attrs.py`) on an
element -- typically an `Input`. Two small pieces, mirroring the
existing `bind_class`/`renderClassBindings` split between a render
pass and a dispatch listener:

- `renderModelBindings(store)` -- one more `store.subscribe` render
  pass, alongside `renderBindings`/`renderClassBindings`: writes
  `store.get(key)` into the element's `.value` whenever state changes
  from *any* source (an `Action.*(...)` button, `Action.reset(...)`,
  another bound input, etc), not just this element's own typing.
  Compares against the element's current `.value` first (as a string)
  so a user's own keystroke -- which already triggered this exact
  state via `wireModelBinding` below, one line before `set()` notifies
  subscribers -- doesn't get its cursor position reset by reassigning
  a `.value` that's already correct.
- `wireModelBinding(getStore)` -- one delegated `input` listener on
  `document` (event delegation via `Element.closest()`, same pattern
  `wireClickInterceptor` uses for `click`), writing the element's
  `.value` into state on every keystroke. Takes a zero-argument getter
  rather than a fixed store, same reason and same contract as
  `wireClickInterceptor(getStore)` (`runtime/dispatch.py`): registered
  exactly once at `DOMContentLoaded`, must keep working across an
  `app_shell` boosted navigation to a *different* stateful page
  without re-registering a second, stale-closure listener.

Deliberately *not* routed through the vendored snabbdom core
(`arklight/backend/js/vdom.py`), same reasoning `renderClassBindings`
already documents for `bind_class`: `.value` is DOM element state, not
a vnode's own rendered children -- there's nothing for `patch()` to
diff here, just a direct property assignment.

Only shipped on a page that actually uses `bind_value=` somewhere
(`has_model_binding` in `arklight/backend/js/render.py`'s
`_collect_usage`/`_build_runtime_js`) -- same "only ship what's used"
discipline `WIRE_WATCHERS_JS`/the per-usage `actions`/`behaviors`/
`derivations` objects already follow.
"""

from __future__ import annotations

RENDER_MODEL_BINDINGS_JS = """  function renderModelBindings(store) {
    document.querySelectorAll("[data-ark-model]").forEach(function (el) {
      var key = el.getAttribute("data-ark-model");
      var value = store.get(key);
      if (el.value !== String(value == null ? "" : value)) {
        el.value = value == null ? "" : value;
      }
    });
  }

"""

WIRE_MODEL_BINDING_JS = """  function wireModelBinding(getStore) {
    document.addEventListener("input", function (event) {
      var el = event.target.closest("[data-ark-model]");
      if (!el) return;
      var store = getStore();
      if (!store) return;
      var key = el.getAttribute("data-ark-model");
      store.set(key, el.value);
    });
  }
"""
