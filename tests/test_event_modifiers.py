"""
Stage 3 of "Reactive-core vdom staging" (docs/DESIGN-NOTES.md): event
modifiers via `.with_modifiers(...)` / `.debounce(...)` / `.throttle(...)`
on an `ActionRef`.
"""

import pytest

from arklight.api import Action, Button, Page, State
from arklight.ast.nodes import ActionRef
from arklight.backend.html.render import HTMLBackend
from arklight.backend.js.render import JSBackend
from arklight.ir.build import build_website_ir
from arklight.ir.normalize import normalize_ark_ast
from arklight.ir.validate import ValidationError, validate_ark_ast


def _ir(pages):
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    return build_website_ir("site", normalized)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_with_modifiers_returns_new_action_ref_with_tokens():
    base = Action.set("saved", True)
    ref = base.with_modifiers("prevent", "once")
    assert ref == ActionRef(action="set", state="saved", args={"value": True}, modifiers=("prevent", "once"))
    assert base.modifiers == ()  # original untouched -- immutable builder


def test_debounce_appends_debounce_token():
    ref = Action.set("saved", True).debounce(300)
    assert ref.modifiers == ("debounce:300",)


def test_throttle_appends_throttle_token():
    ref = Action.increment("count").throttle(250)
    assert ref.modifiers == ("throttle:250",)


def test_modifiers_can_be_chained():
    ref = Action.remove("items", 0).with_modifiers("prevent", "stop").debounce(300)
    assert ref.modifiers == ("prevent", "stop", "debounce:300")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_known_boolean_modifier_passes_validation():
    tree = Page(
        State("saved", False),
        Button("Save", on_click=Action.set("saved", True).with_modifiers("prevent", "stop", "once")),
    )
    validate_ark_ast(normalize_ark_ast({"/": tree}))  # no raise


def test_debounce_with_positive_ms_passes_validation():
    tree = Page(
        State("saved", False),
        Button("Save", on_click=Action.set("saved", True).debounce(300)),
    )
    validate_ark_ast(normalize_ark_ast({"/": tree}))  # no raise


def test_unknown_modifier_raises():
    tree = Page(
        State("saved", False),
        Button("Save", on_click=Action.set("saved", True).with_modifiers("wobble")),
    )
    with pytest.raises(ValidationError, match="unknown modifier 'wobble'"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_debounce_zero_ms_raises():
    tree = Page(
        State("saved", False),
        Button("Save", on_click=Action.set("saved", True).debounce(0)),
    )
    with pytest.raises(ValidationError, match="positive integer"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_debounce_negative_ms_raises():
    tree = Page(
        State("saved", False),
        Button("Save", on_click=Action.set("saved", True).debounce(-50)),
    )
    with pytest.raises(ValidationError, match="positive integer"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_boolean_modifier_with_value_raises():
    tree = Page(
        State("saved", False),
        Button("Save", on_click=Action.set("saved", True).with_modifiers("prevent:300")),
    )
    with pytest.raises(ValidationError, match="doesn't take a value"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_param_modifier_without_value_raises():
    tree = Page(
        State("saved", False),
        Button("Save", on_click=Action.set("saved", True).with_modifiers("debounce")),
    )
    with pytest.raises(ValidationError, match="without a millisecond value"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


# ---------------------------------------------------------------------------
# HTML backend
# ---------------------------------------------------------------------------


def test_html_backend_emits_modifiers_attribute():
    tree = Page(
        State("saved", False),
        Button("Save", on_click=Action.set("saved", True).with_modifiers("prevent", "stop").debounce(300)),
    )
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert 'data-ark-modifiers="prevent,stop,debounce:300"' in html


def test_html_backend_omits_modifiers_attribute_when_none_attached():
    tree = Page(State("count", 0), Button("+1", on_click=Action.increment("count")))
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert "data-ark-modifiers" not in html


# ---------------------------------------------------------------------------
# JS backend
# ---------------------------------------------------------------------------


def test_js_backend_ships_apply_modifiers_when_state_present():
    tree = Page(State("count", 0), Button("+1", on_click=Action.increment("count")))
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    assert "function arkApplyModifiers(el, run)" in js
    assert "data-ark-modifiers" in js


def test_js_backend_ships_nothing_extra_without_state():
    tree = Page(Button("Hi", on_click="toggle", behavior_target="#panel"))
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    assert "arkApplyModifiers" not in js


def test_wire_actions_still_has_exactly_two_try_blocks():
    # Regression guard: Stage 3 must not add a new try/catch inside
    # wireActions itself (arkApplyModifiers is a separate function) --
    # see tests/test_js_error_handling.py's identical assertion.
    tree = Page(State("count", 0), Button("+1", on_click=Action.increment("count")))
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    wire_actions_body = js.split("function wireActions(store) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    assert wire_actions_body.count("try {") == 2
    assert wire_actions_body.count("catch (err)") == 2


def test_runtime_still_has_no_eval_or_new_function():
    tree = Page(
        State("count", 0),
        Button("+1", on_click=Action.increment("count").debounce(300).with_modifiers("stop", "once")),
    )
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    assert "eval(" not in js
    assert "new Function(" not in js
