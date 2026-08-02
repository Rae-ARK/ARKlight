"""
v0.0035: stateful JS -- State/Bind/Action across validation, IR build,
and the HTML/JS backends.
"""

import pytest

from arklight.api import Action, Bind, Button, Container, Page, State, Text
from arklight.ast.nodes import ActionRef
from arklight.backend.html.render import HTMLBackend
from arklight.ir.build import build_website_ir
from arklight.ir.normalize import normalize_ark_ast
from arklight.ir.validate import ValidationError, validate_ark_ast


def _ir(pages):
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    return build_website_ir("site", normalized)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_bind_to_declared_state_passes_validation():
    tree = Page(State("count", 0), Text(Bind("count")))
    validate_ark_ast(normalize_ark_ast({"/": tree}))  # no raise


def test_bind_to_undeclared_state_raises():
    tree = Page(Text(Bind("count")))
    with pytest.raises(ValidationError, match="isn't declared on this page"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_state_nested_inside_container_raises():
    tree = Page(Container(State("count", 0)))
    with pytest.raises(ValidationError, match="direct child of Page"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_duplicate_state_name_raises():
    tree = Page(State("count", 0), State("count", 1))
    with pytest.raises(ValidationError, match="declared more than once"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_action_targeting_undeclared_state_raises():
    tree = Page(Button("+1", on_click=Action.increment("count")))
    with pytest.raises(ValidationError, match="isn't declared on this page"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_action_does_not_require_behavior_target():
    tree = Page(State("count", 0), Button("+1", on_click=Action.increment("count")))
    validate_ark_ast(normalize_ark_ast({"/": tree}))  # no raise -- actions target state, not the DOM


def test_state_is_scoped_per_page():
    pages = {
        "/": Page(State("count", 0), Text(Bind("count"))),
        "/about": Page(Button("+1", on_click=Action.increment("count"))),
    }
    with pytest.raises(ValidationError, match="isn't declared on this page"):
        validate_ark_ast(normalize_ark_ast(pages))


# ---------------------------------------------------------------------------
# IR build
# ---------------------------------------------------------------------------


def test_state_extracted_into_ir_page_state():
    pages = {"/": Page(State("count", 0), Text(Bind("count")))}
    ir = _ir(pages)
    assert ir.pages[0].state == {"count": 0}


def test_state_node_does_not_appear_as_a_renderable_child():
    pages = {"/": Page(State("count", 0), Text("hi"))}
    ir = _ir(pages)
    child_types = [c.type for c in ir.pages[0].root.children]
    assert child_types == ["Text"]


def test_page_without_state_has_empty_state_dict():
    pages = {"/": Page(Text("hi"))}
    ir = _ir(pages)
    assert ir.pages[0].state == {}


# ---------------------------------------------------------------------------
# HTML backend
# ---------------------------------------------------------------------------


def test_html_backend_renders_bind_with_initial_value():
    pages = {"/": Page(State("count", 0), Text(Bind("count")))}
    html = HTMLBackend().render(_ir(pages))["index.html"]
    assert '<span data-ark-bind="count">0</span>' in html


def test_html_backend_hydrates_body_state_as_json():
    pages = {"/": Page(State("count", 0), Text(Bind("count")))}
    html = HTMLBackend().render(_ir(pages))["index.html"]
    assert 'data-ark-state="{&quot;count&quot;: 0}"' in html


def test_html_backend_omits_body_state_when_no_state_declared():
    pages = {"/": Page(Text("hi"))}
    html = HTMLBackend().render(_ir(pages))["index.html"]
    assert "data-ark-state" not in html


def test_html_backend_renders_action_ref_attributes():
    pages = {"/": Page(State("count", 0), Button("+1", on_click=Action.increment("count")))}
    html = HTMLBackend().render(_ir(pages))["index.html"]
    assert 'data-ark-on-click="action:increment"' in html
    assert 'data-ark-action-state="count"' in html
    assert 'data-ark-action-args="{&quot;delta&quot;: 1}"' in html
