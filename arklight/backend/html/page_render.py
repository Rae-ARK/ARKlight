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

Sequenced ahead of `htmx-4` (app-shell navigation) deliberately, per
`docs/Backends/REFACTOR-INDEX.md` row 8: `_render_page` is exactly
where the shell-persistent-region audit that stage calls for has to
look, so landing this extraction first meant that audit landed
directly in `page_render.py` rather than in `render.py` a few commits
before being moved out from under it -- the same reasoning `html-3`
already applied ahead of `htmx-1`.

At the point this module was split out, that was zero behavior
change: same recursion, same tag emission, same generated HTML
byte-for-byte as before it existed. `htmx-4` (docs/Backends/
REFACTOR-INDEX.md row 9) is the first stage to actually change what
`_render_page` emits -- see `_render_page`'s own docstring below for
what `app_shell=True` adds. Every existing caller that doesn't pass
`app_shell` gets the prior byte-for-byte output, unchanged.
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
    page: IRPage,
    site_name: str,
    route_to_path: dict[str, str],
    *,
    site_lang: str,
    app_shell: bool = False,
) -> str:
    """
    `app_shell` (htmx-4, docs/Backends/REFACTOR-INDEX.md row 9):
    `Site(app_shell=True)` -- defaults to `False`, unchanged output
    (same byte-for-byte HTML this function always produced). Set, two
    things change:

    1. `<body hx-boost="true">` -- htmx's own mechanism for turning
       same-origin link clicks into an in-place AJAX swap instead of a
       full document reload. See `arklight/backend/js/render.py` for
       the matching JS-side change (`needs_htmx` now also ships HTMX
       for a site with this flag set, even on a page with no
       behaviors or State(...) of its own).
    2. **The state marker moves.** Per htmx's own docs, `hx-boost`'s
       default swap replaces `<body>`'s *innerHTML* only -- never the
       `<body>` tag's own attributes. A `data-ark-state="..."`
       attribute placed directly on `<body>` (the non-app_shell
       branch below, unchanged) would therefore freeze at whatever
       page first loaded and never update across a boosted
       navigation, silently breaking every State(...) page's
       hydration the moment app-shell navigation reached it. Instead,
       for an app_shell page with state, the JSON blob is emitted as
       a hidden marker element (`<div id="ark-state" ...>`) that's
       part of `body_inner` -- and therefore *is* replaced, with the
       new page's own state, on every boosted swap. `initState()`
       (see `arklight/backend/js/runtime/state.py`) checks for this
       marker first and falls back to the `<body>` attribute, so it
       handles both shapes without needing to know `app_shell` was
       set.
    """
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
    body_attr_parts: list[str] = []
    state_marker = ""
    if page.state:
        state_json = escape(json.dumps(page.state), quote=True)
        if app_shell:
            state_marker = f'<div id="ark-state" data-ark-state="{state_json}" hidden></div>\n'
        else:
            body_attr_parts.append(f' data-ark-state="{state_json}"')
    if app_shell:
        body_attr_parts.append(' hx-boost="true"')
    body_attrs = "".join(body_attr_parts)
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
        f"<body{body_attrs}>\n{state_marker}{body_inner}\n"
        f'<script src="{escape(script_src, quote=True)}" defer></script>\n'
        "</body>\n"
        "</html>\n"
    )
