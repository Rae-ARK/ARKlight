"""
Tests for the v0.0035 stateful-JS vocabulary addendum II: `Action.append`
and `Action.remove`, the first actions that assume a list-valued
`State(...)`.

Mirrors tests/test_stateful_js_vocabulary_addendum.py -- same "new
registry entry + new JS fragment, nothing else in the pipeline changes"
shape as decrement/reset before it.
"""

import pytest

from arklight.api import Action, Button, Page, State, Text, Bind
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
# Validation
# ---------------------------------------------------------------------------


def test_append_targeting_declared_state_passes_validation():
    tree = Page(State("items", []), Button("Add", on_click=Action.append("items", "new")))
    validate_ark_ast(normalize_ark_ast({"/": tree}))  # no raise


def test_remove_targeting_declared_state_passes_validation():
    tree = Page(State("items", ["a"]), Button("Remove", on_click=Action.remove("items", 0)))
    validate_ark_ast(normalize_ark_ast({"/": tree}))  # no raise


def test_append_targeting_undeclared_state_raises():
    tree = Page(Button("Add", on_click=Action.append("items", "new")))
    with pytest.raises(ValidationError, match="isn't declared on this page"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_remove_targeting_undeclared_state_raises():
    tree = Page(Button("Remove", on_click=Action.remove("items", 0)))
    with pytest.raises(ValidationError, match="isn't declared on this page"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


# ---------------------------------------------------------------------------
# IR build -- list-valued initial state flows through untouched.
# ---------------------------------------------------------------------------


def test_list_valued_state_extracted_into_ir_page_state():
    pages = {"/": Page(State("items", ["a", "b"]), Text(Bind("items")))}
    ir = _ir(pages)
    assert ir.pages[0].state == {"items": ["a", "b"]}


# ---------------------------------------------------------------------------
# HTML backend
# ---------------------------------------------------------------------------


def test_html_backend_renders_append_action_attributes():
    pages = {"/": Page(State("items", []), Button("Add", on_click=Action.append("items", "new")))}
    html = HTMLBackend().render(_ir(pages))["index.html"]
    assert 'data-ark-on-click="action:append"' in html
    assert 'data-ark-action-state="items"' in html
    assert 'data-ark-action-args="{&quot;value&quot;: &quot;new&quot;}"' in html


def test_html_backend_renders_remove_action_attributes():
    pages = {"/": Page(State("items", ["a"]), Button("Remove", on_click=Action.remove("items", 0)))}
    html = HTMLBackend().render(_ir(pages))["index.html"]
    assert 'data-ark-on-click="action:remove"' in html
    assert 'data-ark-action-state="items"' in html
    assert 'data-ark-action-args="{&quot;index&quot;: 0}"' in html


def test_html_backend_hydrates_list_valued_state_as_json():
    pages = {"/": Page(State("items", ["a", "b"]), Text(Bind("items")))}
    html = HTMLBackend().render(_ir(pages))["index.html"]
    assert 'data-ark-state="{&quot;items&quot;: [&quot;a&quot;, &quot;b&quot;]}"' in html


# ---------------------------------------------------------------------------
# JS backend
# ---------------------------------------------------------------------------


def test_js_backend_only_ships_append_fragment_when_used():
    pages = {"/": Page(State("items", []), Button("Add", on_click=Action.append("items", "x")))}
    js = JSBackend().render(_ir(pages))["arklight.js"]
    assert "append: function (store, key, args)" in js
    assert "remove: function (store, key, args)" not in js


def test_js_backend_only_ships_remove_fragment_when_used():
    pages = {"/": Page(State("items", ["a"]), Button("Remove", on_click=Action.remove("items", 0)))}
    js = JSBackend().render(_ir(pages))["arklight.js"]
    assert "remove: function (store, key, args)" in js
    assert "append: function (store, key, args)" not in js


def test_js_backend_append_concatenates_onto_existing_list():
    pages = {"/": Page(State("items", []), Button("Add", on_click=Action.append("items", "x")))}
    js = JSBackend().render(_ir(pages))["arklight.js"]
    assert "store.set(key, list.concat([args.value]));" in js


def test_js_backend_remove_filters_by_index():
    pages = {"/": Page(State("items", ["a"]), Button("Remove", on_click=Action.remove("items", 0)))}
    js = JSBackend().render(_ir(pages))["arklight.js"]
    assert "store.set(key, list.filter(function (_, i) { return i !== args.index; }));" in js
