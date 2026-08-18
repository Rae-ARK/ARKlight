"""Install ARKlight into either a system-Python virtual environment or a
private, prebuilt CPython runtime.

This module contains no OS-specific branching beyond what `pathlib` /
`sys.platform` already normalize. It is imported unchanged by the Linux,
Windows, and macOS installer wizards.
"""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import venv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import PYPI_PROJECT

ProgressFn = Callable[[str], None]

#: Release feed for prebuilt, relocatable CPython builds used for the
#: "private runtime" install path. https://github.com/astral-sh/python-build-standalone
PBS_RELEASES_API = "https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest"

#: Default install roots.
DEFAULT_INSTALL_ROOT = Path.home() / ".local" / "share" / "arklight"
DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"


def _noop(_msg: str) -> None:
    pass


def _arch_tag() -> str:
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "x86_64"
    if machine in ("aarch64", "arm64"):
        return "aarch64"
    raise RuntimeError(f"Unsupported architecture for private runtime: {machine}")


def install_system(python_path: str, install_root: Path = DEFAULT_INSTALL_ROOT,
                    progress: ProgressFn = _noop) -> Path:
    """Create an isolated venv around `python_path` and install ARKlight into it.

    Returns the path to the venv's `arklight` console-script entry point.
    """
    venv_dir = install_root / "venv"
    progress(f"Creating isolated environment at {venv_dir}")
    venv_dir.parent.mkdir(parents=True, exist_ok=True)

    # Build the venv using the *chosen* interpreter, not the one running the
    # installer, since the installer may itself be a bundled private Python.
    subprocess.run([python_path, "-m", "venv", str(venv_dir)], check=True)

    pip = venv_dir / "bin" / "pip"
    progress("Installing ARKlight from PyPI")
    subprocess.run([str(pip), "install", "--upgrade", "pip"], check=True)
    subprocess.run([str(pip), "install", PYPI_PROJECT], check=True)

    return venv_dir / "bin" / "arklight"


def _download_private_cpython(dest_dir: Path, progress: ProgressFn) -> Path:
    """Download and extract a prebuilt, relocatable CPython into `dest_dir`.

    Returns the path to the extracted interpreter's `bin/python3`.
    """
    progress("Looking up latest private Python runtime build")
    req = urllib.request.Request(
        PBS_RELEASES_API, headers={"Accept": "application/vnd.github+json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        release = json.load(resp)

    arch = _arch_tag()
    # python-build-standalone asset names look like:
    #   cpython-3.12.4+20240709-x86_64-unknown-linux-gnu-install_only.tar.gz
    wanted_suffix = f"{arch}-unknown-linux-gnu-install_only.tar.gz"
    asset = next(
        (a for a in release.get("assets", [])
         if a["name"].startswith("cpython-") and a["name"].endswith(wanted_suffix)),
        None,
    )
    if asset is None:
        raise RuntimeError(
            f"No matching private Python build found for linux-{arch}"
        )

    progress(f"Downloading {asset['name']}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    archive_path = dest_dir / asset["name"]
    urllib.request.urlretrieve(asset["browser_download_url"], archive_path)

    progress("Extracting private Python runtime")
    with tarfile.open(archive_path) as tf:
        tf.extractall(dest_dir)
    archive_path.unlink(missing_ok=True)

    # install_only archives extract to a top-level "python/" directory.
    extracted = dest_dir / "python"
    python_bin = extracted / "bin" / "python3"
    if not python_bin.exists():
        raise RuntimeError("Private Python runtime extraction did not produce bin/python3")
    return python_bin


def install_private(install_root: Path = DEFAULT_INSTALL_ROOT,
                     progress: ProgressFn = _noop) -> Path:
    """Acquire a private CPython runtime and install ARKlight directly into it.

    No venv is created: the private interpreter already exists solely for
    ARKlight, so it is isolated by construction.

    Returns the path to the private interpreter's `arklight` console-script.
    """
    runtime_dir = install_root / "runtime"
    python_bin = _download_private_cpython(runtime_dir, progress)

    progress("Installing ARKlight into the private runtime")
    subprocess.run([str(python_bin), "-m", "ensurepip", "--upgrade"], check=True)
    subprocess.run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([str(python_bin), "-m", "pip", "install", PYPI_PROJECT], check=True)

    return python_bin.parent / "arklight"


@dataclass(frozen=True)
class InstallResult:
    arklight_entry: Path
    mode: str  # "system" or "private"
