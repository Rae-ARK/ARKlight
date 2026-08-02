"""
`increment` action fragment. See `set.py` for the general shape.
"""

from __future__ import annotations

NAME = "increment"

JS_FRAGMENT = """    increment: function (store, key, args) {
      var delta = args && args.delta !== undefined ? args.delta : 1;
      store.set(key, (store.get(key) || 0) + delta);
    }"""
