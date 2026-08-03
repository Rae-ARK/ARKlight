"""
Stage 2 of "Reactive-core vdom staging" (docs/DESIGN-NOTES.md):
reactive class binding via `Bind.when(...)` / `bind_class=`.
"""

import pytest

from arklight.api import Bind, Container, Page, State
from arklight.ast.nodes import ClassBindSpec
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


def test_bind_when_returns_class_bind_spec():
    spec = Bind.when("active", "is-active")
    assert spec == ClassBindSpec(state="active", class_name="is-active")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_bind_class_to_declared_state_passes_validation():
    tree = Page(
        State("active", False),
        Container("Panel", bind_class=Bind.when("active", "is-active")),
    )
    validate_ark_ast(normalize_ark_ast({"/": tree}))  # no raise


def test_bind_class_to_undeclared_state_raises():
    tree = Page(Container("Panel", bind_class=Bind.when("active", "is-active")))
    with pytest.raises(ValidationError, match="isn't declared on this page"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_bind_class_with_non_spec_value_raises():
    tree = Page(State("active", False), Container("Panel", bind_class="is-active"))
    with pytest.raises(ValidationError, match="Bind.when"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_bind_class_empty_class_name_raises():
    tree = Page(
        State("active", False),
        Container("Panel", bind_class=Bind.when("active", "")),
    )
    with pytest.raises(ValidationError, match="non-empty class_name"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


# ---------------------------------------------------------------------------
# HTML backend
# ---------------------------------------------------------------------------


def test_html_backend_omits_bound_class_when_initial_state_falsy():
    tree = Page(
        State("active", False),
        Container("Panel", class_name="card", bind_class=Bind.when("active", "is-active")),
    )
    ir = _ir({"/": tree})
    html = HTMLBackend().render(ir)["index.html"]
    assert 'class="card"' in html
    assert 'class="card is-active"' not in html
    assert 'data-ark-bind-class="is-active"' in html
    assert 'data-ark-bind-class-state="active"' in html


def test_html_backend_includes_bound_class_when_initial_state_truthy():
    tree = Page(
        State("active", True),
        Container("Panel", class_name="card", bind_class=Bind.when("active", "is-active")),
    )
    ir = _ir({"/": tree})
    html = HTMLBackend().render(ir)["index.html"]
    assert 'class="card is-active"' in html


def test_html_backend_bound_class_with_no_static_class_name():
    tree = Page(
        State("active", True),
        Container("Panel", bind_class=Bind.when("active", "is-active")),
    )
    ir = _ir({"/": tree})
    html = HTMLBackend().render(ir)["index.html"]
    assert 'class="is-active"' in html


# ---------------------------------------------------------------------------
# JS backend
# ---------------------------------------------------------------------------


def test_js_backend_ships_class_binding_pass_when_state_present():
    tree = Page(
        State("active", False),
        Container("Panel", bind_class=Bind.when("active", "is-active")),
    )
    ir = _ir({"/": tree})
    js = JSBackend().render(ir)["arklight.js"]
    assert "renderClassBindings" in js
    assert "classList.toggle" in js
    assert "snabbdom" in js  # Stage 1 core still ships alongside it


def test_js_backend_ships_nothing_extra_without_state():
    tree = Page(Container("Panel", class_name="card"))
    ir = _ir({"/": tree})
    js = JSBackend().render(ir)["arklight.js"]
    assert "renderClassBindings" not in js
    assert "snabbdom" not in js.split("\n", 10)[-1]  # no vdom core body shipped
