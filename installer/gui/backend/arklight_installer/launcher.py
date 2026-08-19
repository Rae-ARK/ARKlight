"""Create the platform-specific launch configuration.

On Linux this means a small wrapper script on the user's PATH (following
the XDG convention of `~/.local/bin`) plus an optional `.desktop` entry so
`arklight` shows up in application launchers/menus. Windows and macOS
variants of this module (not included here) create the equivalent
PATH/registry entries for their platforms.
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

from .install import DEFAULT_BIN_DIR

DESKTOP_ENTRY_DIR = Path.home() / ".local" / "share" / "applications"
MIME_PACKAGE_DIR = Path.home() / ".local" / "share" / "mime" / "packages"


def create_launcher(arklight_entry: Path, bin_dir: Path = DEFAULT_BIN_DIR) -> Path:
    """Write a wrapper script `bin_dir/arklight` that execs the real entry point.

    Returns the wrapper's path.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper = bin_dir / "arklight"
    wrapper.write_text(
        "#!/bin/sh\n"
        f'exec "{arklight_entry}" "$@"\n'
    )
    mode = wrapper.stat().st_mode
    wrapper.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return wrapper


def path_needs_update(bin_dir: Path = DEFAULT_BIN_DIR) -> bool:
    """Return True if `bin_dir` is not already on the user's PATH."""
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    return str(bin_dir) not in path_entries


def _opener_assets_dir() -> Path:
    """Directory containing arklight-open, its .desktop entry, and its MIME
    type XML: installer/linux/opener, two directories up from this file."""
    return Path(__file__).resolve().parents[2] / "linux" / "opener"


def install_opener(bin_dir: Path = DEFAULT_BIN_DIR) -> Path:
    """Install the arklight-open bundle handler to `bin_dir`. Returns its path.

    This is a separate wrapper from the `arklight` launcher created by
    `create_launcher`: it's the program the desktop environment runs when
    the user double-clicks a `.ark` file, not something a user types
    themselves.
    """
    src = _opener_assets_dir() / "arklight-open"
    bin_dir.mkdir(parents=True, exist_ok=True)
    dest = bin_dir / "arklight-open"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    mode = dest.stat().st_mode
    dest.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dest


def register_bundle_mime(opener_path: Path) -> None:
    """Register `application/x-arklight-bundle` and point it at `opener_path`
    as the default handler, so double-clicking a `.ark` file runs
    arklight-open instead of the desktop reporting an unrecognized file
    format.

    Each step is best-effort: a missing `xdg-mime`/`update-mime-database`
    (unusual, but possible on a minimal desktop-less install) means the
    file association silently doesn't get wired up rather than the whole
    ARKlight install failing over an optional integration.
    """
    assets = _opener_assets_dir()

    MIME_PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    mime_xml_dest = MIME_PACKAGE_DIR / "arklight-bundle.xml"
    mime_xml_dest.write_text(
        (assets / "arklight-bundle-mime.xml").read_text(encoding="utf-8"), encoding="utf-8"
    )

    DESKTOP_ENTRY_DIR.mkdir(parents=True, exist_ok=True)
    desktop_src = (assets / "arklight-bundle.desktop").read_text(encoding="utf-8")
    # The source .desktop file assumes `arklight-open` is already on PATH.
    # Point it at the actual installed wrapper instead, since bin_dir may
    # not be on PATH yet at the moment someone double-clicks a bundle.
    desktop_src = desktop_src.replace("Exec=arklight-open %f", f"Exec={opener_path} %f")
    (DESKTOP_ENTRY_DIR / "arklight-bundle.desktop").write_text(desktop_src, encoding="utf-8")

    for cmd in (
        ["update-mime-database", str(MIME_PACKAGE_DIR.parent)],
        ["update-desktop-database", str(DESKTOP_ENTRY_DIR)],
        ["xdg-mime", "default", "arklight-bundle.desktop", "application/x-arklight-bundle"],
    ):
        try:
            subprocess.run(cmd, check=False, capture_output=True)
        except (OSError, FileNotFoundError):
            pass


def create_desktop_entry(wrapper: Path) -> Path:
    """Write a `.desktop` file so ARKlight appears in application menus."""
    DESKTOP_ENTRY_DIR.mkdir(parents=True, exist_ok=True)
    entry_path = DESKTOP_ENTRY_DIR / "arklight.desktop"
    entry_path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=ARKlight\n"
        "Comment=Python-first compiler for building static websites\n"
        f"Exec={wrapper} %F\n"
        "Terminal=true\n"
        "Categories=Development;\n"
    )
    return entry_path
