"""
HTML Backend refactor, Stage 2 (see
docs/Backends/HTML-BACKEND-REFACTOR.md / docs/Backends/REFACTOR-INDEX.md
row 1, `html-2`): the second of the six staged extractions splitting
`arklight/backend/html/render.py`'s five unrelated jobs into their own
modules.

This module owns route/asset-path resolution -- logic that runs once
per link/asset reference a page contains, answering "what does this
`href`/`src`/`srcset`/`poster`/`action`/`formaction` value actually
resolve to from *this* page's output location." `attrs.py` (Stage 3)
will call into this module the same way `render.py` did before the
split; nothing here depends on attribute rendering, head metadata, or
page assembly.

## The `UNROUTED_REFERENCE_ATTRS` fix

This module also lands the reachability fix
`docs/Backends/HTML-BACKEND-REFACTOR.md`'s audit flagged as open:
`srcset` (Picture/PictureSource), `poster` (Video), and `action`/
`formaction` (Form and submit-capable Button/Input) previously fell
through to a build-time warning (`_warn_unrouted_reference`, now
removed) instead of being route-rewritten the way `href`/`src` already
are. Per that audit, each of the four is resolved the way its HTML
semantics actually call for, not uniformly:

- **`action`/`formaction`** name a *route* (a form submitting to
  another page in the same static site, or -- more commonly -- to
  something outside it entirely), the same relationship `href` has to
  its target. They're resolved with `_resolve_route_ref` via
  `ROUTE_AWARE_ATTRS`, exactly like `href`. The audit's own flagged
  sub-question -- whether these should warn-and-skip instead, since a
  form action is at least as likely to target an external API as an
  internal route -- is resolved by `_resolve_route_ref`'s existing
  safety net: it only rewrites a value that both looks internal
  (`_is_internal_route_ref`) *and* matches a route this site actually
  registers (`route_to_path`); an external API URL matches neither
  test and passes through untouched, so no separate warn-and-skip path
  is needed.
- **`poster`** names a *static image asset* (a video's poster frame),
  the same relationship `src` has to Image/Source/Track/IFrame. It's
  resolved with `_resolve_src_ref` via `ASSET_OR_ROUTE_AWARE_ATTRS`,
  exactly like `src` -- route-checked first (an IFrame-style embed),
  falling back to root-relative asset resolution.
- **`srcset`** packs one or more comma-separated `url descriptor`
  pairs into a single attribute value (e.g. `"wide.jpg 800w,
  narrow.jpg 400w"`), so it can't reuse `_resolve_src_ref` directly --
  each URL needs splitting out, resolving independently (same
  route-or-asset treatment `poster`/`src` get), and rejoining with its
  descriptor intact. See `_resolve_srcset_ref`.

`UNROUTED_REFERENCE_ATTRS` and `_warn_unrouted_reference` are removed
entirely, not deprecated -- once all four attributes they covered are
correctly resolved, there is nothing left for that warning to flag.

A separate, pre-existing bug surfaced while wiring `formaction`
through this fix: `formaction` was missing from `PASSTHROUGH_ATTRS`
(`attrs.py`, Stage 3 -- still `render.py` as of this stage), so it was
rendered as `data-formaction="..."` instead of a real `formaction`
attribute regardless of routing. Fixed alongside this module's
extraction since a route-rewritten `formaction` value is not
observable through a `data-formaction` fallback attribute; see
`render.py`'s `PASSTHROUGH_ATTRS` for the one-line fix.
"""

from __future__ import annotations

import posixpath

# Attribute names whose value may be resolved relative to the current
# page ("/", "/about", ...) instead of emitted verbatim. `href` (Link)
# always points at a page route. `action`/`formaction` (Form, and any
# submit-capable Button/Input) get the same treatment for the same
# reason -- see the module docstring's "UNROUTED_REFERENCE_ATTRS fix"
# section for why this is the right resolution for these two and not
# the asset-style one `poster`/`srcset` get below.
ROUTE_AWARE_ATTRS = {"href", "action", "formaction"}

# `src`-shaped attributes: usually a static asset ("assets/1.png" or
# "/assets/1.png"), but checked against known routes first so an
# IFrame-style embed of another ARKlight page still resolves like
# `href` would. `poster` (Video's poster-frame image) joins `src` here
# as part of the `UNROUTED_REFERENCE_ATTRS` fix -- a poster names an
# image asset, not a route, the same relationship `src` has to
# Image/Source/Track/IFrame.
ASSET_OR_ROUTE_AWARE_ATTRS = {"src", "poster"}

# `src` needs different treatment than `href`: a Link's `href` always
# names a *page route* ("/about"), but Image/Source/Track/IFrame's `src`
# usually names a *static asset* ("assets/1.png" or "/assets/1.png") --
# not a route at all. `_resolve_src_ref` below checks route_to_path
# first (so an IFrame embedding another ARKlight page still works like
# href) and otherwise falls back to root-relative asset resolution, the
# same treatment `styles.css`/`arklight.js`/`favicon`/`og_image` already
# get via `_relative_asset_path`. See CHANGELOG.md.
SRC_ATTRS = {"src"}

# `srcset` (Picture/PictureSource) packs multiple comma-separated
# `url descriptor` pairs into one value -- handled by its own resolver,
# `_resolve_srcset_ref`, since neither `_resolve_route_ref` nor
# `_resolve_src_ref` understands the multi-URL shape. Part of the
# `UNROUTED_REFERENCE_ATTRS` fix -- see the module docstring.
SRCSET_ATTRS = {"srcset"}


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
    as-is (better a working absolute link than a silently broken one) --
    this is also what makes rewriting `action`/`formaction` through
    this same function safe: a form action targeting an external API
    never matches a registered route, so it always falls into this
    "leave as-is" path. See the module docstring."""
    route, _, fragment = value.partition("#")
    target_path = route_to_path.get(route)
    if target_path is None:
        return value  # not a known route -- leave untouched

    current_path = route_to_path[current_route]
    current_dir = posixpath.dirname(current_path) or "."
    relative = posixpath.relpath(target_path, current_dir)
    return f"{relative}#{fragment}" if fragment else relative


def _resolve_src_ref(value: str, *, current_route: str, route_to_path: dict[str, str]) -> str:
    """Rewrite a `src`-shaped attribute value (Image, Source, Track,
    IFrame, and -- since the `UNROUTED_REFERENCE_ATTRS` fix -- Video's
    `poster`, and each individual URL inside a `srcset` via
    `_resolve_srcset_ref`) so it resolves correctly from the current
    page's output location.

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


def _resolve_srcset_ref(value: str, *, current_route: str, route_to_path: dict[str, str]) -> str:
    """Rewrite a `srcset` attribute value (PictureSource, and any future
    responsive-image use of the same attribute), part of the
    `UNROUTED_REFERENCE_ATTRS` fix -- see the module docstring.

    `srcset` packs one or more comma-separated `url descriptor` pairs
    into a single string, e.g. `"wide.jpg 800w, narrow.jpg 400w"` or
    `"wide.jpg 2x"` -- the descriptor (a width in `w` or a pixel
    density in `x`) is optional per entry. Each entry's URL is resolved
    independently via `_resolve_src_ref` (the same route-or-asset
    treatment `src`/`poster` get) and rejoined with its descriptor, if
    any, untouched. Empty entries from stray commas/whitespace are
    skipped rather than emitted as blank pairs.
    """
    entries = []
    for raw_entry in value.split(","):
        entry = raw_entry.strip()
        if not entry:
            continue
        # split(None, 1) (not partition(" ")) so any run of whitespace
        # between the URL and its descriptor is treated as a single
        # separator, matching how `_warn_unrouted_reference` used to
        # tokenize the same shape of value.
        tokens = entry.split(None, 1)
        url = tokens[0]
        descriptor = tokens[1] if len(tokens) > 1 else ""
        resolved_url = _resolve_src_ref(url, current_route=current_route, route_to_path=route_to_path)
        entries.append(f"{resolved_url} {descriptor}" if descriptor else resolved_url)
    return ", ".join(entries)


def _relative_asset_path(asset_path: str, *, current_route: str, route_to_path: dict[str, str]) -> str:
    """Like `_resolve_route_ref`, but for a fixed root-level asset
    (e.g. styles.css) rather than a page route."""
    current_path = route_to_path[current_route]
    current_dir = posixpath.dirname(current_path) or "."
    return posixpath.relpath(asset_path, current_dir)
