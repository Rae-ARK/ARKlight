"""
Reactive-state runtime fragments (`refactor-0`, see
`docs/Backends/REFACTOR-INDEX.md` and
`docs/Backends/JS-BACKEND-REFACTOR-PLAN.md`).

Splits `arklight/backend/js/render.py`'s old `_STATE_CORE_JS` /
`_NOTIFY_JS` / `_NAV_HIGHLIGHT_JS` constants (145+ lines, one
triple-quoted string apiece) into one sibling module per function --
`state.py`, `bindings.py`, `modifiers.py`, `dispatch.py`, `nav.py`,
`notify.py` -- mirroring the `arklight.backend.js.actions` /
`arklight.backend.js.behaviors` per-file pattern already established
for the per-name registries. Unlike those two packages, nothing here
is keyed by a registry name: these six pieces are the fixed reactive
core every stateful page ships as a unit, not a per-usage selection,
so this module just reassembles them in the same order the old
monolithic strings held them.

`STATE_CORE_JS` below is byte-for-byte the old `_STATE_CORE_JS` value:
`createState` and `initState` (from `state.py`) sandwich
`renderBindings` / `renderClassBindings` (from `bindings.py`) exactly
as the original triple-quoted string ordered them, followed by
`arkApplyModifiers` (`modifiers.py`) and `wireActions`
(`dispatch.py`). This is a pure refactor -- no generated JS output
changes as a result of this split.
"""

from __future__ import annotations

from arklight.backend.js.runtime.bindings import (
    RENDER_BINDINGS_JS,
    RENDER_CLASS_BINDINGS_JS,
)
from arklight.backend.js.runtime.dispatch import WIRE_ACTIONS_JS
from arklight.backend.js.runtime.modifiers import APPLY_MODIFIERS_JS
from arklight.backend.js.runtime.nav import NAV_HIGHLIGHT_JS
from arklight.backend.js.runtime.notify import NOTIFY_JS
from arklight.backend.js.runtime.state import CREATE_STATE_JS, INIT_STATE_JS

# Reassembled in the exact original order -- see module docstring.
STATE_CORE_JS = (
    CREATE_STATE_JS
    + RENDER_BINDINGS_JS
    + RENDER_CLASS_BINDINGS_JS
    + INIT_STATE_JS
    + APPLY_MODIFIERS_JS
    + WIRE_ACTIONS_JS
)

__all__ = [
    "STATE_CORE_JS",
    "NOTIFY_JS",
    "NAV_HIGHLIGHT_JS",
]
