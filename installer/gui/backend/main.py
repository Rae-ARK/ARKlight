"""
Neutralino shell entry point.

Contract: each command prints exactly one JSON *result* object as its
last line of stdout. install-system/install-private/update-system/
update-private/repair-system/repair-pivot/repair-private/uninstall may
print additional {"progress": "..."} lines before that, one per
install.py/maintenance.py progress callback — the caller should treat
the last JSON line as the result and everything before it as a progress
log. Errors go to stderr with a non-zero exit code, so the caller can
tell "ran and failed" apart from "didn't run."
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

from arklight_installer.detect import find_system_pythons
from arklight_installer.install import (
    DEFAULT_BIN_DIR,
    DEFAULT_INSTALL_ROOT,
    install_private,
    install_system,
)
from arklight_installer.launcher import create_launcher, path_needs_update
from arklight_installer.maintenance import (
    check_repair,
    repair_pivot,
    repair_private,
    repair_system,
    uninstall,
    update_private,
    update_system,
)

# Same endpoints detect.py/install.py ultimately depend on: if neither is
# reachable, neither the PyPI install nor its GitHub fallback can succeed.
CONNECTIVITY_CHECK_URLS = [
    "https://pypi.org/simple/arklight/",
    "https://codeload.github.com/Rae-ARK/ARKlight/tar.gz/refs/heads/main",
]


def _emit(obj: dict) -> None:
    print(json.dumps(obj), flush=True)


def _progress(message: str) -> None:
    _emit({"progress": message})


def cmd_state() -> dict:
    """Is ARKlight already installed? Drives the launch-time branch
    between the Install flow and Update/Repair/Uninstall (Architecture.md
    §3). Stage 1 only needs to answer this question — the maintenance
    flows themselves are Stage 2.
    """
    system_entry = DEFAULT_INSTALL_ROOT / "venv" / "bin" / "arklight"
    if system_entry.exists():
        return {"installed": True, "mode": "system", "entry": str(system_entry)}

    private_entry = DEFAULT_INSTALL_ROOT / "runtime" / "bin" / "arklight"
    if private_entry.exists():
        return {"installed": True, "mode": "private", "entry": str(private_entry)}

    return {"installed": False}


def cmd_connectivity() -> dict:
    """Pre-flight reachability check (Architecture.md §4). Must run, and
    pass, before install/update/repair touches the filesystem at all.
    Reachable if either the PyPI install path or the GitHub fallback path
    can be reached — a PyPI-specific outage shouldn't block an install
    that GitHub could still serve.
    """
    last_reason = "unknown"
    for url in CONNECTIVITY_CHECK_URLS:
        try:
            with urllib.request.urlopen(url, timeout=5):
                return {"reachable": True}
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last_reason = str(exc)
            continue
    return {"reachable": False, "reason": last_reason}


def cmd_list_pythons() -> dict:
    candidates = find_system_pythons()
    return {
        "candidates": [
            {"path": c.path, "version": c.version_str} for c in candidates
        ]
    }


def cmd_install_system(python_path: str) -> dict:
    entry = install_system(python_path, DEFAULT_INSTALL_ROOT, _progress)
    wrapper = create_launcher(entry, DEFAULT_BIN_DIR)
    return {
        "ok": True,
        "mode": "system",
        "entry": str(entry),
        "wrapper": str(wrapper),
        "path_needs_update": path_needs_update(DEFAULT_BIN_DIR),
    }


def cmd_install_private() -> dict:
    entry = install_private(DEFAULT_INSTALL_ROOT, _progress)
    wrapper = create_launcher(entry, DEFAULT_BIN_DIR)
    return {
        "ok": True,
        "mode": "private",
        "entry": str(entry),
        "wrapper": str(wrapper),
        "path_needs_update": path_needs_update(DEFAULT_BIN_DIR),
    }


def cmd_check_repair() -> dict:
    """Stage 2: what should Repair do? Read-only — decides between the
    normal repair path and the pivot-to-private offer without touching
    anything (Architecture.md §3).
    """
    return check_repair(DEFAULT_INSTALL_ROOT)


def cmd_repair_system() -> dict:
    entry = repair_system(DEFAULT_INSTALL_ROOT, _progress)
    wrapper = create_launcher(entry, DEFAULT_BIN_DIR)
    return {"ok": True, "mode": "system", "entry": str(entry), "wrapper": str(wrapper)}


def cmd_repair_pivot() -> dict:
    entry = repair_pivot(DEFAULT_INSTALL_ROOT, _progress)
    wrapper = create_launcher(entry, DEFAULT_BIN_DIR)
    return {"ok": True, "mode": "private", "entry": str(entry), "wrapper": str(wrapper)}


def cmd_repair_private() -> dict:
    entry = repair_private(DEFAULT_INSTALL_ROOT, _progress)
    wrapper = create_launcher(entry, DEFAULT_BIN_DIR)
    return {"ok": True, "mode": "private", "entry": str(entry), "wrapper": str(wrapper)}


def cmd_update_system() -> dict:
    entry = update_system(DEFAULT_INSTALL_ROOT, _progress)
    return {"ok": True, "mode": "system", "entry": str(entry)}


def cmd_update_private() -> dict:
    entry = update_private(DEFAULT_INSTALL_ROOT, _progress)
    return {"ok": True, "mode": "private", "entry": str(entry)}


def cmd_uninstall() -> dict:
    # Installer-binary self-delete is deliberately not fired here yet —
    # see maintenance.self_delete_installer's docstring: no packaged
    # single-binary artifact exists to point it at until Stage 3.
    return uninstall(DEFAULT_INSTALL_ROOT, DEFAULT_BIN_DIR, _progress)


def main() -> int:
    args = sys.argv[1:]
    command = args[0] if args else "state"

    try:
        if command == "state":
            _emit(cmd_state())
        elif command == "connectivity":
            _emit(cmd_connectivity())
        elif command == "list-pythons":
            _emit(cmd_list_pythons())
        elif command == "install-system":
            if len(args) < 2:
                print("install-system requires a python path", file=sys.stderr)
                return 1
            _emit(cmd_install_system(args[1]))
        elif command == "install-private":
            _emit(cmd_install_private())
        elif command == "check-repair":
            _emit(cmd_check_repair())
        elif command == "repair-system":
            _emit(cmd_repair_system())
        elif command == "repair-pivot":
            _emit(cmd_repair_pivot())
        elif command == "repair-private":
            _emit(cmd_repair_private())
        elif command == "update-system":
            _emit(cmd_update_system())
        elif command == "update-private":
            _emit(cmd_update_private())
        elif command == "uninstall":
            _emit(cmd_uninstall())
        else:
            print(f"unknown command: {command}", file=sys.stderr)
            return 1
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller, not swallowed
        print(str(exc), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
