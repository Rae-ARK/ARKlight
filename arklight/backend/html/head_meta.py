"""
HTML Backend refactor, Stage 4 (see
docs/Backends/HTML-BACKEND-REFACTOR.md / docs/Backends/REFACTOR-INDEX.md
row 7, `html-4`): the fourth of the six staged extractions splitting
`arklight/backend/html/render.py`'s five unrelated jobs into their own
modules.

This module owns per-page `<head>` metadata assembly -- logic that
runs once per page, answering "given this page's optional props
(`description`/`favicon`/`og_*`/`meta`/`links`), what extra `<head>`
tags does it need beyond the charset/viewport/title/stylesheet lines
`page_render.py` (Stage 5) always emits." It depends on `routing.py`
(Stage 2) for `_relative_asset_path` (used to resolve `favicon`/
`og_image` the same way `page_render.py` resolves the stylesheet/
script paths), and on nothing from `attrs.py` (Stage 3) or
`page_render.py` (Stage 5) -- both of those import from here, not the
other way around, matching the target shape's stated dependency
direction ("What does the HTML backend do" should be answerable from
`render.py`'s imports without a module depending on something that
hasn't been split out yet).

Independent of the `htmx-*` track per `docs/Backends/REFACTOR-INDEX.md`
row 7's own note: this stage has no shared surface with behavior/
modifier/action attribute emission, so it can land in any order
relative to rows 4-6 -- it's listed in file order here, not because it
gates or is gated by the HTMX rewrite.

Zero behavior change: same optional-prop reading, same tag order, same
generated `<head>` HTML byte-for-byte as before this module existed.
`render.py` re-exports `_render_head_meta` for backward compatibility
with anything that already imported it from there, same as Stages 1-3.
"""

from __future__ import annotations

from html import escape

from arklight.backend.html.routing import _relative_asset_path
from arklight.ir.build import IRPage


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
