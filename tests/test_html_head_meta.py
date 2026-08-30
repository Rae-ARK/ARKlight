"""
Unit tests for `arklight/backend/html/head_meta.py` -- HTML backend
refactor Stage 4 (see docs/Backends/HTML-BACKEND-REFACTOR.md /
docs/Backends/REFACTOR-INDEX.md row 7, `html-4`).

These test `_render_head_meta` directly, independent of
`HTMLBackend.render`/a full IR build -- the same "independent
testability" goal `tests/test_html_tag_map.py` (Stage 1),
`tests/test_html_routing.py` (Stage 2), and `tests/test_html_attrs.py`
(Stage 3) already established. `tests/test_html_backend.py` still
exercises the same behavior end-to-end through real `Page(...)`/
`render()` calls and stays the source of truth for byte-for-byte HTML
output; this file is a faster, narrower complement, not a replacement.
"""

from __future__ import annotations

from arklight.backend.html.head_meta import _render_head_meta
from arklight.ir.build import IRNode, IRPage

ROUTE_TO_PATH = {
    "/": "index.html",
    "/about": "about.html",
    "/blog/post": "blog/post.html",
}


def _page(props: dict) -> IRPage:
    return IRPage(route="/", root=IRNode(type="Page", props=props))


def test_no_optional_props_renders_empty_string():
    page = _page({})
    assert _render_head_meta(page, "Home", current_route="/", route_to_path=ROUTE_TO_PATH) == ""


def test_description_renders_meta_description_tag():
    page = _page({"description": "A test site"})
    result = _render_head_meta(page, "Home", current_route="/", route_to_path=ROUTE_TO_PATH)
    assert '<meta name="description" content="A test site">' in result


def test_favicon_renders_relative_icon_link():
    page = _page({"favicon": "favicon.ico"})
    result = _render_head_meta(
        page, "Home", current_route="/blog/post", route_to_path=ROUTE_TO_PATH
    )
    assert '<link rel="icon" href="../favicon.ico">' in result


def test_og_tags_not_emitted_without_any_og_opt_in_prop():
    page = _page({})
    result = _render_head_meta(page, "Home", current_route="/", route_to_path=ROUTE_TO_PATH)
    assert "og:" not in result


def test_description_alone_triggers_og_title_and_description_fallback():
    page = _page({"description": "A test site"})
    result = _render_head_meta(page, "Home", current_route="/", route_to_path=ROUTE_TO_PATH)
    assert '<meta property="og:title" content="Home">' in result
    assert '<meta property="og:description" content="A test site">' in result


def test_explicit_og_title_overrides_page_title():
    page = _page({"og_title": "Custom OG Title"})
    result = _render_head_meta(page, "Home", current_route="/", route_to_path=ROUTE_TO_PATH)
    assert '<meta property="og:title" content="Custom OG Title">' in result


def test_og_image_resolved_as_relative_asset_path():
    page = _page({"og_image": "social.png"})
    result = _render_head_meta(
        page, "Home", current_route="/blog/post", route_to_path=ROUTE_TO_PATH
    )
    assert '<meta property="og:image" content="../social.png">' in result


def test_favicon_with_leading_slash_resolved_relative_not_cwd_dependent():
    # Bugfix regression: a root-relative favicon (leading "/") used to
    # be passed straight into `_relative_asset_path`, which calls
    # `posixpath.relpath()` -- with one argument absolute, `relpath`
    # resolves against the build's `os.getcwd()` instead of the site
    # structure, so the result varied with the calling directory
    # instead of being a fixed function of the route. A leading "/"
    # must now resolve identically to the same path with no leading
    # "/" (see `routing.py`'s `_resolve_src_ref` for the same fix
    # applied to `src`-shaped attributes).
    with_slash = _page({"favicon": "/assets/favicon.ico"})
    without_slash = _page({"favicon": "assets/favicon.ico"})
    result_with_slash = _render_head_meta(
        with_slash, "Home", current_route="/blog/post", route_to_path=ROUTE_TO_PATH
    )
    result_without_slash = _render_head_meta(
        without_slash, "Home", current_route="/blog/post", route_to_path=ROUTE_TO_PATH
    )
    assert result_with_slash == result_without_slash
    assert '<link rel="icon" href="../assets/favicon.ico">' in result_with_slash


def test_og_image_with_leading_slash_resolved_relative_not_cwd_dependent():
    with_slash = _page({"og_image": "/assets/social.png"})
    without_slash = _page({"og_image": "assets/social.png"})
    result_with_slash = _render_head_meta(
        with_slash, "Home", current_route="/blog/post", route_to_path=ROUTE_TO_PATH
    )
    result_without_slash = _render_head_meta(
        without_slash, "Home", current_route="/blog/post", route_to_path=ROUTE_TO_PATH
    )
    assert result_with_slash == result_without_slash
    assert '<meta property="og:image" content="../assets/social.png">' in result_with_slash


def test_meta_dict_renders_one_tag_per_entry_in_order():
    page = _page({"meta": {"robots": "noindex", "author": "Rae"}})
    result = _render_head_meta(page, "Home", current_route="/", route_to_path=ROUTE_TO_PATH)
    robots_idx = result.index('name="robots"')
    author_idx = result.index('name="author"')
    assert robots_idx < author_idx
    assert '<meta name="robots" content="noindex">' in result
    assert '<meta name="author" content="Rae">' in result


def test_links_list_renders_verbatim_attributes_not_asset_resolved():
    page = _page({"links": [{"rel": "preconnect", "href": "https://fonts.gstatic.com"}]})
    result = _render_head_meta(page, "Home", current_route="/blog/post", route_to_path=ROUTE_TO_PATH)
    # Verbatim, unlike favicon/og_image -- no relative-path rewriting.
    assert '<link rel="preconnect" href="https://fonts.gstatic.com">' in result


def test_links_list_supports_multiple_entries():
    page = _page(
        {
            "links": [
                {"rel": "preconnect", "href": "https://fonts.gstatic.com"},
                {"rel": "icon", "href": "extra-icon.png", "sizes": "32x32"},
            ]
        }
    )
    result = _render_head_meta(page, "Home", current_route="/", route_to_path=ROUTE_TO_PATH)
    assert result.count("<link") == 2
    assert 'sizes="32x32"' in result


def test_values_are_html_escaped():
    page = _page({"description": '<script>alert("x")</script>'})
    result = _render_head_meta(page, "Home", current_route="/", route_to_path=ROUTE_TO_PATH)
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
