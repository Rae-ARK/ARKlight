"""
Unit tests for `arklight/backend/html/tag_map.py` -- HTML backend
refactor Stage 1 (see docs/Backends/HTML-BACKEND-REFACTOR.md).

These test `TAG_MAP`/`VOID_TAGS`/`_tag_for` directly, independent of
`HTMLBackend.render`/a full IR build -- exactly the "independent
testability" goal the refactor doc calls out. `tests/test_html_backend.py`
still exercises the same tag-selection behavior end-to-end and stays
the source of truth for byte-for-byte output; this file is a faster,
narrower complement, not a replacement.
"""

from __future__ import annotations

from arklight.backend.html.tag_map import TAG_MAP, VOID_TAGS, _tag_for
from arklight.ir.build import IRNode


def _node(type_: str, **props) -> IRNode:
    return IRNode(type=type_, props=props, children=[])


def test_tag_map_covers_every_known_component_type():
    # Spot-check a representative sample across the vocabulary
    # addenda rather than every single entry -- the full mapping is
    # exercised end-to-end by test_html_backend.py.
    assert TAG_MAP["Container"] == "div"
    assert TAG_MAP["Text"] == "p"
    assert TAG_MAP["Button"] == "button"
    assert TAG_MAP["Link"] == "a"
    assert TAG_MAP["Table"] == "table"
    assert TAG_MAP["IFrame"] == "iframe"
    assert TAG_MAP["NoScript"] == "noscript"


def test_tag_for_falls_back_to_div_for_unmapped_type():
    # _tag_for is only ever called after validate_node() has already
    # confirmed node.type is a real SCHEMA entry, so this path isn't
    # reachable through the documented API -- but it's still the
    # defined fallback behavior of TAG_MAP.get(..., "div").
    assert _tag_for(_node("SomeUnmappedType")) == "div"


def test_tag_for_heading_uses_level_prop_not_the_static_map():
    for level in range(1, 7):
        assert _tag_for(_node("Heading", level=level)) == f"h{level}"


def test_tag_for_heading_defaults_to_h1_without_a_level():
    assert _tag_for(_node("Heading")) == "h1"


def test_tag_for_heading_defaults_to_h1_for_invalid_level():
    assert _tag_for(_node("Heading", level=0)) == "h1"
    assert _tag_for(_node("Heading", level=7)) == "h1"
    assert _tag_for(_node("Heading", level="not-a-number")) == "h1"


def test_tag_for_non_heading_ignores_any_level_prop():
    # level is Heading-specific; another node type carrying a stray
    # "level" prop shouldn't affect its tag.
    assert _tag_for(_node("Text", level=3)) == "p"


def test_void_tags_are_a_subset_of_tag_map_values():
    # Every void tag this backend knows about should correspond to a
    # real emitted tag name somewhere in TAG_MAP -- catches a typo'd
    # void-tag entry that would otherwise silently never match.
    assert VOID_TAGS <= set(TAG_MAP.values())


def test_void_tags_contains_the_documented_set():
    assert VOID_TAGS == {"img", "hr", "br", "input", "source", "wbr", "col", "area", "track"}
