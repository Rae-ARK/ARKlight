from arklight.api import Page, Text
from arklight.backend.css.render import CSSBackend, STYLESHEET_PATH
from arklight.ir.build import build_website_ir
from arklight.ir.normalize import normalize_ark_ast
from arklight.ir.validate import validate_ark_ast


def test_css_backend_returns_stylesheet_path():
    pages = {"/": Page(Text("hi"))}
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir("site", normalized)

    output = CSSBackend().render(ir)

    assert set(output.keys()) == {STYLESHEET_PATH}


def test_css_backend_stylesheet_covers_core_tags():
    pages = {"/": Page(Text("hi"))}
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir("site", normalized)

    css = CSSBackend().render(ir)[STYLESHEET_PATH]

    for selector in ("body", "h1", "p", "button", "a", ".nav", ".card"):
        assert f"{selector} {{" in css, f"expected a rule for {selector!r} in generated CSS"
