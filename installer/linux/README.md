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

## Adding a real icon

`installer/linux/arklight-installer.desktop` references an
`arklight-installer` icon. Drop a `arklight-installer.png` next to it and
the `.deb`/`.rpm` icon paths and the AppImage build in
`installer/linux/appimage/build-appimage.sh` will pick it up automatically;
until then, the AppImage build generates a minimal placeholder so the build
doesn't fail.
