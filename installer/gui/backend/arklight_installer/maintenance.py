"""Update, Repair, and Uninstall for an existing ARKlight install.

Stage 2 (docs/Implementation.md). `install_system()`/`install_private()`
in install.py remain the only code that actually creates a venv or
acquires a private runtime — this module reuses them rather than
duplicating that logic, per Architecture.md §4 ("Neither function's
internal logic changes for this rebuild; only what calls them does").
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from .install import (
    DEFAULT_BIN_DIR,
    DEFAULT_INSTALL_ROOT,
    _exe,
    _install_arklight,
    _interpreter_path,
    _private_runtime_root,
    _scripts_dir,
    install_private,
    install_system,
)
from .launcher import DESKTOP_ENTRY_DIR, MIME_PACKAGE_DIR

ProgressFn = Callable[[str], None]


def _noop(_msg: str) -> None:
    pass


# --------------------------------------------------------------------------
# Repair: interpreter-validity check (Architecture.md §3)
# --------------------------------------------------------------------------

def _venv_interpreter_path(venv_dir: Path) -> Optional[Path]:
    """Read the `home = ...` line out of `venv_dir/pyvenv.cfg`.

    That's the path to the base interpreter the venv was created against —
    exactly what goes stale if the user later deletes or upgrades their
    global Python.
    """
    cfg = venv_dir / "pyvenv.cfg"
    if not cfg.exists():
        return None
    for line in cfg.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("home"):
            _, _, value = line.partition("=")
            home = Path(value.strip())
            # `home` is the directory containing the interpreter binary,
            # not the binary itself — reconstruct the executable name a
            # venv itself would look for there.
            for name in ("python3", "python"):
                candidate = home / name
                if candidate.exists():
                    return candidate
            return None
    return None


def check_repair(install_root: Path = DEFAULT_INSTALL_ROOT) -> dict:
    """Return what Repair should do, without changing anything yet.

    - {"mode": "system", "interpreter_valid": True, ...}  -> normal repair
    - {"mode": "system", "interpreter_valid": False, ...} -> offer pivot
    - {"mode": "private", ...} -> no interpreter-validity concept applies
    - {"mode": "none"} -> nothing installed to repair
    """
    venv_dir = install_root / "venv"
    if venv_dir.exists():
        interp = _venv_interpreter_path(venv_dir)
        valid = interp is not None and os.access(interp, os.X_OK)
        return {
            "mode": "system",
            "venv": str(venv_dir),
            "interpreter": str(interp) if interp else None,
            "interpreter_valid": valid,
        }

    runtime_dir = install_root / "runtime"
    if _interpreter_path(_private_runtime_root(runtime_dir)).exists():
        return {"mode": "private", "runtime": str(runtime_dir)}

    return {"mode": "none"}


def repair_system(install_root: Path = DEFAULT_INSTALL_ROOT,
                   progress: ProgressFn = _noop) -> Path:
    """Normal repair path: the interpreter still resolves. Rebuild the venv
    against that same interpreter and reinstall ARKlight into it.
    """
    venv_dir = install_root / "venv"
    interp = _venv_interpreter_path(venv_dir)
    if interp is None:
        raise RuntimeError(
            "repair_system() called with no valid interpreter — "
            "use repair_pivot() instead."
        )
    progress(f"Repairing venv against {interp}")
    # install_system() (re)creates the venv from scratch against the given
    # interpreter and reinstalls ARKlight — exactly what "repair" means
    # here, and it keeps this module from re-implementing venv creation.
    return install_system(str(interp), install_root, progress)


def repair_pivot(install_root: Path = DEFAULT_INSTALL_ROOT,
                  progress: ProgressFn = _noop) -> Path:
    """Repair path for a system install whose interpreter is gone: pivot
    onto the private standalone CPython runtime (Architecture.md §3)
    instead of leaving the user with a broken venv and a bare path error.
    """
    progress("Original interpreter is gone — switching to a private runtime")
    old_venv = install_root / "venv"
    entry = install_private(install_root, progress)
    if old_venv.exists():
        shutil.rmtree(old_venv, ignore_errors=True)
    return entry


def repair_private(install_root: Path = DEFAULT_INSTALL_ROOT,
                    progress: ProgressFn = _noop) -> Path:
    """Repair path for a private-runtime install. No interpreter-validity
    failure mode applies here (Architecture.md §3) — the runtime exists
    solely for ARKlight — so repair is just a reinstall into it.
    """
    return install_private(install_root, progress)


# --------------------------------------------------------------------------
# Update: same install step, current stable release, existing runtime
# --------------------------------------------------------------------------

def update_system(install_root: Path = DEFAULT_INSTALL_ROOT,
                   progress: ProgressFn = _noop) -> Path:
    venv_dir = install_root / "venv"
    interp = _venv_interpreter_path(venv_dir)
    if interp is None:
        raise RuntimeError(
            "update_system() called with no valid interpreter — "
            "this is a Repair situation, not Update."
        )
    scripts = _scripts_dir(venv_dir)
    pip = scripts / _exe("pip")
    _install_arklight([str(pip)], progress, upgrade=True)
    return scripts / _exe("arklight")


def update_private(install_root: Path = DEFAULT_INSTALL_ROOT,
                    progress: ProgressFn = _noop) -> Path:
    runtime_dir = install_root / "runtime"
    root = _private_runtime_root(runtime_dir)
    python_bin = _interpreter_path(root)
    if not python_bin.exists():
        raise RuntimeError("update_private() called with no private runtime present.")
    _install_arklight([str(python_bin), "-m", "pip"], progress, upgrade=True)
    return _scripts_dir(root) / _exe("arklight")


# --------------------------------------------------------------------------
# Uninstall
# --------------------------------------------------------------------------

def uninstall(install_root: Path = DEFAULT_INSTALL_ROOT,
              bin_dir: Path = DEFAULT_BIN_DIR,
              progress: ProgressFn = _noop) -> dict:
    """Remove the ARKlight install itself: venv/runtime, the `arklight`
    wrapper, and any `.ark` bundle / application-menu integration.

    Does NOT touch the installer binary itself — see
    `self_delete_installer()` for that, which is a separate step callers
    run afterward (Architecture.md §3: uninstall is the one path with
    OS-specific plumbing, and self-deleting the installer is that part).
    """
    progress("Removing ARKlight install")
    if install_root.exists():
        shutil.rmtree(install_root, ignore_errors=True)

    wrapper = bin_dir / "arklight"
    if wrapper.exists():
        wrapper.unlink()

    opener = bin_dir / "arklight-open"
    if opener.exists():
        opener.unlink()

    progress("Removing application menu / bundle-opener integration")
    for path in (
        DESKTOP_ENTRY_DIR / "arklight.desktop",
        DESKTOP_ENTRY_DIR / "arklight-bundle.desktop",
        MIME_PACKAGE_DIR / "arklight-bundle.xml",
    ):
        if path.exists():
            path.unlink()

    for cmd in (
        ["update-mime-database", str(MIME_PACKAGE_DIR.parent)],
        ["update-desktop-database", str(DESKTOP_ENTRY_DIR)],
    ):
        try:
            subprocess.run(cmd, check=False, capture_output=True)
        except (OSError, FileNotFoundError):
            pass

    return {"ok": True}


def self_delete_installer(exe_path: Path, parent_pid: Optional[int] = None) -> dict:
    """Delete the installer binary itself after an uninstall
    (Architecture.md §3).

    Linux/macOS: the OS holds a running binary's inode open until the
    process exits, so a direct unlink works even while `exe_path` is the
    file currently executing — no helper needed.

    Windows can't delete a running .exe. This spawns a small detached
    helper (`DETACHED_PROCESS` / `CREATE_NEW_PROCESS_GROUP`, so it
    survives this process exiting) that polls for `parent_pid` to
    disappear, deletes `exe_path`, then deletes itself. Only ever called
    from the uninstall path — normal install/update/repair runs never
    touch this function.

    Not yet wired into main.py's `uninstall` command: there is no
    packaged single-binary installer artifact to point `exe_path` at
    until Stage 3 (CPack) exists — calling this against the dev-mode
    `neu run` process would delete the wrong thing. The mechanism is
    implemented and exercised directly (see the module's own tests) so
    Stage 3 only has to wire the real exe path in, not write this logic.
    """
    if sys.platform != "win32":
        try:
            exe_path.unlink()
        except OSError:
            pass
        return {"self_delete_pending": False}

    parent_pid = parent_pid or os.getpid()
    helper = exe_path.parent / "_arklight_uninstall_helper.bat"
    helper.write_text(
        "@echo off\r\n"
        ":wait\r\n"
        f"tasklist /FI \"PID eq {parent_pid}\" | find \"{parent_pid}\" >nul\r\n"
        "if not errorlevel 1 (\r\n"
        "  timeout /t 1 /nobreak >nul\r\n"
        "  goto wait\r\n"
        ")\r\n"
        f"del /f /q \"{exe_path}\"\r\n"
        "del /f /q \"%~f0\"\r\n",
        encoding="utf-8",
    )
    subprocess.Popen(
        ["cmd.exe", "/c", str(helper)],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    return {"self_delete_pending": True, "helper": str(helper)}
