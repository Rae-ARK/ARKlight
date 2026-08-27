"""
HTML Backend.

Converts Website IR into plain, dependency-free HTML files. This is the
only HTML-producing backend in ARKlight; it knows nothing about
ARKlight's Python API -- it only understands IRNode trees (type /
props / children), which is exactly the point of the Backend Interface.

Three things beyond basic tag rendering are handled here:

1. **Internal links are rewritten to relative file paths.** A user
   writes `Link("About", href="/about")` -- a *route*, matching how
   `@site.page("/about")` registers it. If that were emitted verbatim
   as `href="/about"`, it would only work once the site is deployed at
   a domain root; opening the file directly (`file://.../index.html`)
   or serving it from a subdirectory would send the browser to
   `/about` on the local filesystem or wrong origin, not
   `ARK/about.html`. So any `href` starting with "/" (and matching a
   known route) is rewritten to the correct relative path from the
   *current* page's output location. External URLs, `#fragments`,
   `mailto:`, and unrecognized paths are left untouched.

   `src` (Image/Source/Track/IFrame) gets the same route treatment
   *if* it matches a known route, but most `src` values are static
   assets rather than page routes -- e.g. `Image(src="sprites/25.png")`
   -- so any other `src` is instead rewritten as a root-relative asset
   path, the same way the built-in `styles.css`/`arklight.js`/favicon/
   `og_image` references already are. See `_resolve_src_ref`.

2. **A stylesheet link and behavior-runtime script are always
   included**, pointing (relatively) at the CSS/JS backends' output --
   see `arklight.backend.css` and `arklight.backend.js`.

3. **`on_click` / `behavior_target` / `toggle_class` props become
   `data-ark-*` attributes**, not real HTML attributes -- the JS
   runtime reads these to wire up behaviors. See
   `arklight.ir.schema.KNOWN_BEHAVIORS` for the full set and
   `arklight.backend.js` for what actually runs.

4. **v0.0035: `Bind(...)` and `Action.*(...)` render as `data-ark-*`
   hooks too.** A page's `state` (extracted from `State(...)` at the IR
   stage -- see `arklight.ir.build.IRPage.state`) is serialized as JSON
   onto `<body data-ark-state="...">`; a `Bind("count")` node renders
   as a `<span data-ark-bind="count">` pre-filled with that state's
   current value (so the page is fully readable with JS disabled, same
   as everything else ARKlight ships); and an `on_click=Action.*(...)`
   value renders as `data-ark-on-click="action:<name>"` plus
   `data-ark-action-state`/`data-ark-action-args`, which the JS
   backend's reactive core (only shipped for pages that declare state)
   reads to wire up the click.

5. **Stage 3 ("Reactive-core vdom staging"): `.with_modifiers(...)` /
   `.debounce(...)` / `.throttle(...)` on an `ActionRef` render as a
   `data-ark-modifiers="prevent,debounce:300"` attribute** alongside
   the `data-ark-on-click` hooks above -- comma-joined tokens, omitted
   entirely for an `ActionRef` with no modifiers attached.
"""

from __future__ import annotations

import json
from html import escape

from arklight.ast.nodes import ActionRef, ClassBindSpec
from arklight.backend.base import Backend
from arklight.backend.css.render import STYLESHEET_PATH
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
from arklight.backend.html.tag_map import TAG_MAP, VOID_TAGS, _tag_for
from arklight.backend.js.render import SCRIPT_PATH
from arklight.ir.build import IRNode, IRPage, WebsiteIR

# HTML Backend refactor, Stage 1 (see
# docs/Backends/HTML-BACKEND-REFACTOR.md): TAG_MAP/VOID_TAGS/_tag_for
# moved to tag_map.py -- imported above, re-exported here (`TAG_MAP`,
# `VOID_TAGS`, `_tag_for` are still valid `from
# arklight.backend.html.render import ...` names) so nothing importing
# them from their old location breaks. Zero behavior change.

# HTML Backend refactor, Stage 2 (see
# docs/Backends/HTML-BACKEND-REFACTOR.md / docs/Backends/REFACTOR-INDEX.md
# row 1, `html-2`): route/asset-path resolution moved to routing.py --
# imported above, re-exported here for the same backward-compatibility
# reason Stage 1 re-exports TAG_MAP/VOID_TAGS/_tag_for. This stage is
# NOT behavior-preserving in one respect, by design: it also lands the
# `UNROUTED_REFERENCE_ATTRS` fix (`srcset`/`poster`/`action`/
# `formaction` now route/asset-rewritten instead of only warned about)
# -- see routing.py's module docstring for the full reasoning per
# attribute. `UNROUTED_REFERENCE_ATTRS` and `_warn_unrouted_reference`
# are removed, not re-exported: once every attribute they covered is
# correctly resolved, nothing calls them and there is nothing left to
# warn about.

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
BEHAVIOR_PROP_ATTRS = {
    "on_click": "data-ark-on-click",
    "behavior_target": "data-ark-target",
    "toggle_class": "data-ark-toggle-class",
}

# Tags that never have a closing tag / children.
# (VOID_TAGS itself now lives in tag_map.py -- see the Stage 1 note
# above; ROUTE_AWARE_ATTRS/ASSET_OR_ROUTE_AWARE_ATTRS/SRC_ATTRS/
# SRCSET_ATTRS now live in routing.py -- see the Stage 2 note above;
# both imported at the top of this file.)


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


def _render_bind(node: IRNode, *, page_state: dict) -> str:
    """
    v0.0035: `Bind("count")` renders as a `<span data-ark-bind="count">`
    pre-filled with the page's current (build-time) state value, so the
    page is fully readable with JS disabled -- the shipped reactive
    core just keeps this element's text in sync with client-side state
    changes after that.
    """
    name = node.props.get("name")
    value = page_state.get(name, "")
    return f'<span data-ark-bind="{escape(str(name), quote=True)}">{escape(str(value))}</span>'


def _render_children(
    children: list, *, current_route: str, route_to_path: dict[str, str], page_state: dict
) -> str:
    rendered = []
    for child in children:
        if isinstance(child, IRNode):
            rendered.append(
                _render_node(
                    child, current_route=current_route, route_to_path=route_to_path, page_state=page_state
                )
            )
        else:
            rendered.append(escape(str(child)))
    return "".join(rendered)


def _render_node(node: IRNode, *, current_route: str, route_to_path: dict[str, str], page_state: dict) -> str:
    if node.type == "Bind":
        return _render_bind(node, page_state=page_state)

    tag = _tag_for(node)
    attrs = _attr_string(
        node.props,
        current_route=current_route,
        route_to_path=route_to_path,
        page_state=page_state,
        node_type=node.type,
    )

    if tag in VOID_TAGS:
        return f"<{tag}{attrs} />"

    inner = _render_children(
        node.children, current_route=current_route, route_to_path=route_to_path, page_state=page_state
    )
    return f"<{tag}{attrs}>{inner}</{tag}>"


def _render_head_meta(
    page: IRPage, title: str, *, current_route: str, route_to_path: dict[str, str]
) -> str:
    """
    Optional <head> tags beyond charset/viewport/title/stylesheet, all
    sourced the same way `title` already is: plain optional props read
    off the Page(...) node. None of these are in arklight.ir.schema.SCHEMA
    as required, so omitting them is always valid and existing sites are
    unaffected -- this only adds tags when a prop is actually supplied.

    Supported props (all optional):
      description  -- <meta name="description">
      favicon      -- root-relative asset path, resolved the same way
                       stylesheet_href/script_src already are
      og_title, og_description, og_image -- Open Graph tags, emitted
        only once `description` or any `og_*` prop is supplied (so a
        page that touches none of this renders exactly as before);
        og_title/og_description then fall back to title/description
      meta  -- v0.048 Stage A: dict[str, str] of name -> content pairs,
        each rendered as <meta name="..." content="...">. Structured,
        not a raw HTML string -- matches every other extension point
        in the project. Validated in arklight.ir.validate.
      links -- v0.048 Stage A: list[dict[str, str]] of attribute ->
        value pairs, each rendered as a single <link ...> tag (e.g.
        `{"rel": "preconnect", "href": "https://fonts.gstatic.com"}`)
        for webfonts/preconnect/extra icons beyond `favicon`. Emitted
        verbatim -- unlike `favicon`/`og_image`, these are not run
        through `_relative_asset_path`, since a `links` entry is at
        least as likely to point at an external origin (preconnect,
        webfonts) as a local asset.
    """
    description = page.root.props.get("description")
    favicon = page.root.props.get("favicon")

    # Open Graph is fully opt-in: only appears once at least one og_*
    # prop is explicitly supplied, so a page that never touches this
    # feature renders byte-for-byte identically to before this change.
    og_title = og_description = og_image = None
    og_opt_in_keys = ("description", "og_title", "og_description", "og_image")
    if any(page.root.props.get(key) is not None for key in og_opt_in_keys):
        og_title = page.root.props.get("og_title", title)
        og_description = page.root.props.get("og_description", description)
        og_image = page.root.props.get("og_image")

    tags: list[str] = []
    if description:
        tags.append(f'  <meta name="description" content="{escape(str(description), quote=True)}">\n')
    if favicon:
        favicon_href = _relative_asset_path(
            str(favicon), current_route=current_route, route_to_path=route_to_path
        )
        tags.append(f'  <link rel="icon" href="{escape(favicon_href, quote=True)}">\n')
    if og_title:
        tags.append(f'  <meta property="og:title" content="{escape(str(og_title), quote=True)}">\n')
    if og_description:
        tags.append(
            f'  <meta property="og:description" content="{escape(str(og_description), quote=True)}">\n'
        )
    if og_image:
        og_image_href = _relative_asset_path(
            str(og_image), current_route=current_route, route_to_path=route_to_path
        )
        tags.append(f'  <meta property="og:image" content="{escape(og_image_href, quote=True)}">\n')

    # v0.048 Stage A: structured <head> extension points -- see the
    # docstring above. Both are fully opt-in and additive, same as
    # favicon/og_* above: a page that sets neither renders unchanged.
    extra_meta = page.root.props.get("meta")
    if extra_meta:
        for name, content in extra_meta.items():
            tags.append(
                f'  <meta name="{escape(str(name), quote=True)}" '
                f'content="{escape(str(content), quote=True)}">\n'
            )
    extra_links = page.root.props.get("links")
    if extra_links:
        for link in extra_links:
            attrs_html = "".join(
                f' {escape(str(attr), quote=True)}="{escape(str(value), quote=True)}"'
                for attr, value in link.items()
            )
            tags.append(f"  <link{attrs_html}>\n")
    return "".join(tags)


def _render_page(
    page: IRPage, site_name: str, route_to_path: dict[str, str], *, site_lang: str
) -> str:
    title = page.root.props.get("title", site_name)
    lang = page.root.props.get("lang", site_lang)
    body_inner = _render_children(
        page.root.children, current_route=page.route, route_to_path=route_to_path, page_state=page.state
    )
    stylesheet_href = _relative_asset_path(
        STYLESHEET_PATH, current_route=page.route, route_to_path=route_to_path
    )
    script_src = _relative_asset_path(SCRIPT_PATH, current_route=page.route, route_to_path=route_to_path)
    head_meta = _render_head_meta(page, title, current_route=page.route, route_to_path=route_to_path)
    # v0.0035: pages that declare State(...) hydrate the client-side
    # store from here -- a JSON blob of the same initial values the
    # page was rendered with, so client and server never disagree.
    body_attrs = ""
    if page.state:
        body_attrs = f' data-ark-state="{escape(json.dumps(page.state), quote=True)}"'
    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{escape(str(lang), quote=True)}">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{escape(str(title))}</title>\n"
        f'  <link rel="stylesheet" href="{escape(stylesheet_href, quote=True)}">\n'
        f"{head_meta}"
        "</head>\n"
        f"<body{body_attrs}>\n{body_inner}\n"
        f'<script src="{escape(script_src, quote=True)}" defer></script>\n'
        "</body>\n"
        "</html>\n"
    )


class HTMLBackend(Backend):
    name = "html"

    def render(self, ir: WebsiteIR) -> dict[str, str]:
        route_to_path = {page.route: _output_path_for_route(page.route) for page in ir.pages}
        output: dict[str, str] = {}
        for page in ir.pages:
            path = route_to_path[page.route]
            output[path] = _render_page(page, ir.site_name, route_to_path, site_lang=ir.lang)
        return output
