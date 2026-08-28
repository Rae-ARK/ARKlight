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

from arklight.backend.base import Backend
from arklight.backend.css.render import STYLESHEET_PATH
from arklight.backend.html.attrs import (
    BEHAVIOR_PROP_ATTRS,
    PASSTHROUGH_ATTRS,
    PROP_ALIASES,
    _attr_string,
    _style_dict_to_css,
)
from arklight.backend.html.head_meta import _render_head_meta
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

# HTML Backend refactor, Stage 3 (see
# docs/Backends/HTML-BACKEND-REFACTOR.md / docs/Backends/REFACTOR-INDEX.md
# row 3, `html-3`): PASSTHROUGH_ATTRS/PROP_ALIASES/BEHAVIOR_PROP_ATTRS/
# _style_dict_to_css/_attr_string moved to attrs.py -- imported above,
# re-exported here for the same backward-compatibility reason Stages
# 1-2 re-export their own moved names. Zero behavior change: same
# attribute names, same resolution order, same generated HTML
# byte-for-byte as before this stage.

# Tags that never have a closing tag / children.
# (VOID_TAGS itself now lives in tag_map.py -- see the Stage 1 note
# above; ROUTE_AWARE_ATTRS/ASSET_OR_ROUTE_AWARE_ATTRS/SRC_ATTRS/
# SRCSET_ATTRS now live in routing.py -- see the Stage 2 note above;
# PASSTHROUGH_ATTRS/PROP_ALIASES/BEHAVIOR_PROP_ATTRS/_style_dict_to_css/
# _attr_string now live in attrs.py -- see the Stage 3 note above; all
# three are imported at the top of this file.)


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


# HTML Backend refactor, Stage 4 (see
# docs/Backends/HTML-BACKEND-REFACTOR.md / docs/Backends/REFACTOR-INDEX.md
# row 7, `html-4`): `_render_head_meta` moved to head_meta.py -- imported
# above, re-exported here for the same backward-compatibility reason
# Stages 1-3 re-export their own moved names. Zero behavior change:
# same optional-prop reading, same tag order, same generated `<head>`
# HTML byte-for-byte as before this stage.


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
