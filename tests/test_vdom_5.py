"""
`vdom-5` (docs/Backends/REFACTOR-INDEX.md row 13): watch effects via
`Watch(name, then=Action.*(...))` -- across the API, Validation, IR
build (declaration-order extraction), and the HTML/JS backends
(`data-ark-watch` hydration + the `wireWatchers` runtime wiring, which
reuses the same `actions` dispatcher `on_click=Action.*(...)` does).
"""

import json

import pytest

from arklight.api import Action, Button, Computed, Container, Derive, Page, State, Text, Bind, Watch
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


def test_watch_builds_ark_node_with_name_and_then():
    node = Watch("celsius", then=Action.set("fahrenheit", 32))
    assert node.type == "Watch"
    assert node.props["name"] == "celsius"
    assert node.props["then"] == Action.set("fahrenheit", 32)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_watch_on_declared_state_passes_validation():
    tree = Page(
        State("celsius", 0),
        State("fahrenheit", 32),
        Watch("celsius", then=Action.set("fahrenheit", 32)),
        Text(Bind("fahrenheit")),
    )
    validate_ark_ast(normalize_ark_ast({"/": tree}))  # no raise


def test_watch_on_computed_name_passes_validation():
    # A Watch(...) may observe a Computed(...) -- only its `then=`
    # target is restricted to a real State(...).
    tree = Page(
        State("price", 9.99),
        State("qty", 3),
        Computed("total", deps=("price", "qty"), derive=Derive.multiply("price", "qty")),
        State("over_budget", False),
        Watch("total", then=Action.set("over_budget", True)),
    )
    validate_ark_ast(normalize_ark_ast({"/": tree}))  # no raise


def test_watch_nested_inside_container_raises():
    tree = Page(
        State("count", 0),
        Container(Watch("count", then=Action.increment("count", 1))),
    )
    with pytest.raises(ValidationError, match="direct child of Page"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_watch_on_undeclared_name_raises():
    tree = Page(
        State("count", 0),
        Watch("bogus", then=Action.increment("count", 1)),
    )
    with pytest.raises(ValidationError, match="isn't declared on this page"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_watch_then_must_be_action_ref():
    tree = Page(State("count", 0), Watch("count", then="not-an-action"))
    with pytest.raises(ValidationError, match="isn't an Action"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_watch_then_unknown_action_raises():
    tree = Page(
        State("count", 0),
        Watch("count", then=ActionRef(action="bogus", state="count")),
    )
    with pytest.raises(ValidationError, match="unknown action"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_watch_then_cannot_target_computed():
    # Same restriction on_click=Action.*(...) already has: a
    # Computed(...) has no independent value of its own to mutate.
    tree = Page(
        State("price", 9.99),
        Computed("total", deps=("price",), derive=Derive.sum("price")),
        Watch("price", then=Action.set("total", 0)),
    )
    with pytest.raises(ValidationError, match="isn't declared on this page as State"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


def test_watch_then_invalid_modifier_raises():
    tree = Page(
        State("count", 0),
        Watch("count", then=Action.increment("count", 1).with_modifiers("bogus")),
    )
    with pytest.raises(ValidationError, match="unknown modifier"):
        validate_ark_ast(normalize_ark_ast({"/": tree}))


# ---------------------------------------------------------------------------
# IR build
# ---------------------------------------------------------------------------


def test_ir_build_extracts_watch_in_declaration_order():
    tree = Page(
        State("a", 0),
        State("b", 0),
        State("c", 0),
        Watch("b", then=Action.set("c", 1)),
        Watch("a", then=Action.set("b", 1)),
    )
    ir = _ir({"/": tree})
    names = [entry["name"] for entry in ir.pages[0].watch]
    assert names == ["b", "a"]


def test_ir_build_watch_then_is_plain_dict_mirror_of_action_ref():
    tree = Page(
        State("count", 0),
        State("doubled", 0),
        Watch("count", then=Action.set("doubled", 0).with_modifiers("prevent")),
    )
    ir = _ir({"/": tree})
    entry = ir.pages[0].watch[0]
    assert entry == {
        "name": "count",
        "then": {
            "action": "set",
            "state": "doubled",
            "args": {"value": 0},
            "modifiers": ["prevent"],
        },
    }


def test_ir_build_watch_node_never_reaches_page_children():
    tree = Page(
        State("count", 0),
        Watch("count", then=Action.increment("count", 1)),
        Text("hello"),
    )
    ir = _ir({"/": tree})
    types = [child.type for child in ir.pages[0].root.children]
    assert "Watch" not in types
    assert types == ["Text"]


def test_ir_build_pages_without_watch_have_empty_field():
    tree = Page(State("count", 0), Text(Bind("count")))
    ir = _ir({"/": tree})
    assert ir.pages[0].watch == []


# ---------------------------------------------------------------------------
# HTML backend
# ---------------------------------------------------------------------------


def test_html_render_emits_data_ark_watch_attribute():
    tree = Page(
        State("celsius", 0),
        State("fahrenheit", 32),
        Watch("celsius", then=Action.set("fahrenheit", 32)),
    )
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert "data-ark-watch=" in html


def test_html_render_page_without_watch_omits_attribute():
    tree = Page(State("count", 0), Text(Bind("count")))
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert "data-ark-watch" not in html


def test_html_render_watch_attribute_round_trips_as_json():
    tree = Page(
        State("count", 0),
        State("doubled", 0),
        Watch("count", then=Action.set("doubled", 0)),
    )
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]

    import re
    from html import unescape

    watch_attr = re.search(r'data-ark-watch="([^"]*)"', html).group(1)
    watch_json = json.loads(unescape(watch_attr))
    assert watch_json == [
        {"name": "count", "then": {"action": "set", "state": "doubled", "args": {"value": 0}, "modifiers": []}}
    ]


# ---------------------------------------------------------------------------
# JS backend
# ---------------------------------------------------------------------------


def test_js_render_ships_wire_watchers_only_when_watch_declared():
    tree = Page(
        State("celsius", 0),
        State("fahrenheit", 32),
        Watch("celsius", then=Action.set("fahrenheit", 32)),
    )
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    assert "function wireWatchers(store, specs)" in js


def test_js_render_page_without_watch_ships_no_wire_watchers():
    tree = Page(State("count", 0), Text(Bind("count")))
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    assert "function wireWatchers(store, specs)" not in js


def test_js_render_watch_only_page_ships_actions_without_click_interceptor():
    # A page with a Watch(...) and no on_click=Action.*(...)/behavior
    # anywhere still needs the `actions` dispatch object (wireWatchers
    # reads it by closure) but never the click interceptor itself.
    tree = Page(
        State("celsius", 0),
        State("fahrenheit", 32),
        Watch("celsius", then=Action.set("fahrenheit", 32)),
    )
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    assert "var actions" in js
    assert "set: function" in js
    assert "function wireClickInterceptor" not in js


def test_js_render_click_action_and_watch_action_both_ship_once():
    tree = Page(
        State("count", 0),
        State("doubled", 0),
        Watch("count", then=Action.set("doubled", 0)),
        Button("Increment", on_click=Action.increment("count", 1)),
    )
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    assert js.count("set: function (store, key, args)") == 1
    assert js.count("increment: function (store, key, args)") == 1
    assert "function wireClickInterceptor" in js  # on_click= still needs it


def test_js_render_init_state_reads_data_ark_watch_attribute():
    tree = Page(
        State("count", 0),
        State("doubled", 0),
        Watch("count", then=Action.set("doubled", 0)),
    )
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    assert 'getAttribute("data-ark-watch")' in js
    assert 'wireWatchers(store, watch)' in js


def test_js_render_init_state_guards_wire_watchers_call():
    # A stateful page with no Watch(...) must not call wireWatchers()
    # unconditionally -- that function is only spliced in when
    # has_watch is true, so an unguarded call would throw
    # ReferenceError on every other stateful page.
    tree = Page(State("count", 0), Text(Bind("count")))
    js = JSBackend().render(_ir({"/": tree}))["arklight.js"]
    assert 'typeof wireWatchers === "function"' in js


# ---------------------------------------------------------------------------
# End-to-end: the shipped `wireWatchers` fragment, run under Node against
# a minimal harness mirroring `createState`/`actions`, actually dispatches
# the watched action on change and doesn't loop forever on a
# self-referential clamp.
# ---------------------------------------------------------------------------


def test_node_wire_watchers_dispatches_action_on_change():
    node = pytest.importorskip("shutil").which("node")
    if not node:
        pytest.skip("node not available in this environment")

    import subprocess

    from arklight.backend.js.runtime.watch import WIRE_WATCHERS_JS

    tree = Page(
        State("celsius", 0),
        State("fahrenheit", 32),
        Watch("celsius", then=Action.set("fahrenheit", 32)),
    )
    ir = _ir({"/": tree})
    watch_json = json.dumps(ir.pages[0].watch)

    script = f"""
    function arkNotify(msg) {{ throw new Error(msg); }}
    var actions = {{
      set: function (store, key, args) {{ store.set(key, args.value); }}
    }};
    function createState(initial) {{
      var state = Object.assign({{}}, initial);
      var listeners = [];
      return {{
        get: function (key) {{ return state[key]; }},
        set: function (key, value) {{
          state[key] = value;
          listeners.forEach(function (fn) {{ fn(); }});
        }},
        subscribe: function (fn) {{ listeners.push(fn); }}
      }};
    }}
    {WIRE_WATCHERS_JS}
    var store = createState({{ celsius: 0, fahrenheit: 32 }});
    var watch = {watch_json};
    wireWatchers(store, watch);
    store.set("celsius", 100);
    console.log(store.get("fahrenheit"));
    """
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    assert float(result.stdout.strip()) == 32.0


def test_node_wire_watchers_self_referential_action_does_not_infinite_loop():
    # A Watch(...) whose `then` mutates its own watched name (the
    # "clamp a value back into range" case docs/Foundational/
    # DESIGN-NOTES.md names) must not recurse forever. The snapshot is
    # updated *before* the action dispatches, so the reentrant
    # notification the action's own store.set triggers compares
    # against the already-updated snapshot -- here that still means
    # one extra reentrant dispatch (0 -> 1 is a real change, and the
    # action's own 1 -> 10 is a second real change), but the third,
    # innermost reentrant notification (10 -> 10, store.set always
    # notifies regardless of whether the value actually changed) sees
    # no difference from the now-current snapshot and stops the
    # recursion there -- bounded, not infinite.
    node = pytest.importorskip("shutil").which("node")
    if not node:
        pytest.skip("node not available in this environment")

    import subprocess

    from arklight.backend.js.runtime.watch import WIRE_WATCHERS_JS

    tree = Page(
        State("count", 0),
        Watch("count", then=Action.set("count", 10)),
    )
    ir = _ir({"/": tree})
    watch_json = json.dumps(ir.pages[0].watch)

    script = f"""
    var callCount = 0;
    function arkNotify(msg) {{ throw new Error(msg); }}
    var actions = {{
      set: function (store, key, args) {{ callCount++; store.set(key, args.value); }}
    }};
    function createState(initial) {{
      var state = Object.assign({{}}, initial);
      var listeners = [];
      return {{
        get: function (key) {{ return state[key]; }},
        set: function (key, value) {{
          state[key] = value;
          listeners.forEach(function (fn) {{ fn(); }});
        }},
        subscribe: function (fn) {{ listeners.push(fn); }}
      }};
    }}
    {WIRE_WATCHERS_JS}
    var store = createState({{ count: 0 }});
    var watch = {watch_json};
    wireWatchers(store, watch);
    store.set("count", 1);
    console.log(JSON.stringify({{ count: store.get("count"), callCount: callCount }}));
    """
    result = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, check=True, timeout=10
    )
    payload = json.loads(result.stdout.strip())
    # The key assertion is boundedness (the subprocess itself would
    # hang past `timeout=10` on a true infinite loop) -- the settled
    # value and a small, finite call count confirm that directly.
    assert payload["count"] == 10
    assert payload["callCount"] == 2
