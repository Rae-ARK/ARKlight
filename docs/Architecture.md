# ARKlight Installer — Architecture

This is the standing reference for how the installer is built. `Restarting
from zero.md` is the record of *how* the design landed here and stays as
history; this doc is the current state, kept in sync as implementation
proceeds. When the two disagree, this one wins.

---

## 1. Shell

Single HTML/CSS/JS codebase rendered through the OS's own webview
(WebView2 / WebKitGTK / WKWebView) via NeutralinoJS. No bundled Chromium,
no native-toolkit widget ceiling — the UI is a website, styled like one.

`neu build` cross-compiles Linux/Windows/macOS from one codebase.

GUI polish is a shipping requirement, not a follow-up pass. See
`Implementation.md` for where that lands in build order.

---

## 2. Backend

Detection, environment setup, and install logic are Python
(`detect.py` / `install.py`), called by the Neutralino shell rather than
reimplemented in JS. Two entry points:

- `install_system()` — system interpreter found → create a venv, install
  ARKlight into it.
- `install_private()` — no usable system interpreter → download a
  prebuilt CPython, install ARKlight directly into it, no venv.

Neither function's internal logic changes for this rebuild; only what
calls them does.

No Python-version compatibility filtering ships. One install target:
current stable PyPI release. An interpreter that genuinely can't run it
fails at the `pip install` step, loudly, rather than being filtered out
speculatively ahead of time.

---

## 3. Application Lifecycle

No daemon. No autostart entry, no tray icon, nothing resident between
runs. The installer opens, does one thing, and closes.

On launch:

```text
Launch → is ARKlight already installed?
    No  → Install flow
    Yes → Update / Repair / Uninstall flow
```

One binary, whole lifecycle, standard "maintenance mode" shape.

### Repair

Repair's first job is validating the existing install, not blindly
reinstalling over it. The specific failure mode it exists to catch:

- A system-Python install depends on the interpreter it was built
  against still existing at that path. If the user later deletes or
  upgrades their global Python, the venv's internal links point at
  nothing — `arklight` fails with a path error that gives the user no
  indication what actually broke.
- Repair checks whether that interpreter path is still valid.
  - **Valid** → normal repair path (reinstall/repair the venv contents
    against the interpreter that's still there).
  - **Invalid** → offer to pivot the install onto the private standalone
    CPython runtime — the same acquisition path `install_private()`
    already implements — rather than surfacing the broken path and
    leaving the user to work out a fix.

A private-runtime install has no equivalent failure mode: the
interpreter exists solely for ARKlight and isn't something a system
Python update or uninstall touches.

### Uninstall

The one step with OS-specific plumbing. Linux/macOS: the running binary
can delete itself, the OS holds the file open until the process exits.
Windows can't delete a running `.exe`, so uninstall there hands off to a
small detached helper spawned just before exit, which waits for the
parent process to close and then deletes the installer binary. Only
fires on the uninstall path.

---

## 4. Dependencies & Connectivity

CPython (private-runtime path) and ARKlight itself are fetched at
install time — nothing is vendored into the installer binary to make it
work offline. Bundling a CPython per OS/arch into the artifact would
undo the "small binary" property the shell choice depends on.

Before any filesystem change (install, update, or repair):

1. Check reachability of what the step actually needs (PyPI /
   python.org release endpoint — whatever `detect.py`/`install.py`
   already resolve versions and downloads against).
2. If unreachable: stop before touching the filesystem. No partial venv,
   no partially unpacked private CPython.
3. Surface the reason in the wizard itself — connection required because
   the runtime and package are downloaded, not bundled — with a retry.

---

## 5. Build & Packaging

`neu build` produces the per-OS portable binary. CPack wraps that output
into installable native packages (`.deb`/`.rpm`/AppImage on Linux,
`.msi` on Windows, `.dmg`/`.pkg` on macOS) from one `CMakeLists.txt` +
generator list. One GitHub Actions matrix: `neu build` per OS runner,
then CPack per runner, artifacts attached to the release.

---

## 6. Embedded Content Panel (deferred)

Not part of any current stage — there's no documentation site to point
this at yet. Recorded here so the shape is agreed before it's built,
rather than improvised later.

**The idea:** a supplementary panel in the wizard, separate from the
install flow, that can render either bundled local content (a packaged
docs page, the example site) or a live external page — project
documentation, portfolio — in an embedded view via the same OS webview
Neutralino already uses for the app itself. Nav buttons swap what's
loaded; nothing here is generated by the installer, it just points the
frame at one target or another.

**What makes this safe to add later without touching the rest of the
architecture:**

- It is strictly supplementary. It must never gate, block, or share
  state with install/update/repair/uninstall — those are the app;
  this is a waiting-room amenity.
- It is not the §4 connectivity check. §4 is a hard prerequisite: no
  install proceeds without it. This panel's connectivity is soft: if
  the live target doesn't load, it falls back to bundled local content
  and says nothing more dramatic than "showing the offline version."
  The install flow's behavior on a real offline machine is unaffected
  either way.
- It only loads a remote page when the user clicks to view it — nothing
  fetches on launch, on a timer, or in the background. That keeps it
  consistent with §3 (no phoning home) even though the feature involves
  the network.
- Whatever domain(s) it's allowed to load need to be explicit
  (Neutralino's webview isn't unrestricted by default, and shouldn't be
  made more permissive than this one panel needs).

**Sequencing:** this is Stage 4 work, and optional even within Stage 4
— it can land after the core wizard (Install / Update / Repair /
Uninstall) is done and styled, once there's an actual site to point it
at. Nothing else in this document depends on it existing.

---

## 7. What Stays Out of Scope

- No Python-version compatibility matrix maintained by the installer.
- No persistent process, service, or scheduled task of any kind.
- No offline install path — connectivity is a hard prerequisite, stated
  plainly rather than worked around.
- No installer-side ARKlight version pinning — always current stable
  PyPI, per the Version Policy in `README.md`.
