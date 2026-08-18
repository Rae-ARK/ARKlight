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
from pathlib import Path

from .install import DEFAULT_BIN_DIR

DESKTOP_ENTRY_DIR = Path.home() / ".local" / "share" / "applications"


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
