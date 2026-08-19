# ARKlight Installer — Target Architecture (Final Direction)

Supersedes the earlier divergence report. This is where the design has
landed after working through it — captures the decisions so the
`installer` branch can be rebuilt against them instead of the old
Tkinter/PyInstaller shape.

---

## 1. Shell: NeutralinoJS, not Tkinter

**Decision:** single HTML/CSS/JS codebase, rendered through the OS's
existing webview (WebView2 / WebKitGTK / WKWebView) via Neutralino,
not a native toolkit.

**Why this replaces Tkinter:**
- Tkinter is genuinely cross-platform and free (ships with CPython),
  which is why the old branch chose it — but it caps the UI at native
  widget styling. A wizard that's meant to look good is fighting Tk's
  ceiling from the start.
- Neutralino keeps the "no bundled runtime" property Tkinter had —
  small binary (single-digit MB), no Chromium bundle like Electron —
  while making the UI just a website: real typography, animation,
  theming, all in CSS instead of Tk widget options.
- `neu build` cross-compiles for Linux/Windows/macOS from one machine
  and one codebase, which fits a GitHub Actions matrix cleanly — same
  CI shape as before, different build tool.

**Constraint to keep in mind, not a blocker:** stick to well-supported
CSS (flexbox, grid, custom properties, standard transitions/animations).
Older Linux WebKitGTK builds (tied to distro age, not auto-updated the
way Windows/macOS webviews are) are the one place bleeding-edge CSS
(newer color functions, some `backdrop-filter` behavior,
view-transitions) could render inconsistently. Not a portability
problem in practice — just don't reach for this year's CSS spec.

**Maintainer's ruling — non-negotiable:** the whole point of moving off
Tkinter is a wizard that actually looks like something someone designed
on purpose. Picking Neutralino and then shipping stock unstyled webview
HTML defeats the reason it was picked in the first place — that's not a
smaller version of this decision, it's the decision not being made. Real
typography, spacing, a real theme (light/dark), motion on state
transitions — that's the deliverable, not a stretch goal for later.
Anything that ships as an unstyled form is a rejected PR, full stop.

---

## 2. No daemon. Launch-triggered, state-aware, closes when done.

**Decision:** the installer is opened by the user, not resident in the
background.

- **No autostart registration** — no `systemd --user` unit, no macOS
  Login Item, no Windows Registry Run key / Scheduled Task. This was
  the actual complexity source in the "persistent updater" model
  (Sparkle/Squirrel-style) considered earlier, and it's the thing that
  reintroduces exactly the OS-specific work the whole redesign is
  trying to get away from. Dropped entirely.
- **No tray icon, no phoning home, no code-signing pressure from
  persistence** — signing still matters for basic OS trust (Gatekeeper/
  SmartScreen warnings on an unsigned binary), but there's no
  additional pressure from running unattended.
- **On launch, the app checks install state** (does
  `~/.local/share/arklight` — or platform equivalent — already have an
  ARKlight install?) and branches the wizard accordingly:
  - **Not installed →** fresh install flow (same detection/venv/private-
    runtime logic as before, see §4).
  - **Already installed →** Update / Repair / Uninstall flow instead of
    Install. This is the standard "maintenance mode" pattern most
    commercial installers use — one binary handles the whole lifecycle
    without anything running between launches.
- **Uninstall is the one path with OS-specific plumbing left**, and
  it's small and contained: a running binary can delete itself fine on
  Linux/macOS (the OS holds the file open until the process exits),
  but **Windows cannot delete a running .exe**. The standard fix is a
  small detached helper script spawned just before exit, which waits
  for the parent process to close, then deletes the installer binary.
  This only fires on the "uninstall and close" choice — normal
  install/update runs never touch it.

---

## 3. Version gating — removed, per earlier decision, unchanged

**Still stands from the previous report:** no min-version detection,
no greying out incompatible interpreters. The install step is just
`pip install arklight` (or `--upgrade`), latest stable PyPI release,
full stop. `detect.py`'s `fetch_min_python()` / `compatible()` filter
logic gets deleted, not ported into the new frontend.

---

## 4. Backend logic is reused as-is, just called differently

**Decision:** the actual install work — detecting system Python,
creating a venv around it, or downloading a private relocatable
CPython and installing straight into it (no venv, per the earlier
decision) — doesn't get rewritten. `install.py`'s `install_system()`
and `install_private()` are sound; Neutralino's UI shells out to them
(or an equivalent thin Python entry point) the same way the old
Tkinter UI called into them directly. The GUI layer changing doesn't
touch this half of the codebase.

- `install_private()` already correctly skips the venv for the
  bundled-CPython path — unchanged.
- `install_system()` already correctly keeps the venv for an existing
  system interpreter — unchanged.
- The PyPI-metadata version check inside `detect.py` is the only piece
  being removed (§3); everything else in `detect.py`/`install.py`
  carries over.

---

## 4a. Dependencies are fetched, not bundled — offline is a hard stop

**Decision:** CPython (the private-runtime path) and every other
install-time dependency are retrieved from the internet at run time,
the same way `install_private()` / `install_system()` already do it —
nothing gets vendored into the Neutralino binary to make it work
offline. That was never the design and isn't becoming one; a "no
internet" binary would mean bundling a CPython per OS/arch into the
installer artifact itself, which throws away the whole "small binary"
property from §1.

**Required behavior on launch, before any install/update/repair step
starts:**
- Do a connectivity check (reachability against PyPI /
  python.org's release endpoint — whatever `detect.py`/`install.py`
  already hit to resolve versions/downloads — is sufficient, no need
  for a separate generic "ping the internet" check).
- **If it fails, stop before touching the filesystem.** No partial
  venv, no partially-unpacked private CPython, nothing left half-done
  for the user to clean up by hand.
- Tell the user plainly, in the GUI (not a console message they'll
  never see): that ARKlight could not reach the internet, that
  install/update needs a connection because CPython and dependencies
  are downloaded rather than bundled, and what to do next
  (check connection, retry). No silent fallback, no vague generic
  error string.

---

## 5. Build & CI: CPack still fits, now packaging a Neutralino binary instead of a PyInstaller one

**Decision unchanged from the earlier report:** CMake/CPack was always
the right tool for "the boring part" — three hand-rolled bash scripts
(`build-deb.sh`, `build-rpm.sh`, `build-appimage.sh`) duplicating
packaging logic per format was the actual mistake, not the choice to
have a shared GUI. That critique still applies, just aimed at a
different binary now:

- `neu build` produces the portable per-OS binary (Linux/Windows/
  macOS) from one codebase.
- CPack wraps that output into real installable packages — `.deb`/
  `.rpm`/AppImage on Linux, `.msi` on Windows, `.dmg`/`.pkg` on macOS —
  from one `CMakeLists.txt` + generator list, instead of one bespoke
  script per format.
- One GitHub Actions matrix: `neu build` per OS runner, then CPack per
  runner, artifacts attached to the release. Same shape as the
  existing `installer-linux.yml`, extended to all three OSes instead
  of just Linux.

---

## Summary of what changes vs. the old `installer` branch

| Piece | Old (`installer` branch) | New (this direction) |
|---|---|---|
| GUI framework | Tkinter, frozen via PyInstaller | NeutralinoJS (HTML/CSS/JS + OS webview) |
| GUI portability | Cross-platform via CPython + Tk | Cross-platform via `neu build` |
| Runs as | One-shot, install-only | One-shot, state-aware (install / update / repair / uninstall), still no daemon |
| Version gating | Present (contradicts final intent) | Removed |
| venv handling | Correct as-is | Unchanged |
| Private CPython download | Correct as-is | Unchanged |
| Packaging | 3 separate bash scripts | CMake + CPack, one config, multi-OS |
| Uninstall self-delete | N/A (not implemented) | Detached helper script, Windows-only concern |
| Known bug (PyInstaller relative import crash) | Blocking, reported separately | Moot — PyInstaller is no longer in the pipeline |

The net effect: the previously-reported PyInstaller crash disappears
because PyInstaller is no longer part of the stack, the two real
direction problems from the last report (version gating, no CPack) both
get fixed, and the GUI itself gets meaningfully nicer for free — all
without adding OS-specific runtime complexity, since the only
platform-specific code left is the Windows self-delete-on-uninstall
helper.

---

## 6. Cleanup — what's dead as of this direction

Superseded by §1 (Tkinter → Neutralino) and §5 (three bash scripts →
CPack). `detect.py` and `install.py` are explicitly **not** in this
list — they carry over per §4, minus the version-check function
covered in §3. Removal command is in the maintainer's follow-up, not
duplicated here so this doc doesn't drift out of sync with it.
