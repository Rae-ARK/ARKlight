"""Entry point: `python -m arklight_installer`.

The GUI lives in the Neutralino shell now (see installer/gui/backend/
main.py, wired up starting Stage 1) and calls into detect.py/install.py
directly rather than through this module. This entry point is kept as a
plain terminal fallback for developer/debug use outside the shell.
"""
from __future__ import annotations

from .cli import main as cli_main


def main() -> None:
    cli_main()


if __name__ == "__main__":
    main()
