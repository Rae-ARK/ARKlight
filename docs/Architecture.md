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

## 6. Embedded Content Panel — Install-Time Attribution Rotation

Still Stage 4b, still supplementary — but no longer a pure "click to
view" side panel. The install/update path genuinely takes 30s–60s doing
work nobody can watch (venv creation, CPython download/unpack, `pip
install`), and that dead air is the actual moment a normal user is
looking at the screen. That's the natural place for attribution people
understand, without it turning into anything that resembles an ad or a
stall tactic.

**The idea:** while the progress bar for Install/Update/Repair advances,
the panel automatically rotates through:

- bundled local content (packaged docs pages, the example site), and
- the live ARKfolio portfolio page — https://rae-ark.horizonarkstudio.workers.dev/

rendered in the same embedded OS webview Neutralino already uses for
the app itself. What's on screen advances with real install
milestones (per detect/install step), not a fixed timer disconnected
from actual progress — nothing here is generated by the installer, it
just points the frame at bundled content or the live page in turn.

**What's unchanged from the original design:**

- Still strictly supplementary. It must never gate, block, or share
  state with install/update/repair/uninstall — those are the app; this
  is a waiting-room amenity, and the install proceeds at its own pace
  regardless of what the panel is showing or whether a given rotation's
  live fetch succeeded.
- Still not the §4 connectivity check. §4 is a hard prerequisite: no
  install proceeds without it. This panel's connectivity is soft — if
  the live page doesn't load for a given rotation, that slot silently
  falls back to bundled local content and moves on; no dramatic error
  state, no effect on the install itself.
- Domain allowlist stays explicit (Neutralino's webview isn't
  unrestricted by default, and shouldn't be made more permissive than
  this one panel needs).

**What's different:** loading is no longer gated behind a user click —
it's driven by install progress, since the point is filling wait time
that would otherwise sit empty. This narrows §3's "no phoning home"
guarantee rather than breaking it: the panel still never fetches
anything before an install/update/repair step is actually running
(nothing on launch, nothing idle, nothing between runs) — it just
doesn't wait for a click once that step has started, because that step
already required connectivity per §4. No new network dependency is
introduced; this is a display decision layered on a fetch that was
already happening.

**Sequencing:** unchanged — Stage 4b, landing after the core wizard
(Install / Update / Repair / Uninstall) is done and styled, once
ARKfolio is the real thing to point at.

---

## 7. ARK Bundle MIME Handling

Not a new feature — `.ark` bundles already register
`application/x-arklight-bundle` and route through `arklight-open`
(`installer/linux/opener/`), which hands an unsealed bundle straight to
the browser or unpacks a sealed one first. Two real gaps this stage
targets:

1. **Linux-only today.** The MIME/opener wiring
   (`arklight-bundle-mime.xml`, `arklight-bundle.desktop`,
   `install_opener()` in `launcher.py`) only runs on the Linux install
   path. Windows and macOS installs leave `.ark` double-clicks
   unhandled entirely. This is the actual gap the "write once, debug
   everywhere" framing points at: the association exists on the one OS
   it was built and tested on first, and is simply absent on the other
   two rather than broken on them.
2. **Sealed bundles touch disk to open.** `_unpack_and_open()` currently
   unpacks the full sealed archive into a `tempfile.mkdtemp()` directory
   on disk before pointing the browser at the extracted `index.html`.
   That leaves real files behind — for content the user likely sealed
   specifically because they didn't want it sitting around unencrypted.

**Fix direction:**

- Registration becomes a proper per-OS install step alongside
  `install_system()`/`install_private()`, not a Linux-specific side
  path: Windows via a registry ProgID + `.ark` extension association,
  macOS via `Info.plist` `CFBundleDocumentTypes`/Launch Services, Linux
  keeping its existing `xdg-mime` approach. Same one-shot,
  launch-triggered shape as the rest of the installer (§3) — nothing
  resident; the OS simply knows to invoke the opener when `.ark` is
  double-clicked or opened from a link.
- The opener stops writing unpacked sealed content to disk. Unpack
  target moves in-memory — decrypt/unpack into a buffer, hand that off
  to the default browser (short-lived local loopback endpoint or
  equivalent in-memory hand-off) — then the opener's one-shot run ends,
  same as it already does for the unsealed case. Nothing unpacked lands
  in a temp directory waiting to be cleaned up.

**Scope guard, consistent with §6 and the rest of this document:** this
is opener behavior, not a new resident process. The opener still runs
once per double-click and exits; "loads to RAM and hands off to the
browser" describes what happens inside that one short-lived run, not a
new background service.

---

## 8. What Stays Out of Scope

- No Python-version compatibility matrix maintained by the installer.
- No persistent process, service, or scheduled task of any kind.
- No offline install path — connectivity is a hard prerequisite, stated
  plainly rather than worked around.
- No installer-side ARKlight version pinning — always current stable
  PyPI, per the Version Policy in `README.md`.
- No disk-persisted unpacked sealed-bundle content from the `.ark`
  opener (§7) — in-memory hand-off only.
