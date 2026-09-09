"""
`format` derivation fragment. See `sum.py` for the general shape.

Fixed `{name}`-style substitution over named state values only --
mirrors `arklight.ir.build._evaluate_derivation`'s `"format"` case
(itself mirroring `arklight.api.Derive.format`'s own docstring: this
is `str.format`-shaped, never a general string-eval). `args.names_map`
maps each `{placeholder}` in `args.template` to the state/computed
name whose value fills it; a placeholder with no entry in
`names_map` is left untouched, same as the Python-side regex
substitution's `match.group(0)` fallback.
"""

from __future__ import annotations

NAME = "format"

JS_FRAGMENT = """    format: function (state, names, args) {
      var template = args.template;
      var namesMap = args.names_map || {};
      return template.replace(/\\{(\\w+)\\}/g, function (match, key) {
        var stateName = namesMap[key];
        return stateName !== undefined ? state[stateName] : match;
      });
    }"""
