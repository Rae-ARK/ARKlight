"""
HTML Backend.

Converts Website IR into plain, dependency-free HTML files. This is the
only HTML-producing backend in ARKlight; it knows nothing about
ARKlight's Python API -- it only understands IRNode trees (type /
props / children), which is exactly the point of the Backend Interface.

Two things beyond basic tag rendering are handled here, both fixes for
real "it doesn't work when I actually open it" bugs:

1. **Internal links are rewritten to relative file paths.** A user
   writes `Link("About", href="/about")` -- a *route*, matching how
   `@site.page("/about")` registers it. If that were emitted verbatim
   as `href="/about"`, it would only work once the site is deployed at
   a domain root; opening the file directly (`file://.../index.html`)
   or serving it from a subdirectory would send the browser to
   `/about` on the local filesystem or wrong origin, not
   `dist/about.html`. So any href/src starting with "/" (and matching
   a known route) is rewritten to the correct relative path from the
   *current* page's output location. External URLs, `#fragments`,
   `mailto:`, and unrecognized paths are left untouched.

2. **A stylesheet link is always included**, pointing (relatively) at
   the CSS backend's output -- see `arklight.backend.css`.
"""

from __future__ import annotations

import posixpath
from html import escape

from arklight.backend.base import Backend
from arklight.backend.css.render import STYLESHEET_PATH
from arklight.ir.build import IRNode, IRPage, WebsiteIR

# Maps an IR node type to an HTML tag name.
TAG_MAP: dict[str, str] = {
    "Page": "body",  # Page's children become <body> content; see _render_page
    "Container": "div",
    "Heading": "h1",  # level overridden via `level` prop, see _tag_for
    "Text": "p",
    "Button": "button",
    "Link": "a",
    "Image": "img",
    "List": "ul",
    "Item": "li",
}

# Prop names that map straight through to HTML attributes.
PASSTHROUGH_ATTRS = {"id", "class", "style", "href", "src", "alt", "title", "target", "name", "type"}

# Props whose HTML attribute name differs from the prop's Python name
# (needed because `class` and `for` are Python keywords/reserved-ish
# and awkward as kwargs).
PROP_ALIASES = {"class_name": "class"}

# Attribute names whose value may be resolved relative to the current
# page ("/", "/about", ...) instead of emitted verbatim.
ROUTE_AWARE_ATTRS = {"href", "src"}

# Tags that never have a closing tag / children.
VOID_TAGS = {"img"}


def _style_dict_to_css(style: dict) -> str:
    parts = []
    for prop, value in style.items():
        if value is None or value is False:
            continue
        css_prop = prop.replace("_", "-")
        parts.append(f"{css_prop}: {value}")
    return "; ".join(parts)


def _output_path_for_route(route: str) -> str:
    """
    Maps a route to a static output file path.

    "/"          -> index.html
    "/about"     -> about.html
    "/blog/post" -> blog/post.html
    """
    trimmed = route.strip("/")
    if trimmed == "":
        return "index.html"
    return f"{trimmed}.html"


def _is_internal_route_ref(value: str) -> bool:
    """True for values that look like an ARKlight route (`/`, `/about`),
    as opposed to an external/absolute URL, protocol-relative URL,
    fragment, or mailto/tel link."""
    if not value.startswith("/"):
        return False
    if value.startswith("//"):
        return False  # protocol-relative external URL
    return True


def _resolve_route_ref(value: str, *, current_route: str, route_to_path: dict[str, str]) -> str:
    """Rewrite an internal route reference into a relative file path
    from the current page's output location. Unknown routes are left
    as-is (better a working absolute link than a silently broken one)."""
    route, _, fragment = value.partition("#")
    target_path = route_to_path.get(route)
    if target_path is None:
        return value  # not a known route -- leave untouched

    current_path = route_to_path[current_route]
    current_dir = posixpath.dirname(current_path) or "."
    relative = posixpath.relpath(target_path, current_dir)
    return f"{relative}#{fragment}" if fragment else relative


def _relative_asset_path(asset_path: str, *, current_route: str, route_to_path: dict[str, str]) -> str:
    """Like `_resolve_route_ref`, but for a fixed root-level asset
    (e.g. styles.css) rather than a page route."""
    current_path = route_to_path[current_route]
    current_dir = posixpath.dirname(current_path) or "."
    return posixpath.relpath(asset_path, current_dir)


def _attr_string(props: dict, *, current_route: str, route_to_path: dict[str, str]) -> str:
    parts = []
    for key, value in props.items():
        if key == "level":
            continue  # handled specially for Heading
        if value is None or value is False:
            continue

        attr_name = PROP_ALIASES.get(key, key)

        if attr_name == "style" and isinstance(value, dict):
            value = _style_dict_to_css(value)

        if attr_name in ROUTE_AWARE_ATTRS and isinstance(value, str) and _is_internal_route_ref(value):
            value = _resolve_route_ref(value, current_route=current_route, route_to_path=route_to_path)

        if attr_name not in PASSTHROUGH_ATTRS and not attr_name.startswith("data-"):
            # Unknown props are still emitted as data-* attributes rather
            # than silently dropped, so nothing a user writes disappears.
            attr_name = f"data-{attr_name}"

        if value is True:
            parts.append(f" {attr_name}")
        else:
            parts.append(f' {attr_name}="{escape(str(value), quote=True)}"')
    return "".join(parts)


def _tag_for(node: IRNode) -> str:
    if node.type == "Heading":
        level = node.props.get("level", 1)
        if not isinstance(level, int) or not (1 <= level <= 6):
            level = 1
        return f"h{level}"
    return TAG_MAP.get(node.type, "div")


def _render_children(children: list, *, current_route: str, route_to_path: dict[str, str]) -> str:
    rendered = []
    for child in children:
        if isinstance(child, IRNode):
            rendered.append(_render_node(child, current_route=current_route, route_to_path=route_to_path))
        else:
            rendered.append(escape(str(child)))
    return "".join(rendered)


def _render_node(node: IRNode, *, current_route: str, route_to_path: dict[str, str]) -> str:
    tag = _tag_for(node)
    attrs = _attr_string(node.props, current_route=current_route, route_to_path=route_to_path)

    if tag in VOID_TAGS:
        return f"<{tag}{attrs} />"

    inner = _render_children(node.children, current_route=current_route, route_to_path=route_to_path)
    return f"<{tag}{attrs}>{inner}</{tag}>"


def _render_page(page: IRPage, site_name: str, route_to_path: dict[str, str]) -> str:
    title = page.root.props.get("title", site_name)
    body_inner = _render_children(page.root.children, current_route=page.route, route_to_path=route_to_path)
    stylesheet_href = _relative_asset_path(
        STYLESHEET_PATH, current_route=page.route, route_to_path=route_to_path
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{escape(str(title))}</title>\n"
        f'  <link rel="stylesheet" href="{escape(stylesheet_href, quote=True)}">\n'
        "</head>\n"
        f"<body>\n{body_inner}\n</body>\n"
        "</html>\n"
    )


class HTMLBackend(Backend):
    name = "html"

    def render(self, ir: WebsiteIR) -> dict[str, str]:
        route_to_path = {page.route: _output_path_for_route(page.route) for page in ir.pages}
        output: dict[str, str] = {}
        for page in ir.pages:
            path = route_to_path[page.route]
            output[path] = _render_page(page, ir.site_name, route_to_path)
        return output
