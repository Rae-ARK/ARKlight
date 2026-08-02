"""
Per-action JS runtime fragments (v0.0035).

Mirrors `arklight.backend.js.behaviors`: each sibling module exports
`NAME` (matching a key in `arklight.ir.schema.ACTION_REGISTRY`) and
`JS_FRAGMENT` (that action's `name: function (store, key, args) {
... }` entry). `JSBackend.render()` includes the reactive core (and
only the action fragments actually used) for a build only when at
least one page declares `State(...)`.
"""

from __future__ import annotations

from arklight.backend.js.actions import decrement, increment, reset, set, toggle_bool

ACTION_MODULES = {
    set.NAME: set,
    increment.NAME: increment,
    decrement.NAME: decrement,
    toggle_bool.NAME: toggle_bool,
    reset.NAME: reset,
}

ACTION_FRAGMENTS: dict[str, str] = {
    name: module.JS_FRAGMENT for name, module in ACTION_MODULES.items()
}
