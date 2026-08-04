# The container-width bug: `--ark-max-width` was unreachable, now it isn't

Status: **Fixed.** This file exists because `arklight/api.py`'s own
`Site.__init__` comment already pointed here before this file did --
the fix landed in the CSS backend refactor without a matching doc,
leaving a dangling reference in ARKlight's own source. This is that
doc, written after the fact from the compiler's side; a downstream
site (`arklight-vs-frontend`) independently diagnosed the same bug
from the outside and has its own, symptom-first writeup at
`docs/CONTAINER-WIDTH-BUG.md` in that repo -- the two documents cover
the same root cause from opposite ends (site author hitting the
symptom vs. compiler source explaining the fix) and are both worth
reading.

## The symptom

Every site ARKlight built, on any desktop viewport, rendered as a
narrow column (720px) with permanently empty margins on either side,
regardless of viewport width -- not a broken render, but a hard cap
that wasted most of a wide screen with no way for a site author to
change it.

## Root cause

`--ark-max-width` was a hardcoded `720px` baked directly into the old
monolithic `arklight/backend/css/render.py`'s `BASE_CSS` string
constant, with no public API path to override it:

- `Page(...)` props never reached `<body>` -- only `title`/
  `description`/`favicon`/`og_*` did.
- `Site.style(name, rules)` only ever emitted `.name { ... }` class
  selectors -- no way to target `:root` or `body` through it.
- Even a `--ark-*` override on a wrapper `<div>` inside `body` couldn't
  reach this specific variable, because `body` resolves its own
  `max-width: var(--ark-max-width)` from the un-overridden `:root`
  value before any site-authored descendant exists in the tree. CSS
  custom properties only cascade downward; a child can never widen its
  own parent's already-resolved box.

`--ark-bg` had the same structural problem for the same reason (both
are read *directly* by `body`'s own rule, not by a descendant).

## The fix

Landed in `7aabfb5` ("CSS Backend is being refactored for
predictability. Stage 1 done."), alongside the broader
`arklight/backend/css/` service-oriented refactor (see
`docs/CSS-BACKEND-REFACTOR.md`) -- but the fix itself is small and
independent of that reorganization:

1. **`--ark-max-width` changed from a fixed `720px` to a fluid
   `min(100% - 3rem, 75rem)`** in what's now
   `arklight/backend/css/design_tokens.py`'s `ROOT_VAR_DEFAULTS` --
   the same intrinsic-sizing idiom (`min`/`clamp`/`minmax`) the rest
   of the base stylesheet already uses for `.switcher`/`.grid`/
   `.fluid-heading`. This alone means `body` now reflows with the
   viewport instead of capping at a fixed pixel column, with zero API
   changes -- every existing site gets a wider, still-readable column
   automatically.
2. **`Site(max_width=..., bg=...)` became real constructor kwargs**
   (`arklight/api.py`), threaded through `WebsiteIR.css_var_overrides`
   to `CSSBackend`, which generates the `:root { ... }` block from
   `ROOT_VAR_DEFAULTS` merged with those overrides instead of the old
   hardcoded constant. This is the actual override path point 3 above
   says any real fix needs: it sets the variable at `:root` scope,
   which is an *ancestor* of `body`, not a descendant -- so `body`
   picks it up when it resolves its own rule, instead of the
   downward-only cascade problem a wrapper div would hit.

```python
site = Site(max_width="90rem", bg="#0f0f1a")
```

Both kwargs stay optional (default `None`); a site that passes neither
gets ARKlight's stock fluid default, unchanged from before this was an
option.

## Why this doc didn't exist until now

The fix commit changed three source files and zero doc files -- no
`CHANGELOG.md`, `README.md`, or `PROGRESS.md` entry, despite adding a
genuine, working public API (`Site(max_width=..., bg=...)`) that nothing
outside `arklight/api.py`'s own inline comment described. See
`CHANGELOG.md` and `README.md`'s "Styling components" section for the
user-facing writeup that now exists alongside this one.
