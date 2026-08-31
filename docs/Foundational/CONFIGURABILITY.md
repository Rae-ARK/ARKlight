# Configurability: the reachability rule

**Not to be confused with `arklight.config.py`** -- the optional
project-level settings file (`live-streaming` host/port today, more
sections planned), documented in the main
[`README.md`](../../README.md#configuration-arklightconfigpy) and
implemented in `arklight/config.py`. This doc is about a different
kind of configurability: which fixed values inside the compiler
*should* grow into a `Site(...)`/`Page(...)` kwarg (or CLI flag) with
a default, and which should stay an internal constant.

ARKlight's internals hold a lot of fixed values -- default colors,
spacing, tag maps, attribute allow-lists, an iteration count. A few of
these have grown a real override path (a `Site(...)`/`Page(...)` kwarg,
or an `arklight build --flag`, always defaulting to today's behavior);
most haven't, and shouldn't. This doc names the rule that already
governs which is which -- used ad hoc in `arklight/api.py`'s and
`arklight/backend/css/design_tokens.py`'s own comments ("reachability
rule", "unreachable-value bug class") and worked out the hard way
across three real bugs (`docs/CONTAINER-WIDTH-BUG.md`) -- so future
work applies it up front instead of re-deriving it per change. The
first deliberate application of it is the planned HTML backend
refactor, `docs/HTML-BACKEND-REFACTOR.md`.

## The rule

Something becomes a user-defined value with a default -- not a bare
internal constant -- when **both** hold:

1. **A real site could plausibly want a different value.** Not "some
   site, somewhere, in theory" -- a concrete, expected reason (a
   site's brand color, a non-English audience, a wider layout).
   Compiler wiring that only ARKlight itself has any stake in --how a
   route resolves to a file path, which HTML tag a `Heading` becomes,
   how a `dict` value gets escaped into an attribute-- never qualifies,
   no matter how mechanically easy it would be to expose.
2. **Nothing today already reaches it.** If a value is already
   reachable through an existing, generic escape hatch -- `style=` on
   a wrapper, `class_name=` plus `Site.style(...)`, the `data-*`
   passthrough -- a bespoke kwarg on top is redundant API surface for
   something that already works. Case in point: `--ark-grid-min` and
   the other layout-primitive tokens in `design_tokens.py` were always
   reachable per-instance via `style="--ark-grid-min: 20rem"`; the
   sitewide `Site(grid_min=...)` kwarg they eventually got was closing
   a *convenience* gap, not fixing brokenness -- optional, and
   correctly lower priority than a real reachability bug.

If only (1) holds -- a site might plausibly want it different, but an
existing mechanism already reaches it -- leave it internal-only and
point people at the escape hatch that already works, rather than
adding a parallel one. If only (2) holds -- genuinely unreachable, but
nothing about the value is site-specific, it's pure compiler plumbing
-- also leave it internal; unreachability is only a defect when the
thing being unreachable is something a site should be able to reach in
the first place.

Only when **both** hold is a hardcoded value doing real, avoidable
harm -- that's the "unreachable-value bug class" `CONTAINER-WIDTH-BUG.md`
names: `--ark-max-width` at a fixed `720px` had both properties (real
sites want wider layouts; nothing -- not `style=`, not `class_name=`,
not any prop -- reached it, because `body` read it directly at the top
of the cascade, before any site-authored descendant exists). That's
what made it a bug rather than a missing nice-to-have, and why fixing
it (alongside `--ark-bg`, the same problem for the same structural
reason) shipped ahead of the layout-primitive convenience kwargs.

## What "expose it" looks like

Every override path added under this rule follows the same shape, so
a reader learns it once and recognizes it everywhere:

- **A new optional kwarg, always defaulting to today's behavior** --
  `= None` for most (`Site(max_width: str | None = None)`), or an
  explicit today's-default where the param is naturally string-typed
  rather than optional (`Site(lang: str = "en")`). Never a required
  param -- every existing call site keeps working, unchanged output,
  with zero edits.
- **Threaded through exactly one path** to the one place that actually
  reads it -- e.g. `Site.__init__` -> `WebsiteIR` -> the one backend
  consuming it. No parallel copies of the same value living in two
  places that could drift.
- **A matching CLI flag on `arklight build`, forwarded the same way --
  but only when the value is something a one-off build invocation
  (CI producing a variant, a staging build) would plausibly want to
  flip without editing the site file.** Not automatic for every new
  kwarg. `--max-width`/`--bg`/`--font-family`/`--lang`/`--button-text`
  all qualify -- each is a single design/content token a build script
  might reasonably override per-invocation. A hypothetical
  `Site(custom_404=...)` would not automatically need a CLI twin --
  that's page content authored once, not a per-build variant.
- **Verified behavior-preserving for every existing call site.** An
  unconfigured site's build output must be byte-for-byte identical to
  before the kwarg existed. If the new default differs from historical
  output even slightly, that's a breaking change being introduced
  alongside an option, not a pure addition -- and needs to be called
  out as one, not folded silently into "added an override."

## What stays internal, on purpose

Not exposing something is a decision, not an oversight. These
categories stay a plain module-level constant or private function,
with no kwarg, regardless of how a request for "make this
configurable" is phrased:

- **Structural compiler plumbing.** `TAG_MAP`, `VOID_TAGS`,
  `_output_path_for_route` -- nothing about *how* a `Heading` becomes
  `<h1>`-`<h6>`, or a route becomes a file path, is a per-site
  decision. ARKlight's whole pitch is that this part is handled, not
  configured.
- **Safety-critical, deliberately fixed behavior.** HTML-escaping
  (`html.escape`), the closed `KNOWN_BEHAVIORS`/`Action.*` vocabulary,
  the choice of PBKDF2 itself as the KDF (only its iteration count --
  a tunable strength knob, not a mechanism choice -- is exposed; see
  `ARKSEAL2` in `arklight/packer/seal.py`). Making any of these
  user-overridable would reopen exactly the injection/arbitrary-code
  surface ARKlight's non-goals rule out.
- **Attribute/prop naming maps.** `PASSTHROUGH_ATTRS`, `PROP_ALIASES`,
  `BEHAVIOR_PROP_ATTRS` -- these define the *shape* of the public API
  (which kwarg maps to which HTML attribute), not a value within it. A
  site author who wants some other HTML attribute passed through
  already gets one, automatically, via the `data-*` fallback at the
  end of `_attr_string` -- that generic mechanism is the intentional
  escape hatch here, not a reason to keep special-casing individual
  attribute names one at a time.
- **Anything a generic escape hatch already reaches.** `style=`,
  `class_name=` plus `Site.style(...)`, `data-*`. A bespoke kwarg on
  top of one of these is optional convenience (fine to ship, per the
  layout-primitive-tokens precedent above), never a bug fix -- and
  shouldn't be described or prioritized as one.

## A smell to watch for

The pattern behind all three real bugs this rule was extracted from
(`--ark-max-width`, `--ark-bg`, `<html lang="en">`) looked the same in
source every time: a literal baked directly into an f-string or a
fixed dict value, with *no* comment explaining why it's fixed there.
If you're touching code with a bare literal like that and can't
immediately answer "why doesn't this already go through
`css_var_overrides` / a prop / a kwarg" -- that's the signal to run
this rule, not to assume someone already ran it. Contrast with
`TAG_MAP`'s entries, which also look like bare literals but where the
answer is immediate and satisfying: "this is what the tag *is*, not a
style choice."

## Applying this

`docs/HTML-BACKEND-REFACTOR.md` is the first place this rule gets run
deliberately against a whole file, before any module split happens --
worth reading alongside this doc rather than as a separate exercise.
