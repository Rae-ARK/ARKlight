"""
`sum` derivation fragment (`vdom-4` -- see `arklight.ir.schema.DERIVATION_REGISTRY`).

Every derivation fragment has the same shape: `name: function (state,
names, args) { ... return <value>; }`, called by `createState`'s
recompute pass (`arklight/backend/js/runtime/state.py`) with the
store's plain state object, the owning `Computed(...)`'s `names` in
declared order, and its `args` dict (already parsed from JSON -- see
`arklight/backend/js/render.py`). Mirrors `arklight.ir.build`'s
build-time `_evaluate_derivation("sum", ...)` case so a page's
server-rendered `Bind(...)` text never disagrees with what the client
recomputes after the first state change.
"""

from __future__ import annotations

NAME = "sum"

JS_FRAGMENT = """    sum: function (state, names, args) {
      return names.reduce(function (total, name) {
        return total + (Number(state[name]) || 0);
      }, 0);
    }"""
