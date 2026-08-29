# Experimental APIs

## What counts as "experimental"

ARKlight's default surface is built entirely on the intrinsic layout
model described in `docs/DESIGN-NOTES.md`: flexbox/grid sizing
keywords (`minmax()`, `auto-fit`, `clamp()`, `flex-wrap`) and the
`.stack`/`.cluster`/`.switcher`/`.grid`/`.sidebar` utility classes
built on top of them. Nothing in that model is keyed to a specific
viewport width, device class, or browser engine -- it reflows from
available space alone.

**Any feature that steps outside that model is, by definition, an
experimental API.** That currently means:

- `css-media-queries` -- `@media` conditions keyed to viewport width/
  height/orientation, reachable two ways: `Site.media_query(...)` (see
  below), and, as of v0.048 Stage B, a per-node `responsive_style=
  {"(max-width: 600px)": {...}}` prop any component may carry. Both
  compile to the same kind of viewport-keyed `@media` block and share
  this one gate -- see `docs/DESIGN-NOTES.md` ("v0.048: CSS media
  queries + `<head>` extension") for `responsive_style`'s design.
- `experimental-install-pwa` -- a native browser install-prompt button
  (`arklight pwa ... --install-button`), which depends entirely on
  `beforeinstallprompt` support in the visiting browser engine.
- `css-import` -- `Site.import_style(url)`, a real `@import
  url("...");` statement. Flagged because the imported file's contents
  can't be validated by ARKlight the way every other generated rule
  is -- it's fetched and applied by the browser at request time, from
  whatever the URL resolves to then, and it also blocks the CSS Object
  Model until it resolves. Prefer `Page(links=[{"rel": "stylesheet",
  "href": ...}])` where possible; reach for `import_style` only when a
  stylesheet truly isn't reachable that way.

This list grows as new escape hatches are added. **There is no
"experimental by convention" bucket** -- if a feature isn't in
`arklight/experimental.py`'s registry, it isn't flagged, and nothing
should ship that bends the intrinsic-layout rule without also being
added there first.

## Why gate instead of block

ARKlight could simply refuse to offer `@media`/native-install-prompt
support at all. It doesn't, because both are legitimate answers to
real constraints (a design that truly must key off viewport
characteristics; a PWA that wants a native install affordance instead
of a normal link). Blocking them outright would just push authors to
route around ARKlight entirely for that one page. Gating instead:

1. keeps the *default* path 100% intrinsic (nobody hits this without
   opting in by name), and
2. makes the tradeoff visible at build time, every time, rather than
   a silent landmine discovered later on a device the author didn't
   test on.

## CLI contract

Every registered experimental feature has two warning surfaces,
handled by `arklight/experimental.py` and printed by the CLI
(`arklight/cli/main.py`):

1. **Inline, at the moment it's detected** -- a compact banner,
   interleaved with the normal `[ARKlight]` stage log:

   ```
   ⚠️  [EXPERIMENTAL FEATURE ACTIVE]: Component 'Button' unlocked an experimental API.
      -> Feature: experimental-install-pwa
      -> Note: Runtime stability relies entirely on native browser engine support.
   ```

2. **End-of-run summary** -- one full block per *distinct* feature
   actually used (not once per occurrence), printed after the command
   reports success, mirroring the existing `[ARKlight ALPHA]` warning
   pattern in `_print_alpha_warnings`:

   ```
   ⚠ Experimental API enabled
       Feature : css-media-queries
       Media queries target viewport characteristics rather than
       intrinsic layout.
       ...
   Legacy API detected: css-media-queries
   This feature predates ARKlight's intrinsic layout model and is
   retained for compatibility. New projects should prefer .switcher,
   .grid, .cluster, .sidebar, or other intrinsic layout primitives.
   ```

Neither surface is gated behind `--verbose`/`--debug` -- unlike normal
stage narration, an experimental-API warning is not "nice to have with
more output," it's the entire point of gating the feature in the first
place, so it always prints.

## Android: why this matters more there, not less

Media queries and other viewport-keyed logic are especially unreliable
on Android specifically, more so than "mobile vs desktop" framing
usually implies:

- **No single "phone" viewport.** Android ships across an enormous
  spread of physical widths, pixel densities, and aspect ratios, from
  budget devices to tablets to unfolded foldables mid-hinge -- a
  breakpoint tuned against one reference device silently mis-lays-out
  on the next.
- **Foldables move the goalposts at runtime.** A single session can
  cross a breakpoint without a page reload (fold/unfold), which
  `@media` static width thresholds have no concept of at all; only
  layout that reflows continuously (the intrinsic model) tracks that
  correctly.
- **Chrome-derived WebViews vary by OEM/version.** Support for newer
  viewport units (`dvh`/`svh`/`lvh`) and container queries lags behind
  desktop Chrome on a meaningful slice of installed Android browsers,
  so a media-query-gated layout can silently fall back to its
  un-queried state on exactly the devices most likely to need it.
- **The back/navigation surface is non-standard.** Android's system
  back gesture/button, and where a browser chrome places its own back
  affordance, differs by OEM skin and browser -- a page that assumes a
  fixed viewport height to lay out its own in-page "back" control (a
  common reason to reach for a breakpoint) will find that assumption
  wrong on some fraction of real devices. Prefer laying out navigation
  with intrinsic sizing (`.cluster`, `min-height: 100dvh` instead of a
  fixed `vh`, safe-area insets via `env(safe-area-inset-*)`) so the
  control stays reachable regardless of how much chrome the OS/browser
  combination has claimed.

None of this is an argument against ever using `@media` -- it's the
argument for `css-media-queries` being flagged loudly instead of
offered as a first-class, unremarkable primitive: the failure mode is
specifically worse on Android's device spread than the "iPhone vs
desktop" case most breakpoint intuition is built around, so an author
reaching for it should see that tradeoff every single build, not just
the first time.

## Adding a new experimental feature

1. Add an entry to `FEATURES` in `arklight/experimental.py` (id,
   inline note, wrapped detail paragraph, legacy/back-compat note).
2. Call `arklight.experimental.emit(feature_id, on_warning=log, ...)`
   at the point the feature is detected (compile-time for build-time
   features, post-build for `arklight pwa`-style steps).
3. Document the feature above, including *why* it's outside the
   intrinsic model, not just that it is.
