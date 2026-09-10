"""
`wireWatchers`: `vdom-5` (docs/Backends/REFACTOR-INDEX.md row 13) --
the runtime half of `Watch(name, then=Action.*(...))`
(`arklight.api.Watch`).

Per docs/Foundational/DESIGN-NOTES.md ("Watch effects"): no new
dispatch mechanism. A watch effect reuses the exact same
`ACTION_REGISTRY` dispatcher `wireClickInterceptor`
(`arklight/backend/js/runtime/dispatch.py`) already uses for
`Action.*(...)` -- the closed `actions` object built by
`arklight/backend/js/render.py`'s `_actions_object_js` -- just invoked
from a `store.subscribe` callback instead of a click listener.

`wireWatchers(store, specs)` is called once, from `initState()`
(`arklight/backend/js/runtime/state.py`), with the page's freshly
constructed store and the `data-ark-watch` JSON blob
(`IRPage.watch`, `[{"name": ..., "then": {"action": ..., "state": ...,
"args": {...}, "modifiers": [...]}}, ...]`) already parsed. It
snapshots each watched name's current value, then registers one more
`store.subscribe` listener alongside the existing `renderBindings`/
`renderClassBindings` pair: on every notification it re-reads each
watched name and, for any that actually changed since the last
snapshot, updates the snapshot *before* dispatching that watch's
`then` action.

Updating the snapshot before dispatch (not after) is deliberate, not
incidental: `store.set`'s `listeners.forEach` call is synchronous, so
an action that itself mutates the same watched name re-enters this
same subscriber while the outer call is still iterating `specs`. With
the snapshot already updated to the value the action *read* before
running, that reentrant pass only dispatches again if the action
actually produced a further change from that already-updated snapshot
-- so a `then=Action.set(name, <fixed value>)` clamp settles in a
small, fixed number of reentrant passes (the last of which sees the
same value the previous pass just set and stops there), never an
unbounded loop, even though `store.set` itself always notifies
regardless of whether the value actually changed. Any *other* spec
whose watched name genuinely changed as a side effect of that action
is still correctly picked up on the same reentrant pass, matching a
synchronous watcher's usual semantics (Vue's non-`flush: "post"`
watchers behave the same way).

`.modifiers` (Stage 3's `.with_modifiers(...)`/`.debounce(...)`/
`.throttle(...)`) are deliberately not read here -- see
`arklight.ir.schema.MODIFIER_REGISTRY`'s docstring for why those exist
at all: they're a *click-timing* concern (coalescing rapid clicks on
one element), which has no equivalent for a state-change subscription
that already only fires once per actual value change. `ir.validate`
doesn't restrict a `Watch(...)`'s `then=` from carrying modifiers (the
same `ActionRef` shape `on_click=` uses), but this fragment simply
never reads `spec.then.modifiers`, so any present are silently inert
-- consistent with `actions[...]` fragments themselves never touching
modifier tokens either (`wireClickInterceptor` reads `hx-trigger` at
the *element* level, upstream of the actual `action(...)` call this
fragment also makes).
"""

from __future__ import annotations

WIRE_WATCHERS_JS = """  function wireWatchers(store, specs) {
    if (!store || !specs || !specs.length) return;
    var last = specs.map(function (spec) { return store.get(spec.name); });
    store.subscribe(function () {
      specs.forEach(function (spec, i) {
        var current = store.get(spec.name);
        if (current === last[i]) return;
        last[i] = current;
        try {
          var action = actions[spec.then.action];
          if (!action) return;
          action(store, spec.then.state, spec.then.args || {});
        } catch (err) {
          arkNotify("Something went wrong updating this page -- an unsupported or unexpected case was hit.");
        }
      });
    });
  }

"""
