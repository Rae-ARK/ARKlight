"""Install ARKlight into either a system-Python virtual environment or a
private, prebuilt CPython runtime.

This module contains no OS-specific branching beyond what `pathlib` /
`sys.platform` already normalize. It is imported unchanged by the Linux,
Windows, and macOS installer wizards.
"""
from __future__ import annotations

import hashlib
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

#: Fallback source if PyPI install fails — codeload is a plain archive
#: download (no API rate limit, no git dependency on the target machine),
#: unlike the GitHub REST API used for the private-runtime feed above.
GITHUB_SOURCE_ARCHIVE_URL = "https://codeload.github.com/Rae-ARK/ARKlight/tar.gz/refs/heads/main"

#: Default install roots.
DEFAULT_INSTALL_ROOT = Path.home() / ".local" / "share" / "arklight"
DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"


def _noop(_msg: str) -> None:
    pass


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a subprocess with its stdout/stderr captured, never inherited.

    This backend's own stdout is a line-oriented JSON protocol main.js
    parses (see main.py's module docstring) — letting a child process
    (venv, pip, ensurepip...) write its normal chatter straight to our
    stdout corrupts that stream. A completely unremarkable line like
    "Requirement already satisfied: pip in ..." is exactly what broke it:
    main.js's JSON.parse choked on the bare word "Requirement".

    On failure, re-raises with the child's actual stderr attached — a
    bare CalledProcessError's default message is just the exit code, not
    why it failed.
    """
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(
            f"`{' '.join(cmd)}` failed (exit {exc.returncode})"
            + (f": {detail}" if detail else "")
        ) from exc


def _install_arklight(pip_argv: list[str], progress: ProgressFn, upgrade: bool = False) -> None:
    """Install ARKlight, preferring the published PyPI release and falling
    back to building from GitHub's `main` branch if PyPI install fails —
    e.g. PyPI itself is unreachable/down, or a version hasn't been
    published there yet.

    `pip_argv` is the pip invocation prefix: `[str(pip)]` for a venv's own
    pip executable, or `[str(python_bin), "-m", "pip"]` for a private
    runtime that only exposes pip as a module. `upgrade` is for Update
    (Stage 2), which needs `pip install --upgrade` rather than a fresh
    install of an interpreter that may already have ARKlight in it.
    """
    progress("Installing ARKlight from PyPI" if not upgrade else "Updating ARKlight from PyPI")
    pypi_args = [*pip_argv, "install", *(["--upgrade"] if upgrade else []), PYPI_PROJECT]
    try:
        _run(pypi_args)
        return
    except RuntimeError as exc:
        progress(f"PyPI install failed ({exc}) — falling back to GitHub")

    progress("Downloading ARKlight source from GitHub")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        archive_path = tmp_path / "arklight-src.tar.gz"
        urllib.request.urlretrieve(GITHUB_SOURCE_ARCHIVE_URL, archive_path)

        with tarfile.open(archive_path) as tf:
            tf.extractall(tmp_path)

        # GitHub's tarball extracts to a single "<repo>-<branch>/" directory.
        extracted_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
        if len(extracted_dirs) != 1:
            raise RuntimeError(
                "Unexpected GitHub archive layout: expected exactly one "
                f"top-level directory, found {len(extracted_dirs)}"
            )

        progress("Installing ARKlight from GitHub source")
        # --force-reinstall: a local source install has no version to
        # compare against an already-installed PyPI release, so plain
        # --upgrade can no-op when we actually need the GitHub copy in.
        github_args = [*pip_argv, "install", *(["--force-reinstall"] if upgrade else []), str(extracted_dirs[0])]
        _run(github_args)


def _scripts_dir(root: Path) -> Path:
    """Return the directory holding executables/console-scripts for a venv
    or install_only Python tree rooted at `root`.

    Both venv and python-build-standalone install_only archives put
    executables in "bin/" on Linux/macOS and "Scripts/" on Windows — this
    is the one place that split is encoded so it isn't duplicated (and
    silently assumed wrong on Windows) at every call site.
    """
    return root / "Scripts" if sys.platform == "win32" else root / "bin"


def _exe(name: str) -> str:
    """Append the platform's executable suffix to a bare command name."""
    return f"{name}.exe" if sys.platform == "win32" else name


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
    _run([python_path, "-m", "venv", str(venv_dir)])

    scripts = _scripts_dir(venv_dir)
    pip = scripts / _exe("pip")
    _run([str(pip), "install", "--upgrade", "pip"])
    _install_arklight([str(pip)], progress)

    return scripts / _exe("arklight")


def _verify_asset_checksum(archive_path: Path, asset: dict, release: dict) -> None:
    """Verify `archive_path` against a SHA-256 sourced from the GitHub
    Releases API, before anything extracts or runs it.

    Tries two sources, in order:
    1. The asset's own `digest` field (GitHub API returns this as
       `"sha256:<hex>"` for assets uploaded with a known digest).
    2. A `SHA256SUMS`-style checksums file published as a sibling asset in
       the same release, which python-build-standalone includes.

    Raises RuntimeError if a checksum was found and did not match. If
    neither source is available, this raises RuntimeError as well —
    silently proceeding without verification defeats the point.
    """
    digest = asset.get("digest")  # e.g. "sha256:abc123..."
    expected = None
    if digest and digest.startswith("sha256:"):
        expected = digest.split(":", 1)[1].lower()
    else:
        sums_asset = next(
            (a for a in release.get("assets", [])
             if a["name"].upper() in ("SHA256SUMS", "SHA256SUMS.TXT")
             or a["name"].lower().endswith(".sha256")),
            None,
        )
        if sums_asset is not None:
            with urllib.request.urlopen(sums_asset["browser_download_url"], timeout=15) as resp:
                sums_text = resp.read().decode("utf-8", errors="replace")
            for line in sums_text.splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1].lstrip("*") == asset["name"]:
                    expected = parts[0].lower()
                    break

    if expected is None:
        raise RuntimeError(
            f"No checksum available for {asset['name']} from the GitHub "
            "release — refusing to extract an unverified Python runtime."
        )

    hasher = hashlib.sha256()
    with open(archive_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    actual = hasher.hexdigest().lower()

    if actual != expected:
        archive_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Checksum mismatch for {asset['name']}: expected {expected}, "
            f"got {actual}. The download was discarded."
        )


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
    #   cpython-3.12.4+20240709-x86_64-pc-windows-msvc-install_only.tar.gz
    #   cpython-3.12.4+20240709-aarch64-apple-darwin-install_only.tar.gz
    # This MUST match the platform this code is currently running on — an
    # earlier version of this function hardcoded the Linux triple on every
    # OS, which on Windows silently downloaded and extracted a Linux
    # tarball. That archive's share/terminfo directory (ncurses' terminal
    # database, Unix-only) is full of real POSIX symlinks used as terminal
    # aliases; Windows can create the reparse point but can't resolve the
    # POSIX-relative target, which fails extraction with
    # "[WinError 1921] The name of the file cannot be resolved by the
    # system" deep into an unrelated-looking file.
    if sys.platform == "win32":
        target_triple = f"{arch}-pc-windows-msvc"
    elif sys.platform == "darwin":
        target_triple = f"{arch}-apple-darwin"
    elif sys.platform.startswith("linux"):
        target_triple = f"{arch}-unknown-linux-gnu"
    else:
        raise RuntimeError(f"Unsupported platform for private runtime: {sys.platform}")
    wanted_suffix = f"{target_triple}-install_only.tar.gz"
    asset = next(
        (a for a in release.get("assets", [])
         if a["name"].startswith("cpython-") and a["name"].endswith(wanted_suffix)),
        None,
    )
    if asset is None:
        raise RuntimeError(
            f"No matching private Python build found for {target_triple}"
        )

    progress(f"Downloading {asset['name']}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    archive_path = dest_dir / asset["name"]
    urllib.request.urlretrieve(asset["browser_download_url"], archive_path)

    progress("Verifying download integrity")
    _verify_asset_checksum(archive_path, asset, release)

    progress("Extracting private Python runtime")
    with tarfile.open(archive_path) as tf:
        # filter="data" rejects path-traversal (../) and other unsafe
        # members instead of silently extracting them — see Python's own
        # tarfile docs on unfiltered extractall() being unsafe against a
        # maliciously crafted archive.
        tf.extractall(dest_dir, filter="data")
    archive_path.unlink(missing_ok=True)

    # install_only archives extract to a top-level "python/" directory.
    # Windows builds place python.exe directly in that root (no bin/
    # subdirectory); Unix builds put it under bin/python3.
    extracted = dest_dir / "python"
    python_bin = extracted / "python.exe" if sys.platform == "win32" else extracted / "bin" / "python3"
    if not python_bin.exists():
        raise RuntimeError(f"Private Python runtime extraction did not produce {python_bin.name}")
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

    _run([str(python_bin), "-m", "ensurepip", "--upgrade"])
    _run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"])
    _install_arklight([str(python_bin), "-m", "pip"], progress)

    # pip installs console-scripts into Scripts/ on Windows, but python_bin
    # itself sits directly in the runtime root there (not a bin/ sibling
    # to Scripts/) — so this can't just reuse python_bin.parent the way
    # the Unix layout (bin/python3, bin/arklight side by side) allows.
    return _scripts_dir(python_bin.parent) / _exe("arklight")


@dataclass(frozen=True)
class InstallResult:
    arklight_entry: Path
    mode: str  # "system" or "private"
