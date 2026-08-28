"""
Unit tests for `arklight/backend/html/page_render.py` -- HTML backend
refactor Stage 5 (see docs/Backends/HTML-BACKEND-REFACTOR.md /
docs/Backends/REFACTOR-INDEX.md row 8, `html-5`).

These test `_render_bind`/`_render_children`/`_render_node`/
`_render_page` directly, independent of `HTMLBackend.render`/a full IR
build -- the same "independent testability" goal
`tests/test_html_tag_map.py` (Stage 1), `tests/test_html_routing.py`
(Stage 2), `tests/test_html_attrs.py` (Stage 3), and
`tests/test_html_head_meta.py` (Stage 4) already established.
`tests/test_html_backend.py` still exercises the same behavior
end-to-end through real `Page(...)`/`render()` calls and stays the
source of truth for byte-for-byte HTML output; this file is a faster,
narrower complement, not a replacement.
"""

from __future__ import annotations

from arklight.backend.html.page_render import (
    _render_bind,
    _render_children,
    _render_node,
    _render_page,
)
from arklight.ir.build import IRNode, IRPage

ROUTE_TO_PATH = {
    "/": "index.html",
    "/about": "about.html",
    "/blog/post": "blog/post.html",
}


# ---------------------------------------------------------------------------
# _render_bind
# ---------------------------------------------------------------------------


def test_render_bind_renders_span_with_current_state_value():
    node = IRNode(type="Bind", props={"name": "count"})
    result = _render_bind(node, page_state={"count": 3})
    assert result == '<span data-ark-bind="count">3</span>'


def test_render_bind_defaults_to_empty_string_when_key_missing():
    node = IRNode(type="Bind", props={"name": "missing"})
    result = _render_bind(node, page_state={})
    assert result == '<span data-ark-bind="missing"></span>'


def test_render_bind_escapes_value():
    node = IRNode(type="Bind", props={"name": "html"})
    result = _render_bind(node, page_state={"html": "<b>x</b>"})
    assert "&lt;b&gt;x&lt;/b&gt;" in result


# ---------------------------------------------------------------------------
# _render_node / _render_children
# ---------------------------------------------------------------------------


def test_render_node_renders_simple_container():
    node = IRNode(type="Container", props={}, children=["hi"])
    result = _render_node(node, current_route="/", route_to_path=ROUTE_TO_PATH, page_state={})
    assert result == "<div>hi</div>"


def test_render_node_renders_void_tag_self_closing():
    node = IRNode(type="Image", props={"src": "pic.png"})
    result = _render_node(node, current_route="/", route_to_path=ROUTE_TO_PATH, page_state={})
    assert result == '<img src="pic.png" />'


def test_render_node_dispatches_bind_type_to_render_bind():
    node = IRNode(type="Bind", props={"name": "count"})
    result = _render_node(node, current_route="/", route_to_path=ROUTE_TO_PATH, page_state={"count": 1})
    assert result == '<span data-ark-bind="count">1</span>'


def test_render_children_flattens_text_and_nested_nodes():
    children = ["before ", IRNode(type="Strong", props={}, children=["mid"]), " after"]
    result = _render_children(
        children, current_route="/", route_to_path=ROUTE_TO_PATH, page_state={}
    )
    assert result == "before <strong>mid</strong> after"


def test_render_children_escapes_bare_text():
    result = _render_children(
        ["<script>"], current_route="/", route_to_path=ROUTE_TO_PATH, page_state={}
    )
    assert result == "&lt;script&gt;"


def test_render_node_recurses_and_resolves_internal_links_relative_to_route():
    node = IRNode(type="Link", props={"href": "/about"}, children=["About"])
    result = _render_node(
        node, current_route="/blog/post", route_to_path=ROUTE_TO_PATH, page_state={}
    )
    assert result == '<a href="../about.html">About</a>'


# ---------------------------------------------------------------------------
# _render_page
# ---------------------------------------------------------------------------


def test_render_page_produces_full_document_shell():
    page = IRPage(route="/", root=IRNode(type="Page", props={"title": "Home"}, children=["hi"]))
    html = _render_page(page, "My Site", ROUTE_TO_PATH, site_lang="en")
    assert html.startswith("<!DOCTYPE html>\n")
    assert '<html lang="en">' in html
    assert "<title>Home</title>" in html
    assert '<link rel="stylesheet" href="styles.css">' in html
    assert '<script src="arklight.js" defer></script>' in html
    assert "hi" in html
    assert html.endswith("</html>\n")


def test_render_page_falls_back_to_site_name_when_no_title():
    page = IRPage(route="/", root=IRNode(type="Page", props={}, children=[]))
    html = _render_page(page, "My Site", ROUTE_TO_PATH, site_lang="en")
    assert "<title>My Site</title>" in html


def test_render_page_falls_back_to_site_lang_when_no_page_lang():
    page = IRPage(route="/", root=IRNode(type="Page", props={}, children=[]))
    html = _render_page(page, "My Site", ROUTE_TO_PATH, site_lang="fr")
    assert '<html lang="fr">' in html


def test_render_page_page_lang_overrides_site_lang():
    page = IRPage(route="/", root=IRNode(type="Page", props={"lang": "de"}, children=[]))
    html = _render_page(page, "My Site", ROUTE_TO_PATH, site_lang="en")
    assert '<html lang="de">' in html


def test_render_page_no_state_omits_data_ark_state_attr():
    page = IRPage(route="/", root=IRNode(type="Page", props={}, children=[]), state={})
    html = _render_page(page, "My Site", ROUTE_TO_PATH, site_lang="en")
    assert "data-ark-state" not in html


def test_render_page_with_state_hydrates_body_as_json():
    page = IRPage(route="/", root=IRNode(type="Page", props={}, children=[]), state={"count": 0})
    html = _render_page(page, "My Site", ROUTE_TO_PATH, site_lang="en")
    assert 'data-ark-state="{&quot;count&quot;: 0}"' in html


def test_render_page_resolves_stylesheet_and_script_relative_to_nested_route():
    page = IRPage(route="/blog/post", root=IRNode(type="Page", props={}, children=[]))
    html = _render_page(page, "My Site", ROUTE_TO_PATH, site_lang="en")
    assert '<link rel="stylesheet" href="../styles.css">' in html
    assert '<script src="../arklight.js" defer></script>' in html


def test_render_page_includes_head_meta_when_description_supplied():
    page = IRPage(
        route="/", root=IRNode(type="Page", props={"description": "A site"}, children=[])
    )
    html = _render_page(page, "My Site", ROUTE_TO_PATH, site_lang="en")
    assert '<meta name="description" content="A site">' in html
