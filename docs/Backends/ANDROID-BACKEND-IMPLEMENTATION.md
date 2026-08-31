# Android Backend Implementation: Staged Order

Status: **Stage 0 in progress**, Stages 1-4 not started. This file
does not restate the design already written in `docs/DESIGN-NOTES.md`
("v0.0438: Android backend -- androidx.webkit.WebViewAssetLoader
packaging") -- it exists only to turn that section's prose "Staging"
list into a trackable table, the same role `REFACTOR-INDEX.md` plays
for the HTML/HTMX/JS refactor track, and to pin down the one external
dependency every stage below builds on: the existing Viewer app.

## The existing app this evolves

**[`ARKlight-Viewer-for-Android-Devices`](https://github.com/Rae-ARK/ARKlight-Viewer-for-Android-Devices)**
-- Apache-2.0, already a working Android `.ark`-bundle viewer built on
AndroidX `WebView`. Per `DESIGN-NOTES.md`'s "Updated direction" note,
this backend's job is **evolving that repo into ARKlight's Android
runtime**, not writing a second Android project from scratch. Its
`app/src/main/java/com/arklight/viewer/` package already gives Stage 0
most of what it needs to split out:

| File | What it does today | Runtime role going forward |
|---|---|---|
| `MainActivity.kt` | Viewer-mode `Activity`: bundle picker (`ActivityResultContracts.OpenDocument`), toolbar/menu, `WebViewAssetLoader` wired to two path handlers (`/entry/` for the instant-render entry page, `/site/` for the extracted full site), passphrase prompt dialog. | Splits into the shared `WebViewAssetLoader`/origin-handling core (kept) + Viewer-mode-only UI (bundle picker, menu, passphrase dialog -- stays Viewer-only, does not belong in Application mode per `DESIGN-NOTES.md`'s "if a visible element exists solely because the app used to be a browser for arbitrary bundles, it doesn't belong in application mode" rule). |
| `ArkBundle.kt` | Splits a `.ark` file at its `</html>\n` boundary marker (mirrors `arklight/packer/bundle.py`'s split point); unseals + unzips the archive half, preferring an in-RAM `SiteBacking.Ram` and falling back to `SiteBacking.Disk` under `MemoryGuard`'s guidance. | Already isolated from the Activity -- reusable as-is by both Viewer mode (arbitrary `.ark` files) and Application mode (one bundle baked in at build time), no split needed. |
| `ArkSeal.kt` | Unseals a sealed `.ark` archive half (embedded-key or passphrase-derived), mirroring `arklight/packer/bundle.py`'s sealing format. | Same as `ArkBundle.kt` -- already a standalone, reusable unit. |
| `MemoryGuard.kt` | Decides RAM vs. disk backing for an extraction based on available headroom. | Already standalone; reusable as-is. |
| `ArkViewerApplication.kt` | `Application` subclass (process-wide init). | Becomes the runtime's shared `Application` base, or stays Viewer-mode-specific depending on what Stage 0's split finds Application-mode needs -- open question, see "Open questions for Stage 0" below. |
| `AndroidManifest.xml` | Viewer-mode manifest: intent filters for opening `.ark`/`.zip`-mimetype files from Files/Downloads/share sheets, app icon/label. | Application mode needs its own manifest (no bundle-open intent filters, fixed single-purpose launcher icon/label from `arklight.config.py`'s `"android"` section) -- generated per-project by Stage 1's `scaffold`, not shared with Viewer mode's manifest. |

`ArkBundle.kt`/`ArkSeal.kt`/`MemoryGuard.kt` needing no split (they're
already decoupled from `MainActivity`) is exactly what
`DESIGN-NOTES.md` means by "already separates the bundle/sealing
concerns into their own files ... rather than mixing them into the
activity" -- Stage 0's real work is narrower than a from-scratch
runtime extraction, concentrated in `MainActivity.kt`'s Viewer-mode UI
vs. shared-runtime split.

## Staged order

Mirrors `docs/DESIGN-NOTES.md`'s "Staging" list under "v0.0438: Android
backend" 1:1 -- this table adds status tracking and file-level
pointers, it does not renumber or reorder anything from that section.

| # | Stage | What | Toolchain required | Depends on | Status |
|---|---|---|---|---|---|
| 0 | Promote the Viewer repo | Split `MainActivity.kt` into a shared runtime piece (`WebViewAssetLoader` setup, the `/entry/` + `/site/` path handlers, origin handling) and a thin Viewer-mode-only shell (bundle picker, menu, passphrase dialog) on top of it, per the file-by-file table above. `ArkBundle.kt`/`ArkSeal.kt`/`MemoryGuard.kt` carry over unchanged. Lands inside `arklight`'s own tree as the packaging backend's template/runtime source (exact module path TBD by whoever implements the split -- candidate: `arklight/backend/android/runtime/`), not as a fork of the Viewer repo -- the Viewer repo stays the standalone app; this backend vendors/templates from the shared pieces it factors out. | None -- pure refactor of existing Kotlin | none | **In progress** |
| 1 | `arklight android scaffold <build-dir> -o <project-dir>` | Templating only: generate the Kotlin/Gradle/manifest project shell from Stage 0's runtime pieces, in **Application mode** (one bundle baked in at build time, no Viewer chrome), copy `<build-dir>` into `app/src/main/assets/`, wire `MainActivity` to Stage 0's shared `WebViewAssetLoader` setup pointed at those assets. Reads app identity from `arklight.config.py`'s `"android"` section (`app_name`/`package_id`/`version_name`/`version_code`/`icon`/`splash`/`orientation`/`edge_to_edge` -- see `DESIGN-NOTES.md`'s "App identity metadata" subsection for the full key list and defaults). | None -- genuinely zero-dependency, per `DESIGN-NOTES.md`'s "The toolchain is unavoidable" correction (templating source files needs nothing; *building* them is what needs a JDK, which is Stage 2's problem, not this one's) | Stage 0 | Not started |
| 2 | `arklight android build <build-dir> -o <project-dir>` | Runs Stage 1, then shells out to the generated project's `./gradlew assembleDebug` via `subprocess`; catches a missing-JDK `FileNotFoundError`/`OSError` specifically and prints the actionable message `DESIGN-NOTES.md`'s "Graceful failure when no JDK is present" subsection specifies, rather than a raw traceback. | JDK + Android SDK + network (Gradle/AGP/AndroidX resolution) -- on the *user's* machine, not ARKlight's own install | Stage 1 | Not started |
| 3 | `arklight android build --install` | Stage 2, then `adb install` onto a connected device/emulator if `adb` is on `PATH`; same graceful-`FileNotFoundError` handling if not. | Stage 2's toolchain + `adb` + a connected device/emulator | Stage 2 | Not started |
| 4 | `arklight android build --release` | Stage 2 targeting `assembleRelease` instead of `assembleDebug`; signing config (keystore path/passwords) passed through to Gradle as the user's own concern -- ARKlight does not manage keystores or credentials on the user's behalf (see `DESIGN-NOTES.md`'s "Explicitly out of scope" list). | Stage 2's toolchain + a signing config the user supplies | Stage 2 | Not started |

Each rung is independently useful and additive, same "`arklight pack`
runs after `build`, never touching the compiler internals" shape
`arklight.packer` already established -- `arklight android` reads an
existing `build-dir` and never imports the parser/ir/HTML/CSS/JS
backend internals it's packaging, per `DESIGN-NOTES.md`'s "A staged
CLI ladder" subsection.

## Open questions for Stage 0

Left open on purpose rather than pre-decided here -- these belong in
the implementation itself once someone is actually doing the
`MainActivity.kt` split, not settled speculatively in a staging doc:

- **Exact module path for the vendored/templated runtime source**
  inside `arklight`'s own tree (candidate above:
  `arklight/backend/android/runtime/`) -- needs to fit however
  `arklight.cli.scaffold`'s existing template-file convention
  (`arklight/cli/templates/`) already stores non-Python template
  content, or a new convention if that one doesn't fit Kotlin/Gradle
  files well.
- **Whether `ArkViewerApplication.kt` is shared or Viewer-mode-only.**
  Its current responsibilities need auditing against the "if Android
  itself requires or benefits from it, it stays in the runtime both
  modes share" rule from `DESIGN-NOTES.md` before deciding.
- **Packed `.ark` vs. unpacked tree for Application mode's baked-in
  bundle.** `DESIGN-NOTES.md` allows either ("drop it into the
  runtime's `assets/` folder as either a `site.ark` or an unpacked
  `index.html` + `pages/` + `assets/` tree") -- Stage 1 needs to pick
  one default. An unpacked tree skips `ArkBundle`/`ArkSeal` entirely
  for the common case (no runtime unsealing needed for a bundle that
  was never sealed to begin with), which is the simpler default;
  packing/sealing stays available as an opt-in for anyone who wants
  the same distributable-bundle protections Application mode's baked
  assets would otherwise skip.

## Explicitly out of scope

Same list `DESIGN-NOTES.md`'s "v0.0438" section already states --
repeated here only so this table doesn't imply any of it is
Stage-0-through-4 work: iOS (`WKWebView`/`WKURLSchemeHandler` is a
separate design), any native-plugin/push/deep-link bridge beyond
serving assets, Play Store signing/publishing automation beyond
passing signing config through to Gradle, and any change to the
HTML/CSS/JS backends themselves -- this is a packaging backend that
consumes an existing `build-dir` as opaque input, the same way
`arklight.packer` already does for `.ark` bundles.
