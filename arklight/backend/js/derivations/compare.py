"""
`compare` derivation fragment. See `sum.py` for the general shape.

`args.op` is validated at build time against
`arklight.ir.schema.COMPARE_OPS` -- never a raw operator string
executed as code (mirrors why `on_click`/`action` are closed
vocabularies rather than arbitrary strings). The `default: return
false` branch is unreachable once Validation has run, same as the
Python-side `_evaluate_derivation`'s own unreachable fallback.
"""

from __future__ import annotations

NAME = "compare"

JS_FRAGMENT = """    compare: function (state, names, args) {
      var a = state[names[0]];
      var b = state[names[1]];
      switch (args.op) {
        case "eq": return a === b;
        case "ne": return a !== b;
        case "gt": return a > b;
        case "lt": return a < b;
        case "gte": return a >= b;
        case "lte": return a <= b;
        default: return false;
      }
    }"""
