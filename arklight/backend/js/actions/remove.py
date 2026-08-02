"""
`remove` action fragment. See `append.py` and `set.py` for context.

Removes the element at `args.index` from a list-valued `State(...)`.
Index-based (not value-based) on purpose -- it's the unambiguous case
(a value-based `remove` would need an equality rule for objects) and
matches the common "remove the Nth item in a rendered list" use case.
"""

from __future__ import annotations

NAME = "remove"

JS_FRAGMENT = """    remove: function (store, key, args) {
      var list = store.get(key) || [];
      store.set(key, list.filter(function (_, i) { return i !== args.index; }));
    }"""
