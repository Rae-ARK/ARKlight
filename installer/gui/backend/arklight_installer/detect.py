"""Detect CPython interpreters on the host system.

No version-compatibility filtering here: per docs/Architecture.md §2,
the installer has one install target (current stable PyPI release) and
lets that release's own package metadata be what fails, loudly, if an
interpreter genuinely can't run it — rather than the installer
predicting that ahead of time.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

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
