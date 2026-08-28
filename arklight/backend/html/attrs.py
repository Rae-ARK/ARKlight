"""
HTML Backend refactor, Stage 3 (see
docs/Backends/HTML-BACKEND-REFACTOR.md / docs/Backends/REFACTOR-INDEX.md
row 3, `html-3`): the third of the six staged extractions splitting
`arklight/backend/html/render.py`'s five unrelated jobs into their own
modules.

This module owns attribute rendering -- logic that runs once per node,
answering "given this node's props, what HTML attribute string does it
actually emit." It depends on `routing.py` (Stage 2) for the
route/asset-path resolution `_attr_string` delegates to for
`href`/`src`/`srcset`-shaped values, and on nothing from `head_meta.py`
or `page_render.py` (Stages 4-5) -- those depend on this module, not
the other way around, matching the target shape's stated dependency
direction.

Sequenced ahead of `htmx-1` (see `docs/Backends/REFACTOR-INDEX.md`)
deliberately: the HTMX attribute-emission rewrite
(`data-ark-on-click`/`data-ark-modifiers` -> `hx-on:click`/
`hx-trigger`) lands directly in this module once it starts, rather
than in the 460-line `render.py` a few commits before being moved out
from under it.

Zero behavior change: same attribute names, same resolution order,
same generated HTML byte-for-byte as before this module existed.
`render.py` re-exports `PASSTHROUGH_ATTRS`/`PROP_ALIASES`/
`BEHAVIOR_PROP_ATTRS`/`_style_dict_to_css`/`_attr_string` for backward
compatibility with anything that already imported them from there,
same as Stages 1-2.

`htmx-1` (see `docs/Backends/HTMX-INTEGRATION.md` "Stage 1 --
Behaviors" / `docs/Backends/REFACTOR-INDEX.md` row 4) landed here as
promised above: a plain string `on_click` (a named behavior --
`"toggle"`, `"scroll-to"`, `"copy"`, `"dismiss"`) now emits
`hx-on:click="arkRunBehavior('<name>', this)"` instead of
`data-ark-on-click="<name>"`, so HTMX's own attribute-processing pass
does the wiring that `arklight/backend/js/render.py`'s now-deleted
`wireBehaviors()` used to do by hand. `behavior_target`/`toggle_class`
are unchanged -- they still compile to `data-ark-target`/
`data-ark-toggle-class`, which the behavior fragments in
`arklight/backend/js/behaviors/` read off the clicked element exactly
as before; only *how the click gets wired* changed, not what a
behavior does once it runs. `on_click=Action.*(...)` (an `ActionRef`)
is untouched -- that still emits `data-ark-on-click="action:..."`,
matched-pair with `wireActions()`/`dispatch.py`, which is `htmx-3`
scope, not this stage's.
"""

from __future__ import annotations

import json
from html import escape

from arklight.ast.nodes import ActionRef, ClassBindSpec
from arklight.backend.html.routing import (
    ASSET_OR_ROUTE_AWARE_ATTRS,
    ROUTE_AWARE_ATTRS,
    SRCSET_ATTRS,
    _is_internal_route_ref,
    _resolve_route_ref,
    _resolve_src_ref,
    _resolve_srcset_ref,
)

# Prop names that map straight through to HTML attributes.
PASSTHROUGH_ATTRS = {
    "id", "class", "style", "href", "src", "alt", "title", "target", "name", "type",
    # v0.003: forms.
    "value", "placeholder", "required", "disabled", "checked", "readonly",
    "min", "max", "step", "pattern", "rows", "cols", "for", "multiple",
    "selected", "maxlength", "minlength", "autocomplete", "accept", "action",
    "method", "enctype", "novalidate", "label", "size", "autofocus", "form",
    # Stage 2 (docs/Backends/HTML-BACKEND-REFACTOR.md) discovery: `formaction`
    # was missing here entirely, so it always rendered as `data-formaction`
    # instead of a real HTML attribute, independent of the routing question
    # -- see routing.py's module docstring, "A separate, pre-existing bug".
    "formaction",
    # v0.003: tables.
    "colspan", "rowspan", "scope", "headers",
    # v0.003: media.
    "controls", "autoplay", "loop", "muted", "poster", "preload",
    # v0.003: <details>, <blockquote>/<q>, <time>.
    "open", "cite", "datetime", "download",
    # v0.003: accessibility (beyond the generic aria_* -> aria-* mapping
    # below, `role` is common enough to spell out explicitly).
    "role", "tabindex",
    # v0.003 (second addendum): lists (<ol>).
    "start", "reversed",
    # v0.003 (second addendum): responsive images (<picture><source>)
    # and native lazy-loading/decoding hints on <img>/<iframe>.
    "srcset", "sizes", "media", "loading", "decoding",
    # v0.003 (second addendum): native widgets (<meter>).
    "low", "high", "optimum",
    # v0.003 (second addendum): bidi text (<bdo>, and <bdi> where
    # explicit direction is needed) plus generic `dir` support.
    "dir",
    # v0.003 (second addendum): table column grouping (<col span>).
    "span",
    # v0.003 (second addendum): <track> (video/audio captions).
    "kind", "srclang", "default",
    # v0.003 (second addendum): image maps (<area>).
    "shape", "coords",
    # v0.003 (second addendum): <iframe> embeds.
    "allow", "allowfullscreen", "sandbox", "referrerpolicy",
}

# Props whose HTML attribute name differs from the prop's Python name
# (needed because `class` and `for` are Python keywords/awkward as kwargs).
PROP_ALIASES = {"class_name": "class", "for_": "for", "html_for": "for"}

# v0.003 behavior props (arklight.ir.schema.KNOWN_BEHAVIORS) -> the
# data-ark-* attribute the JS runtime actually reads. Kept separate
# from PROP_ALIASES/the generic data-* fallback so the attribute names
# are exact and documented in one place, matching what
# arklight/backend/js/render.py's RUNTIME_JS expects.
#
# `on_click` itself is deliberately absent as of `htmx-1`: a plain
# string `on_click` no longer maps through this generic dict at all --
# `_attr_string` below special-cases it (same way it already
# special-cased `on_click=Action.*(...)`/`ActionRef` before this
# stage) so it can emit the `hx-on:click="arkRunBehavior(...)"` shape
# HTMX needs instead of a bespoke `data-ark-on-click` attribute. The
# two props that describe what a behavior does once wired --
# `behavior_target`/`toggle_class` -- are unaffected and stay here.
BEHAVIOR_PROP_ATTRS = {
    "behavior_target": "data-ark-target",
    "toggle_class": "data-ark-toggle-class",
}


def _style_dict_to_css(style: dict) -> str:
    parts = []
    for prop, value in style.items():
        if value is None or value is False:
            continue
        css_prop = prop.replace("_", "-")
        parts.append(f"{css_prop}: {value}")
    return "; ".join(parts)


def _attr_string(
    props: dict,
    *,
    current_route: str,
    route_to_path: dict[str, str],
    page_state: dict | None = None,
    # `node_type` is no longer read here: its only use was
    # `_warn_unrouted_reference`'s message, removed by the
    # `UNROUTED_REFERENCE_ATTRS` fix (see routing.py's module
    # docstring). Kept as an accepted-but-unused kwarg rather than
    # removed, since `_render_node` already passes it and a future
    # attribute-shape warning is a plausible enough reason to want it
    # again that dropping and later re-adding the parameter isn't
    # worth the churn.
    node_type: str = "node",
) -> str:
    props = dict(props)  # local copy -- may splice the initial bound class in below

    bind_class = props.get("bind_class")
    if isinstance(bind_class, ClassBindSpec) and page_state is not None:
        # Stage 2 ("Reactive-core vdom staging"): pre-fill the class the
        # same way `_render_bind` pre-fills bound text, so the page
        # reflects its initial state correctly with JS disabled -- the
        # shipped runtime just keeps this in sync after that.
        if page_state.get(bind_class.state):
            existing = props.get("class_name")
            classes = existing.split() if isinstance(existing, str) and existing else []
            if bind_class.class_name not in classes:
                classes.append(bind_class.class_name)
            props["class_name"] = " ".join(classes)

    parts = []
    for key, value in props.items():
        if key == "level":
            continue  # handled specially for Heading
        if value is None or value is False:
            continue

        if key == "on_click" and isinstance(value, ActionRef):
            # v0.0035: Action.*(...) values carry their own attribute
            # shape (action name + target state + JSON args) instead of
            # the plain data-ark-on-click="<behavior name>" a string
            # on_click gets below.
            parts.append(f' data-ark-on-click="action:{escape(value.action, quote=True)}"')
            parts.append(f' data-ark-action-state="{escape(value.state, quote=True)}"')
            if value.args:
                parts.append(f' data-ark-action-args="{escape(json.dumps(value.args), quote=True)}"')
            if value.modifiers:
                # Stage 3 ("Reactive-core vdom staging"): comma-joined
                # modifier tokens, read by the JS runtime's
                # arkApplyModifiers -- see arklight/backend/js/render.py.
                modifiers_str = ",".join(value.modifiers)
                parts.append(f' data-ark-modifiers="{escape(modifiers_str, quote=True)}"')
            continue

        if key == "on_click" and isinstance(value, str):
            # htmx-1 (docs/Backends/HTMX-INTEGRATION.md "Stage 1 --
            # Behaviors"): a named behavior wires through HTMX's
            # `hx-on:click` instead of `data-ark-on-click` + the
            # now-deleted `wireBehaviors()` query/listener pass.
            # `arkRunBehavior` is exposed on `window` by
            # `arklight/backend/js/render.py`'s `_behaviors_block` --
            # HTMX evaluates this attribute's value as a function body
            # with `this` bound to the element that received the
            # event, so `this` here *is* the clicked element, the same
            # thing `wireBehaviors()` used to pass as `el`. The
            # behavior name is escaped, not validated here -- the
            # Validation stage (`arklight.ir.validate`) already
            # rejects anything not in `KNOWN_BEHAVIORS` before this
            # code runs.
            call = f"arkRunBehavior('{value}', this)"
            parts.append(f' hx-on:click="{escape(call, quote=True)}"')
            continue

        if key == "bind_class" and isinstance(value, ClassBindSpec):
            # Stage 2: the runtime reads these two to know which class
            # to toggle and which state key drives it -- the initial
            # value (if any) was already folded into `class_name` above.
            parts.append(f' data-ark-bind-class="{escape(value.class_name, quote=True)}"')
            parts.append(f' data-ark-bind-class-state="{escape(value.state, quote=True)}"')
            continue

        if key in BEHAVIOR_PROP_ATTRS:
            attr_name = BEHAVIOR_PROP_ATTRS[key]
        elif key.startswith("aria_"):
            # v0.003: generic accessibility convention -- `aria_label`,
            # `aria_hidden`, `aria_expanded`, etc. all map straight to
            # their real `aria-*` attribute without needing an entry
            # per attribute name (there are dozens in the ARIA spec).
            attr_name = "aria-" + key[len("aria_"):].replace("_", "-")
        else:
            attr_name = PROP_ALIASES.get(key, key)

            if attr_name == "style" and isinstance(value, dict):
                value = _style_dict_to_css(value)

            if attr_name in ROUTE_AWARE_ATTRS and isinstance(value, str) and _is_internal_route_ref(value):
                value = _resolve_route_ref(value, current_route=current_route, route_to_path=route_to_path)
            elif attr_name in ASSET_OR_ROUTE_AWARE_ATTRS and isinstance(value, str) and value:
                value = _resolve_src_ref(value, current_route=current_route, route_to_path=route_to_path)
            elif attr_name in SRCSET_ATTRS and isinstance(value, str) and value:
                # UNROUTED_REFERENCE_ATTRS fix (docs/Backends/HTML-BACKEND-REFACTOR.md
                # audit / docs/Backends/REFACTOR-INDEX.md row 1): `srcset`
                # packs multiple URLs into one value, so it gets its own
                # resolver rather than reusing _resolve_route_ref/_resolve_src_ref
                # directly -- see routing.py's module docstring.
                value = _resolve_srcset_ref(value, current_route=current_route, route_to_path=route_to_path)

            if attr_name not in PASSTHROUGH_ATTRS and not attr_name.startswith("data-"):
                # Unknown props are still emitted as data-* attributes rather
                # than silently dropped, so nothing a user writes disappears.
                attr_name = f"data-{attr_name}"

        if value is True:
            parts.append(f" {attr_name}")
        else:
            parts.append(f' {attr_name}="{escape(str(value), quote=True)}"')
    return "".join(parts)
