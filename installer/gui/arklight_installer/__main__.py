"""Entry point: `python -m arklight_installer` or the frozen executable."""
from __future__ import annotations

import sys


def main() -> None:
    try:
        from .ui import main as gui_main
        gui_main()
    except ImportError:
        # Tkinter isn't available (e.g. a minimal/headless Python build).
        # Fall back to a plain terminal install rather than failing outright.
        print("Graphical interface unavailable (Tkinter not found); "
              "falling back to a terminal install.", file=sys.stderr)
        from .cli import main as cli_main
        cli_main()


if __name__ == "__main__":
    main()
