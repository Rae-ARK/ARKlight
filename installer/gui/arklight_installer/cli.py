"""Terminal fallback for environments without Tkinter (e.g. minimal/headless
Python builds, some server distros that split Tk into a separate package).

Implements the same install flow as `ui.py`, driven by prompts instead of
widgets, so the installer never simply fails when Tk is missing.
"""
from __future__ import annotations

from .detect import fetch_min_python, find_system_pythons, compatible
from .install import DEFAULT_INSTALL_ROOT, install_system, install_private
from .launcher import create_launcher, create_desktop_entry, path_needs_update, DEFAULT_BIN_DIR


def main() -> None:
    print("ARKlight Installer (terminal mode)\n")

    print("Checking for a compatible Python…")
    min_version = fetch_min_python()
    candidates = find_system_pythons()
    compat = compatible(candidates, min_version)
    min_str = ".".join(map(str, min_version))
    print(f"ARKlight requires Python {min_str}+.\n")

    use_private = True
    chosen_path = None
    if compat:
        best = compat[0]
        print(f"Found a compatible system Python: {best.version_str} at {best.path}")
        answer = input("Use it? [Y/n] ").strip().lower()
        if answer in ("", "y", "yes"):
            use_private = False
            chosen_path = best.path
    else:
        print("No compatible system Python found; a private runtime will be installed.")

    def report(msg: str) -> None:
        print(f"  -> {msg}")

    if use_private:
        entry = install_private(DEFAULT_INSTALL_ROOT, report)
    else:
        entry = install_system(chosen_path, DEFAULT_INSTALL_ROOT, report)

    report("Creating launcher")
    wrapper = create_launcher(entry, DEFAULT_BIN_DIR)

    menu_answer = input("Add ARKlight to the application menu? [Y/n] ").strip().lower()
    if menu_answer in ("", "y", "yes"):
        create_desktop_entry(wrapper)

    print(f"\nInstalled the `arklight` command at:\n  {wrapper}")
    if path_needs_update(DEFAULT_BIN_DIR):
        print(
            f"\n{wrapper.parent} is not on your PATH yet. Add this to your shell "
            f'profile:\n\n    export PATH="{wrapper.parent}:$PATH"\n'
        )
