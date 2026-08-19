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

#: ARKlight's own minimum supported Python version, used as a fallback if
#: the live PyPI metadata lookup in `detect.py` cannot be reached (e.g. the
#: user is offline). Keep this in sync with ARKlight's `pyproject.toml`
#: `requires-python` field; it is a fallback, not the source of truth.
FALLBACK_MIN_PYTHON = (3, 10)

PYPI_PROJECT = "arklight"
