# HTML Backend Refactor: Service-Oriented, Staged

Status: **Design only -- not started.** This file exists because two
other docs already pointed here before it existed:
`CHANGELOG.md`'s `[0.0431]` entry and `PROGRESS.md`'s "v0.0431 --
Emergency patch" section both say their remaining findings (`<html
lang="en">` hardcoded, `--ark-max-width` unreachable, untyped
`--ark-*` custom properties) were "tracked against the CSS/HTML
backend refactor in `docs/DESIGN-NOTES.md`" -- but no such section was
ever written there. The CSS half of that promise got its own doc,
`docs/CSS-BACKEND-REFACTOR.md`, and shipped. This is the HTML half,
written before implementation starts rather than after, so the
module split doesn't bake in today's audit gaps the way skipping this
step would.

Of the three findings that sent readers here: `<html lang="en">` is
now fixed (`Site(lang=...)`/`Page(lang=...)`/`arklight build --lang`,
see `CHANGELOG.md`'s `[0.0434]` entry) and `--ark-max-width` was fixed
earlier by the CSS refactor (`docs/CONTAINER-WIDTH-BUG.md`). Untyped
`--ark-*` custom properties is a CSS-backend-scoped question, out of
this doc's `arklight/backend/html/` scope. What sent the *original*
external audit to the HTML backend in the first place --
`UNROUTED_REFERENCE_ATTRS` (`srcset`/`poster`/`action`/`formaction`
not route-rewritten the way `href`/`src` are) -- is still open; see
the audit below. Note: there is also a separate HTMX proposal, since 
it was massive. it got it's own document refer, `docs/HTMX-INTEGRATION.md`.

Scope: **`arklight/backend/html/` only.** No other backend, pipeline
stage, or public API changes as part of this work.

## Why

`arklight/backend/html/render.py` has grown to ~580 lines doing five
unrelated jobs -- the same shape `arklight/backend/css/render.py` was
in before `docs/CSS-BACKEND-REFACTOR.md`'s split, just with more
surface area:

1. Static tag/attribute maps (data, never changes at runtime) --
   `TAG_MAP`, `VOID_TAGS`, `PASSTHROUGH_ATTRS`, `PROP_ALIASES`,
   `BEHAVIOR_PROP_ATTRS`, `ROUTE_AWARE_ATTRS`,
   `UNROUTED_REFERENCE_ATTRS`.
2. Route/asset-path resolution (logic, runs per link/asset reference)
   -- `_output_path_for_route`, `_is_internal_route_ref`,
   `_resolve_route_ref`, `_relative_asset_path`,
   `_warn_unrouted_reference`.
3. Attribute rendering (logic, runs per node) --
   `_style_dict_to_css`, `_attr_string`, `_tag_for`.
4. Per-page assembly -- head metadata, state hydration, body
   composition (logic, runs per page) -- `_render_head_meta`,
   `_render_bind`, `_render_children`, `_render_node`, `_render_page`.
5. `Backend` interface orchestration -- `HTMLBackend.render`.

Mixing these means the same blast-radius problem the CSS refactor
named: editing how `srcset` route-rewriting works risks the same file
as editing head-meta tags, and there's no single place a future
contributor (human or AI) can look to answer "where does X live"
without reading the whole file top to bottom.

## Reachability audit (`docs/CONFIGURABILITY.md`) before any split

Doing this audit *before* drawing module boundaries matters -- a split
organized around today's constants would silently carry today's gaps
forward as if they were settled. Running every constant/function above
through `docs/CONFIGURABILITY.md`'s rule:

- **Genuine unreachable-value bug, still open:**
  `UNROUTED_REFERENCE_ATTRS` (`srcset` on `Picture`/`PictureSource`,
  `poster` on `Video`, `action`/`formaction` on `Form`). Property 1
  holds -- a site plausibly wants these route-rewritten exactly like
  `href`/`src` are, for the same reason (a route-shaped value 404s
  once the site isn't served from a domain root). Property 2 holds --
  nothing rewrites them today; the v0.0431 patch added a build-time
  warning (`_warn_unrouted_reference`) that flags the gap but doesn't
  close it. Both properties holding makes this the same bug class as
  `--ark-max-width` was, not a nice-to-have -- it belongs in this
  refactor's `routing.py` (see below), extending `ROUTE_AWARE_ATTRS`-
  style rewriting to these four. Two real sub-decisions, not yet made:
  `srcset` needs its comma-separated `url descriptor` pairs split and
  rejoined per-URL rather than rewritten as one string; and whether
  `action`/`formaction` should warn-and-skip instead of rewrite, since
  a form action is at least as likely to target an external API as an
  internal route (flagged already in `PROGRESS.md`, unresolved there
  too).
- **Correctly internal, no kwarg needed, ever:** `TAG_MAP`,
  `VOID_TAGS`, `PASSTHROUGH_ATTRS`, `PROP_ALIASES`,
  `BEHAVIOR_PROP_ATTRS`. These are `docs/CONFIGURABILITY.md`'s
  "structural compiler plumbing" and "attribute/prop naming maps"
  categories almost by the book -- none of them is a value a site
  would tune, they're the definition of what a node *is*. The
  `data-*` fallback at the end of `_attr_string` is the actual escape
  hatch for "I want some other attribute passed through," and it
  already works -- no per-attribute kwarg is missing here.
- **Open question, not a decided gap:** whether
  `_output_path_for_route`'s route -> file-path mapping (`/about` ->
  `about.html`, nested routes -> `blog/post.html`) should ever be
  overridable -- e.g. a `.htm` extension, or extensionless output for
  static hosts that prefer it. No concrete site need has surfaced yet
  (property 1 unconfirmed), so this stays internal until one does --
  noted here so whoever picks this up doesn't have to rediscover the
  question, not because it's already been answered.

## Target shape

Each concern becomes its own module under `arklight/backend/html/`,
mirroring the CSS refactor's "modules, not classes-for-everything"
choice for the same reason: every piece here is a pure function of its
inputs, so a `FooService` class wrapper would add ceremony with no
behavioral benefit. HTML's surface area splits into more modules than
CSS's did, mainly because HTML additionally has a per-node routing
concern (rewriting `href`/`src`) that CSS never had:

| Module | Responsibility | Kind |
|---|---|---|
| `tag_map.py` | `TAG_MAP`, `VOID_TAGS`, `_tag_for(node)` | Data + tiny pure fn |
| `routing.py` | `ROUTE_AWARE_ATTRS`, `UNROUTED_REFERENCE_ATTRS`, `_output_path_for_route`, `_is_internal_route_ref`, `_resolve_route_ref`, `_relative_asset_path`, `_warn_unrouted_reference` | Data + pure functions |
| `attrs.py` | `PASSTHROUGH_ATTRS`, `PROP_ALIASES`, `BEHAVIOR_PROP_ATTRS`, `_style_dict_to_css`, `_attr_string` | Data + pure function |
| `head_meta.py` | `_render_head_meta` | Pure function |
| `page_render.py` | `_render_bind`, `_render_children`, `_render_node`, `_render_page` | Pure functions (per-page composition) |
| `render.py` | `HTMLBackend.render` composes the above into `{path: contents}`; satisfies the `Backend` interface | Orchestration only |

Why this makes future work easier -- same reasoning the CSS refactor's
doc gives, holding equally here:

- **Change isolation.** Fixing the `UNROUTED_REFERENCE_ATTRS` gap above
  touches only `routing.py`. Adding a new semantic tag touches only
  `tag_map.py`. Neither risks the other.
- **Independent testability.** Each module becomes unit-testable
  against its own inputs/outputs without going through
  `HTMLBackend.render` or a full IR build, once
  `tests/test_html_backend.py` is split alongside the modules.
- **Obvious extension points.** The `@media`/`<head>` work already
  planned for v0.048 (`docs/DESIGN-NOTES.md`) gets a natural home in
  `head_meta.py` instead of growing `_render_page` further.
- **Cheap to read.** "What does the HTML backend do" becomes answerable
  from `render.py`'s imports, not a 580-line scroll.
- **No new runtime cost or dependency.** Pure reorganization -- same
  functions, same call graph, same generated HTML byte-for-byte at
  every stage that isn't explicitly labeled as also landing the
  `routing.py` fix.

## Staging

Each stage is a self-contained, behavior-preserving commit.
`tests/test_html_backend.py` (whole suite as a sanity check) passes
unchanged after every stage -- if it doesn't, that stage isn't done.
The one exception is called out below: the stage that also lands the
`UNROUTED_REFERENCE_ATTRS` fix necessarily changes behavior for the
four newly-rewritten attributes, and should update/extend the tests
that cover them rather than leave them "unchanged."

- [x] **Stage 1** -- Extract `TAG_MAP`/`VOID_TAGS`/`_tag_for` into
  `tag_map.py` (data + one tiny pure fn, zero behavior change).
  `render.py` imports them. DONE -- `render.py` re-exports all three
  names for backward compatibility; `tests/test_html_tag_map.py` adds
  independent unit coverage alongside the existing
  `tests/test_html_backend.py` end-to-end suite, which passes
  unchanged (byte-for-byte identical generated HTML).
- [x] **Stage 2** -- Extract routing/asset-path resolution into
  `routing.py`. Land the `UNROUTED_REFERENCE_ATTRS` reachability fix
  from the audit above here, or as its own immediately-following
  commit if the fix needs more design time than the pure move --
  either is fine, but don't block the move on the fix finishing, and
  don't ship the fix silently disguised as "just a move" either. DONE
  -- `render.py` re-exports the moved names for backward
  compatibility, same as Stage 1. The fix landed in the same commit as
  the move: `srcset`/`poster` now resolve like `src`
  (route-checked-first, asset-fallback) and `action`/`formaction` now
  resolve like `href`, via a new `_resolve_srcset_ref` for `srcset`'s
  multi-URL shape; `UNROUTED_REFERENCE_ATTRS`/`_warn_unrouted_reference`
  removed entirely (see `routing.py`'s module docstring for the
  per-attribute reasoning, including the pre-existing `formaction` ->
  `data-formaction` bug fixed alongside it).
  `tests/test_html_routing.py` adds independent unit coverage
  (`tag_map.py`'s Stage 1 pattern); `tests/test_html_backend.py`'s
  existing suite passes unchanged except for the four newly-rewritten
  attributes' tests, extended per this doc's own exception above.
- [ ] **Stage 3** -- Extract `PASSTHROUGH_ATTRS`/`PROP_ALIASES`/
  `BEHAVIOR_PROP_ATTRS`/`_style_dict_to_css`/`_attr_string` into
  `attrs.py`.
- [ ] **Stage 4** -- Extract `_render_head_meta` into `head_meta.py`.
- [ ] **Stage 5** -- Extract `_render_bind`/`_render_children`/
  `_render_node`/`_render_page` into `page_render.py`. `render.py`
  left holding only `HTMLBackend`, whose `render()` becomes a short
  composition of the sibling modules.
- [ ] **Stage 6** -- Confirm (don't assume) whether `README.md`'s
  "Compiler pipeline" HTML Backend line still describes only external
  behavior -- it does today, so this is likely a no-op, same as the
  CSS refactor's equivalent check.

## Status

**Stage 1 IMPLEMENTED** (`tag_map.py`; see CHANGELOG.md). **Stage 2
IMPLEMENTED** (`routing.py`, including the `UNROUTED_REFERENCE_ATTRS`
fix; see CHANGELOG.md). Stages 3-6 not started. `docs/CONFIGURABILITY.md`
and this design doc exist so that when the rest of this work starts,
the module boundaries are decided in advance rather than worked out
mid-refactor.
