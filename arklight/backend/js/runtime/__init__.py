"""
Reactive-state runtime fragments (`refactor-0`, see
`docs/Backends/REFACTOR-INDEX.md` and
`docs/Backends/JS-BACKEND-REFACTOR-PLAN.md`).

Splits `arklight/backend/js/render.py`'s old `_STATE_CORE_JS` /
`_NOTIFY_JS` / `_NAV_HIGHLIGHT_JS` constants (145+ lines, one
triple-quoted string apiece) into one sibling module per function --
`state.py`, `bindings.py`, `dispatch.py`, `nav.py`, `notify.py` --
mirroring the `arklight.backend.js.actions` /
`arklight.backend.js.behaviors` per-file pattern already established
for the per-name registries. Unlike those two packages, nothing here
is keyed by a registry name: these five pieces are the fixed reactive
core every stateful page ships as a unit, not a per-usage selection,
so this module just reassembles them in the same order the old
monolithic string held them.

At `refactor-0`, `STATE_CORE_JS` below was byte-for-byte the old
`_STATE_CORE_JS` value, and a sixth sibling -- `modifiers.py` -- sat
between `state.py` and `dispatch.py`, holding `arkApplyModifiers`.
`htmx-2` (see `docs/Backends/HTMX-INTEGRATION.md` "Stage 2 --
Modifiers" / `docs/Backends/REFACTOR-INDEX.md` row 5) deleted that
module and its export entirely: modifier tokens now compile to an
`hx-trigger` attribute at build time (`arklight/backend/html/attrs.py`)
instead of being parsed by a shipped runtime function, so there is
nothing left for a `modifiers.py` sibling to hold. `STATE_CORE_JS` is
reassembled the same way, minus that one piece.

`htmx-3` (see `docs/Backends/HTMX-INTEGRATION.md` "Stage 3 -- Replace
`wireActions()` wiring loop" / `docs/Backends/REFACTOR-INDEX.md` row 6)
renamed `dispatch.py`'s export from `WIRE_ACTIONS_JS` to
`ACTION_INTERCEPTOR_JS` -- the per-element `querySelectorAll`/
`forEach` wiring loop it used to hold is gone, replaced by a single
delegated `click` listener (`wireActionInterceptor`). See that
module's docstring for why this isn't literally the `htmx:beforeRequest`
interceptor `HTMX-INTEGRATION.md` describes.

`htmx-5` (see `docs/Backends/HTMX-INTEGRATION.md` "Stage 4 -- Audit
and remove remaining hand-rolled plumbing" / `docs/Backends/
REFACTOR-INDEX.md` row 10) renamed that export again, to
`CLICK_INTERCEPTOR_JS` (function `wireClickInterceptor`), and pulled
it out of `STATE_CORE_JS` entirely -- it's no longer a piece of the
reactive-state bundle. This module's docstring above described
`STATE_CORE_JS` as "the fixed reactive core every stateful page ships
as a unit"; that framing stopped being accurate for the interceptor
once `htmx-5` made it also dispatch named-behavior clicks, which have
nothing to do with reactive state and can appear on a page with no
`State(...)` at all (see `dispatch.py`'s module docstring for why that
stage happened -- folding behavior dispatch out of vendored HTMX's
`hx-on:click`, which used a `Function`-from-string call ARKlight's own
"no eval" invariant doesn't permit). `arklight/backend/js/render.py`'s
`_build_runtime_js` now includes `CLICK_INTERCEPTOR_JS` whenever a
page uses a named behavior *or* an action, independent of `has_state`,
alongside `STATE_CORE_JS` (createState/bindings/initState) whenever
`has_state` alone -- the two are shipped independently now, not always
together.
"""

from __future__ import annotations

from arklight.backend.js.runtime.bindings import (
    RENDER_BINDINGS_JS,
    RENDER_CLASS_BINDINGS_JS,
)
from arklight.backend.js.runtime.dispatch import CLICK_INTERCEPTOR_JS
from arklight.backend.js.runtime.nav import NAV_HIGHLIGHT_JS
from arklight.backend.js.runtime.notify import NOTIFY_JS
from arklight.backend.js.runtime.state import CREATE_STATE_JS, INIT_STATE_JS

# Reactive-state pieces only -- the click interceptor is no longer
# part of this bundle as of htmx-5 (see module docstring above).
STATE_CORE_JS = (
    CREATE_STATE_JS
    + RENDER_BINDINGS_JS
    + RENDER_CLASS_BINDINGS_JS
    + INIT_STATE_JS
)

__all__ = [
    "STATE_CORE_JS",
    "CLICK_INTERCEPTOR_JS",
    "NOTIFY_JS",
    "NAV_HIGHLIGHT_JS",
]
