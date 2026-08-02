"""
Reserved for v0.0035 (stateful JS).

Scaffolding only -- no behavior fragments live here yet. Per
`docs/DESIGN-NOTES.md` ("v0.0035: stateful JS -- capability, not
vocabulary"), `arklight/backend/js/render.py` currently holds one
hand-written `RUNTIME_JS` string with a hardcoded `behaviors` object
inside it, matched by the flat `KNOWN_BEHAVIORS` frozenset in
`arklight/ir/schema.py`.

The plan, not yet implemented, is for both to become data:

- `arklight/ir/schema.py`: `KNOWN_BEHAVIORS` (frozenset) becomes
  `BEHAVIOR_REGISTRY: dict[str, BehaviorSpec]`, with `KNOWN_BEHAVIORS`
  kept as `frozenset(BEHAVIOR_REGISTRY)` so Validation's existing check
  doesn't change shape. A parallel `ACTION_REGISTRY` covers the new
  `Action.*` vocabulary (`set`, `increment`, `toggle_bool`, ...).
- This package: one module per behavior/action (e.g. `toggle.py`,
  `scroll_to.py`), each exporting a small JS fragment (a function body
  as a string) plus its `BehaviorSpec`/`ActionSpec`. `JSBackend.render()`
  will assemble the runtime from only the fragments a given site's IR
  actually references, instead of one static, hand-maintained string.

This alone adds no new vocabulary and changes no behavior at runtime --
it is purely a place for that refactor to land. See
`docs/DESIGN-NOTES.md` for the full design and `PROGRESS.md` for
current status.
"""

from __future__ import annotations
