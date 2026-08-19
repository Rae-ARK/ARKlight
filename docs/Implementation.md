# ARKlight Installer — Implementation Plan

Staged build order for `Architecture.md`. Each stage should be
functionally complete and checkable before moving to the next. UI is
deliberately last: everything through Stage 3 should be inspectable and
testable as raw, unstyled Neutralino output first — the fastest way to
verify the plumbing actually works is to not be distracted by how it
looks yet. Once Stage 3 is solid, Stage 4 turns that into the wizard
described in `README.md`'s Design Goals, and can be reviewed the way any
website in progress gets reviewed — open it, click through it, flag
what to change.

---

## Stage 0 — Shell scaffolding

- `neu create` project skeleton, confirm `neu build` produces a running
  binary on at least one target OS.
- Wire the JS side to shell out to a Python entry point (thin wrapper
  around `detect.py`/`install.py`, or those modules called directly) and
  get a value back — no real logic yet, just prove the round trip works.
- CI stub: one GitHub Actions job that runs `neu build` on push, no
  CPack yet.

**Done when:** a Neutralino window opens, a button click triggers a
Python call, and the result renders as plain text somewhere on the page.

---

## Stage 1 — Detection & install flow

- Launch-time state check: does an ARKlight install already exist
  (`~/.local/share/arklight` or platform equivalent)? Branch accordingly
  (this is the one point Stage 4 will replace with the actual
  Install-vs-Maintenance-mode screens — for now, two plain code paths is
  enough).
- Connectivity pre-flight (`Architecture.md` §4): check before touching
  the filesystem, stop cleanly and report a reason if it fails. Build
  and test the failure path deliberately, not just the happy path.
- Wire `install_system()` and `install_private()` in for real. System
  Python detection, venv creation, private CPython acquisition — all
  functional, output can just be console/log text at this stage.
- Confirm both paths leave a working `arklight` command behind.

**Done when:** a full install works end to end through the plain
scaffolding UI on at least one OS, with an offline run correctly
stopping before any filesystem change.

---

## Stage 2 — Update, Repair, Uninstall

- Update: re-run the install step against the existing environment/
  runtime, current stable PyPI release.
- Repair: implement the interpreter-validity check from
  `Architecture.md` §3 — for a system-Python install, confirm the venv's
  interpreter path still resolves. Build both branches: still-valid
  (normal repair) and gone (pivot to private runtime via
  `install_private()`).
- Uninstall: remove the install on Linux/macOS directly; implement and
  test the Windows detached-helper self-delete path specifically, since
  it's the one piece of OS-specific code in the whole app and the
  easiest to get subtly wrong.

**Done when:** all three flows work from the plain UI, and Repair has
been tested against a deliberately broken system-Python install (delete
or move the interpreter it was pointed at, confirm it's detected and the
pivot offer appears and works).

---

## Stage 3 — Packaging & CI

- `CMakeLists.txt` + CPack generator list wrapping the `neu build`
  output into `.deb`/`.rpm`/AppImage (Linux), `.msi` (Windows), `.dmg`/
  `.pkg` (macOS).
- Extend the Stage 0 CI stub into the full matrix: `neu build` per OS
  runner, then CPack per runner, artifacts attached to the release.
- Sanity-install each package format on a clean machine/VM/container —
  this is what actually validates Stage 0–2 rather than just the local
  dev environment.

**Done when:** a tagged release produces installable packages for every
supported OS/format, and each one runs Stage 1's install flow
successfully from a clean state.

---

## Stage 4 — UI

Everything above already works; this stage is exclusively about turning
the plain scaffolding into the wizard `README.md` describes — typography,
theming (light/dark), motion on state transitions, the actual screen
flow for Install / Update / Repair / Uninstall, and the connectivity and
Repair-pivot moments getting real explanatory copy instead of log lines.

Because Stages 0–3 are done first, this stage is reviewable like any
front-end work in progress: run the binary, click through each flow,
give feedback against the running build rather than against a
description of it.

**Done when:** every flow from Stages 1–2 has a real screen, the
no-connectivity stop and the Repair pivot both read clearly to someone
who isn't a developer, and the whole thing matches the Design Goals in
`README.md`.

---

## Stage 4b — Embedded content panel (optional, not blocking)

Only worth doing once Stage 4 is done and there's an actual
documentation/portfolio site to point it at — see `Architecture.md` §6
for what this is and the constraints it has to respect (supplementary
only, no effect on the real connectivity gate, user-initiated loads
only, explicit domain allowlist).

- Add the panel and its nav toggle to the finished wizard, wired to
  bundled local content by default.
- Point one nav option at the live external site; confirm the fallback
  to bundled content actually fires when that site doesn't load,
  rather than just leaving the frame blank.
- Confirm this has zero effect on Stage 1–2 behavior with the panel
  never opened — it should be possible to delete this stage's work
  entirely without touching anything else.
- The URL to add: ARKfolio (My Portfolio) - https://rae-ark.horizonarkstudio.workers.dev/

**Done when:** the panel loads bundled content with no network access
at all, and — once the site exists — swaps to the live page on request
without changing how install/update/repair/uninstall behave.
