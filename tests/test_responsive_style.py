"""
Tests for v0.048 Stage B: `responsive_style={...}` + `@media`
compilation -- see docs/DESIGN-NOTES.md ("v0.048: CSS media queries +
`<head>` extension") and docs/EXPERIMENTAL-APIS.md.
"""

from __future__ import annotations

import pytest

from arklight.api import Container, Page, Text
from arklight.backend.css.custom_styles import render_responsive_styles
from arklight.backend.css.render import CSSBackend, STYLESHEET_PATH
from arklight.compiler.pipeline import compile_site_file
from arklight.ir.build import build_website_ir
from arklight.ir.normalize import normalize_ark_ast
from arklight.ir.validate import ValidationError, validate_ark_ast


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validate_accepts_well_formed_responsive_style():
    pages = {
        "/": Page(
            Container(
                Text("hi"),
                responsive_style={"(max-width: 600px)": {"display": "none"}},
            )
        )
    }
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)  # must not raise


def test_validate_rejects_non_dict_responsive_style():
    pages = {"/": Page(Container(Text("hi"), responsive_style="not-a-dict"))}
    normalized = normalize_ark_ast(pages)
    with pytest.raises(ValidationError):
        validate_ark_ast(normalized)


def test_validate_rejects_empty_responsive_style():
    pages = {"/": Page(Container(Text("hi"), responsive_style={}))}
    normalized = normalize_ark_ast(pages)
    with pytest.raises(ValidationError):
        validate_ark_ast(normalized)


def test_validate_rejects_empty_condition_key():
    pages = {"/": Page(Container(Text("hi"), responsive_style={"": {"display": "none"}}))}
    normalized = normalize_ark_ast(pages)
    with pytest.raises(ValidationError):
        validate_ark_ast(normalized)


def test_validate_rejects_non_dict_rules_value():
    pages = {
        "/": Page(
            Container(Text("hi"), responsive_style={"(max-width: 600px)": "none"})
        )
    }
    normalized = normalize_ark_ast(pages)
    with pytest.raises(ValidationError):
        validate_ark_ast(normalized)


def test_validate_rejects_empty_rules_dict():
    pages = {
        "/": Page(Container(Text("hi"), responsive_style={"(max-width: 600px)": {}}))
    }
    normalized = normalize_ark_ast(pages)
    with pytest.raises(ValidationError):
        validate_ark_ast(normalized)


def test_validate_rejects_non_string_property_name():
    pages = {
        "/": Page(
            Container(
                Text("hi"),
                responsive_style={"(max-width: 600px)": {1: "none"}},
            )
        )
    }
    normalized = normalize_ark_ast(pages)
    with pytest.raises(ValidationError):
        validate_ark_ast(normalized)


def test_validate_rejects_bool_value():
    pages = {
        "/": Page(
            Container(
                Text("hi"),
                responsive_style={"(max-width: 600px)": {"display": True}},
            )
        )
    }
    normalized = normalize_ark_ast(pages)
    with pytest.raises(ValidationError):
        validate_ark_ast(normalized)


def test_validate_accepts_numeric_value():
    pages = {
        "/": Page(
            Container(
                Text("hi"),
                responsive_style={"(max-width: 600px)": {"opacity": 0}},
            )
        )
    }
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)  # must not raise


# ---------------------------------------------------------------------------
# IR build: generated class + responsive_rules collection
# ---------------------------------------------------------------------------


def test_build_strips_responsive_style_from_ir_props_and_adds_class():
    pages = {
        "/": Page(
            Container(
                Text("hi"),
                responsive_style={"(max-width: 600px)": {"display": "none"}},
            )
        )
    }
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir("site", normalized)

    container = ir.pages[0].root.children[0]
    assert "responsive_style" not in container.props
    assert container.props["class_name"] == "arkgen-1"
    assert ir.responsive_rules == [
        ("(max-width: 600px)", "arkgen-1", {"display": "none"})
    ]


def test_build_preserves_existing_class_name_alongside_generated_one():
    pages = {
        "/": Page(
            Container(
                Text("hi"),
                class_name="card",
                responsive_style={"(max-width: 600px)": {"display": "none"}},
            )
        )
    }
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir("site", normalized)

    container = ir.pages[0].root.children[0]
    assert container.props["class_name"] == "card arkgen-1"


def test_build_assigns_distinct_classes_per_node_in_document_order():
    pages = {
        "/": Page(
            Container(
                Container(Text("a"), responsive_style={"(max-width: 600px)": {"display": "none"}}),
                Container(Text("b"), responsive_style={"(min-width: 900px)": {"display": "flex"}}),
            )
        )
    }
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir("site", normalized)

    outer = ir.pages[0].root.children[0]
    first, second = outer.children
    assert first.props["class_name"] == "arkgen-1"
    assert second.props["class_name"] == "arkgen-2"
    assert ir.responsive_rules == [
        ("(max-width: 600px)", "arkgen-1", {"display": "none"}),
        ("(min-width: 900px)", "arkgen-2", {"display": "flex"}),
    ]


def test_build_one_node_multiple_conditions_share_one_class():
    pages = {
        "/": Page(
            Container(
                Text("hi"),
                responsive_style={
                    "(max-width: 600px)": {"display": "none"},
                    "(min-width: 900px)": {"display": "flex"},
                },
            )
        )
    }
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir("site", normalized)

    container = ir.pages[0].root.children[0]
    assert container.props["class_name"] == "arkgen-1"
    assert ir.responsive_rules == [
        ("(max-width: 600px)", "arkgen-1", {"display": "none"}),
        ("(min-width: 900px)", "arkgen-1", {"display": "flex"}),
    ]


def test_build_no_responsive_style_leaves_responsive_rules_empty():
    pages = {"/": Page(Text("hi"))}
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir("site", normalized)

    assert ir.responsive_rules == []


def test_build_records_experimental_usage_per_node():
    pages = {
        "/": Page(
            Container(Text("a"), responsive_style={"(max-width: 600px)": {"display": "none"}}),
            Container(Text("b"), responsive_style={"(max-width: 600px)": {"display": "none"}}),
        )
    }
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir("site", normalized)

    usages = [u for u in ir.experimental_usages if u.feature_id == "css-media-queries"]
    assert len(usages) == 2
    assert all(u.component == "Container" for u in usages)


def test_build_on_warning_called_once_per_node():
    pages = {
        "/": Page(
            Container(Text("a"), responsive_style={"(max-width: 600px)": {"display": "none"}}),
        )
    }
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)

    banners: list[str] = []
    build_website_ir("site", normalized, on_warning=banners.append)

    assert len(banners) == 1
    assert "EXPERIMENTAL FEATURE ACTIVE" in banners[0]


# ---------------------------------------------------------------------------
# CSS backend rendering
# ---------------------------------------------------------------------------


def test_render_responsive_styles_empty_is_empty_string():
    assert render_responsive_styles([]) == ""


def test_render_responsive_styles_produces_at_media_block_condition_verbatim():
    css = render_responsive_styles(
        [("(max-width: 600px)", "arkgen-1", {"display": "none"})]
    )
    # Condition inserted verbatim (already parenthesized by the author),
    # not auto-wrapped in an extra layer of parens.
    assert "@media (max-width: 600px) {" in css
    assert "@media ((max-width: 600px))" not in css
    assert ".arkgen-1 {" in css
    assert "display: none;" in css


def test_render_responsive_styles_supports_compound_condition():
    css = render_responsive_styles(
        [("screen and (max-width: 600px)", "arkgen-1", {"display": "none"})]
    )
    assert "@media screen and (max-width: 600px) {" in css


def test_render_responsive_styles_converts_underscores_to_dashes():
    css = render_responsive_styles(
        [("(max-width: 600px)", "arkgen-1", {"background_color": "red"})]
    )
    assert "background-color: red;" in css


def test_css_backend_includes_responsive_rules_last_in_cascade():
    pages = {
        "/": Page(
            Container(
                Text("hi"),
                class_name="card",
                responsive_style={"(max-width: 600px)": {"display": "none"}},
            )
        )
    }
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir("site", normalized)

    css = CSSBackend().render(ir)[STYLESHEET_PATH]
    assert ".arkgen-1 {" in css
    assert css.rindex("@media (max-width: 600px)") > css.rindex(".card")


def test_css_backend_no_responsive_style_unchanged():
    pages = {"/": Page(Text("hi"))}
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir("site", normalized)

    css = CSSBackend().render(ir)[STYLESHEET_PATH]
    assert "arkgen-" not in css


# ---------------------------------------------------------------------------
# End-to-end: compiler pipeline
# ---------------------------------------------------------------------------


def test_compile_site_file_threads_responsive_style_into_ir(tmp_path):
    site_file = tmp_path / "site.py"
    site_file.write_text(
        "from arklight import Site, Page, Container, Text\n"
        "site = Site(name='Test')\n"
        "@site.page('/')\n"
        "def home():\n"
        "    return Page(Container(Text('hi'), responsive_style="
        "{'(max-width: 600px)': {'display': 'none'}}))\n"
    )
    ir = compile_site_file(site_file)

    assert ir.responsive_rules == [
        ("(max-width: 600px)", "arkgen-1", {"display": "none"})
    ]
    usages = [u for u in ir.experimental_usages if u.feature_id == "css-media-queries"]
    assert len(usages) == 1


def test_compile_site_file_raises_on_malformed_responsive_style(tmp_path):
    site_file = tmp_path / "site.py"
    site_file.write_text(
        "from arklight import Site, Page, Container, Text\n"
        "site = Site(name='Test')\n"
        "@site.page('/')\n"
        "def home():\n"
        "    return Page(Container(Text('hi'), responsive_style={}))\n"
    )
    from arklight.compiler.pipeline import CompileError

    with pytest.raises(CompileError):
        compile_site_file(site_file)
