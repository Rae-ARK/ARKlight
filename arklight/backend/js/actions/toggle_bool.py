"""
`toggle_bool` action fragment. See `set.py` for the general shape.
"""

from __future__ import annotations

NAME = "toggle_bool"

JS_FRAGMENT = """    toggle_bool: function (store, key) {
      store.set(key, !store.get(key));
    }"""
