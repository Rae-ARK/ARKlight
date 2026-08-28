from arklight.api import Action, Bind, Button, Page, State, Text
from arklight.ast.nodes import ActionRef
from arklight.backend.js.render import JSBackend, SCRIPT_PATH
from arklight.ir.build import build_website_ir
from arklight.ir.normalize import normalize_ark_ast
from arklight.ir.validate import validate_ark_ast


def _ir(pages):
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    return build_website_ir("site", normalized)


def _plain_ir():
    return _ir({"/": Page(Text("hi"))})


def test_js_backend_returns_script_path():
    output = JSBackend().render(_plain_ir())
    assert set(output.keys()) == {SCRIPT_PATH}


def test_js_runtime_ships_no_behaviors_when_none_are_used():
    # v0.0035: JSBackend only concatenates the behavior fragments a
    # site's IR actually references -- a page with no on_click at all
    # gets none of them.
    js = JSBackend().render(_plain_ir())[SCRIPT_PATH]
    assert "toggle:" not in js
    assert '"scroll-to":' not in js
    assert "copy:" not in js
    assert "dismiss:" not in js
    assert "wireBehaviors" not in js


def test_js_runtime_includes_only_the_behavior_actually_used():
    pages = {"/": Page(Button("Show", on_click="toggle", behavior_target="#panel"))}
    js = JSBackend().render(_ir(pages))[SCRIPT_PATH]
    assert "toggle:" in js
    # htmx-1: no more data-ark-on-click wiring loop -- the runtime now
    # exposes arkBehaviors/arkRunBehavior for HTMX's hx-on:click to
    # call directly (see arklight/backend/js/render.py).
    assert "arkBehaviors" in js
    assert "arkRunBehavior" in js
    assert "data-ark-on-click" not in js
    assert "data-ark-target" in js
    assert "data-ark-toggle-class" in js
    # Behaviors that aren't referenced on this site don't ship.
    assert '"scroll-to":' not in js
    assert "copy:" not in js
    assert "dismiss:" not in js


def test_js_runtime_highlights_active_nav_link_unconditionally():
    js = JSBackend().render(_plain_ir())[SCRIPT_PATH]
    assert "highlightActiveNavLink" in js
    assert "is-active" in js


def test_js_runtime_has_no_eval_or_new_function():
    # Sanity check that the shipped runtime doesn't execute arbitrary
    # strings -- it only dispatches to the fixed `behaviors`/`actions`
    # objects.
    js = JSBackend().render(_plain_ir())[SCRIPT_PATH]
    assert "eval(" not in js
    assert "new Function(" not in js


def test_js_runtime_implements_copy_and_dismiss_when_used():
    pages = {
        "/": Page(
            Button("Copy", on_click="copy", behavior_target="#snippet"),
            Button("Close", on_click="dismiss", behavior_target="#banner"),
        )
    }
    js = JSBackend().render(_ir(pages))[SCRIPT_PATH]
    assert "copy:" in js
    assert "dismiss:" in js
    assert "navigator.clipboard" in js
    assert "toggle:" not in js


def test_js_runtime_omits_state_core_when_no_page_declares_state():
    js = JSBackend().render(_plain_ir())[SCRIPT_PATH]
    assert "createState" not in js
    assert "data-ark-state" not in js
    assert "wireActionInterceptor" not in js


def test_js_runtime_includes_state_core_and_used_actions_only():
    pages = {
        "/": Page(
            State("count", 0),
            Text(Bind("count")),
            Button("+1", on_click=Action.increment("count")),
        )
    }
    js = JSBackend().render(_ir(pages))[SCRIPT_PATH]
    assert "createState" in js
    assert "increment:" in js
    # `set` / `toggle_bool` weren't referenced on this site.
    assert "toggle_bool:" not in js
    assert "\n    set: function (store, key, args) {" not in js
    # htmx-1: this page ships vendored HTMX (state is present), which
    # -- like any general-purpose library -- has its own internal
    # eval/new Function uses unrelated to ARKlight's own "no eval, no
    # new Function" guarantee about its own authored code. Scope the
    # check to what ARKlight itself generated.
    from arklight.backend.js.htmx import HTMX_JS

    ark_authored_js = js.replace(HTMX_JS, "")
    assert "eval(" not in ark_authored_js
    assert "new Function(" not in ark_authored_js


def test_action_ref_targets_survive_into_ir():
    pages = {
        "/": Page(
            State("count", 0),
            Button("Reset", on_click=Action.set("count", 0)),
        )
    }
    ir = _ir(pages)
    button = ir.pages[0].root.children[0]
    on_click = button.props["on_click"]
    assert isinstance(on_click, ActionRef)
    assert on_click.action == "set"
    assert on_click.state == "count"
    assert on_click.args == {"value": 0}
