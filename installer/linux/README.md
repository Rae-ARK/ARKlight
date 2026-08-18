# ARKlight Installer — Linux

This directory packages the shared installer codebase in
`installer/gui/arklight_installer/` for Linux. There is no
Linux-specific installer *logic* here — detection, download, venv/private
runtime setup, and launcher creation all live in `installer/gui/` and are
identical across Windows, Linux, and macOS. This directory only turns that
codebase into the package formats Linux users expect.

## What gets built

Running `installer/linux/build.sh all` produces three artifacts in
`dist/`:

| Format      | Where it's built             | Fits                                   |
|-------------|-------------------------------|-----------------------------------------|
| `.deb`      | `installer/linux/debian/`     | Debian, Ubuntu, and derivatives         |
| `.rpm`      | `installer/linux/rpm/`        | Fedora, openSUSE, RHEL and derivatives  |
| `.AppImage` | `installer/linux/appimage/`   | Any distro, no installation required    |

All three wrap the same standalone binary: `installer/gui/` frozen with
PyInstaller (`arklight_installer.spec`), which bundles its own Python
interpreter so the installer itself has no system-Python dependency. (The
Python detection *inside* the installer is a separate, later step — it's
about the Python ARKlight will run on, not the Python the installer runs
on.)

## Building locally

```sh
# all three formats
installer/linux/build.sh all

# just one
installer/linux/build.sh deb
installer/linux/build.sh rpm
installer/linux/build.sh appimage
```

Requirements: `python3`, `dpkg-deb` (for `.deb`), `rpmbuild` (for `.rpm`),
and `appimagetool` on `PATH` (for `.AppImage`). `pyinstaller` is installed
automatically into a throwaway build venv.

## Building in CI

`.github/workflows/installer-linux.yml` builds all three formats on every
push to `installer` that touches `installer/**`, on pull requests, on
manual dispatch, and attaches them to GitHub releases. It builds for both
`x86_64` and `aarch64` from the same workflow using a runner matrix — no
per-arch code, just a different runner.

## `.ark` bundle file association

The wizard's last step (opt-in, checked by default) fixes the "unrecognized
file format" problem for `.ark` bundles double-clicked in a file manager:

- **Unsealed bundles** open directly in the default browser. A `.ark` file
  is valid HTML up to its `</html>` tag (see `arklight/packer/bundle.py`
  on the `main` branch), so nothing else is needed.
- **Sealed bundles** open a small password dialog first
  (`installer/linux/opener/arklight-open`). Confirming it runs `arklight
  unpack` into a temp directory and opens the *extracted* `index.html`
  instead, so sealed bundles opened this way get a fully working copy —
  assets included — not just the degraded in-place polyglot view.
  Embedded-key-sealed bundles (the default `arklight pack` mode) don't
  need a real password, so that dialog shows a single "Unlock and Open"
  button instead of a password field; only passphrase-sealed bundles
  prompt for one.

This is wired up via `installer/gui/arklight_installer/launcher.py`
(`install_opener` / `register_bundle_mime`), which installs
`arklight-open` next to the `arklight` launcher and registers
`application/x-arklight-bundle` with `xdg-mime` using the MIME
definition and desktop entry in `installer/linux/opener/`. All three
files there (`arklight-open`, `arklight-bundle.desktop`,
`arklight-bundle-mime.xml`) are bundled into the frozen installer binary
via `datas` in `arklight_installer.spec`, so they're available at
`sys._MEIPASS` even when running as a packaged `.deb`/`.rpm`/AppImage.

The opener intentionally doesn't import `arklight.packer` — it only peeks
the fixed-offset bytes needed to classify a bundle as plain, embedded-key
sealed, or passphrase sealed, then shells out to the already-installed
`arklight` CLI for the actual unpack. That keeps it working regardless of
which interpreter it happens to run under.

## Adding a real icon

`installer/linux/arklight-installer.desktop` references an
`arklight-installer` icon. Drop a `arklight-installer.png` next to it and
the `.deb`/`.rpm` icon paths and the AppImage build in
`installer/linux/appimage/build-appimage.sh` will pick it up automatically;
until then, the AppImage build generates a minimal placeholder so the build
doesn't fail.
