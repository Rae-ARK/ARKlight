"""
Per-behavior JS runtime fragments (v0.0035).

Each sibling module exports `NAME` (matching a key in
`arklight.ir.schema.BEHAVIOR_REGISTRY`) and `JS_FRAGMENT` (that
behavior's `name: function (el) { ... }` entry, as JS source text).
`JSBackend.render()` (`arklight/backend/js/render.py`) concatenates
only the fragments a given site's IR actually references into the
`behaviors` dispatch object, instead of one hand-maintained runtime
string always shipping every behavior.

Adding a new named behavior later is: one new module here (`NAME` +
`JS_FRAGMENT`), one new `arklight.ir.schema.BEHAVIOR_REGISTRY` entry,
and a line in `BEHAVIOR_MODULES` below -- never a change to
`JSBackend`'s generation logic itself.
"""

from __future__ import annotations

from arklight.backend.js.behaviors import copy, dismiss, scroll_to, toggle

BEHAVIOR_MODULES = {
    toggle.NAME: toggle,
    scroll_to.NAME: scroll_to,
    copy.NAME: copy,
    dismiss.NAME: dismiss,
}

# name -> that behavior's JS dispatch-object entry (source text).
BEHAVIOR_FRAGMENTS: dict[str, str] = {
    name: module.JS_FRAGMENT for name, module in BEHAVIOR_MODULES.items()
}
