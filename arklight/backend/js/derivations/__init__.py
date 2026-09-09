"""
Per-derivation JS runtime fragments (`vdom-4`, see
`docs/Backends/REFACTOR-INDEX.md` row 12).

Mirrors `arklight.backend.js.actions`: each sibling module exports
`NAME` (matching a key in `arklight.ir.schema.DERIVATION_REGISTRY`)
and `JS_FRAGMENT` (that derivation's `name: function (state, names,
args) { ... }` entry). `createState`'s recompute pass
(`arklight/backend/js/runtime/state.py`) looks a `Computed(...)`'s
`kind` up in the `derivations` object these fragments assemble into,
and calls it with the store's plain state object plus that
`Computed(...)`'s `names`/`args` (both already parsed from the
`data-ark-computed` JSON blob -- see
`arklight/backend/html/page_render.py`). `JSBackend.render()` ships
the `derivations` object -- and only the fragments actually used --
for a build only when at least one page declares `Computed(...)`,
same "only ship what's used" discipline `ACTION_FRAGMENTS`/
`BEHAVIOR_FRAGMENTS` already apply.
"""

from __future__ import annotations

from arklight.backend.js.derivations import compare, count, format, join, multiply, sum

DERIVATION_MODULES = {
    sum.NAME: sum,
    multiply.NAME: multiply,
    join.NAME: join,
    count.NAME: count,
    format.NAME: format,
    compare.NAME: compare,
}

DERIVATION_FRAGMENTS: dict[str, str] = {
    name: module.JS_FRAGMENT for name, module in DERIVATION_MODULES.items()
}
