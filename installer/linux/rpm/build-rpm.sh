#!/usr/bin/env bash
# Assemble and build arklight-installer-<version>.<arch>.rpm from a frozen
# PyInstaller binary. Called by installer/linux/build.sh.
set -euo pipefail

FROZEN_BIN="$1"
VERSION="$2"
ARCH="$3"      # uname -m, e.g. x86_64
DIST_DIR="$4"

case "$ARCH" in
    x86_64) RPM_ARCH="x86_64" ;;
    aarch64) RPM_ARCH="aarch64" ;;
    *) echo "Unsupported arch for .rpm: $ARCH" >&2; exit 1 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LINUX_DIR="$(dirname "$SCRIPT_DIR")"
RPMBUILD_ROOT="$(mktemp -d)"
trap 'rm -rf "$RPMBUILD_ROOT"' EXIT

mkdir -p "$RPMBUILD_ROOT"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

rpmbuild --define "_topdir $RPMBUILD_ROOT" \
    --define "_arklight_version $VERSION" \
    --define "_arklight_rpm_arch $RPM_ARCH" \
    --define "_arklight_frozen_bin $FROZEN_BIN" \
    --define "_arklight_desktop_file $LINUX_DIR/arklight-installer.desktop" \
    --target "$RPM_ARCH" \
    -bb "$SCRIPT_DIR/arklight-installer.spec"

BUILT_RPM="$(find "$RPMBUILD_ROOT/RPMS" -name '*.rpm' | head -n1)"
if [[ -z "$BUILT_RPM" ]]; then
    echo "rpmbuild did not produce an .rpm file" >&2
    exit 1
fi

mkdir -p "$DIST_DIR"
cp "$BUILT_RPM" "$DIST_DIR/"
echo "Built $DIST_DIR/$(basename "$BUILT_RPM")"
