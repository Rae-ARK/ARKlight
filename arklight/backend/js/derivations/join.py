"""
`join` derivation fragment. See `sum.py` for the general shape.

`args.sep` defaults to `" "`, matching `Derive.join(*names, sep=" ")`'s
own Python-side default (`arklight.api.Derive.join`).
"""

from __future__ import annotations

NAME = "join"

JS_FRAGMENT = """    join: function (state, names, args) {
      var sep = args && args.sep !== undefined ? args.sep : " ";
      return names
        .map(function (name) { return state[name]; })
        .join(sep);
    }"""
