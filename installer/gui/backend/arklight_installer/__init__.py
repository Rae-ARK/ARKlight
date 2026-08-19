"""ARKlight Installer.

A single, platform-agnostic GUI installer for ARKlight.

This package intentionally contains no platform-specific branching beyond
what the standard library already abstracts away (``os.name``,
``sys.platform``, ``shutil.which``). The same code runs unmodified on
Windows, Linux, and macOS; only the surrounding packaging (installer/linux,
installer/windows, installer/macos) differs per platform.

See installer/README.md for the design goals this package implements.
"""

__version__ = "0.1.0"

PYPI_PROJECT = "arklight"
