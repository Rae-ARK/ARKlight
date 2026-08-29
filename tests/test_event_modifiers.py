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


def test_html_backend_emits_hx_trigger_for_modifiers():
    # htmx-2: replaces the old comma-joined data-ark-modifiers
    # attribute with HTMX's own hx-trigger modifier syntax --
    # "prevent" contributes nothing (honored by construction).
    tree = Page(
        State("saved", False),
        Button("Save", on_click=Action.set("saved", True).with_modifiers("prevent", "stop").debounce(300)),
    )
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert 'hx-trigger="click consume debounce:300ms"' in html
    assert "data-ark-modifiers" not in html


def test_html_backend_omits_hx_trigger_when_none_attached():
    tree = Page(State("count", 0), Button("+1", on_click=Action.increment("count")))
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert "hx-trigger" not in html
    assert "data-ark-modifiers" not in html


# ---------------------------------------------------------------------------
# JS backend
# ---------------------------------------------------------------------------


def test_js_backend_no_longer_ships_apply_modifiers():
    # htmx-2: arkApplyModifiers and the data-ark-modifiers attribute it
    # used to parse are both gone -- modifiers compile to hx-trigger at
    # build time instead (see the HTML backend tests above).
    tree = Page(
        State("count", 0),
        Button("+1", on_click=Action.increment("count").debounce(300).with_modifiers("stop", "once")),
    )
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    assert "arkApplyModifiers" not in js
    assert "data-ark-modifiers" not in js


def test_js_backend_ships_nothing_extra_without_state():
    tree = Page(Button("Hi", on_click="toggle", behavior_target="#panel"))
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    assert "arkApplyModifiers" not in js


def test_wire_action_interceptor_has_exactly_one_try_block():
    # htmx-3 (see docs/Backends/HTMX-INTEGRATION.md "Stage 3") replaced
    # wireActions()'s two-try-block shape (a per-element wiring guard
    # plus an inner per-click dispatch guard) with a single delegated
    # click listener, `wireActionInterceptor` -- there's no separate
    # wiring phase per element any more, so one try/catch around the
    # attribute-read + dispatch is the whole guard. See
    # tests/test_htmx_3.py for this stage's dedicated coverage and
    # tests/test_js_error_handling.py's identical assertion.
    tree = Page(State("count", 0), Button("+1", on_click=Action.increment("count")))
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    wire_body = js.split("function wireActionInterceptor(getStore) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    assert wire_body.count("try {") == 1
    assert wire_body.count("catch (err)") == 1


def test_runtime_still_has_no_eval_or_new_function():
    # htmx-1: this page now also ships vendored HTMX (state is
    # present), which -- like any general-purpose library -- contains
    # its own internal `eval`/`new Function` uses the "no eval, no new
    # Function" guarantee was never about. That guarantee is about
    # ARKlight's *own* authored runtime code never treating a string
    # as executable code; it doesn't extend to a vendored third-party
    # dependency's internals. See test_js_error_handling.py's
    # identical adjustment for the same reasoning.
    from arklight.backend.js.htmx import HTMX_JS

    tree = Page(
        State("count", 0),
        Button("+1", on_click=Action.increment("count").debounce(300).with_modifiers("stop", "once")),
    )
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    ark_authored_js = js.replace(HTMX_JS, "")
    assert "eval(" not in ark_authored_js
    assert "new Function(" not in ark_authored_js
