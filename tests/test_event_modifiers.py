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


def test_wire_click_interceptor_action_branch_has_exactly_one_try_block():
    # htmx-3 (see docs/Backends/HTMX-INTEGRATION.md "Stage 3") replaced
    # wireActions()'s two-try-block shape (a per-element wiring guard
    # plus an inner per-click dispatch guard) with a single delegated
    # click listener -- there's no separate wiring phase per element
    # any more, so one try/catch around the attribute-read + dispatch
    # is the whole guard for a given dispatch kind. htmx-5 (docs/
    # Backends/REFACTOR-INDEX.md row 10) renamed that listener
    # wireActionInterceptor -> wireClickInterceptor and gave it a
    # second branch (behaviors), each with its own try/catch -- so
    # this test now scopes to the action branch specifically. See
    # tests/test_htmx_3.py and tests/test_htmx_5.py for dedicated
    # coverage, and tests/test_js_error_handling.py's identical
    # assertion.
    tree = Page(State("count", 0), Button("+1", on_click=Action.increment("count")))
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    wire_body = js.split("function wireClickInterceptor(getStore) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    action_branch = wire_body.split('raw.indexOf("action:") === 0) {')[1].split("} else if")[0]
    assert action_branch.count("try {") == 1
    assert action_branch.count("catch (err)") == 1


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


# ---------------------------------------------------------------------------
# Bug fix (docs/bug_fixes.md finding 1): compiled `hx-trigger` modifiers
# are now actually enforced by wireClickInterceptor at dispatch time,
# not just compiled into inert markup. These assertions are static --
# same as every other test in this module -- since nothing in this test
# suite executes the emitted JS; they check that the enforcement logic
# is present in the right branch, with the right per-element bookkeeping
# shape, rather than simulating click timing.
# ---------------------------------------------------------------------------


def test_click_interceptor_reads_hx_trigger_for_modifier_enforcement():
    tree = Page(
        State("count", 0),
        Button("+1", on_click=Action.increment("count").debounce(300)),
    )
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    wire_body = js.split("function wireClickInterceptor(getStore) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    assert 'el.getAttribute("hx-trigger")' in wire_body
    assert "parseTriggerModifiers" in wire_body


def test_click_interceptor_enforces_once_per_element():
    tree = Page(
        State("count", 0),
        Button("+1", on_click=Action.increment("count").with_modifiers("once")),
    )
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    wire_body = js.split("function wireClickInterceptor(getStore) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    assert "onceFired" in wire_body
    assert "new WeakSet()" in wire_body


def test_click_interceptor_enforces_throttle_per_element():
    tree = Page(
        State("count", 0),
        Button("+1", on_click=Action.increment("count").throttle(250)),
    )
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    wire_body = js.split("function wireClickInterceptor(getStore) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    assert "throttleLast" in wire_body
    assert "Date.now()" in wire_body


def test_click_interceptor_enforces_debounce_per_element():
    tree = Page(
        State("count", 0),
        Button("+1", on_click=Action.increment("count").debounce(300)),
    )
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    wire_body = js.split("function wireClickInterceptor(getStore) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    assert "debounceTimers" in wire_body
    assert "setTimeout(" in wire_body
    assert "clearTimeout(existingTimer)" in wire_body


def test_click_interceptor_stop_calls_stop_propagation():
    tree = Page(
        State("count", 0),
        Button("+1", on_click=Action.increment("count").with_modifiers("stop")),
    )
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    wire_body = js.split("function wireClickInterceptor(getStore) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    assert "event.stopPropagation()" in wire_body


def test_click_interceptor_without_modifiers_still_dispatches_synchronously():
    # An unmodified Action.*(...) button has no hx-trigger attribute at
    # all (attrs.py omits it entirely -- see
    # test_html_backend_omits_hx_trigger_when_none_attached above), so
    # parseTriggerModifiers must return its all-false/all-null default
    # rather than erroring on a missing attribute, and the action must
    # still fire on the same click (no debounce delay introduced for
    # the common, unmodified case).
    tree = Page(State("count", 0), Button("+1", on_click=Action.increment("count")))
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert "hx-trigger" not in html
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    wire_body = js.split("function wireClickInterceptor(getStore) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    assert "if (!raw) return mods;" in wire_body
