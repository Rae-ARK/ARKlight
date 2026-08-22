# ARKlight Installer — Readiness Checklist

**Scope:** what's needed to take the `installer` branch from "builds
successfully in CI" to "safe to hand a stranger a GitHub Release link."
Every item below was checked directly against the current source
(`Rae-ARK/ARKlight@installer`) or a live web search done while writing
this — nothing here is generic installer-checklist boilerplate.

---

## 1. Dev-mode config left on — fix before any tagged release

**`installer/gui/neutralino.config.json`, `modes.window`:**

```json
"enableInspector": true,
"hidden": false,
"exitProcessOnClose": false
```

- **`enableInspector: true`** — confirmed via Neutralino's own docs:
  this is the literal flag that *"automatically opens the developer
  tools window on startup."* This is the standard `neu create`
  scaffold default; it needs to be flipped to `false` before a real
  build. This is very likely also the root cause of "the close button
  doesn't work" — a separate devtools window may be what's actually
  keeping the process alive after the main window closes. **Test
  `enableInspector: false` alone first**, before touching anything
  else, and see if the close-button symptom disappears with it.
- **`hidden: false`** — Neutralino's own tracked issue on startup
  time (#1217) documents ~1–1.5s to first paint with a visible blank/
  white window during that gap on a plain static page. The documented
  workaround is `"hidden": true` + an explicit `Neutralino.window.show()`
  once the first real paint is ready. Not applied here.
- **`exitProcessOnClose: false`** — this one is *not* obviously a bug
  by itself. `main.js` already registers a real handler
  (`Neutralino.events.on('windowClose', onWindowClose)` →
  `Neutralino.app.exit()`), which is the documented pattern for apps
  that want to intercept the close event (e.g. to confirm before
  quitting) rather than let the OS kill the process unconditionally.
  Leave this as-is unless `enableInspector: false` alone doesn't fix
  the close-button symptom — then look here next.

**Also worth doing:** add `singleInstance`-equivalent protection by
hand. Neutralino has no built-in single-instance guard (open feature
request, unresolved upstream — issue #901). For most apps that's a
minor annoyance; for *this* app it's a real risk — two installer
processes writing to `~/.local/share/arklight` (or the platform
equivalent) concurrently during an install is a corruption path, not
just a UX wrinkle. Add an explicit lock-file check in
`checkInstallState()`.

---

## 2. No integrity verification on the downloaded Python runtime

**`installer/gui/backend/arklight_installer/install.py`,
`_download_private_cpython`:**

- Fetches the latest `python-build-standalone` release via the GitHub
  API (over HTTPS — that part's fine), then does
  `urllib.request.urlretrieve(asset["browser_download_url"], archive_path)`
  and extracts it with **zero checksum or signature verification**.
  This is an executable Python runtime landing on the user's disk with
  no integrity check between "GitHub said this is the URL" and
  "we ran it." At minimum, verify against the SHA-256 the GitHub
  Releases API already returns for the asset (or `python-build-
  standalone`'s own published checksums file, if it publishes one)
  before extracting anything.
- **`tf.extractall(dest_dir)`** with no `filter=` argument. Python's
  own `tarfile` docs flag unfiltered `extractall()` as unsafe against
  a maliciously crafted archive (path traversal via `../` entries) —
  this is exactly why Python 3.12+ added the `filter` parameter and
  emits a `DeprecationWarning` on unfiltered use. This codebase is
  running Python 3.12 already (confirmed locally), so
  `tf.extractall(dest_dir, filter="data")` is a one-line fix, not a
  version-support tradeoff.

This is the same principle the project's own `ADI` design doc (a
different but related piece of this ecosystem) already states for
itself: *"an incomplete or incorrectly verified artifact must never
become an active cached dependency."* Right now the installer doesn't
hold itself to that standard yet.

---

## 3. The "license" shown in the Windows/macOS installer UI isn't a license

**`installer/CMakeLists.txt`:**

```cmake
configure_file("${CMAKE_CURRENT_SOURCE_DIR}/../README.md" "${_ark_license_txt}" COPYONLY)
set(CPACK_RESOURCE_FILE_LICENSE "${_ark_license_txt}")
```

There is no `LICENSE` file anywhere in this repo (checked directly —
`find . -iname "LICENSE*"` returns nothing). The CMake comment is
honest about *why* it's using `README.md` (WiX/productbuild only
accept `.txt`/`.rtf`-family files, and `README.md`'s extension fails
both generators) — but the actual content a Windows MSI or macOS pkg
installer shows the user in its license-acceptance screen is the
project README, not license terms. ARKlight's own main repo has a
real `LICENSE` (GPLv3 + an "Additional Terms" addendum with a real
attribution requirement, per earlier review of that repo) — this repo
needs its own equivalent `LICENSE` file, copied into a `.txt` the same
way, rather than substituting the README.

---

## 4. No code signing anywhere in the release pipeline

Checked `.github/workflows/installer-build.yml` directly — it builds
and packages for all three OSes (WIX/.msi, DragNDrop+productbuild/
.dmg+.pkg, DEB/RPM/AppImage) and attaches them straight to a GitHub
Release on an `installer-v*` tag. **No signing step exists for any
platform.** What this means concretely, verified against current
requirements for both OSes:

- **Windows:** an unsigned `.msi` triggers *"Windows protected your
  PC"* SmartScreen warnings by default. Signing with even a standard
  (OV) certificate helps, but SmartScreen reputation is **not
  automatic on signing alone** — it builds over time based on download
  volume under a consistent signing identity; a brand-new signed
  binary can still warn on its first releases. There's no way around
  this except: sign consistently, keep the same certificate across
  releases, and expect early-adopter friction regardless.
- **macOS:** as of the current Gatekeeper model, signing and
  notarization are **two separate steps, both required** — a signed-
  but-not-notarized `.pkg`/`.dmg` is still blocked by Gatekeeper, and
  notarization does not substitute for signing. This needs an active
  Apple Developer ID (paid program membership), `notarytool` submission
  as a CI step after `productbuild`/`hdiutil`, and `stapler staple` on
  the result so Gatekeeper can verify offline. Without this, macOS
  users get a "cannot check this app for malicious software" block, not
  just a warning — for a `.pkg` installer specifically (not just the
  `.app` inside it), current reports (Aug 2026 developer forum thread)
  indicate this has recently gotten *more* strict on newer macOS
  versions, not less — this is worth re-verifying against Apple's
  current docs close to actual release time, not assumed stable from
  this checklist alone.
- **Linux:** no signing blocker exists for `.deb`/`.rpm`/AppImage in
  the same sense — no OS-level Gatekeeper/SmartScreen equivalent blocks
  installation. GPG-signing the `.deb`/`.rpm` repo metadata is still
  good practice if these are ever hosted in an apt/dnf repo rather than
  downloaded standalone from a GitHub Release, but it's not a hard
  blocker the way the other two platforms are.

**Bottom line: this is the single largest gap between "builds in CI"
and "a stranger can install this without their OS actively fighting
them."** Signing/notarization requires paid developer program
enrollment on both Windows and macOS and CI secrets management for the
certificates — real cost and real setup time, not a quick fix, and
worth scoping as its own separate piece of work before a public
release tag.

---

## 5. Missing platform icons — already self-flagged, still open

`CMakeLists.txt` already has honest inline comments about this rather
than silently working around it:

```cmake
# NOTE: no .ico bundled yet (only resources/icons/appIcon.png exists) —
# WIX/CPACK_PACKAGE_ICON left unset until one is added. Real gap, not
# silently worked around.
```
```cmake
# NOTE: no .icns bundled yet — same gap as the Windows .ico, left
# unset rather than faked.
```

Both are real, both are small (generate a `.ico`/`.icns` from the
existing `appIcon.png`), and both are worth doing before a real release
since a generic default icon in the taskbar/dock is a strong "this
looks unfinished" signal to a new user.

---

## 6. Self-delete-on-uninstall isn't wired to the real packaged binary yet

`maintenance.py` and `main.js` both have matching comments:

> *"packaged single-binary artifact to point it at until Stage 3."*

This comment predates the CMakeLists/CI work — Stage 3 packaging
**now exists** (confirmed: real CPack config, real CI job producing
real `.msi`/`.dmg`/`.deb`/`.rpm`/AppImage artifacts), but the runtime
uninstall logic hasn't been updated to point at the actual installed
binary path each packaging format produces. This is a real, findable
gap: the comments are stale relative to what's actually been built
since they were written, and the Windows-can't-delete-a-running-.exe
helper-script logic (correctly designed in `Restarting from zero.md`)
still needs the real path wired in before uninstall actually works
end to end on a packaged install.

---

## Priority order, if only some of this gets done before a release tag

1. **§1** (`enableInspector`, `hidden`) — trivial, one-line config
   changes, fixes the two bugs you already noticed firsthand.
2. **§4** (signing) — the actual release blocker. Nothing else here
   matters if the installer gets blocked or scare-screened by the OS
   before a user can even run it.
3. **§2** (checksum + `tarfile` filter) — small in code size, large in
   consequence if skipped; this is the one item on this list with
   real security stakes, not just polish.
4. **§3** (real `LICENSE` file) — small, but currently means every
   Windows/macOS installer shows the wrong document as "the license."
5. **§5 / §6** — cosmetic and completeness gaps respectively; lowest
   urgency, but both already correctly self-documented in-repo as
   known-open rather than silently skipped.
