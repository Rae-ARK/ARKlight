"""
HTML Backend refactor, Stage 5 (see
docs/Backends/HTML-BACKEND-REFACTOR.md / docs/Backends/REFACTOR-INDEX.md
row 8, `html-5`): the fifth of the six staged extractions splitting
`arklight/backend/html/render.py`'s five unrelated jobs into their own
modules.

This module owns per-page composition -- logic that runs once per
page (`_render_page`) or recursively per node within it
(`_render_bind`/`_render_children`/`_render_node`), assembling a
complete HTML document out of the pieces the other four modules
provide: `tag_map.py` (Stage 1, tag names), `routing.py` (Stage 2,
route/asset-path resolution), `attrs.py` (Stage 3, attribute strings),
and `head_meta.py` (Stage 4, `<head>` tags). With this stage done,
`render.py` is left holding only `HTMLBackend`, whose `render()`
becomes a short composition of the sibling modules -- exactly the
target shape's stated end state.

Sequenced ahead of the not-yet-started `htmx-4` (app-shell navigation)
deliberately, per `docs/Backends/REFACTOR-INDEX.md` row 8: `_render_page`
is exactly where a shell-persistent-region audit has to look once that
stage starts, so landing this extraction first means that audit lands
directly in `page_render.py` rather than in `render.py` a few commits
before being moved out from under it -- the same reasoning `html-3`
already applied ahead of `htmx-1`.

Zero behavior change: same recursion, same tag emission, same
generated HTML byte-for-byte as before this module existed.
`render.py` re-exports `_render_bind`/`_render_children`/
`_render_node`/`_render_page` for backward compatibility with anything
that already imported them from there, same as Stages 1-4.
"""

from __future__ import annotations

import json
from html import escape

from arklight.backend.css.render import STYLESHEET_PATH
from arklight.backend.html.attrs import _attr_string
from arklight.backend.html.head_meta import _render_head_meta
from arklight.backend.html.routing import _relative_asset_path
from arklight.backend.html.tag_map import VOID_TAGS, _tag_for
from arklight.backend.js.render import SCRIPT_PATH
from arklight.ir.build import IRNode, IRPage


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
