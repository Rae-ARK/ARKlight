# KaiOS backend -- packaging ARKlight output as a KaiOS app (PLANNING)

This is an **implementation** design doc: it treats KaiOS the way
`docs/DESIGN-NOTES.md` already treats Android and Desktop --- as a
`arklight kaios` **packaging backend** that wraps an existing
`arklight build` output directory into a shippable platform artifact,
not a new codegen target and not a rewrite of the HTML/CSS/JS
backends. Platform *constraints* (memory, engine version, input
model, storage, build toolchain) are already covered in depth by
[`kaios-app-design-doc.md`](./kaios-app-design-doc.md) in this same
directory -- that doc is reverse-engineered from a real, shipped
KaiOS app (`strukturart/o.map`) and is treated here as the source of
truth for "what KaiOS actually requires." This doc only answers the
question that doc doesn't: **what does ARKlight, specifically, need
to build and ship to turn its own compiler output into a KaiOS app?**

Status: design only. Nothing under `arklight/backend/` or
`arklight/packer/` implements any of this yet. Same "design complete,
implementation not started" discipline every other PLANNING section
in `docs/DESIGN-NOTES.md` follows -- referenced from `PROGRESS.md`'s
snapshot table, not summarized in `README.md` until it actually
lands.

## 1. What this is, in one line

A new `arklight kaios` CLI backend that packages an existing
`arklight build` output directory into a KaiOS **packaged app** --
a `manifest.webapp` plus the build's own files, zipped -- so the same
static site that already runs standalone in a browser or as a `.ark`
polyglot can also install and run on a real KaiOS device (or the
Gonk/B2G desktop simulator used for development), without ARKlight
ever running a JVM, invoking a native toolchain, or becoming a
general-purpose app framework.

## 2. Why this is the *easy* packaging backend, not the hard one

Read against `docs/DESIGN-NOTES.md`'s Android backend section
("v0.0438"), the honest comparison matters: Android needed a JDK +
Android SDK + Gradle + AndroidX/Google Maven, because
`WebViewAssetLoader` only exists as compiled Kotlin/Java bytecode --
there was no way to avoid a native build step. **KaiOS has no
equivalent problem.** A KaiOS packaged app is, structurally:

```
my-site.zip
├── manifest.webapp      <- JSON, not compiled
├── index.html            <- already what arklight build produced
├── styles.css             |
├── arklight.js             |
└── assets/                |
```

That's it. `manifest.webapp` is JSON (see §4), and the archive is a
plain ZIP -- Gecko's packaged-app installer reads it directly, no
build step, no compiler, no external SDK. This makes `arklight kaios`
structurally closer to `arklight.packer` (`arklight pack` -> `.ark`)
than to `arklight android`: **read an already-built directory, write
an archive, done.** Same "never imports the parser/ir/backend
internals" shape `arklight/packer/bundle.py`'s own module docstring
states for `.ark` bundles, and the same one this doc commits to for
`arklight/backend/kaios/` (or `arklight/packer/kaios.py` -- see §7 for
why the latter is probably the right home).

The one real toolchain dependency -- and it's optional, not required
to produce a working app -- is `pfs` / KaiOS's `webide`/App Manager
tooling for pushing a build to a physical device or the simulator over
ADB. That's a *deployment* convenience, not a build requirement; the
zip itself is valid and sideloadable without it. This mirrors the
Android backend's own "templating the source is genuinely free;
building it never can be" distinction, except here the *whole
artifact* is on the free side of that line, not just the source
templates.

## 3. What ARKlight's existing output already gets right for free

This section exists because it's the part worth being honest is
*not* new work -- KaiOS's platform constraints (per
`kaios-app-design-doc.md` §§1-6) line up with decisions ARKlight's
compiler already made for unrelated reasons:

- **No inline `<script>`, no `eval`, no `new Function`.** KaiOS
  certified/privileged packaged apps enforce a CSP that forbids
  inline scripts and `eval`-family execution outright (Content
  Security Policy is not optional there the way it is on the open
  web). ARKlight's HTML backend already emits exactly one external
  `<script src="arklight.js">` tag (see
  `arklight/backend/html/render.py`'s `SCRIPT_PATH` import) and the
  JS backend's own closed-registry discipline (§"Explicitly out of
  scope for v0.044" in `docs/DESIGN-NOTES.md`: "Any real
  JS/template-expression evaluator, `eval`, or `new Function` --
  permanent non-goal") means `arklight.js` never contains either.
  Nothing needs to change here; it's a CSP pass by construction, not
  by review.
- **Static file output, no server assumption.** `arklight build`
  already produces plain files with relative paths (`Backend.render()`
  returns `dict[str, str]`, written to disk by the pipeline, never
  assuming a running server) -- exactly the shape a packaged app's
  `file://`/app-package-relative loading needs. There is no
  `fetch("/api/...")`-shaped assumption anywhere in current output to
  unwind.
- **Only-ship-what's-used JS.** `JSBackend.render()` already includes
  the reactive core (and vdom, and per-stage additions like Stage 3's
  `arkApplyModifiers`) only for pages that declare `State(...)` /
  use modifiers -- on a platform where every extra KB of parsed JS is
  a real cost on a Cortex-A7-class single/dual-core part (per
  `kaios-app-design-doc.md` §1), this existing discipline is a direct,
  unplanned win for this backend, not something this milestone needs
  to add.

## 4. `manifest.webapp` -- what this backend actually generates

The one genuinely new artifact. A minimal, valid packaged-app
manifest, generated from data ARKlight's IR already has (mirroring
how the Android backend design reads existing `Page`/`Site` props
rather than asking the user to fill out a second config file):

```json
{
  "name": "<Site.title, truncated to KaiOS's ~20-char launcher-grid limit>",
  "description": "<Page(description=...) from the entry page, if set>",
  "launch_path": "/index.html",
  "type": "privileged",
  "icons": {
    "56": "/assets/icon-56.png",
    "112": "/assets/icon-112.png"
  },
  "orientation": "portrait-primary",
  "fullscreen": "true",
  "csp": "default-src 'self'; script-src 'self'; object-src 'none'",
  "permissions": {}
}
```

Design decisions worth stating explicitly, each with a reason (same
"grow as data, state the reason" discipline this file uses
everywhere):

- **`type: "privileged"`, not `"web"` or `"certified"`.** `"web"`-type
  hosted/packaged apps get the weakest permission set and, on some
  KaiOS versions, a less reliable install path for a packaged (as
  opposed to hosted) app; `"certified"` is reserved for
  carrier/OEM-signed system apps and requires a signing relationship
  ARKlight has no business assuming. `"privileged"` is the correct
  default for a third-party packaged app and is what
  `kaios-app-design-doc.md`'s source project (`o.map`) itself ships
  as.
- **`icons` sizes fixed at 56/112, not user-configurable in v1.**
  KaiOS's launcher grid expects specific icon sizes; getting this
  wrong is a silent-failure mode (blank or default icon), not a build
  error. If `Site(...)` gains an `icon=` prop before this backend
  ships, generation reads it and resizes; until then, a missing icon
  is a documented, explicit CLI warning (same "warn, don't
  silently omit" pattern `v0.0431`'s unrouted-`srcset` warning
  already established for the HTML backend) rather than a broken
  manifest.
- **`csp` is generated, not left to the platform default,** and is
  deliberately at least as strict as what §3 already guarantees
  ARKlight's own output needs (`script-src 'self'`, no `'unsafe-
  inline'`, no `'unsafe-eval'`). Writing it explicitly documents the
  guarantee in the manifest itself rather than relying on it being
  true by accident of current output.
- **`permissions: {}` by default.** ARKlight's compiler has no
  concept of device permissions (geolocation, contacts, etc.) in its
  IR today, and there is no vocabulary for a `Page`/`Site` to request
  one. Shipping an empty permissions object is the honest reflection
  of that -- not a placeholder to be filled in later by this
  milestone, but a real scope boundary (see §6).

## 5. Packaging: reusing, not duplicating, the `.ark` bundle's ZIP path

`arklight/packer/bundle.py` already builds ZIP archives from a build
directory (the "plain, generically-openable ZIP tail" mode used when
`sealed=False`). `arklight kaios build` should reuse that low-level
ZIP-writing path rather than hand-rolling a second one: the only
things a KaiOS package needs beyond a bundle's existing "read build
dir, write ZIP" behavior are (a) the generated `manifest.webapp` added
at the archive root, and (b) *no* HTML-inlining/polyglot step -- a
`.ark` bundle's defining trick (HTML parsers stop at `</html>`, so
the file opens as a page *and* as an archive) is actively wrong here,
since a KaiOS installer expects a normal ZIP with `manifest.webapp`
at byte 0 of the *listing*, not a polyglot page. This is a concrete
argument for factoring the ZIP-writing primitive out of
`arklight/packer/bundle.py`'s `_inline_entry_page`-adjacent code into
something both `pack()` and a future `kaios_pack()` call, rather than
copy-pasting archive-writing logic -- flagged here as a prerequisite
refactor, not assumed to fall out of this milestone automatically.

Staged CLI shape, mirroring the Android backend's "ladder, not one
all-or-nothing command" precedent:

1. **`arklight kaios scaffold`** -- generates `manifest.webapp` next
   to (or reading from) an existing `build-dir`, no packaging yet.
   Lets someone inspect/hand-edit the manifest before it's zipped.
2. **`arklight kaios build`** -- runs `scaffold` implicitly if no
   manifest exists, then zips `build-dir` + `manifest.webapp` into
   `<site-name>.zip`. This is the terminal step for most users --
   unlike Android, there is no further native compile stage.
3. **`arklight kaios build --install`** -- optionally invokes the
   KaiOS `webide`/ADB-based push tooling if found on `PATH`, same
   graceful `FileNotFoundError` handling (clear message, exit `1`,
   never a raw traceback) the Android backend design already commits
   to for its own optional `adb install` step. Explicitly optional:
   the zip from step 2 is already a complete, valid, sideloadable
   artifact without this.

## 6. Explicitly out of scope

Same convention this repo already uses (`v0.044`, the Android
backend section) to stop scope creep before it's assumed-in later:

- **Device permission requests** (geolocation, camera, etc.) --
  ARKlight's IR has no vocabulary for this at all yet; adding
  `permissions` support here would mean inventing that vocabulary as
  a side effect of a packaging milestone, backwards from how every
  other capability in this compiler has grown (IR/API first, backend
  support second).
- **`mozActivity` integration** (share sheets, cross-app launches) --
  a real KaiOS capability documented in
  `kaios-app-design-doc.md`, but it's an *app-authoring* primitive
  (something a site's own JS would call), not a *packaging* concern;
  out of scope for a backend whose job is "wrap already-built output,"
  same boundary `arklight.packer` already draws for itself.
- **Runtime polyfilling for Gecko 48 (KaiOS 2.5)'s older JS engine.**
  `arklight.js`'s current output (ES6 `let`/`const`/arrow
  functions/template literals/classes-in-the-vdom-core) already runs
  on Gecko 48 without transformation -- verified against
  `kaios-app-design-doc.md`'s own engine notes, which place KaiOS
  2.5 at Gecko 48/SpiderMonkey circa 2016, well past ES6 support.
  If a *future* JS backend stage (v0.044's remaining sub-systems, or
  anything past them) introduces syntax Gecko 48 doesn't support,
  that's a JS-backend compatibility concern to catch at that stage,
  not something this packaging backend should silently work around
  with a transpile step -- ARKlight has no build-time JS transpiler
  today and adding one is a far larger commitment than packaging
  calls for. This applies equally to any future vendored dependency,
  not just hand-written stages -- see
  `docs/Backends/JS-BACKEND-REFACTOR-PLAN.md`'s "Cross-cutting risk"
  section, which flags that HTMX (proposed for the app-shell
  navigation work that section describes, and directly relevant here
  since it's what would let a packaged KaiOS build avoid full-page
  reloads between routes) has not yet been verified against Gecko 48
  the way ARKlight's own hand-written output has.
- **Certified-app signing / carrier submission tooling.** Getting an
  app onto the KaiOS Store or carrier-preloaded is a relationship and
  process this backend has no way to automate or should try to; it
  produces a valid, installable package and stops there, the same way
  the Android backend design explicitly leaves keystore/signing
  credential handling to the user rather than ARKlight inventing its
  own credential story.

## 7. Where this lives in the codebase

Proposed as `arklight/packer/kaios.py` (a sibling of `bundle.py` and
`seal.py`), **not** `arklight/backend/kaios/` -- despite the "backend"
framing in this doc's title, this is deliberately not a `Backend`
subclass (`arklight/backend/base.py`). A `Backend.render()`
implementation participates in the compiler pipeline's `backends=[...]`
list and receives `WebsiteIR` directly; this feature, like `.ark`
packing and (per its own design doc) the Android backend, only ever
reads an *already-built* output directory and never touches
parser/ir/backend internals. Placing it under `arklight/packer/`
keeps that boundary explicit in the module graph, not just in prose --
the same reasoning `arklight/packer/bundle.py`'s own docstring gives
for why *it* isn't a `Backend`.

## 8. Suggested milestone number and ordering

Not yet assigned in `PROGRESS.md`'s snapshot table. Given the Desktop
backend (`v0.060`) and Android backend (`v0.080`) are already
sequenced as later, heavier-toolchain packaging milestones, and this
backend has *no* native toolchain dependency at all (§2), it arguably
belongs *before* both of them in implementation order even if it's
numbered after them for roadmap-narrative reasons (KaiOS is a much
smaller install base than Android/desktop) -- flagged here as a
sequencing question for whoever schedules it, not decided by this
doc.
