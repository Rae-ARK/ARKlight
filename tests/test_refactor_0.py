"""
`refactor-0` (see docs/Backends/REFACTOR-INDEX.md and
docs/Backends/JS-BACKEND-REFACTOR-PLAN.md): the module split of
`arklight/backend/js/render.py`'s old `_STATE_CORE_JS` / `_NOTIFY_JS`
/ `_NAV_HIGHLIGHT_JS` constants into
`arklight/backend/js/runtime/{state,bindings,dispatch,nav,notify}.py`.

At `refactor-0` a sixth sibling, `modifiers.py`, also existed here
(holding `arkApplyModifiers`); `htmx-2` (see
docs/Backends/HTMX-INTEGRATION.md "Stage 2 -- Modifiers") deleted it
along with the `data-ark-modifiers` attribute it used to parse, so
this file's coverage of it is deleted too -- see
`tests/test_event_modifiers.py` for `htmx-2`'s own coverage.

`htmx-3` (see docs/Backends/HTMX-INTEGRATION.md "Stage 3") renamed
`dispatch.py`'s export from `WIRE_ACTIONS_JS` to
`ACTION_INTERCEPTOR_JS` and replaced the `wireActions(store)` function
it held with `wireActionInterceptor(store)` -- a single delegated
`click` listener instead of a `querySelectorAll`/`forEach` wiring
loop. This file's assertions below are updated for that rename; see
`tests/test_htmx_3.py` for this stage's own dedicated coverage.

This is documented as a pure refactor -- no generated-JS output
change -- so this stage's tests assert two things: the sibling
modules exist and expose the fragments they're supposed to (mirroring
the `test_js_backend.py` coverage the `actions/`/`behaviors/`
packages already get), and `JSBackend.render()`'s output is
unaffected by the split (every function name that used to come from
the monolithic string constants is still present exactly once, for
both a plain page and a stateful one).
"""

from arklight.api import Action, Button, Page, State, Text
from arklight.backend.js.render import JSBackend, SCRIPT_PATH
from arklight.backend.js.runtime import NAV_HIGHLIGHT_JS, NOTIFY_JS, STATE_CORE_JS
from arklight.backend.js.runtime.bindings import (
    RENDER_BINDINGS_JS,
    RENDER_CLASS_BINDINGS_JS,
)
from arklight.backend.js.runtime.dispatch import ACTION_INTERCEPTOR_JS
from arklight.backend.js.runtime.nav import NAV_HIGHLIGHT_JS as NAV_MODULE_JS
from arklight.backend.js.runtime.notify import NOTIFY_JS as NOTIFY_MODULE_JS
from arklight.backend.js.runtime.state import CREATE_STATE_JS, INIT_STATE_JS
from arklight.ir.build import build_website_ir
from arklight.ir.normalize import normalize_ark_ast
from arklight.ir.validate import validate_ark_ast


def _ir(pages):
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    return build_website_ir("site", normalized)


def _plain_ir():
    return _ir({"/": Page(Text("hi"))})


def _stateful_ir():
    pages = {
        "/": Page(
            State("count", 0),
            Text("hi"),
            Button("Add", on_click=Action.increment("count")),
        )
    }
    return _ir(pages)


# --- New modules expose the fragments the merged staging table says
# --- they should (docs/Backends/REFACTOR-INDEX.md row `refactor-0`).


def test_state_module_exports_create_and_init_state():
    assert "function createState(initial)" in CREATE_STATE_JS
    assert "function initState()" in INIT_STATE_JS


def test_bindings_module_exports_both_render_passes():
    assert "function renderBindings(store)" in RENDER_BINDINGS_JS
    assert "function renderClassBindings(store)" in RENDER_CLASS_BINDINGS_JS


def test_dispatch_module_exports_wire_action_interceptor():
    assert "function wireActionInterceptor(store)" in ACTION_INTERCEPTOR_JS


def test_nav_module_exports_highlight_active_nav_link():
    assert "function highlightActiveNavLink()" in NAV_MODULE_JS
    assert NAV_MODULE_JS == NAV_HIGHLIGHT_JS


def test_notify_module_exports_ark_notify():
    assert "function arkNotify(message)" in NOTIFY_MODULE_JS
    assert NOTIFY_MODULE_JS == NOTIFY_JS


def test_runtime_package_reassembles_state_core_in_original_order():
    # createState, renderBindings, renderClassBindings, initState,
    # wireActionInterceptor -- same slot the old `_STATE_CORE_JS`
    # triple-quoted string held wireActions() in, minus arkApplyModifiers
    # (deleted by htmx-2 -- see tests/test_event_modifiers.py) and with
    # wireActions() itself renamed/replaced by htmx-3 (see
    # tests/test_htmx_3.py).
    names = [
        "function createState(initial)",
        "function renderBindings(store)",
        "function renderClassBindings(store)",
        "function initState()",
        "function wireActionInterceptor(store)",
    ]
    positions = [STATE_CORE_JS.index(name) for name in names]
    assert positions == sorted(positions)


# --- `JSBackend.render()` output is unaffected: pure refactor.


def test_plain_page_runtime_unaffected_by_the_split():
    js = JSBackend().render(_plain_ir())[SCRIPT_PATH]
    assert "createState" not in js
    assert "wireActionInterceptor" not in js
    assert "highlightActiveNavLink" in js
    assert js.count("function highlightActiveNavLink") == 1


def test_stateful_page_runtime_unaffected_by_the_split():
    js = JSBackend().render(_stateful_ir())[SCRIPT_PATH]
    for name in [
        "function createState",
        "function renderBindings",
        "function renderClassBindings",
        "function initState",
        "function wireActionInterceptor",
        "function highlightActiveNavLink",
        "function arkNotify",
    ]:
        assert js.count(name) == 1, name
