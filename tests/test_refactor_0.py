"""
`refactor-0` (see docs/Backends/REFACTOR-INDEX.md and
docs/Backends/JS-BACKEND-REFACTOR-PLAN.md): the module split of
`arklight/backend/js/render.py`'s old `_STATE_CORE_JS` / `_NOTIFY_JS`
/ `_NAV_HIGHLIGHT_JS` constants into
`arklight/backend/js/runtime/{state,bindings,modifiers,dispatch,nav,
notify}.py`.

This is documented as a pure refactor -- no generated-JS output
change -- so this stage's tests assert two things: the six new
sibling modules exist and expose the fragments they're supposed to
(mirroring the `test_js_backend.py` coverage the `actions/`/
`behaviors/` packages already get), and `JSBackend.render()`'s output
is unaffected by the split (every function name that used to come
from the monolithic string constants is still present exactly once,
for both a plain page and a stateful one).
"""

from arklight.api import Action, Button, Page, State, Text
from arklight.backend.js.render import JSBackend, SCRIPT_PATH
from arklight.backend.js.runtime import NAV_HIGHLIGHT_JS, NOTIFY_JS, STATE_CORE_JS
from arklight.backend.js.runtime.bindings import (
    RENDER_BINDINGS_JS,
    RENDER_CLASS_BINDINGS_JS,
)
from arklight.backend.js.runtime.dispatch import WIRE_ACTIONS_JS
from arklight.backend.js.runtime.modifiers import APPLY_MODIFIERS_JS
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


def test_modifiers_module_exports_apply_modifiers():
    assert "function arkApplyModifiers(el, run)" in APPLY_MODIFIERS_JS


def test_dispatch_module_exports_wire_actions():
    assert "function wireActions(store)" in WIRE_ACTIONS_JS


def test_nav_module_exports_highlight_active_nav_link():
    assert "function highlightActiveNavLink()" in NAV_MODULE_JS
    assert NAV_MODULE_JS == NAV_HIGHLIGHT_JS


def test_notify_module_exports_ark_notify():
    assert "function arkNotify(message)" in NOTIFY_MODULE_JS
    assert NOTIFY_MODULE_JS == NOTIFY_JS


def test_runtime_package_reassembles_state_core_in_original_order():
    # createState, renderBindings, renderClassBindings, initState,
    # arkApplyModifiers, wireActions -- same order the old
    # `_STATE_CORE_JS` triple-quoted string held them in.
    names = [
        "function createState(initial)",
        "function renderBindings(store)",
        "function renderClassBindings(store)",
        "function initState()",
        "function arkApplyModifiers(el, run)",
        "function wireActions(store)",
    ]
    positions = [STATE_CORE_JS.index(name) for name in names]
    assert positions == sorted(positions)


# --- `JSBackend.render()` output is unaffected: pure refactor.


def test_plain_page_runtime_unaffected_by_the_split():
    js = JSBackend().render(_plain_ir())[SCRIPT_PATH]
    assert "createState" not in js
    assert "wireActions" not in js
    assert "highlightActiveNavLink" in js
    assert js.count("function highlightActiveNavLink") == 1


def test_stateful_page_runtime_unaffected_by_the_split():
    js = JSBackend().render(_stateful_ir())[SCRIPT_PATH]
    for name in [
        "function createState",
        "function renderBindings",
        "function renderClassBindings",
        "function initState",
        "function arkApplyModifiers",
        "function wireActions",
        "function highlightActiveNavLink",
        "function arkNotify",
    ]:
        assert js.count(name) == 1, name
