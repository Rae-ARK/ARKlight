from arklight.api import Container, Heading, Page, Text
from arklight.ir.build import IRNode, build_website_ir
from arklight.ir.normalize import normalize_ark_ast
from arklight.ir.validate import validate_ark_ast


def test_build_website_ir_basic_shape():
    pages = {"/": Page(Heading("Hi"), Text("body"))}
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)

    ir = build_website_ir("my-site", normalized)

    assert ir.site_name == "my-site"
    assert len(ir.pages) == 1
    page = ir.pages[0]
    assert page.route == "/"
    assert isinstance(page.root, IRNode)
    assert page.root.type == "Page"
    assert [c.type for c in page.root.children] == ["Heading", "Text"]


def test_build_website_ir_preserves_text_children_as_strings():
    pages = {"/": Page(Heading("Title"))}
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir("site", normalized)

    heading = ir.pages[0].root.children[0]
    assert heading.children == ["Title"]


def test_build_website_ir_multiple_routes():
    pages = {
        "/": Page(Heading("Home")),
        "/about": Page(Heading("About")),
    }
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir("site", normalized)

    routes = {p.route for p in ir.pages}
    assert routes == {"/", "/about"}


def test_build_website_ir_nested_containers():
    pages = {"/": Page(Container(Text("a"), Container(Text("b"))))}
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir("site", normalized)

    outer_container = ir.pages[0].root.children[0]
    inner_container = outer_container.children[1]
    assert inner_container.type == "Container"
    assert inner_container.children[0].type == "Text"
