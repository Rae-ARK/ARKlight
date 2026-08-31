"""
Android packaging backend -- vendored/templated runtime source.

Not a compiler `Backend` (`arklight.backend.base.Backend`, IR ->
output files) -- this package holds Kotlin/Gradle/XML *template*
content for `arklight android scaffold` (`arklight.cli.android`), the
same "generate project files from a build-dir, never touch the
parser/ir/HTML/CSS/JS backends" role `arklight.packer` and
`arklight.pwa` already play for `.ark` bundles and PWA manifests
respectively. It lives under `arklight.backend` rather than next to
those two because `docs/Backends/ANDROID-BACKEND-IMPLEMENTATION.md`
("Open questions for Stage 0") names `arklight/backend/android/
runtime/` as this module's candidate home up front.

See `arklight.backend.android.runtime` for the actual template
content, and `arklight.cli.android` for the CLI command that turns it
into files on disk.
"""
