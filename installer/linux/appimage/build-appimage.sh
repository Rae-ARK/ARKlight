#!/usr/bin/env bash
# Assemble and build ARKlight-Installer-<version>-<arch>.AppImage from a
# frozen PyInstaller binary. Requires appimagetool on PATH (fetched by the
# GitHub Actions workflow). Called by installer/linux/build.sh.
set -euo pipefail

FROZEN_BIN="$1"
VERSION="$2"
ARCH="$3"      # uname -m, e.g. x86_64
DIST_DIR="$4"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LINUX_DIR="$(dirname "$SCRIPT_DIR")"
APPDIR="$(mktemp -d)/ARKlight-Installer.AppDir"
trap 'rm -rf "$(dirname "$APPDIR")"' EXIT

mkdir -p "$APPDIR/usr/bin"
install -m 0755 "$FROZEN_BIN" "$APPDIR/usr/bin/arklight-installer"

cp "$LINUX_DIR/arklight-installer.desktop" "$APPDIR/arklight-installer.desktop"

# AppImages require a top-level icon; fall back to a minimal placeholder if
# no branded icon has been added to the repo yet.
ICON_SRC="$LINUX_DIR/arklight-installer.png"
if [[ -f "$ICON_SRC" ]]; then
    cp "$ICON_SRC" "$APPDIR/arklight-installer.png"
else
    python3 - "$APPDIR/arklight-installer.png" <<'PY'
import struct, sys, zlib
path = sys.argv[1]
w = h = 1
def chunk(tag, data):
    c = tag + data
    return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c))
png = b'\x89PNG\r\n\x1a\n'
png += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
raw = b'\x00' + b'\x22\x22\x22'
png += chunk(b'IDAT', zlib.compress(raw))
png += chunk(b'IEND', b'')
open(path, 'wb').write(png)
PY
fi

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/arklight-installer" "$@"
EOF
chmod +x "$APPDIR/AppRun"

mkdir -p "$DIST_DIR"
OUTPUT="$DIST_DIR/ARKlight-Installer-${VERSION}-${ARCH}.AppImage"
ARCH="$ARCH" appimagetool "$APPDIR" "$OUTPUT"
echo "Built $OUTPUT"
