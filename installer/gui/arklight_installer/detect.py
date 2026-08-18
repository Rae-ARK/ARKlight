"""Detect compatible CPython interpreters on the host system.

Per installer/README.md, the compatibility source of truth is ARKlight's
own package metadata (`requires-python` on PyPI), not a constant baked
into the installer. We fetch that metadata at install time and fall back
to `FALLBACK_MIN_PYTHON` only if the network is unavailable.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from . import FALLBACK_MIN_PYTHON, PYPI_PROJECT

_CANDIDATE_NAMES = [
    "python3", "python",
    "python3.13", "python3.12", "python3.11", "python3.10",
]


@dataclass(frozen=True)
class PythonCandidate:
    path: str
    version: tuple[int, int, int]

    @property
    def version_str(self) -> str:
        return ".".join(str(p) for p in self.version)


def fetch_min_python() -> tuple[int, int]:
    """Return ARKlight's minimum required (major, minor) Python version.

    Reads `requires-python` from PyPI's JSON API. Falls back to the
    baked-in constant if the lookup fails for any reason (offline, PyPI
    unreachable, unexpected response shape).
    """
    url = f"https://pypi.org/pypi/{PYPI_PROJECT}/json"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.load(resp)
        requires = data["info"]["requires_python"]  # e.g. ">=3.10"
        digits = "".join(c if c.isdigit() or c == "." else " " for c in requires)
        parts = [p for p in digits.split() if p]
        major, minor = (int(x) for x in parts[0].split(".")[:2])
        return major, minor
    except (urllib.error.URLError, KeyError, ValueError, IndexError, TimeoutError):
        return FALLBACK_MIN_PYTHON


def _probe(path: str) -> Optional[PythonCandidate]:
    """Run `path -c "import sys; print(sys.version_info[:3])"` and parse it."""
    try:
        out = subprocess.run(
            [path, "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
            capture_output=True, text=True, timeout=5, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        major, minor, patch = (int(x) for x in out.stdout.strip().split("."))
    except ValueError:
        return None
    return PythonCandidate(path=path, version=(major, minor, patch))


def find_system_pythons() -> list[PythonCandidate]:
    """Return every discoverable CPython interpreter on PATH, deduplicated."""
    seen_paths: set[str] = set()
    candidates: list[PythonCandidate] = []

    for name in _CANDIDATE_NAMES:
        found = shutil.which(name)
        if not found or found in seen_paths:
            continue
        seen_paths.add(found)
        probed = _probe(found)
        if probed is not None:
            candidates.append(probed)

    # Always consider the interpreter running the installer itself, in case
    # it was launched with a bundled/private Python via PyInstaller — this
    # keeps `find_system_pythons` honest about what's actually usable.
    self_path = sys.executable
    if self_path and self_path not in seen_paths:
        probed = _probe(self_path)
        if probed is not None:
            candidates.append(probed)

    return candidates


def compatible(candidates: list[PythonCandidate], min_version: tuple[int, int]) -> list[PythonCandidate]:
    """Filter candidates down to those meeting `min_version`."""
    return [c for c in candidates if (c.version[0], c.version[1]) >= min_version]
