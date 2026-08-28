"""
Unit tests for `arklight/backend/html/attrs.py` -- HTML backend
refactor Stage 3 (see docs/Backends/HTML-BACKEND-REFACTOR.md /
docs/Backends/REFACTOR-INDEX.md row 3, `html-3`).

These test the attribute-rendering data/functions directly,
independent of `HTMLBackend.render`/a full IR build -- the same
"independent testability" goal `tests/test_html_tag_map.py` (Stage 1)
and `tests/test_html_routing.py` (Stage 2) already established.
`tests/test_html_backend.py` still exercises the same behavior
end-to-end through real `Page(...)`/`render()` calls and stays the
source of truth for byte-for-byte HTML output; this file is a faster,
narrower complement, not a replacement.
"""

from __future__ import annotations

from arklight.ast.nodes import ActionRef, ClassBindSpec
from arklight.backend.html.attrs import (
    BEHAVIOR_PROP_ATTRS,
    PASSTHROUGH_ATTRS,
    PROP_ALIASES,
    _attr_string,
    _style_dict_to_css,
)

ROUTE_TO_PATH = {
    "/": "index.html",
    "/about": "about.html",
    "/blog/post": "blog/post.html",
}


# ---------------------------------------------------------------------------
# Data tables -- moved verbatim, so these pin the exact set/mapping
# ---------------------------------------------------------------------------


def test_passthrough_attrs_includes_formaction():
    # The pre-existing `formaction` gap fixed alongside Stage 2's move
    # (see routing.py's module docstring) -- confirming it survived
    # this stage's move too.
    assert "formaction" in PASSTHROUGH_ATTRS


def test_passthrough_attrs_includes_core_html_attrs():
    for attr in ("id", "class", "style", "href", "src", "alt", "title"):
        assert attr in PASSTHROUGH_ATTRS


def test_prop_aliases_maps_class_name_and_for():
    assert PROP_ALIASES == {"class_name": "class", "for_": "for", "html_for": "for"}


def test_behavior_prop_attrs_maps_known_behaviors():
    # htmx-1: `on_click` no longer lives in this dict -- see the
    # docstring above BEHAVIOR_PROP_ATTRS in attrs.py for why (a
    # string on_click is now special-cased to emit hx-on:click
    # directly, ahead of this generic dict-based dispatch).
    assert BEHAVIOR_PROP_ATTRS == {
        "behavior_target": "data-ark-target",
        "toggle_class": "data-ark-toggle-class",
    }


# ---------------------------------------------------------------------------
# _style_dict_to_css
# ---------------------------------------------------------------------------


def test_style_dict_to_css_converts_underscores_to_dashes():
    assert _style_dict_to_css({"font_weight": "bold"}) == "font-weight: bold"


def test_style_dict_to_css_joins_multiple_properties():
    css = _style_dict_to_css({"color": "red", "font_size": "12px"})
    assert css == "color: red; font-size: 12px"


def test_style_dict_to_css_skips_none_and_false_values():
    css = _style_dict_to_css({"color": "red", "display": None, "hidden": False})
    assert css == "color: red"


def test_style_dict_to_css_empty_dict_is_empty_string():
    assert _style_dict_to_css({}) == ""


# ---------------------------------------------------------------------------
# _attr_string
# ---------------------------------------------------------------------------


def test_attr_string_renders_passthrough_attr():
    result = _attr_string({"id": "main"}, current_route="/", route_to_path=ROUTE_TO_PATH)
    assert result == ' id="main"'


def test_attr_string_renders_class_name_alias():
    result = _attr_string({"class_name": "card"}, current_route="/", route_to_path=ROUTE_TO_PATH)
    assert result == ' class="card"'


def test_attr_string_renders_style_dict_as_css():
    result = _attr_string(
        {"style": {"font_weight": "bold"}}, current_route="/", route_to_path=ROUTE_TO_PATH
    )
    assert result == ' style="font-weight: bold"'


def test_attr_string_unknown_prop_becomes_data_attr():
    result = _attr_string({"whatever": "1"}, current_route="/", route_to_path=ROUTE_TO_PATH)
    assert result == ' data-whatever="1"'


def test_attr_string_aria_prop_maps_to_aria_dash():
    result = _attr_string({"aria_label": "Close"}, current_route="/", route_to_path=ROUTE_TO_PATH)
    assert result == ' aria-label="Close"'


def test_attr_string_true_value_renders_boolean_attr():
    result = _attr_string({"disabled": True}, current_route="/", route_to_path=ROUTE_TO_PATH)
    assert result == " disabled"


def test_attr_string_none_and_false_values_are_dropped():
    result = _attr_string(
        {"disabled": False, "hidden": None}, current_route="/", route_to_path=ROUTE_TO_PATH
    )
    assert result == ""


def test_attr_string_skips_level_prop():
    # `level` is handled specially by the Heading tag-selection logic
    # (tag_map.py), never rendered as an attribute here.
    result = _attr_string({"level": 2}, current_route="/", route_to_path=ROUTE_TO_PATH)
    assert result == ""


def test_attr_string_rewrites_internal_href_relative_to_current_route():
    result = _attr_string(
        {"href": "/about"}, current_route="/blog/post", route_to_path=ROUTE_TO_PATH
    )
    assert result == ' href="../about.html"'


def test_attr_string_leaves_external_href_untouched():
    result = _attr_string(
        {"href": "https://example.com"}, current_route="/", route_to_path=ROUTE_TO_PATH
    )
    assert result == ' href="https://example.com"'


def test_attr_string_action_ref_renders_data_ark_action_attrs():
    ref = ActionRef(action="increment", state="count", args={"delta": 1})
    result = _attr_string({"on_click": ref}, current_route="/", route_to_path=ROUTE_TO_PATH)
    assert 'data-ark-on-click="action:increment"' in result
    assert 'data-ark-action-state="count"' in result
    assert 'data-ark-action-args="{&quot;delta&quot;: 1}"' in result


def test_attr_string_action_ref_with_modifiers_renders_hx_trigger():
    # htmx-2: "prevent" contributes no token (honored by construction),
    # "once" maps straight across.
    ref = ActionRef(action="set", state="saved", args={}).with_modifiers("prevent", "once")
    result = _attr_string({"on_click": ref}, current_route="/", route_to_path=ROUTE_TO_PATH)
    assert 'hx-trigger="click once"' in result
    assert "data-ark-modifiers" not in result


def test_attr_string_action_ref_without_modifiers_omits_hx_trigger():
    ref = ActionRef(action="set", state="saved", args={})
    result = _attr_string({"on_click": ref}, current_route="/", route_to_path=ROUTE_TO_PATH)
    assert "hx-trigger" not in result
    assert "data-ark-modifiers" not in result


def test_attr_string_action_ref_with_only_prevent_omits_hx_trigger():
    # "prevent" alone has no hx-trigger equivalent -- nothing left to
    # emit once it's excluded, so the attribute is omitted entirely.
    ref = ActionRef(action="set", state="saved", args={}).with_modifiers("prevent")
    result = _attr_string({"on_click": ref}, current_route="/", route_to_path=ROUTE_TO_PATH)
    assert "hx-trigger" not in result


def test_attr_string_action_ref_debounce_and_throttle_render_ms_suffixed_hx_trigger():
    ref = ActionRef(action="set", state="saved", args={}).debounce(300)
    result = _attr_string({"on_click": ref}, current_route="/", route_to_path=ROUTE_TO_PATH)
    assert 'hx-trigger="click debounce:300ms"' in result

    ref = ActionRef(action="increment", state="count", args={}).throttle(250)
    result = _attr_string({"on_click": ref}, current_route="/", route_to_path=ROUTE_TO_PATH)
    assert 'hx-trigger="click throttle:250ms"' in result


def test_attr_string_action_ref_stop_maps_to_consume():
    ref = ActionRef(action="remove", state="items", args={}).with_modifiers("stop")
    result = _attr_string({"on_click": ref}, current_route="/", route_to_path=ROUTE_TO_PATH)
    assert 'hx-trigger="click consume"' in result


def test_attr_string_action_ref_combined_modifiers_render_in_order():
    ref = (
        ActionRef(action="remove", state="items", args={})
        .with_modifiers("prevent", "stop")
        .debounce(300)
    )
    result = _attr_string({"on_click": ref}, current_route="/", route_to_path=ROUTE_TO_PATH)
    assert 'hx-trigger="click consume debounce:300ms"' in result


def test_attr_string_bind_class_renders_data_ark_bind_class_attrs():
    spec = ClassBindSpec(state="active", class_name="is-active")
    result = _attr_string({"bind_class": spec}, current_route="/", route_to_path=ROUTE_TO_PATH)
    assert 'data-ark-bind-class="is-active"' in result
    assert 'data-ark-bind-class-state="active"' in result


def test_attr_string_bind_class_prefills_class_name_from_page_state():
    spec = ClassBindSpec(state="active", class_name="is-active")
    result = _attr_string(
        {"bind_class": spec, "class_name": "card"},
        current_route="/",
        route_to_path=ROUTE_TO_PATH,
        page_state={"active": True},
    )
    assert 'class="card is-active"' in result


def test_attr_string_bind_class_does_not_prefill_when_state_falsy():
    spec = ClassBindSpec(state="active", class_name="is-active")
    result = _attr_string(
        {"bind_class": spec, "class_name": "card"},
        current_route="/",
        route_to_path=ROUTE_TO_PATH,
        page_state={"active": False},
    )
    assert 'class="card"' in result
    assert "is-active" not in result.split('data-ark-bind-class="')[0]
