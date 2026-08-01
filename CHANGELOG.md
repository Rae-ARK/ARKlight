# Changelog

All notable changes to ARKlight are tracked here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/); versions
follow the milestone scheme from ARCHITECTURE.md rather than strict
SemVer.

## [0.003] -- JavaScript helpers

### Added

- `JSBackend` (`arklight.backend.js`) generating a static
  `arklight.js`: a fixed, closed vocabulary of client-side behaviors
  (`toggle`, `scroll-to`) plus automatic current-page nav-link
  highlighting. No arbitrary JavaScript is ever accepted from user
  code.
- `on_click` / `behavior_target` / `toggle_class` props on any
  component, validated against `arklight.ir.schema.KNOWN_BEHAVIORS` at
  build time and rendered as `data-ark-*` attributes.
- `default_backends()` now returns `[HTMLBackend(), CSSBackend(),
  JSBackend()]`.
- `.nav a.is-active` and `.hidden` added to the default stylesheet.
- `docs/DESIGN-NOTES.md`: styling ceiling, audience positioning,
  Svelte-comparison, and Mitosis-reframe (state/event semantics as the
  real prerequisite for v0.100) writeups.
- 9 new tests (66 total): JS backend content, behavior validation, and
  HTML attribute/script-tag rendering. Also verified interactively with
  Playwright against a real headless browser (nav highlighting + toggle
  click), not just by inspecting generated HTML.
- Example site: home page gained a working "Show details" toggle using
  `on_click="toggle"`, with no hand-written JavaScript.

### Changed

- CLI/package version bumped to 0.003.

## [0.002] -- CSS

### Added

- `CSSBackend` (`arklight.backend.css`) generating a default
  `styles.css` (typography, spacing, buttons, links, `.nav`/`.card`/
  `.muted` utility classes) -- every generated site is styled with zero
  CSS written by hand.
- `arklight.compiler.pipeline.build()` now runs a list of backends by
  default (`default_backends() -> [HTMLBackend(), CSSBackend()]`) and
  merges their output; customizable via `build(..., backends=[...])`.
- `class_name` and `style` (dict) props on any component, rendered as
  the HTML `class` attribute and an inline `style` attribute
  respectively.
- CLI: `arklight build` now opens the built site in the default
  browser automatically (`--open`, the default) or can be disabled
  (`--no-open`).
- 15 new tests (57 total): CSS backend output, relative-link
  resolution, `class_name`/`style` rendering, stylesheet link
  correctness, CLI browser-open behavior.

### Fixed

- **Internal links (`Link(..., href="/about")`) now compile to real
  relative file paths** instead of root-absolute routes. Previously,
  opening `dist/index.html` directly (the normal "first setup"
  experience) sent `href="/about"` to the filesystem root instead of
  `dist/about.html` -- pages appeared linked in the Python source but
  the links didn't actually work once rendered. The HTML backend is
  now route-aware and rewrites internal hrefs based on each page's
  actual output location; external URLs, fragments, and `mailto:`/
  `tel:` links are left untouched.
- The bundled example site now actually links Home and About to each
  other (via a shared `nav()` helper function) and uses the new
  styling props, instead of looking unstyled.

## [0.001] -- Python → HTML

First working compiler pipeline: a Python site file compiles all the
way to static HTML files, matching the full pipeline described in
ARCHITECTURE.md.

### Added

- `ARKNode` ARK AST node type and `node()` component factory.
- Public API: `Site`, `Page`, `Heading`, `Text`, `Button`, `Container`,
  `Link`, `Image`, `List`, `Item`.
- Static Python AST discovery stage (`arklight.parser.discover`) using
  the stdlib `ast` module.
- Site-file loader (`arklight.parser.loader`) that executes a site file
  in isolation and returns the live `Site` object.
- Normalization stage: flattens nested list children, drops
  `None`/`False`, wraps bare strings as `Text` nodes where appropriate.
- Validation stage: schema-checked component types, required props,
  and text-only nesting rules, with precise error messages.
- Shared component schema (`arklight.ir.schema`) used by both
  normalization and validation.
- Website IR (`IRNode` / `IRPage` / `WebsiteIR`), kept structurally
  distinct from the ARK AST.
- Backend interface (`Backend.render(ir) -> {path: contents}`).
- HTML backend: component-to-tag mapping, heading levels, prop-to-HTML
  attribute mapping (including a `data-*` fallback for unknown props),
  HTML escaping, and route-to-file-path mapping.
- Compiler pipeline (`compile_site_file`, `build`) unifying every
  stage behind a single `CompileError` for any failure.
- CLI: `arklight build <entry.py> [-o OUTPUT_DIR]`, `arklight --version`.
- Example site (`examples/hello_site/site.py`) with two pages.
- 42 tests covering every stage in isolation and end-to-end.
- Packaging via `pyproject.toml` (`pip install -e .`).

### Fixed

- Normalization no longer double-wraps strings inside text-only
  components (e.g. `Heading("hi")` no longer became an invalid
  `Heading(Text("hi"))`).
- Errors raised inside a page function (e.g. referencing an undefined
  component) are now caught by the pipeline and surfaced as
  `CompileError`, not left to propagate as raw exceptions.
