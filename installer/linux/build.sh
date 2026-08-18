#!/usr/bin/env bash
# Build the ARKlight Installer for Linux: a standalone binary, plus
# .deb, .rpm, and AppImage packages wrapping it.
#
# Usage: installer/linux/build.sh [deb|rpm|appimage|all]
#
# Requires: python3, pip, pyinstaller (installed into a throwaway venv
# below), and for packaging: dpkg-deb (deb), rpmbuild (rpm),
# appimagetool (appimage). GitHub Actions installs these; see
# .github/workflows/installer-linux.yml.
set -euo pipefail

TARGET="${1:-all}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GUI_DIR="$ROOT_DIR/installer/gui"
LINUX_DIR="$ROOT_DIR/installer/linux"
BUILD_DIR="$ROOT_DIR/build/linux"
DIST_DIR="$ROOT_DIR/dist"
VERSION="$(python3 -c "import tomllib,sys; print(tomllib.load(open('$GUI_DIR/pyproject.toml','rb'))['project']['version'])")"
ARCH="$(uname -m)"

mkdir -p "$BUILD_DIR" "$DIST_DIR"

echo "==> Building arklight-installer $VERSION for linux-$ARCH"

echo "==> Setting up build environment"
python3 -m venv "$BUILD_DIR/venv"
source "$BUILD_DIR/venv/bin/activate"
pip install --upgrade pip >/dev/null
pip install pyinstaller >/dev/null

echo "==> Freezing with PyInstaller"
cd "$GUI_DIR"
pyinstaller --noconfirm --distpath "$BUILD_DIR/pyinstaller-dist" \
    --workpath "$BUILD_DIR/pyinstaller-work" arklight_installer.spec
deactivate

FROZEN_BIN="$BUILD_DIR/pyinstaller-dist/arklight-installer"
if [[ ! -f "$FROZEN_BIN" ]]; then
    echo "PyInstaller did not produce $FROZEN_BIN" >&2
    exit 1
fi

build_deb() {
    echo "==> Building .deb"
    bash "$LINUX_DIR/debian/build-deb.sh" "$FROZEN_BIN" "$VERSION" "$ARCH" "$DIST_DIR"
}

build_rpm() {
    echo "==> Building .rpm"
    bash "$LINUX_DIR/rpm/build-rpm.sh" "$FROZEN_BIN" "$VERSION" "$ARCH" "$DIST_DIR"
}

build_appimage() {
    echo "==> Building AppImage"
    bash "$LINUX_DIR/appimage/build-appimage.sh" "$FROZEN_BIN" "$VERSION" "$ARCH" "$DIST_DIR"
}

case "$TARGET" in
    deb) build_deb ;;
    rpm) build_rpm ;;
    appimage) build_appimage ;;
    all)
        build_deb
        build_rpm
        build_appimage
        ;;
    *)
        echo "Unknown target: $TARGET (expected deb|rpm|appimage|all)" >&2
        exit 1
        ;;
esac

echo "==> Done. Artifacts in $DIST_DIR"
ls -la "$DIST_DIR"
