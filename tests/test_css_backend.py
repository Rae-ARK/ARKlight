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


def test_css_backend_stylesheet_covers_v0_004_tags():
    pages = {"/": Page(Text("hi"))}
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir("site", normalized)

    css = CSSBackend().render(ir)[STYLESHEET_PATH]

    for selector in (
        "details", "summary", "code", "pre", "blockquote", "table",
        "th, td", "input, textarea, select", "fieldset", "legend",
    ):
        assert f"{selector} {{" in css, f"expected a rule for {selector!r} in generated CSS"


def test_css_backend_includes_intrinsic_layout_utilities():
    pages = {"/": Page(Text("hi"))}
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir("site", normalized)

    css = CSSBackend().render(ir)[STYLESHEET_PATH]

    for utility_class in (".stack", ".cluster", ".sidebar", ".switcher", ".grid", ".center", ".reel"):
        assert f"{utility_class} {{" in css or f"{utility_class} >" in css, (
            f"expected an intrinsic layout rule for {utility_class!r}"
        )


def test_css_backend_has_no_media_or_container_queries():
    # Structural constraint (see docs/DESIGN-NOTES.md): everything
    # responsive has to come from intrinsic sizing, since `Page` has no
    # `<head>` hook for a breakpoint-based rule.
    pages = {"/": Page(Text("hi"))}
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir("site", normalized)

    css = CSSBackend().render(ir)[STYLESHEET_PATH]
    import re

    code_only = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)

    assert "@media" not in code_only
    assert "@container" not in code_only
