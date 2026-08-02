"""
`set` action fragment (v0.0035 -- see `arklight.ir.schema.ACTION_REGISTRY`).

Every action fragment has the same shape: `name: function (store, key,
args) { ... }`, called by the reactive core's action dispatcher with
the page's state store, the target state's key, and the `ActionRef`'s
`args` dict (already parsed from JSON -- see
`arklight/backend/js/render.py`).
"""

from __future__ import annotations

NAME = "set"

JS_FRAGMENT = """    set: function (store, key, args) {
      store.set(key, args.value);
    }"""
