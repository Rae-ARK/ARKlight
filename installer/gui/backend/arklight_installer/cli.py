"""Terminal-only install flow, driven by prompts.

Used directly by `python -m arklight_installer` (see __main__.py) for
developer/debug use outside the Neutralino shell. The shell itself
drives the same detect.py/install.py calls through backend/main.py
instead of this module.
"""
from __future__ import annotations

from .detect import find_system_pythons
from .install import DEFAULT_INSTALL_ROOT, install_system, install_private
from .launcher import (
    create_launcher, create_desktop_entry, path_needs_update, DEFAULT_BIN_DIR,
    install_opener, register_bundle_mime,
)


def main() -> None:
    print("ARKlight Installer (terminal mode)\n")

    print("Checking for a system Python…")
    candidates = find_system_pythons()

    use_private = True
    chosen_path = None
    if candidates:
        best = candidates[0]
        print(f"Found a system Python: {best.version_str} at {best.path}")
        answer = input("Use it? [Y/n] ").strip().lower()
        if answer in ("", "y", "yes"):
            use_private = False
            chosen_path = best.path
    else:
        print("No system Python found; a private runtime will be installed.")

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

    bundle_answer = input(
        "Open .ark bundles by double-clicking (sealed ones ask for a password)? [Y/n] "
    ).strip().lower()
    if bundle_answer in ("", "y", "yes"):
        report("Associating .ark bundles")
        opener = install_opener(DEFAULT_BIN_DIR)
        register_bundle_mime(opener)

    print(f"\nInstalled the `arklight` command at:\n  {wrapper}")
    if path_needs_update(DEFAULT_BIN_DIR):
        print(
            f"\n{wrapper.parent} is not on your PATH yet. Add this to your shell "
            f'profile:\n\n    export PATH="{wrapper.parent}:$PATH"\n'
        )
