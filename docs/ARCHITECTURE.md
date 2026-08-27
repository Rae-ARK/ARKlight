# ARKlight Architecture

## Vision

**ARKlight is a Python-first compiler for building static websites where
developers work with a structured component API, while the output remains
ordinary, dependency-free HTML.**

Write your site in Python. ARKlight compiles it to standard HTML with CSS and
vanilla JavaScript. The browser never executes Python — you get predictable,
inspectable, portable output that works anywhere static files are hosted.

Python ergonomics at authorship time. Clean web artifacts at deployment time.
No Python runtime in production. No framework bloat.

## Core Principles

- Flask-like simplicity.
- Functions over classes.
- One obvious way.
- Beginner friendly.
- AI-friendly API.
- Backend independent compiler.
- Configurable only where it needs to be -- an internal value gets a
  user-facing override (`Site(...)`/`Page(...)` kwarg, `arklight build`
  flag) only when a real site could want it different *and* nothing
  already reaches it; otherwise it stays a plain internal constant. See
  `docs/CONFIGURABILITY.md` for the full rule and worked examples.

## Compiler Pipeline

```
Python Source
    |
    v
Python AST
    |
    v
ARK AST
    |
    v
Normalization
    |
    v
Validation
    |
    v
Website IR
    |
    v
Backend Interface
    |
    v
HTML Backend
    |
    v
index.html
```

## Website IR

Each node contains:
- type
- props
- children

The IR models website intent rather than HTML.

## Backend Interface

Current:
- HTML (`arklight/backend/html/`) -- a service-oriented module split
  (mirroring the CSS backend below) is designed and Stage 1 of 6 is
  now implemented (`tag_map.py`), see
  `docs/Backends/HTML-BACKEND-REFACTOR.md`.
- CSS (`arklight/backend/css/`) -- already split into
  `base_stylesheet.py`/`design_tokens.py`/`custom_styles.py`/
  `render.py`, see `docs/CSS-BACKEND-REFACTOR.md`.
- JavaScript (`arklight/backend/js/`)

Future:
- Vue
- Svelte
- Android (`arklight android` -- packaging backend, not a template/
  codegen backend like Vue/Svelte: wraps an existing `build-dir` into
  a native Android project via `androidx.webkit.WebViewAssetLoader`,
  same "reads already-built output, never touches the
  parser/ir/backend internals" shape as `arklight.packer`. See
  `docs/DESIGN-NOTES.md` ("v0.0438: Android backend"), PLANNING.)

## Public API

Everything is a function.

Children are positional arguments.

Properties are keyword arguments.

Components are Python functions.

```python
from arklight import *

site = Site()

@site.page("/")
def home():
    return Page(
        Heading("ARKlight"),
        Text("Build websites with Python."),
        Button("Get Started")
    )
```

## Repository

```
arklight-framework/
  arklight/
    compiler/
    parser/
    ast/
    ir/
    backend/
      html/
    cli/
  examples/
  tests/
  docs/
```

## Milestones

This is the canonical roadmap -- `README.md` and `PROGRESS.md` link
here rather than keeping their own copies. Status: DONE / PLANNED.

| Version | What | Status |
|---|---|---|
| v0.001 | Python → HTML | DONE |
| v0.002 | CSS (default stylesheet) | DONE |
| v0.003 | JavaScript helpers, incl. two vocabulary extension addenda (semantic layout, forms, tables, media, intrinsic responsive layout utilities, `copy`/`dismiss` behaviors) | DONE |
| v0.0035 | Stateful JS -- registry-driven behaviors + actions; `State`/`Bind`/`Action.*` | DONE |
| v0.004a | CLI scaffolding (`arklight new <name> --template simple\|production`) | DONE |
| v0.036 | ARK Bundle spec v1 -- single-file `.ark` packaging of a site's build output (`arklight pack`) | DONE |
| v0.037 | Sealed ARK Bundles -- archive half encrypted by default, `assets/` + all files carried over, `arklight unpack` | DONE |
| v0.041 | CLI/pipeline/JS runtime error-handling hardening + stateful JS vocabulary addenda I & II (`Action.decrement/reset/append/remove`) | DONE |
| v0.042 | Extra CSS features -- `Site.style(name, rules)` custom CSS class authoring, `arklight search <name>` component-schema lookup, `arklight --help`/bare `arklight` help text | DONE |
| v0.043 | Optional `<head>` metadata props (`description`/`favicon`/`og_*` on `Page(...)`) + `Backend.postprocess(...)` extension hook | DONE |
| v0.048 | CSS `@media` queries + structured `<head>`/`<header>` extension -- Stage A (`meta`/`links` on `Page(...)`, DONE) + Stage B (`responsive_style` + `@media` compilation, DONE); see `docs/DESIGN-NOTES.md` | DONE |
| v0.054 | JS backend capability expansion -- computed/derived state, watch effects, two-way input binding, per-item list rendering, conditional show/hide, event modifiers, reactive class binding, all via closed registries (no arbitrary JS/eval) -- design complete in `docs/DESIGN-NOTES.md`, implementation not started | PLANNED |
| vdom-staging | Reactive-core vdom staging, Stage 1 of 8 -- vendored snabbdom bare core (`init`/`h`/`vnode`/`htmlDomApi`) swapped into `State`'s re-render pass (Stage 1, DONE); reactive class binding via direct `classList.toggle` (Stage 2, DONE); event modifiers/computed state/two-way binding/watch effects/conditional show-hide/list rendering (Stages 3-7, feeding `v0.054`), then `localStorage` persistence (Stage 8) -- see `docs/DESIGN-NOTES.md` ("Reactive-core vdom staging") | IN PROGRESS |
| v0.060 | User-defined, reusable components | PLANNED |
| v0.080 | Desktop backend -- `arklight desktop` packages a `build-dir` into a cross-platform desktop app (Tauri-based or similar); design pending | PLANNED |
| v0.100 | Android backend -- `arklight android` packages a `build-dir` into a native Android project via `androidx.webkit.WebViewAssetLoader` (staged `scaffold` -> `build` -> `--install` -> `--release` CLI ladder); design complete in `docs/DESIGN-NOTES.md`, implementation not started | PLANNED |
| v0.120 | KaiOS backend -- `arklight kaios` packages a `build-dir` into a KaiOS packaged app (`manifest.webapp` + zip, no native toolchain dependency); design complete in `docs/Backends/KAIOS-BACKEND-IMPLEMENTATION.md`, implementation not started | PLANNED |
| v1.0 | Stable compiler | PLANNED |

**Renumbered.** v0.048 (CSS `@media` + `<head>` extension) is now
DONE -- both Stage A (`meta`/`links` on `Page(...)`) and Stage B
(`responsive_style` + `@media` compilation) have landed; see
`docs/DESIGN-NOTES.md` for both designs and `PROGRESS.md` for the
implementation record of each stage. With v0.048 out of the way, the
milestones behind it were renumbered to close the gap and make room
for a dedicated KaiOS slot: JS backend capability expansion moved
`v0.044` -> `v0.054`; user-defined components moved `v0.100` ->
`v0.060`; the Desktop backend moved `v0.060` -> `v0.080`; the Android
backend moved `v0.080` -> `v0.100`; and the KaiOS backend -- previously
designed but unnumbered -- was given `v0.120`. None of this reordering
changes scope or design, only sequencing: v0.054 (JS backend
expansion) is queued next; v0.060 (user-defined components), v0.080
(Desktop), v0.100 (Android), and v0.120 (KaiOS) are designed (Desktop
excepted -- design pending) but implementation is deferred. Alternate
backends (Vue, Svelte) remain moved to unscheduled future work,
pending further development of the IR and state/event semantics.

## Non-goals

- Browser-side Python
- Virtual DOM
- Runtime Python
- Feature creep

---

See `PROGRESS.md` in the repo root for implementation status and
`CHANGELOG.md` for version history.
