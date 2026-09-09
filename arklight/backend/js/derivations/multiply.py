"""
`multiply` derivation fragment. See `sum.py` for the general shape.
"""

from __future__ import annotations

NAME = "multiply"

JS_FRAGMENT = """    multiply: function (state, names, args) {
      return names.reduce(function (total, name) {
        return total * (Number(state[name]) || 0);
      }, 1);
    }"""
