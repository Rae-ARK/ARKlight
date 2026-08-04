# CSS Backend Refactor: Service-Oriented, Staged

Scope: **`arklight/backend/css/` only.** No other backend, pipeline
stage, or public API changes as part of this work.

## Why

`arklight/backend/css/render.py` grew to ~700 lines by accretion
across v0.002 -> v0.0431 (base stylesheet text, `:root`/`@property`
design-token generation, `site.style(...)` custom-class rendering, and
the `CSSBackend` orchestrator all in one file). None of it was wrong,
but it had drifted into one file doing four unrelated jobs:

1. Static default CSS text (data, never changes at runtime).
2. Computing the `:root { --ark-*: ...; }` + `@property` block from
   `ROOT_VAR_DEFAULTS`/`ROOT_VAR_SYNTAX` merged with a site's
   `css_var_overrides` (logic, runs every build).
3. Turning `site.style(name, rules)` registrations into `.name { ... }`
   blocks (logic, runs every build).
4. Assembling the above into one stylesheet string and satisfying the
   `Backend` interface (orchestration).

Mixing these means every change -- editing a default color, adding a
new `--ark-*` token, or touching how custom classes render -- touches
the same file and risks the same blast radius, and there's no single
place a future contributor (human or AI) can look to answer "where
does X live" without reading the whole file top to bottom.

## Target shape

Each concern becomes its own module under `arklight/backend/css/`,
with `render.py` reduced to pure composition. This is deliberately
**modules, not classes-for-everything** -- Python's module system
already gives each file a clean namespace and a single import path,
so wrapping each concern in a `FooService` class would be boilerplate
with no behavioral benefit here (no dependency injection, no runtime
polymorphism needed -- every "service" is a pure function of its
inputs). Each module still reads as one thing with one job, which is
the actual goal of "service-oriented" here: swap-able,
independently-testable units with a narrow, explicit interface,
without the ceremony a class hierarchy would add for no reason.

| Module | Responsibility | Kind |
|---|---|---|
| `base_stylesheet.py` | Static default CSS text (`BASE_CSS_HEADER`, `BASE_CSS_BODY`) | Data only |
| `design_tokens.py` *(stage 2)* | `ROOT_VAR_DEFAULTS`/`ROOT_VAR_SYNTAX` + `render_root_and_property_rules(overrides)` | Data + pure function |
| `custom_styles.py` *(stage 3)* | `render_custom_styles(custom_styles)` for `site.style(...)` | Pure function |
| `render.py` | `CSSBackend.render` composes the above into one stylesheet string; satisfies the `Backend` interface | Orchestration only |

Why this makes future refactoring easier:

- **Change isolation.** Editing a default color touches only
  `base_stylesheet.py`. Adding a new `--ark-*` token touches only
  `design_tokens.py`. Neither risks the other, and a diff's file list
  alone tells a reviewer (or a future AI session) which concern
  changed.
- **Independent testability.** Each module can be unit-tested against
  its own inputs/outputs without going through `CSSBackend.render` or
  a full IR build, once tests are split alongside the modules (see
  Stage 4).
- **Obvious extension points.** A future backend feature -- e.g.
  per-node `style=` collection into real rules, or the `@media`
  extension planned in `docs/DESIGN-NOTES.md` (v0.048) -- gets its own
  new sibling module instead of growing an existing one further.
- **Cheap to read.** `render.py` stays small enough that "what does
  the CSS backend do" is answerable by reading one file's imports, not
  by scrolling 700 lines.
- **No new runtime cost or dependency.** This is a pure code
  reorganization -- same functions, same call graph, same generated
  CSS byte-for-byte. Verified by the existing `tests/test_css_backend.py`
  suite passing unchanged at every stage (no new test infrastructure
  needed to prove behavior-preservation).

## Staging

Each stage is a self-contained, behavior-preserving commit. Tests
(`tests/test_css_backend.py`, whole suite as a sanity check) pass
unchanged after every stage -- if they don't, that stage isn't done.

- [x] **Stage 1** -- Extract `BASE_CSS_HEADER`/`BASE_CSS_BODY` into
  `base_stylesheet.py` (data only, zero logic). `render.py` now
  imports them.
- [x] **Stage 2** -- Extract `ROOT_VAR_DEFAULTS`, `ROOT_VAR_SYNTAX`,
  and `_render_root_and_property_rules` into `design_tokens.py` as
  `render_root_and_property_rules(overrides)`.
- [ ] **Stage 3** -- Extract `_render_custom_styles` into
  `custom_styles.py` as `render_custom_styles(custom_styles)`.
- [ ] **Stage 4** -- `render.py` left holding only `STYLESHEET_PATH`
  and `CSSBackend`, whose `render()` becomes a short composition of
  the three sibling modules. Split `tests/test_css_backend.py`'s
  cases across the new module boundaries where that adds clarity
  (optional, only if it doesn't just move code around for its own
  sake). Update `README.md`'s "Compiler pipeline" CSS Backend line if
  its description of `render.py` internals goes stale.

## Status

Stages 1-2 complete. Stages 3-4 not started. Resume by picking up
Stage 3 above -- `render.py`'s current `_render_custom_styles` is the
extraction target, same pattern as Stages 1-2: new module
(`custom_styles.py`), move code, update the one import site, run
tests.
