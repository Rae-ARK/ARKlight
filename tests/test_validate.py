import pytest

from arklight.api import Button, Container, Heading, Image, Link, Page, Text
from arklight.ast.nodes import ARKNode
from arklight.ir.normalize import normalize_node
from arklight.ir.validate import ValidationError, validate_node, validate_page


def norm_validate(tree):
    n = normalize_node(tree)
    validate_node(n)
    return n


def test_valid_tree_passes():
    tree = Page(Heading("Hi"), Text("body"), Button("Go"))
    norm_validate(tree)  # should not raise


def test_unknown_component_type_raises():
    bad = ARKNode(type="Frobnicator", props={}, children=[])
    with pytest.raises(ValidationError, match="Unknown component type"):
        validate_node(bad)


def test_missing_required_prop_raises():
    tree = Link("click me")  # missing href
    with pytest.raises(ValidationError, match="missing required prop 'href'"):
        norm_validate(tree)


def test_image_with_children_raises():
    bad = ARKNode(type="Image", props={"src": "a.png"}, children=[ARKNode("Text", {}, ["x"])])
    with pytest.raises(ValidationError, match="must not have children"):
        validate_node(bad)


def test_nested_component_inside_text_only_raises():
    # Bypass normalization to simulate a malformed tree directly.
    bad = ARKNode(type="Heading", props={}, children=[ARKNode("Text", {}, ["nested"])])
    with pytest.raises(ValidationError, match="can only contain text"):
        validate_node(bad)


def test_page_route_must_return_page_root():
    not_a_page = Text("oops")
    with pytest.raises(ValidationError, match="must return Page"):
        validate_page("/", not_a_page)


def test_container_can_hold_nested_components():
    tree = Page(Container(Text("a"), Link("b", href="/x")))
    norm_validate(tree)  # should not raise


def test_valid_on_click_behavior_passes():
    tree = Page(Button("Show", on_click="toggle", behavior_target="#panel"))
    norm_validate(tree)  # should not raise


def test_unknown_on_click_behavior_raises():
    tree = Page(Button("Show", on_click="explode", behavior_target="#panel"))
    with pytest.raises(ValidationError, match="isn't a recognized behavior"):
        norm_validate(tree)


def test_on_click_without_behavior_target_raises():
    tree = Page(Button("Show", on_click="toggle"))
    with pytest.raises(ValidationError, match="no `behavior_target` prop"):
        norm_validate(tree)
