"""
Tests for the v0.0035 stateful-JS vocabulary addendum: `Action.decrement`
and `Action.reset`.

Mirrors the style of tests/test_stateful_js.py -- these are the two most
commonly needed additions to the closed action vocabulary (a counter's
`-1` counterpart to `increment`, and "put this state back the way it
started"), added the same way `increment`/`toggle_bool` were: a new
ACTION_REGISTRY entry, a new JS fragment module, nothing else in the
compiler pipeline changes. Everything else identified as a candidate
(list append/remove, derived/computed state, debounced actions,
input-bound `set`) is deliberately left for a future version -- see
docs/DESIGN-NOTES.md.
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


def test_decrement_targeting_declared_state_passes_validation():
    tree = Page(State("count", 0), Button("-1", on_click=Action.decrement("count")))
    validate_ark_ast(normalize_ark_ast({"/": tree}))  # no raise


def test_reset_targeting_declared_state_passes_validation():
    tree = Page(State("count", 0), Button("Reset", on_click=Action.reset("count")))
    validate_ark_ast(normalize_ark_ast({"/": tree}))  # no raise


def test_decrement_targeting_undeclared_state_raises():
    tree = Page(Button("-1", on_click=Action.decrement("count")))
    with pytest.raises(ValidationError, match="isn't declared on this page"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_reset_targeting_undeclared_state_raises():
    tree = Page(Button("Reset", on_click=Action.reset("count")))
    with pytest.raises(ValidationError, match="isn't declared on this page"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


# ---------------------------------------------------------------------------
# HTML backend
# ---------------------------------------------------------------------------


def test_html_backend_renders_decrement_action_attributes():
    pages = {"/": Page(State("count", 5), Button("-1", on_click=Action.decrement("count")))}
    html = HTMLBackend().render(_ir(pages))["index.html"]
    assert 'data-ark-on-click="action:decrement"' in html
    assert 'data-ark-action-state="count"' in html
    assert 'data-ark-action-args="{&quot;delta&quot;: 1}"' in html


def test_html_backend_renders_reset_action_attributes():
    pages = {"/": Page(State("count", 5), Button("Reset", on_click=Action.reset("count")))}
    html = HTMLBackend().render(_ir(pages))["index.html"]
    assert 'data-ark-on-click="action:reset"' in html
    assert 'data-ark-action-state="count"' in html
    # reset takes no arguments -- an empty `args` dict is falsy, so the
    # HTML backend omits `data-ark-action-args` entirely, same as the
    # existing `toggle_bool` (also zero-argument) behavior.
    assert "data-ark-action-args" not in html


# ---------------------------------------------------------------------------
# JS backend
# ---------------------------------------------------------------------------


def test_js_backend_only_ships_decrement_fragment_when_used():
    # Action fragments take `(store, key, ...)`; the always-present store
    # methods on createState (`set`, `reset`) take different arities, so
    # matching the full signature avoids confusing the two namespaces.
    pages = {"/": Page(State("count", 0), Button("-1", on_click=Action.decrement("count")))}
    js = JSBackend().render(_ir(pages))["arklight.js"]
    assert "decrement: function (store, key, args)" in js
    assert "increment: function (store, key, args)" not in js
    assert "reset: function (store, key)" not in js


def test_js_backend_only_ships_reset_fragment_when_used():
    pages = {"/": Page(State("count", 0), Button("Reset", on_click=Action.reset("count")))}
    js = JSBackend().render(_ir(pages))["arklight.js"]
    assert "reset: function (store, key)" in js
    assert "increment: function (store, key, args)" not in js


def test_js_backend_reset_reads_from_stores_own_initial_snapshot():
    pages = {"/": Page(State("count", 0), Button("Reset", on_click=Action.reset("count")))}
    js = JSBackend().render(_ir(pages))["arklight.js"]
    # The reactive core's `reset` method (not the action fragment) is
    # what actually reads the captured `initial` snapshot.
    assert "reset: function (key) {" in js
    assert "state[key] = initial[key];" in js


def test_js_backend_ships_no_action_fragments_for_pure_display_state():
    pages = {"/": Page(State("count", 0), Text(Bind("count")))}
    js = JSBackend().render(_ir(pages))["arklight.js"]
    # `actions` should be the empty object -- none of the action
    # fragments (identified by their `(store, key, ...)` signature)
    # should be present, even though the store's own `set`/`reset`
    # methods (different arity) are always shipped once state exists.
    assert "  var actions = {};" in js
    for name in ("set", "increment", "decrement", "toggle_bool", "reset"):
        assert f"{name}: function (store, key" not in js
