import pytest

from arklight.api import Container, Heading, Page, Text
from arklight.ir.normalize import normalize_node


def test_flattens_nested_lists():
    tree = Container([Text("a"), [Text("b"), Text("c")]])
    result = normalize_node(tree)
    assert [c.type for c in result.children] == ["Text", "Text", "Text"]


def test_wraps_bare_strings_in_container_as_text():
    tree = Container("hello")
    result = normalize_node(tree)
    assert len(result.children) == 1
    assert result.children[0].type == "Text"
    assert result.children[0].children == ["hello"]


def test_does_not_wrap_bare_strings_inside_text_only_component():
    tree = Heading("hello")
    result = normalize_node(tree)
    assert result.children == ["hello"]


def test_drops_none_and_false_children():
    tree = Container(Text("kept"), None, False)
    result = normalize_node(tree)
    assert len(result.children) == 1
    assert result.children[0].children == ["kept"]


def test_rejects_unsupported_child_type():
    tree = Container(object())
    with pytest.raises(TypeError):
        normalize_node(tree)


def test_recursive_normalization_on_full_page():
    tree = Page(Heading("Title"), Container([Text("x"), None, "y"]))
    result = normalize_node(tree)
    heading, container = result.children
    assert heading.children == ["Title"]
    assert [c.children for c in container.children] == [["x"], ["y"]]
