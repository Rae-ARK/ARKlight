"""The installer wizard UI.

Built with Tkinter because it ships with every standard CPython
distribution, which lets the *same* wizard code run on Windows, Linux, and
macOS without pulling in a heavier GUI toolkit or a per-platform UI layer.
"""
from __future__ import annotations

import threading
import traceback
from pathlib import Path
from tkinter import Tk, StringVar, BooleanVar, ttk, messagebox

from . import __version__
from .detect import fetch_min_python, find_system_pythons, compatible, PythonCandidate
from .install import DEFAULT_INSTALL_ROOT, install_system, install_private
from .launcher import create_launcher, create_desktop_entry, path_needs_update, DEFAULT_BIN_DIR

WINDOW_TITLE = f"ARKlight Installer {__version__}"
PAD = 16


class InstallerApp:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry("520x360")
        self.root.resizable(False, False)

        self.min_version: tuple[int, int] | None = None
        self.system_candidates: list[PythonCandidate] = []
        self.compatible_candidates: list[PythonCandidate] = []

        self.mode = StringVar(value="system")  # "system" or "private"
        self.selected_python = StringVar()
        self.create_menu_entry = BooleanVar(value=True)

        self.container = ttk.Frame(self.root, padding=PAD)
        self.container.pack(fill="both", expand=True)

        self._show_welcome()

    # ---- frame management -------------------------------------------------
    def _clear(self) -> None:
        for child in self.container.winfo_children():
            child.destroy()

    # ---- Step 1: welcome ---------------------------------------------------
    def _show_welcome(self) -> None:
        self._clear()
        ttk.Label(self.container, text="Welcome to the ARKlight Installer",
                  font=("TkDefaultFont", 14, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            self.container,
            wraplength=480, justify="left",
            text=("This installer sets up ARKlight, the Python-first compiler "
                  "for building static websites.\n\n"
                  "It will find a compatible Python on your system, or install "
                  "a private one just for ARKlight, then install the current "
                  "stable ARKlight release."),
        ).pack(anchor="w")

        button_row = ttk.Frame(self.container)
        button_row.pack(side="bottom", fill="x", pady=(PAD, 0))
        ttk.Button(button_row, text="Next", command=self._start_detection).pack(side="right")

    # ---- Step 2: detect python (runs off the UI thread) --------------------
    def _start_detection(self) -> None:
        self._clear()
        ttk.Label(self.container, text="Checking for a compatible Python…").pack(anchor="w")
        progress = ttk.Progressbar(self.container, mode="indeterminate")
        progress.pack(fill="x", pady=PAD)
        progress.start(12)

        def work() -> None:
            try:
                min_version = fetch_min_python()
                candidates = find_system_pythons()
                compat = compatible(candidates, min_version)
            except Exception:
                self.root.after(0, lambda: self._show_error(traceback.format_exc()))
                return
            self.root.after(0, lambda: self._show_python_choice(min_version, candidates, compat))

        threading.Thread(target=work, daemon=True).start()

    def _show_python_choice(self, min_version, candidates, compat) -> None:
        self.min_version = min_version
        self.system_candidates = candidates
        self.compatible_candidates = compat
        self._clear()

        min_str = ".".join(map(str, min_version))
        ttk.Label(self.container, text="Choose a Python runtime",
                  font=("TkDefaultFont", 14, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(self.container, text=f"ARKlight requires Python {min_str} or newer.",
                  wraplength=480, justify="left").pack(anchor="w", pady=(0, PAD))

        if compat:
            best = compat[0]
            ttk.Radiobutton(
                self.container, variable=self.mode, value="system",
                text=f"Use system Python ({best.version_str} at {best.path})",
            ).pack(anchor="w")
            self.selected_python.set(best.path)
        else:
            ttk.Label(
                self.container, foreground="#a33",
                text="No compatible system Python was found.", wraplength=480,
            ).pack(anchor="w")
            self.mode.set("private")

        ttk.Radiobutton(
            self.container, variable=self.mode, value="private",
            text="Install a private Python just for ARKlight (recommended if unsure)",
        ).pack(anchor="w", pady=(4, 0))

        ttk.Checkbutton(
            self.container, variable=self.create_menu_entry,
            text="Add ARKlight to the application menu",
        ).pack(anchor="w", pady=(PAD, 0))

        button_row = ttk.Frame(self.container)
        button_row.pack(side="bottom", fill="x", pady=(PAD, 0))
        ttk.Button(button_row, text="Install", command=self._start_install).pack(side="right")
        ttk.Button(button_row, text="Back", command=self._show_welcome).pack(side="right", padx=(0, 8))

    # ---- Step 3: install (runs off the UI thread) ---------------------------
    def _start_install(self) -> None:
        self._clear()
        status = StringVar(value="Starting install…")
        ttk.Label(self.container, textvariable=status, wraplength=480).pack(anchor="w")
        progress = ttk.Progressbar(self.container, mode="indeterminate")
        progress.pack(fill="x", pady=PAD)
        progress.start(12)

        def report(msg: str) -> None:
            self.root.after(0, lambda: status.set(msg))

        def work() -> None:
            try:
                if self.mode.get() == "system":
                    entry = install_system(self.selected_python.get(),
                                            DEFAULT_INSTALL_ROOT, report)
                else:
                    entry = install_private(DEFAULT_INSTALL_ROOT, report)

                report("Creating launcher")
                wrapper = create_launcher(entry, DEFAULT_BIN_DIR)
                if self.create_menu_entry.get():
                    create_desktop_entry(wrapper)
                needs_path = path_needs_update(DEFAULT_BIN_DIR)
            except Exception:
                self.root.after(0, lambda: self._show_error(traceback.format_exc()))
                return
            self.root.after(0, lambda: self._show_finish(wrapper, needs_path))

        threading.Thread(target=work, daemon=True).start()

    # ---- Step 4: finish ------------------------------------------------------
    def _show_finish(self, wrapper: Path, needs_path: bool) -> None:
        self._clear()
        ttk.Label(self.container, text="ARKlight is ready",
                  font=("TkDefaultFont", 14, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            self.container, wraplength=480, justify="left",
            text=f"Installed the `arklight` command at:\n{wrapper}",
        ).pack(anchor="w")

        if needs_path:
            ttk.Label(
                self.container, wraplength=480, justify="left", foreground="#a33",
                text=(f"\n{wrapper.parent} is not on your PATH yet. Add this line to "
                      "your shell profile (~/.bashrc, ~/.zshrc, etc.) and restart your "
                      f'shell:\n\n    export PATH="{wrapper.parent}:$PATH"'),
            ).pack(anchor="w", pady=(PAD, 0))

        button_row = ttk.Frame(self.container)
        button_row.pack(side="bottom", fill="x", pady=(PAD, 0))
        ttk.Button(button_row, text="Close", command=self.root.destroy).pack(side="right")

    # ---- error handling --------------------------------------------------
    def _show_error(self, details: str) -> None:
        messagebox.showerror("ARKlight Installer — Error", details)
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    InstallerApp().run()
