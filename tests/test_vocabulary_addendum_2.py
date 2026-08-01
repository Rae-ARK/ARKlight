"""
Tests for the second v0.003 vocabulary addendum ("even more vocabulary"):
OrderedList/DescriptionList, Picture/PictureSource, native widgets
(Progress/Meter/Datalist/Output), Dialog, the rest of text-level
semantics (incl. bidi + ruby), table ColGroup/Col, Track, image maps
(Map/Area), IFrame, and NoScript.

Mirrors the style of tests/test_html_backend.py and tests/test_validate.py:
each addition is data in arklight.ir.schema.SCHEMA, so these tests mostly
confirm the tag mapping, attribute mapping, and schema rules -- not new
compiler logic (there isn't any).
"""

import pytest

from arklight.api import (
    Address,
    Area,
    Bdi,
    Bdo,
    Caption,
    Col,
    ColGroup,
    Data,
    Datalist,
    Del,
    Dfn,
    Dialog,
    DescriptionDetails,
    DescriptionList,
    DescriptionTerm,
    Form,
    IFrame,
    Ins,
    Item,
    Kbd,
    Link,
    Map,
    Meter,
    NoScript,
    Option,
    OrderedList,
    Output,
    Page,
    Picture,
    PictureSource,
    Progress,
    Q,
    Rp,
    Rt,
    Ruby,
    Samp,
    Source,
    Table,
    TableRow,
    Text,
    Track,
    Var,
    Wbr,
)
from arklight.ast.nodes import ARKNode
from arklight.backend.css.render import CSSBackend
from arklight.backend.html.render import HTMLBackend
from arklight.ir.build import build_website_ir
from arklight.ir.normalize import normalize_ark_ast, normalize_node
from arklight.ir.validate import ValidationError, validate_ark_ast, validate_node


def render(pages: dict, site_name: str = "site"):
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir(site_name, normalized)
    return HTMLBackend().render(ir)


def norm_validate(tree):
    n = normalize_node(tree)
    validate_node(n)
    return n


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


def test_ordered_list_renders_as_ol_with_items():
    output = render({"/": Page(OrderedList(Item("one"), Item("two"), start=3))})
    html = output["index.html"]
    assert '<ol start="3"><li>one</li><li>two</li></ol>' in html


def test_ordered_list_reversed_is_boolean_attribute():
    output = render({"/": Page(OrderedList(Item("a"), reversed=True))})
    assert "<ol reversed>" in output["index.html"]


def test_description_list_term_and_details():
    output = render(
        {
            "/": Page(
                DescriptionList(
                    DescriptionTerm("HTML"),
                    DescriptionDetails(Text("A markup language.")),
                )
            )
        }
    )
    html = output["index.html"]
    assert "<dl><dt>HTML</dt><dd><p>A markup language.</p></dd></dl>" in html


def test_description_term_rejects_nested_component():
    tree = Page(DescriptionList(DescriptionTerm(Text("nope"))))
    with pytest.raises(ValidationError, match="can only contain text"):
        norm_validate(tree)


# ---------------------------------------------------------------------------
# Responsive images
# ---------------------------------------------------------------------------


def test_picture_with_source_and_fallback_img():
    from arklight.api import Image

    output = render(
        {
            "/": Page(
                Picture(
                    PictureSource(srcset="wide.jpg", media="(min-width: 800px)"),
                    Image(src="fallback.jpg", alt="x", loading="lazy"),
                )
            )
        }
    )
    html = output["index.html"]
    assert '<source srcset="wide.jpg" media="(min-width: 800px)" />' in html
    assert 'loading="lazy"' in html


def test_picture_source_requires_srcset():
    bad = ARKNode(type="PictureSource", props={}, children=[])
    with pytest.raises(ValidationError, match="srcset"):
        validate_node(bad, path="root")


# ---------------------------------------------------------------------------
# Native widgets
# ---------------------------------------------------------------------------


def test_progress_and_meter_render_with_attrs():
    output = render(
        {
            "/": Page(
                Progress(value="70", max="100"),
                Meter(value="0.6", min="0", max="1", low="0.2", high="0.8", optimum="0.5"),
            )
        }
    )
    html = output["index.html"]
    assert '<progress value="70" max="100">' in html
    assert 'low="0.2"' in html and 'high="0.8"' in html and 'optimum="0.5"' in html


def test_datalist_with_options_and_output():
    output = render(
        {
            "/": Page(
                Datalist(Option("A"), Option("B"), id="choices"),
                Output("42", for_="a b"),
            )
        }
    )
    html = output["index.html"]
    assert '<datalist id="choices"><option>A</option><option>B</option></datalist>' in html
    assert '<output for="a b">42</output>' in html


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------


def test_dialog_open_renders_natively_no_js_needed():
    output = render(
        {
            "/": Page(
                Dialog(
                    Text("Are you sure?"),
                    Form(method="dialog"),
                    open=True,
                )
            )
        }
    )
    html = output["index.html"]
    assert "<dialog open>" in html
    assert '<form method="dialog">' in html


# ---------------------------------------------------------------------------
# More text-level semantics
# ---------------------------------------------------------------------------


def test_more_text_semantics_render_correct_tags():
    output = render(
        {
            "/": Page(
                Kbd("Ctrl"),
                Samp("Error"),
                Var("x"),
                Data("42", value="42"),
                Ins(Text("added")),
                Del(Text("removed")),
                Q("quoted", cite="https://example.com"),
                Dfn("term"),
                Address(Text("123 Main St")),
                Wbr(),
            )
        }
    )
    html = output["index.html"]
    for expected in (
        "<kbd>Ctrl</kbd>",
        "<samp>Error</samp>",
        "<var>x</var>",
        '<data value="42">42</data>',
        # Ins/Del are real containers (not text-only, like Blockquote) --
        # explicit `Text(...)` wrap, same idiom as `Blockquote(Text(...))`.
        "<ins><p>added</p></ins>",
        "<del><p>removed</p></del>",
        '<q cite="https://example.com">quoted</q>',
        "<dfn>term</dfn>",
        "<address><p>123 Main St</p></address>",
        "<wbr />",
    ):
        assert expected in html


def test_data_requires_value_prop():
    bad = ARKNode(type="Data", props={}, children=["x"])
    with pytest.raises(ValidationError, match="value"):
        validate_node(bad, path="root")


def test_bdi_and_bdo_support_dir_attribute():
    output = render({"/": Page(Bdi("اسم"), Bdo("text", dir="rtl"))})
    html = output["index.html"]
    assert "<bdi>اسم</bdi>" in html
    assert '<bdo dir="rtl">text</bdo>' in html


def test_ruby_annotation_renders_rt_and_rp():
    from arklight.api import Span

    # Ruby is a real container (not text-only, since it must also hold
    # Rt/Rp children), so the base text is wrapped in an inline `Span`
    # -- same idiom as `Blockquote(Text("..."))` elsewhere; a bare
    # string would auto-wrap in a block-level `Text`/<p>, which isn't
    # what an inline element like <ruby> wants.
    output = render({"/": Page(Ruby(Span("漢"), Rp("("), Rt("kan"), Rp(")")))})
    html = output["index.html"]
    assert "<ruby><span>漢</span><rp>(</rp><rt>kan</rt><rp>)</rp></ruby>" in html


# ---------------------------------------------------------------------------
# Table extras
# ---------------------------------------------------------------------------


def test_colgroup_and_col_render_inside_table():
    output = render(
        {
            "/": Page(
                Table(
                    ColGroup(Col(span="2"), Col()),
                    Caption("Demo"),
                    TableRow(),
                )
            )
        }
    )
    html = output["index.html"]
    assert '<colgroup><col span="2" /><col /></colgroup>' in html


# ---------------------------------------------------------------------------
# Media: Track
# ---------------------------------------------------------------------------


def test_video_with_track_captions():
    from arklight.api import Video

    output = render(
        {
            "/": Page(
                Video(
                    Source(src="movie.mp4", type="video/mp4"),
                    Track(src="captions-en.vtt", kind="captions", srclang="en", label="English", default=True),
                    controls=True,
                )
            )
        }
    )
    html = output["index.html"]
    assert '<track src="captions-en.vtt" kind="captions" srclang="en" label="English" default />' in html


def test_track_requires_src():
    bad = ARKNode(type="Track", props={}, children=[])
    with pytest.raises(ValidationError, match="src"):
        validate_node(bad, path="root")


# ---------------------------------------------------------------------------
# Image maps
# ---------------------------------------------------------------------------


def test_map_and_area_render():
    from arklight.api import Image

    output = render(
        {
            "/": Page(
                Image(src="floorplan.png", alt="Floor plan", usemap="#rooms"),
                Map(
                    Area(shape="rect", coords="0,0,100,100", href="/kitchen", alt="Kitchen"),
                    name="rooms",
                ),
            )
        }
    )
    html = output["index.html"]
    assert '<map name="rooms">' in html
    assert 'shape="rect"' in html and 'coords="0,0,100,100"' in html


def test_map_requires_name():
    bad = ARKNode(type="Map", props={}, children=[])
    with pytest.raises(ValidationError, match="name"):
        validate_node(bad, path="root")


# ---------------------------------------------------------------------------
# Embeds: IFrame
# ---------------------------------------------------------------------------


def test_iframe_renders_with_attrs_and_no_children():
    output = render(
        {
            "/": Page(
                IFrame(
                    src="https://example.com/embed",
                    title="Embedded widget",
                    loading="lazy",
                    allowfullscreen=True,
                    sandbox="allow-scripts",
                )
            )
        }
    )
    html = output["index.html"]
    assert 'src="https://example.com/embed"' in html
    assert 'title="Embedded widget"' in html
    assert "allowfullscreen" in html
    assert 'sandbox="allow-scripts"' in html
    assert "<iframe" in html and "</iframe>" in html


def test_iframe_rejects_children():
    bad = ARKNode(type="IFrame", props={"src": "x"}, children=[ARKNode(type="Text", children=["x"])])
    with pytest.raises(ValidationError, match="must not have children"):
        validate_node(bad, path="root")


# ---------------------------------------------------------------------------
# NoScript
# ---------------------------------------------------------------------------


def test_noscript_wraps_fallback_content():
    output = render({"/": Page(NoScript(Text("Enable JavaScript to use the toggle above.")))})
    html = output["index.html"]
    assert "<noscript><p>Enable JavaScript to use the toggle above.</p></noscript>" in html


# ---------------------------------------------------------------------------
# CSS backend sanity: new tags get some default styling.
# ---------------------------------------------------------------------------


def test_css_backend_includes_rules_for_new_tags():
    css = CSSBackend().render(build_website_ir("site", {}))["styles.css"]
    for selector in ("dialog", "kbd", "iframe", "progress, meter", "dl {"):
        assert selector in css
