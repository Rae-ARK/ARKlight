"""
`count` derivation fragment. See `sum.py` for the general shape.

Reads a single list-valued (or string-valued, or plain-object-valued)
`State(...)`/`Computed(...)`'s length -- mirrors
`arklight.ir.build._evaluate_derivation`'s `"count"` case, which
accepts the same three shapes (`list`/`tuple`, `str`, `dict`) and
falls back to `0` for anything else.
"""

from __future__ import annotations

NAME = "count"

JS_FRAGMENT = """    count: function (state, names, args) {
      var value = state[names[0]];
      if (Array.isArray(value) || typeof value === "string") { return value.length; }
      if (value && typeof value === "object") { return Object.keys(value).length; }
      return 0;
    }"""
