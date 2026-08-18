#!/usr/bin/env bash
# Assemble and build arklight-installer_<version>_<arch>.deb from a frozen
# PyInstaller binary. Called by installer/linux/build.sh; not meant to be
# run standalone (though it can be, given the same four arguments).
set -euo pipefail

FROZEN_BIN="$1"
VERSION="$2"
ARCH="$3"      # uname -m, e.g. x86_64
DIST_DIR="$4"

case "$ARCH" in
    x86_64) DEB_ARCH="amd64" ;;
    aarch64) DEB_ARCH="arm64" ;;
    *) echo "Unsupported arch for .deb: $ARCH" >&2; exit 1 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LINUX_DIR="$(dirname "$SCRIPT_DIR")"
PKG_ROOT="$(mktemp -d)"
trap 'rm -rf "$PKG_ROOT"' EXIT

mkdir -p "$PKG_ROOT/DEBIAN"
mkdir -p "$PKG_ROOT/usr/bin"
mkdir -p "$PKG_ROOT/usr/share/applications"

install -m 0755 "$FROZEN_BIN" "$PKG_ROOT/usr/bin/arklight-installer"
install -m 0644 "$LINUX_DIR/arklight-installer.desktop" \
    "$PKG_ROOT/usr/share/applications/arklight-installer.desktop"

sed -e "s/__VERSION__/$VERSION/" -e "s/__DEB_ARCH__/$DEB_ARCH/" \
    "$SCRIPT_DIR/control" > "$PKG_ROOT/DEBIAN/control"

OUTPUT="$DIST_DIR/arklight-installer_${VERSION}_${DEB_ARCH}.deb"
dpkg-deb --build --root-owner-group "$PKG_ROOT" "$OUTPUT"
echo "Built $OUTPUT"
