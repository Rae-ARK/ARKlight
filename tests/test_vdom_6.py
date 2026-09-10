"""
`vdom-6` (docs/Backends/REFACTOR-INDEX.md row 14): two-way input
binding via `bind_value=Bind.model(...)` -- across the API, Validation,
the HTML backend (`value=` pre-fill + `data-ark-model` compilation),
and the JS backend (`renderModelBindings`/`wireModelBinding` wiring).
"""

import pytest

from arklight.api import Action, Bind, Button, Computed, Container, Derive, Input, Page, State, Text
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


def test_bind_model_returns_the_state_name():
    assert Bind.model("query") == "query"


def test_bind_value_prop_accepts_a_plain_string_too():
    node = Input(bind_value="query")
    assert node.props["bind_value"] == "query"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_bind_value_to_declared_state_passes_validation():
    tree = Page(
        State("query", ""),
        Input(bind_value=Bind.model("query")),
    )
    validate_ark_ast(normalize_ark_ast({"/": tree}))  # no raise


def test_bind_value_to_undeclared_state_raises():
    tree = Page(Input(bind_value=Bind.model("query")))
    with pytest.raises(ValidationError, match="isn't declared on this page"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_bind_value_targeting_computed_name_raises():
    # Mirrors Action.*(...)'s own restriction: a Computed(...) has no
    # independent value of its own for user input to write back into.
    tree = Page(
        State("price", 9.99),
        State("qty", 3),
        Computed("total", deps=("price", "qty"), derive=Derive.multiply("price", "qty")),
        Input(bind_value=Bind.model("total")),
    )
    with pytest.raises(ValidationError, match="Computed"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_bind_value_empty_string_raises():
    tree = Page(State("query", ""), Input(bind_value=""))
    with pytest.raises(ValidationError, match="non-empty state name"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_bind_value_non_string_raises():
    tree = Page(State("query", ""), Input(bind_value=123))
    with pytest.raises(ValidationError, match="non-empty state name"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


# ---------------------------------------------------------------------------
# HTML backend
# ---------------------------------------------------------------------------


def test_html_backend_prefills_value_from_initial_state():
    tree = Page(State("query", "hello"), Input(bind_value=Bind.model("query")))
    ir = _ir({"/": tree})
    html = HTMLBackend().render(ir)["index.html"]
    assert 'value="hello"' in html
    assert 'data-ark-model="query"' in html


def test_html_backend_explicit_value_prop_wins_over_state_prefill():
    tree = Page(
        State("query", "from-state"),
        Input(value="from-prop", bind_value=Bind.model("query")),
    )
    ir = _ir({"/": tree})
    html = HTMLBackend().render(ir)["index.html"]
    assert 'value="from-prop"' in html
    assert 'value="from-state"' not in html


def test_html_backend_bind_value_with_no_initial_state_entry_omits_value():
    # bind_value targeting a real declared State(...) is required by
    # Validation, so this exercises the "state value is None" branch
    # in the pre-fill, not an undeclared-name path.
    tree = Page(State("query", None), Input(bind_value=Bind.model("query")))
    ir = _ir({"/": tree})
    html = HTMLBackend().render(ir)["index.html"]
    assert "value=" not in html
    assert 'data-ark-model="query"' in html


# ---------------------------------------------------------------------------
# JS backend
# ---------------------------------------------------------------------------


def test_js_backend_ships_model_binding_wiring_when_used():
    tree = Page(State("query", ""), Input(bind_value=Bind.model("query")))
    ir = _ir({"/": tree})
    js = JSBackend().render(ir)["arklight.js"]
    assert "renderModelBindings" in js
    assert "wireModelBinding(" in js
    assert 'data-ark-model' in js  # el.getAttribute("data-ark-model")


def test_js_backend_ships_nothing_extra_without_bind_value():
    tree = Page(State("count", 0), Button("+", on_click=Action.increment("count", 1)))
    ir = _ir({"/": tree})
    js = JSBackend().render(ir)["arklight.js"]
    # The typeof-guarded call in STATE_CORE_JS is always present on any
    # stateful page (same as wireWatchers's own guard) -- what matters
    # is that the fragment defining the function is never shipped.
    assert "function renderModelBindings(store)" not in js
    assert "function wireModelBinding(getStore)" not in js


def test_js_backend_model_binding_reuses_same_store_getter_as_click_interceptor():
    # has_model_binding implies has_state, so wireModelBinding should
    # be registered with the same live-store getter wireClickInterceptor
    # gets, not a fixed value -- exercised together on one page.
    tree = Page(
        State("count", 0),
        State("query", ""),
        Button("+", on_click=Action.increment("count", 1)),
        Input(bind_value=Bind.model("query")),
    )
    ir = _ir({"/": tree})
    js = JSBackend().render(ir)["arklight.js"]
    assert "wireClickInterceptor(function () { return arkStore; })" in js
    assert "wireModelBinding(function () { return arkStore; })" in js


def test_js_backend_calls_render_model_bindings_on_init():
    tree = Page(State("query", ""), Input(bind_value=Bind.model("query")))
    ir = _ir({"/": tree})
    js = JSBackend().render(ir)["arklight.js"]
    assert "renderModelBindings(arkStore)" in js


# ---------------------------------------------------------------------------
# End-to-end: the shipped `renderModelBindings`/`wireModelBinding`
# fragments, run under Node against minimal stand-ins for `document`/
# `store` (no real DOM available in this environment), actually sync
# state -> value and value -> state in both directions.
# ---------------------------------------------------------------------------


def test_node_render_model_bindings_writes_state_into_element_value():
    node = pytest.importorskip("shutil").which("node")
    if not node:
        pytest.skip("node not available in this environment")

    import subprocess

    from arklight.backend.js.runtime.model import RENDER_MODEL_BINDINGS_JS

    script = f"""
    {RENDER_MODEL_BINDINGS_JS}
    var el = {{ value: "", attrs: {{ "data-ark-model": "query" }},
      getAttribute: function (n) {{ return this.attrs[n]; }} }};
    var document = {{ querySelectorAll: function (sel) {{ return [el]; }} }};
    var store = {{ get: function (key) {{ return {{ query: "typed value" }}[key]; }} }};
    renderModelBindings(store);
    console.log(el.value);
    """
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "typed value"


def test_node_wire_model_binding_writes_input_value_into_state():
    node = pytest.importorskip("shutil").which("node")
    if not node:
        pytest.skip("node not available in this environment")

    import subprocess

    from arklight.backend.js.runtime.model import WIRE_MODEL_BINDING_JS

    script = f"""
    {WIRE_MODEL_BINDING_JS}
    var handlers = {{}};
    var el = {{ value: "new text", attrs: {{ "data-ark-model": "query" }},
      getAttribute: function (n) {{ return this.attrs[n]; }},
      closest: function (sel) {{ return this.attrs["data-ark-model"] !== undefined ? this : null; }} }};
    var document = {{ addEventListener: function (type, fn) {{ handlers[type] = fn; }} }};
    var state = {{ query: "" }};
    var store = {{
      get: function (key) {{ return state[key]; }},
      set: function (key, value) {{ state[key] = value; }}
    }};
    wireModelBinding(function () {{ return store; }});
    handlers["input"]({{ target: el }});
    console.log(store.get("query"));
    """
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "new text"
