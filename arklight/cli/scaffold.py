"""
`arklight new` -- project scaffolding.

    arklight new <name> [--template simple|production] [--dir PATH]

Turns one of the in-package templates (`arklight.cli.templates`) into
a real directory of files. This module owns validation and filesystem
writing; the templates themselves only ever return
`dict[relative_path, contents]` and never touch disk. See
docs/DESIGN-NOTES.md, "v0.004: CLI scaffolding (`arklight new`)".
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from arklight.cli.templates import TEMPLATES

# Reserved names that would either be meaningless as a project
# directory (".", "..") or -- if allowed through to `Path(dest_dir) /
# name` -- let `name` smuggle in path separators and write outside the
# intended destination (e.g. name="../evil" or name="a/b").
_RESERVED_NAMES = {".", ".."}


class ScaffoldError(RuntimeError):
    """Raised when `arklight new` can't create a project."""


@dataclass
class NewResult:
    project_dir: Path
    written_paths: list[Path]
    template: str


def _validate_name(name: str) -> None:
    if not name or not name.strip():
        raise ScaffoldError("Project name must not be empty.")
    if name in _RESERVED_NAMES:
        raise ScaffoldError(f"{name!r} is not a valid project name.")
    if os.sep in name or (os.altsep and os.altsep in name) or "/" in name:
        raise ScaffoldError(
            f"Project name {name!r} must not contain a path separator. "
            "Use --dir to choose where the project is created instead."
        )


def new_project(
    name: str,
    *,
    template: str = "simple",
    dest_dir: str | Path | None = None,
) -> NewResult:
    """
    Scaffold a new ARKlight project called `name` using `template`
    ("simple" or "production") into `dest_dir` (default: current
    working directory).

    Raises ScaffoldError if `name`/`template` are invalid, or if the
    target directory already exists and is non-empty.
    """
    _validate_name(name)

    try:
        build_files = TEMPLATES[template]
    except KeyError as exc:
        available = ", ".join(sorted(TEMPLATES))
        raise ScaffoldError(
            f"Unknown template {template!r}. Available templates: {available}."
        ) from exc

    parent = Path(dest_dir) if dest_dir is not None else Path.cwd()
    project_dir = parent / name

    if project_dir.exists():
        if not project_dir.is_dir():
            raise ScaffoldError(f"{project_dir} already exists and is not a directory.")
        if any(project_dir.iterdir()):
            raise ScaffoldError(
                f"{project_dir} already exists and is not empty. Choose a "
                "different name, or pass --dir to scaffold elsewhere."
            )

    files = build_files(name)

    written: list[Path] = []
    for rel_path, contents in files.items():
        dest = project_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(contents, encoding="utf-8")
        written.append(dest)

    return NewResult(project_dir=project_dir, written_paths=sorted(written), template=template)
