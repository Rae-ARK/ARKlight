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
import posixpath
import warnings
from html import escape

from arklight.ast.nodes import ActionRef, ClassBindSpec
from arklight.backend.base import Backend
from arklight.backend.css.render import STYLESHEET_PATH
from arklight.backend.js.render import SCRIPT_PATH
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
    # v0.003: semantic layout.
    "Header": "header",
    "Footer": "footer",
    "Main": "main",
    "Nav": "nav",
    "Section": "section",
    "Article": "article",
    "Aside": "aside",
    "Figure": "figure",
    "FigCaption": "figcaption",
    "Details": "details",
    "Summary": "summary",
    # v0.003: text-level semantics.
    "Strong": "strong",
    "Em": "em",
    "Small": "small",
    "Mark": "mark",
    "Code": "code",
    "Cite": "cite",
    "Abbr": "abbr",
    "Sub": "sub",
    "Sup": "sup",
    "Span": "span",
    "Time": "time",
    "HorizontalRule": "hr",
    "LineBreak": "br",
    "Pre": "pre",
    "Blockquote": "blockquote",
    # v0.003: forms.
    "Form": "form",
    "Input": "input",
    "Textarea": "textarea",
    "Select": "select",
    "Option": "option",
    "OptGroup": "optgroup",
    "Label": "label",
    "FieldSet": "fieldset",
    "Legend": "legend",
    # v0.003: tables.
    "Table": "table",
    "TableHead": "thead",
    "TableBody": "tbody",
    "TableFoot": "tfoot",
    "TableRow": "tr",
    "TableHeaderCell": "th",
    "TableCell": "td",
    "Caption": "caption",
    # v0.003: media.
    "Video": "video",
    "Audio": "audio",
    "Source": "source",
    # v0.003 (second addendum): lists.
    "OrderedList": "ol",
    "DescriptionList": "dl",
    "DescriptionTerm": "dt",
    "DescriptionDetails": "dd",
    # v0.003 (second addendum): responsive images.
    "Picture": "picture",
    "PictureSource": "source",
    # v0.003 (second addendum): native widgets.
    "Progress": "progress",
    "Meter": "meter",
    "Datalist": "datalist",
    "Output": "output",
    # v0.003 (second addendum): dialog.
    "Dialog": "dialog",
    # v0.003 (second addendum): more text-level semantics.
    "Kbd": "kbd",
    "Samp": "samp",
    "Var": "var",
    "Data": "data",
    "Ins": "ins",
    "Del": "del",
    "Q": "q",
    "Dfn": "dfn",
    "Address": "address",
    "Wbr": "wbr",
    "Bdi": "bdi",
    "Bdo": "bdo",
    # v0.003 (second addendum): ruby annotations.
    "Ruby": "ruby",
    "Rt": "rt",
    "Rp": "rp",
    # v0.003 (second addendum): table extras.
    "ColGroup": "colgroup",
    "Col": "col",
    # v0.003 (second addendum): media.
    "Track": "track",
    # v0.003 (second addendum): image maps.
    "Map": "map",
    "Area": "area",
    # v0.003 (second addendum): embeds.
    "IFrame": "iframe",
    # v0.003 (second addendum): no-JS fallback.
    "NoScript": "noscript",
}

# Prop names that map straight through to HTML attributes.
PASSTHROUGH_ATTRS = {
    "id", "class", "style", "href", "src", "alt", "title", "target", "name", "type",
    # v0.003: forms.
    "value", "placeholder", "required", "disabled", "checked", "readonly",
    "min", "max", "step", "pattern", "rows", "cols", "for", "multiple",
    "selected", "maxlength", "minlength", "autocomplete", "accept", "action",
    "method", "enctype", "novalidate", "label", "size", "autofocus", "form",
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

# Attribute names whose value may be resolved relative to the current
# page ("/", "/about", ...) instead of emitted verbatim. `href` (Link)
# always points at a page route. `src` (Image/Source/Track/IFrame)
# usually points at a static asset instead -- see `_resolve_src_ref`.
ROUTE_AWARE_ATTRS = {"href"}
ASSET_OR_ROUTE_AWARE_ATTRS = {"src"}

# `src` needs different treatment than `href`: a Link's `href` always
# names a *page route* ("/about"), but Image/Source/Track/IFrame's `src`
# usually names a *static asset* ("assets/1.png" or "/assets/1.png") --
# not a route at all. `_resolve_src_ref` below checks route_to_path
# first (so an IFrame embedding another ARKlight page still works like
# href) and otherwise falls back to root-relative asset resolution, the
# same treatment `styles.css`/`arklight.js`/`favicon`/`og_image` already
# get via `_relative_asset_path`. See CHANGELOG.md.
SRC_ATTRS = {"src"}

# v0.0431 emergency patch: these attributes can *also* carry an internal
# route reference (Picture/PictureSource's `srcset`, Video's `poster`,
# Form's `action`/`formaction`) but are NOT in ROUTE_AWARE_ATTRS yet --
# route-rewriting for them is a known gap, tracked for a real fix in a
# later release (see CHANGELOG.md). Until then this set only drives a
# build-time warning so a site author finds out at build time, not by
# discovering a 404 after deploying outside the domain root.
UNROUTED_REFERENCE_ATTRS = {"srcset", "poster", "action", "formaction"}

# Tags that never have a closing tag / children.
VOID_TAGS = {
    "img", "hr", "br", "input", "source",
    # v0.003 (second addendum).
    "wbr", "col", "area", "track",
}


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


def _warn_unrouted_reference(attr_name: str, value: str, *, node_type: str) -> None:
    """v0.0431 emergency patch: `attr_name` is one of
    UNROUTED_REFERENCE_ATTRS and isn't route-rewritten today (see the
    comment on that set). If `value` looks like it was written the same
    way a `href`/`src` route reference would be, warn at build time
    instead of letting it silently 404 outside a domain-root deploy.

    `srcset` is a comma-separated list of `url descriptor` pairs, so
    each URL is checked individually; the other attrs here are a single
    value.
    """
    if attr_name == "srcset":
        candidates = [entry.strip().split()[0] for entry in value.split(",") if entry.strip()]
    else:
        candidates = [value]

    flagged = [c for c in candidates if _is_internal_route_ref(c)]
    if not flagged:
        return

    warnings.warn(
        f"[ARKlight ALPHA] {node_type!r} has {attr_name}={value!r}, which looks "
        f"like an internal route reference (e.g. {flagged[0]!r}), but "
        f"{attr_name!r} is not route-rewritten yet in this alpha build -- it "
        f"will be emitted as-is and may 404 if the site is deployed from a "
        f"subdirectory or opened via file://. This is a known limitation "
        f"under active maintenance; a fix is planned for the v0.0431 "
        f"emergency patch series. Until then, prefer a value that already "
        f"resolves correctly from wherever you deploy, or track the fix in "
        f"CHANGELOG.md.",
        stacklevel=2,
    )


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


def _resolve_src_ref(value: str, *, current_route: str, route_to_path: dict[str, str]) -> str:
    """Rewrite a `src` attribute value (Image, Source, Track, IFrame) so
    it resolves correctly from the current page's output location.

    Bugfix: unlike `href` (which always points at another ARKlight page
    route), `src` most commonly points at a *static asset* -- e.g.
    `assets/1.png` or `sprites/25.png`, copied verbatim into
    `<output_dir>/assets` by the build (see
    `compiler/pipeline.py::_copy_assets`) -- not a page route. Previously
    only `href`/`src` values matching a *known route* were rewritten, so
    an asset reference (not a route) was silently passed through
    unchanged and broke on any page not at the output root -- exactly
    the class of bug `_relative_asset_path` already exists to prevent
    for `styles.css`/`arklight.js`/`favicon`/`og_image`, just never
    applied here.

    So: if the value matches a *known* page route, treat it as one (an
    `IFrame` embedding another ARKlight page, say) and resolve it the
    same way `href` does. Otherwise, treat it as a root-relative static
    asset path and rewrite it with `_relative_asset_path`, stripping any
    leading "/" first -- passing a leading-slash value straight into
    `_relative_asset_path` would make the result depend on the build
    process's current working directory instead of the site structure,
    swapping one nondeterministic bug for another.

    External URLs (`https://...`), protocol-relative URLs (`//...`),
    and `data:` URIs are left untouched, same as `href`.
    """
    if value.startswith("//") or "://" in value:
        return value  # protocol-relative or scheme:// external URL
    if value.startswith("data:"):
        return value

    if _is_internal_route_ref(value) and value.partition("#")[0] in route_to_path:
        return _resolve_route_ref(value, current_route=current_route, route_to_path=route_to_path)

    asset_path = value.lstrip("/")
    return _relative_asset_path(asset_path, current_route=current_route, route_to_path=route_to_path)


def _relative_asset_path(asset_path: str, *, current_route: str, route_to_path: dict[str, str]) -> str:
    """Like `_resolve_route_ref`, but for a fixed root-level asset
    (e.g. styles.css) rather than a page route."""
    current_path = route_to_path[current_route]
    current_dir = posixpath.dirname(current_path) or "."
    return posixpath.relpath(asset_path, current_dir)


def _attr_string(
    props: dict,
    *,
    current_route: str,
    route_to_path: dict[str, str],
    page_state: dict | None = None,
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
            elif attr_name in UNROUTED_REFERENCE_ATTRS and isinstance(value, str):
                _warn_unrouted_reference(attr_name, value, node_type=node_type)

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
