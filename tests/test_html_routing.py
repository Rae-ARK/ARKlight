"""
Unit tests for `arklight/backend/html/routing.py` -- HTML backend
refactor Stage 2 (see docs/Backends/HTML-BACKEND-REFACTOR.md /
docs/Backends/REFACTOR-INDEX.md row 1, `html-2`).

These test the route/asset-path resolution functions directly,
independent of `HTMLBackend.render`/a full IR build -- the same
"independent testability" goal `tests/test_html_tag_map.py` already
established for Stage 1. `tests/test_html_backend.py` still exercises
the same behavior end-to-end through real `Page(...)`/`render()` calls
and stays the source of truth for byte-for-byte HTML output; this file
is a faster, narrower complement, not a replacement.

This file also covers the `UNROUTED_REFERENCE_ATTRS` fix this stage
lands (`srcset`/`poster`/`action`/`formaction` route/asset-rewritten
instead of only warned about) at the function level, complementing the
end-to-end coverage added to `tests/test_html_backend.py` for the same
fix.
"""

from __future__ import annotations

from arklight.backend.html import routing
from arklight.backend.html.routing import (
    ASSET_OR_ROUTE_AWARE_ATTRS,
    ROUTE_AWARE_ATTRS,
    SRC_ATTRS,
    SRCSET_ATTRS,
    _is_internal_route_ref,
    _output_path_for_route,
    _relative_asset_path,
    _resolve_route_ref,
    _resolve_src_ref,
    _resolve_srcset_ref,
)

ROUTE_TO_PATH = {
    "/": "index.html",
    "/about": "about.html",
    "/blog/post": "blog/post.html",
}


# ---------------------------------------------------------------------------
# Attribute-classification sets
# ---------------------------------------------------------------------------


def test_route_aware_attrs_includes_href_action_and_formaction():
    # `action`/`formaction` joined `href` here as part of the
    # UNROUTED_REFERENCE_ATTRS fix -- see the module docstring.
    assert ROUTE_AWARE_ATTRS == {"href", "action", "formaction"}


def test_asset_or_route_aware_attrs_includes_src_and_poster():
    assert ASSET_OR_ROUTE_AWARE_ATTRS == {"src", "poster"}


def test_srcset_attrs_is_its_own_set():
    assert SRCSET_ATTRS == {"srcset"}


def test_src_attrs_moved_verbatim():
    assert SRC_ATTRS == {"src"}


def test_unrouted_reference_attrs_no_longer_exists():
    # The whole point of this stage's fix: once every attribute
    # UNROUTED_REFERENCE_ATTRS covered is correctly resolved, the set
    # (and the warning function that read it) has nothing left to do
    # and is removed, not deprecated.
    assert not hasattr(routing, "UNROUTED_REFERENCE_ATTRS")
    assert not hasattr(routing, "_warn_unrouted_reference")


# ---------------------------------------------------------------------------
# _output_path_for_route
# ---------------------------------------------------------------------------


def test_output_path_for_root_route():
    assert _output_path_for_route("/") == "index.html"


def test_output_path_for_simple_route():
    assert _output_path_for_route("/about") == "about.html"


def test_output_path_for_nested_route():
    assert _output_path_for_route("/blog/post") == "blog/post.html"


# ---------------------------------------------------------------------------
# _is_internal_route_ref
# ---------------------------------------------------------------------------


def test_internal_route_ref_true_for_leading_slash():
    assert _is_internal_route_ref("/about") is True
    assert _is_internal_route_ref("/") is True


def test_internal_route_ref_false_for_protocol_relative_url():
    assert _is_internal_route_ref("//cdn.example.com/x.js") is False


def test_internal_route_ref_false_for_external_url():
    assert _is_internal_route_ref("https://example.com") is False


def test_internal_route_ref_false_for_fragment_and_mailto():
    assert _is_internal_route_ref("#section") is False
    assert _is_internal_route_ref("mailto:a@example.com") is False


# ---------------------------------------------------------------------------
# _resolve_route_ref (href, and -- since this stage's fix --
# action/formaction)
# ---------------------------------------------------------------------------


def test_resolve_route_ref_known_route_same_level():
    result = _resolve_route_ref("/about", current_route="/", route_to_path=ROUTE_TO_PATH)
    assert result == "about.html"


def test_resolve_route_ref_known_route_across_nested_depth():
    result = _resolve_route_ref("/", current_route="/blog/post", route_to_path=ROUTE_TO_PATH)
    assert result == "../index.html"


def test_resolve_route_ref_unknown_route_left_untouched():
    # This is also what makes rewriting action/formaction through this
    # same function safe: a form action targeting an external API
    # never matches a registered route, so it always lands here.
    result = _resolve_route_ref("/does-not-exist", current_route="/", route_to_path=ROUTE_TO_PATH)
    assert result == "/does-not-exist"


def test_resolve_route_ref_preserves_fragment():
    result = _resolve_route_ref("/about#team", current_route="/", route_to_path=ROUTE_TO_PATH)
    assert result == "about.html#team"


# ---------------------------------------------------------------------------
# _resolve_src_ref (src, and -- since this stage's fix -- poster, plus
# each URL inside a resolved srcset)
# ---------------------------------------------------------------------------


def test_resolve_src_ref_known_route_treated_as_embed():
    result = _resolve_src_ref("/about", current_route="/", route_to_path=ROUTE_TO_PATH)
    assert result == "about.html"


def test_resolve_src_ref_unknown_route_shaped_value_treated_as_asset():
    result = _resolve_src_ref("/sprites/25.png", current_route="/", route_to_path=ROUTE_TO_PATH)
    assert result == "sprites/25.png"


def test_resolve_src_ref_relative_asset_rewritten_for_nested_page():
    result = _resolve_src_ref(
        "sprites/25.png", current_route="/blog/post", route_to_path=ROUTE_TO_PATH
    )
    assert result == "../sprites/25.png"


def test_resolve_src_ref_external_url_left_untouched():
    assert _resolve_src_ref("https://cdn.example.com/a.png", current_route="/", route_to_path=ROUTE_TO_PATH) == (
        "https://cdn.example.com/a.png"
    )


def test_resolve_src_ref_protocol_relative_url_left_untouched():
    assert _resolve_src_ref("//cdn.example.com/a.png", current_route="/", route_to_path=ROUTE_TO_PATH) == (
        "//cdn.example.com/a.png"
    )


def test_resolve_src_ref_data_uri_left_untouched():
    value = "data:image/png;base64,aGVsbG8="
    assert _resolve_src_ref(value, current_route="/", route_to_path=ROUTE_TO_PATH) == value


# ---------------------------------------------------------------------------
# _resolve_srcset_ref -- new in this stage, part of the
# UNROUTED_REFERENCE_ATTRS fix
# ---------------------------------------------------------------------------


def test_resolve_srcset_ref_single_entry_with_width_descriptor():
    result = _resolve_srcset_ref("wide.jpg 800w", current_route="/blog/post", route_to_path=ROUTE_TO_PATH)
    assert result == "../wide.jpg 800w"


def test_resolve_srcset_ref_single_entry_with_density_descriptor():
    result = _resolve_srcset_ref("hi-res.jpg 2x", current_route="/blog/post", route_to_path=ROUTE_TO_PATH)
    assert result == "../hi-res.jpg 2x"


def test_resolve_srcset_ref_entry_without_descriptor():
    result = _resolve_srcset_ref("plain.jpg", current_route="/blog/post", route_to_path=ROUTE_TO_PATH)
    assert result == "../plain.jpg"


def test_resolve_srcset_ref_multiple_entries_each_resolved_independently():
    result = _resolve_srcset_ref(
        "wide.jpg 800w, narrow.jpg 400w", current_route="/blog/post", route_to_path=ROUTE_TO_PATH
    )
    assert result == "../wide.jpg 800w, ../narrow.jpg 400w"


def test_resolve_srcset_ref_skips_empty_entries_from_stray_commas():
    result = _resolve_srcset_ref(
        "wide.jpg 800w, , narrow.jpg 400w", current_route="/blog/post", route_to_path=ROUTE_TO_PATH
    )
    assert result == "../wide.jpg 800w, ../narrow.jpg 400w"


def test_resolve_srcset_ref_external_url_entry_left_untouched():
    result = _resolve_srcset_ref(
        "https://cdn.example.com/wide.jpg 800w, narrow.jpg 400w",
        current_route="/blog/post",
        route_to_path=ROUTE_TO_PATH,
    )
    assert result == "https://cdn.example.com/wide.jpg 800w, ../narrow.jpg 400w"


def test_resolve_srcset_ref_known_route_entry_treated_as_embed():
    result = _resolve_srcset_ref("/about 800w", current_route="/", route_to_path=ROUTE_TO_PATH)
    assert result == "about.html 800w"


# ---------------------------------------------------------------------------
# _relative_asset_path
# ---------------------------------------------------------------------------


def test_relative_asset_path_same_level():
    assert _relative_asset_path("styles.css", current_route="/", route_to_path=ROUTE_TO_PATH) == "styles.css"


def test_relative_asset_path_nested_page():
    result = _relative_asset_path("styles.css", current_route="/blog/post", route_to_path=ROUTE_TO_PATH)
    assert result == "../styles.css"
