from arklight.ast.nodes import ARKNode, node


def test_node_factory_builds_ark_node():
    Heading = node("Heading")
    result = Heading("Hello", id="title")

    assert isinstance(result, ARKNode)
    assert result.type == "Heading"
    assert result.props == {"id": "title"}
    assert result.children == ["Hello"]


def test_node_factory_multiple_children():
    Container = node("Container")
    a = node("Text")("a")
    b = node("Text")("b")
    result = Container(a, b)

    assert result.children == [a, b]
    assert result.props == {}


def test_node_repr_does_not_crash():
    n = node("Text")("hi")
    assert "Text" in repr(n)
