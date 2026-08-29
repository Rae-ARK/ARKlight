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

5. **`.with_modifiers(...)` / `.debounce(...)` / `.throttle(...)` on an
   `ActionRef` render as an `hx-trigger="click debounce:300ms"`
   attribute** alongside the `data-ark-on-click` hooks above. At Stage
   3 ("Reactive-core vdom staging") this was a comma-joined
   `data-ark-modifiers` attribute instead; `htmx-2` (see
   `arklight.backend.html.attrs._modifiers_to_hx_trigger`) replaced it
   with HTMX's own trigger-modifier syntax. Omitted entirely for an
   `ActionRef` with no modifiers attached, or one carrying only
   `"prevent"` (which has no `hx-trigger` equivalent).

6. **htmx-4 (docs/Backends/REFACTOR-INDEX.md row 9): `Site(app_shell=
   True)` emits `hx-boost="true"` on `<body>`**, turning same-origin
   link clicks into an in-place AJAX swap instead of a full document
   reload -- see `page_render.py`'s `_render_page` docstring for the
   full reasoning, including why a state page's `data-ark-state` blob
   moves off `<body>` and into the swapped content when this is set.
   A node carrying `shell_persistent=True` (and, per Validation, a
   matching `id`) compiles to `hx-preserve="true"`, htmx's mechanism
   for keeping that element untouched across a boosted swap -- the
   fix for the "shell-persistent regions (nav/header) survive a
   boosted swap" half of the same design doc. Defaults to `False`;
   every existing site's output is unaffected.

## HTML Backend refactor -- module map

This file used to hold all five of the HTML backend's unrelated jobs
in one ~580-line module; `docs/Backends/HTML-BACKEND-REFACTOR.md`
splits them across sibling modules, staged one concern per commit:

- **Stage 1** -- `tag_map.py`: IR-node-type -> HTML-tag-name mapping
  (`TAG_MAP`, `VOID_TAGS`, `_tag_for`).
- **Stage 2** -- `routing.py`: route/asset-path resolution
  (`ROUTE_AWARE_ATTRS`, `_output_path_for_route`,
  `_is_internal_route_ref`, `_resolve_route_ref`, `_resolve_src_ref`,
  `_resolve_srcset_ref`, `_relative_asset_path`), including the
  `UNROUTED_REFERENCE_ATTRS` reachability fix.
- **Stage 3** -- `attrs.py`: attribute rendering (`PASSTHROUGH_ATTRS`,
  `PROP_ALIASES`, `BEHAVIOR_PROP_ATTRS`, `_style_dict_to_css`,
  `_attr_string`).
- **Stage 4** -- `head_meta.py`: per-page `<head>` metadata assembly
  (`_render_head_meta`).
- **Stage 5** -- `page_render.py`: per-page composition
  (`_render_bind`, `_render_children`, `_render_node`, `_render_page`).

With Stage 5 done, this file holds only `HTMLBackend`, whose
`render()` is a short composition of the sibling modules above --
the target shape's stated end state. Every name from Stages 1-5 is
still re-exported here (`from arklight.backend.html.render import ...`
keeps working for anything that imported them from their old
location), so this docstring is the map for "where does X actually
live now," not a list of what's still defined in this file.

**Stage 6** (confirming whether `README.md`'s "Compiler pipeline" HTML
Backend line still describes only external behavior) is a check
against the finished state of this split, not a code change, and is
not yet done.
"""

from __future__ import annotations

from arklight.backend.base import Backend
from arklight.backend.html.attrs import (
    BEHAVIOR_PROP_ATTRS,
    PASSTHROUGH_ATTRS,
    PROP_ALIASES,
    _attr_string,
    _style_dict_to_css,
)
from arklight.backend.html.head_meta import _render_head_meta
from arklight.backend.html.page_render import (
    _render_bind,
    _render_children,
    _render_node,
    _render_page,
)
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
from arklight.ir.build import WebsiteIR

# All of the re-exported names above (Stages 1-5) exist purely for
# backward compatibility with anything already doing
# `from arklight.backend.html.render import <name>` -- see the module
# docstring's "module map" section for where each one is actually
# defined and maintained now. Zero behavior change from any stage:
# same tag names, same route/asset resolution, same attribute
# strings, same <head> tags, same per-page composition, same
# generated HTML byte-for-byte as before this split started.


class HTMLBackend(Backend):
    name = "html"

    def render(self, ir: WebsiteIR) -> dict[str, str]:
        route_to_path = {page.route: _output_path_for_route(page.route) for page in ir.pages}
        output: dict[str, str] = {}
        for page in ir.pages:
            path = route_to_path[page.route]
            output[path] = _render_page(
                page, ir.site_name, route_to_path, site_lang=ir.lang, app_shell=ir.app_shell
            )
        return output
