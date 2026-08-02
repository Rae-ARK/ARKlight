"""
`reset` action fragment. See `set.py` for the general shape.

v0.0035 vocabulary addendum: the second most-requested gap after
`decrement`. `Action.set(name, <literal>)` can already put a key back
to a fixed value, but that means hardcoding the initial value a second
time at every call site (and re-editing every call site if the initial
value in `State(...)` ever changes). `reset` instead reads the store's
own captured `initial` snapshot -- see the `reset` method added to
`createState` in `arklight/backend/js/render.py`'s `_STATE_CORE_JS` --
so "put this back the way it started" needs no argument at all.
"""

from __future__ import annotations

NAME = "reset"

JS_FRAGMENT = """    reset: function (store, key) {
      store.reset(key);
    }"""
