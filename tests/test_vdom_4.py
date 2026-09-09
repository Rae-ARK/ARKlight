"""
`vdom-4` (docs/Backends/REFACTOR-INDEX.md row 12): computed/derived
state via `Computed(...)`/`Derive.*(...)` -- across the API, Validation,
IR build (dependency ordering + build-time initial-value evaluation),
and the HTML/JS backends (`data-ark-computed` hydration + the
`derivations`/`createState` runtime wiring).
"""

import json

import pytest

from arklight.api import Computed, Derive, Page, State, Text, Bind
from arklight.ast.nodes import DerivationRef
from arklight.backend.html.render import HTMLBackend
from arklight.backend.js.derivations import DERIVATION_FRAGMENTS
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


def test_derive_multiply_returns_derivation_ref():
    ref = Derive.multiply("price", "qty")
    assert ref == DerivationRef(kind="multiply", names=("price", "qty"))


def test_derive_join_carries_sep_arg():
    ref = Derive.join("first", "last", sep="-")
    assert ref == DerivationRef(kind="join", names=("first", "last"), args={"sep": "-"})


def test_derive_compare_carries_op_arg():
    ref = Derive.compare("count", "limit", "gt")
    assert ref == DerivationRef(kind="compare", names=("count", "limit"), args={"op": "gt"})


def test_computed_builds_ark_node_with_deps_and_derive():
    node = Computed("total", deps=("price", "qty"), derive=Derive.multiply("price", "qty"))
    assert node.type == "Computed"
    assert node.props["name"] == "total"
    assert node.props["deps"] == ("price", "qty")
    assert node.props["derive"] == Derive.multiply("price", "qty")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_computed_with_declared_deps_passes_validation():
    tree = Page(
        State("price", 9.99),
        State("qty", 3),
        Computed("total", deps=("price", "qty"), derive=Derive.multiply("price", "qty")),
        Text(Bind("total")),
    )
    validate_ark_ast(normalize_ark_ast({"/": tree}))  # no raise


def test_computed_nested_inside_container_raises():
    from arklight.api import Container

    tree = Page(
        State("price", 9.99),
        Container(Computed("total", deps=("price",), derive=Derive.sum("price"))),
    )
    with pytest.raises(ValidationError, match="direct child of Page"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_computed_depending_on_undeclared_state_raises():
    tree = Page(Computed("total", deps=("price",), derive=Derive.sum("price")))
    with pytest.raises(ValidationError, match="isn't declared on this page"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_computed_unknown_derivation_kind_raises():
    tree = Page(
        State("price", 9.99),
        Computed("total", deps=("price",), derive=DerivationRef(kind="bogus", names=("price",))),
    )
    with pytest.raises(ValidationError, match="unknown derivation"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_computed_derive_names_must_be_subset_of_deps():
    tree = Page(
        State("price", 9.99),
        State("qty", 3),
        Computed("total", deps=("price",), derive=Derive.multiply("price", "qty")),
    )
    with pytest.raises(ValidationError, match="isn't in this Computed"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_computed_compare_with_two_names_passes():
    tree = Page(
        State("price", 9.99),
        State("limit", 5.0),
        Computed("over_limit", deps=("price", "limit"), derive=Derive.compare("price", "limit", "gt")),
    )
    validate_ark_ast(normalize_ark_ast({"/": tree}))  # no raise


def test_computed_compare_with_wrong_arity_raises():
    tree = Page(
        State("price", 9.99),
        Computed(
            "bad",
            deps=("price",),
            derive=DerivationRef(kind="compare", names=("price",), args={"op": "eq"}),
        ),
    )
    with pytest.raises(ValidationError, match="needs"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_computed_unknown_compare_op_raises():
    tree = Page(
        State("a", 1),
        State("b", 2),
        Computed("cmp", deps=("a", "b"), derive=DerivationRef(kind="compare", names=("a", "b"), args={"op": "bogus"})),
    )
    with pytest.raises(ValidationError, match="unknown op"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_computed_dependency_cycle_raises():
    tree = Page(
        State("seed", 1),
        Computed("a", deps=("b",), derive=Derive.sum("b")),
        Computed("b", deps=("a",), derive=Derive.sum("a")),
    )
    with pytest.raises(ValidationError, match="dependency cycle"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_computed_name_cannot_be_action_target():
    from arklight.api import Action, Button

    tree = Page(
        State("price", 9.99),
        Computed("total", deps=("price",), derive=Derive.sum("price")),
        Button("Reset", on_click=Action.set("total", 0)),
    )
    with pytest.raises(ValidationError, match="isn't declared on this page as State"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_computed_forward_reference_to_later_computed_passes():
    # A Computed(...) may depend on another Computed(...) declared
    # later in Page(...)'s children.
    tree = Page(
        State("price", 9.99),
        State("qty", 3),
        Computed("with_tax", deps=("subtotal",), derive=Derive.multiply("subtotal")),
        Computed("subtotal", deps=("price", "qty"), derive=Derive.multiply("price", "qty")),
    )
    validate_ark_ast(normalize_ark_ast({"/": tree}))  # no raise


# ---------------------------------------------------------------------------
# IR build
# ---------------------------------------------------------------------------


def test_ir_build_topologically_orders_computed_by_dependency():
    tree = Page(
        State("price", 9.99),
        State("qty", 3),
        Computed("with_tax", deps=("subtotal",), derive=Derive.multiply("subtotal")),
        Computed("subtotal", deps=("price", "qty"), derive=Derive.multiply("price", "qty")),
    )
    ir = _ir({"/": tree})
    names = [name for name, _spec in ir.pages[0].computed]
    assert names.index("subtotal") < names.index("with_tax")


def test_ir_build_evaluates_computed_initial_values():
    tree = Page(
        State("price", 10.0),
        State("qty", 4),
        Computed("total", deps=("price", "qty"), derive=Derive.multiply("price", "qty")),
    )
    ir = _ir({"/": tree})
    assert ir.pages[0].computed_initial == {"total": 40.0}


def test_ir_build_evaluates_chained_computed_initial_values():
    tree = Page(
        State("price", 10.0),
        State("qty", 2),
        Computed("subtotal", deps=("price", "qty"), derive=Derive.multiply("price", "qty")),
        Computed("with_tax", deps=("subtotal",), derive=Derive.multiply("subtotal")),
    )
    ir = _ir({"/": tree})
    assert ir.pages[0].computed_initial["subtotal"] == 20.0
    assert ir.pages[0].computed_initial["with_tax"] == 20.0


def test_ir_build_pages_without_computed_have_empty_fields():
    tree = Page(State("count", 0), Text(Bind("count")))
    ir = _ir({"/": tree})
    assert ir.pages[0].computed == []
    assert ir.pages[0].computed_initial == {}


# ---------------------------------------------------------------------------
# HTML backend
# ---------------------------------------------------------------------------


def test_html_render_prefills_bind_text_with_computed_initial_value():
    tree = Page(
        State("price", 10.0),
        State("qty", 3),
        Computed("total", deps=("price", "qty"), derive=Derive.multiply("price", "qty")),
        Text(Bind("total")),
    )
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert 'data-ark-bind="total">30.0<' in html


def test_html_render_emits_data_ark_computed_attribute():
    tree = Page(
        State("price", 10.0),
        State("qty", 3),
        Computed("total", deps=("price", "qty"), derive=Derive.multiply("price", "qty")),
        Text(Bind("total")),
    )
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert "data-ark-computed=" in html
    # data-ark-state stays mutable-only -- no computed name leaks into it.
    import re

    state_attr = re.search(r'data-ark-state="([^"]*)"', html).group(1)
    from html import unescape

    state_json = json.loads(unescape(state_attr))
    assert "total" not in state_json
    assert state_json == {"price": 10.0, "qty": 3}


def test_html_render_page_without_computed_omits_attribute():
    tree = Page(State("count", 0), Text(Bind("count")))
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert "data-ark-computed" not in html


# ---------------------------------------------------------------------------
# JS backend
# ---------------------------------------------------------------------------


def test_js_render_ships_only_used_derivation_kinds():
    tree = Page(
        State("price", 10.0),
        State("qty", 3),
        Computed("total", deps=("price", "qty"), derive=Derive.multiply("price", "qty")),
        Text(Bind("total")),
    )
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    assert "multiply: function" in js
    for kind in ("sum", "join", "count", "format", "compare"):
        assert f"{kind}: function" not in js


def test_js_render_ships_every_used_derivation_kind_once():
    tree = Page(
        State("price", 10.0),
        State("qty", 3),
        State("first", "Ada"),
        State("last", "Lovelace"),
        Computed("total", deps=("price", "qty"), derive=Derive.multiply("price", "qty")),
        Computed("full_name", deps=("first", "last"), derive=Derive.join("first", "last")),
        Text(Bind("total")),
    )
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    assert js.count("multiply: function") == 1
    assert js.count("join: function") == 1


def test_js_render_page_without_computed_ships_no_derivations_object():
    tree = Page(State("count", 0), Text(Bind("count")))
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    assert "var derivations" not in js
    assert "createState" in js  # State(...) alone still ships the reactive core


def test_js_render_create_state_recomputes_after_set_and_reset():
    tree = Page(
        State("count", 0),
        Computed("doubled", deps=("count",), derive=Derive.sum("count", "count")),
        Text(Bind("doubled")),
    )
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    assert "function createState(initial, computed)" in js
    assert "recomputeAll" in js
    # recompute must run before listener notification, not after.
    assert "recomputeAll();\n        listeners.forEach" in js.replace("\r\n", "\n")


def test_js_render_init_state_reads_data_ark_computed_attribute():
    tree = Page(
        State("count", 0),
        Computed("doubled", deps=("count",), derive=Derive.sum("count", "count")),
        Text(Bind("doubled")),
    )
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    assert 'getAttribute("data-ark-computed")' in js


def test_derivation_fragments_registry_covers_every_known_kind():
    from arklight.ir.schema import DERIVATION_REGISTRY

    assert set(DERIVATION_FRAGMENTS) == set(DERIVATION_REGISTRY)


# ---------------------------------------------------------------------------
# End-to-end: build-time initial value agrees with a Node evaluation of
# the shipped runtime's own derivation fragments (kind-for-kind parity
# between arklight.ir.build._evaluate_derivation and
# arklight/backend/js/derivations/*.py -- see both modules' docstrings).
# ---------------------------------------------------------------------------


def test_node_runtime_recompute_matches_build_time_initial_value():
    node = pytest.importorskip("shutil").which("node")
    if not node:
        pytest.skip("node not available in this environment")

    import subprocess

    tree = Page(
        State("price", 10.0),
        State("qty", 4),
        Computed("total", deps=("price", "qty"), derive=Derive.multiply("price", "qty")),
    )
    ir = _ir({"/": tree})
    assert ir.pages[0].computed_initial["total"] == 40.0

    script = f"""
    var derivations = {{
      multiply: function (state, names, args) {{
        return names.reduce(function (total, name) {{
          return total * (Number(state[name]) || 0);
        }}, 1);
      }}
    }};
    function createState(initial, computed) {{
      var state = Object.assign({{}}, initial);
      (computed || []).forEach(function (entry) {{
        var name = entry[0], spec = entry[1];
        state[name] = derivations[spec.kind](state, spec.names, spec.args);
      }});
      return state;
    }}
    var state = createState({json.dumps({"price": 10.0, "qty": 4})}, {json.dumps(ir.pages[0].computed)});
    console.log(state.total);
    """
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    assert float(result.stdout.strip()) == ir.pages[0].computed_initial["total"]
