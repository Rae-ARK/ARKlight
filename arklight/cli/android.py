"""
`arklight android scaffold` -- Stage 1 of
docs/Backends/ANDROID-BACKEND-IMPLEMENTATION.md.

    arklight android scaffold <build-dir> -o <project-dir>

Templating only, no toolchain required -- see that file's staged-order
table and docs/Foundational/DESIGN-NOTES.md's "v0.0438: Android
backend" section. This module is the CLI-facing counterpart to
`arklight.backend.android.runtime` (the pure template-content builder,
see its own docstring): it owns everything that module deliberately
leaves out -- reading `arklight.config.py`'s `"android"` section
(mirroring `arklight.cli.live_streaming`'s own `"live_streaming"`
read), resolving/validating that config against defaults, copying the
`build-dir` itself into `app/src/main/assets/`, copying in an optional
raw icon/splash image, and writing every generated file to disk. Same
"template builders never touch disk, the CLI module owns filesystem
writes" split `arklight.cli.scaffold` already established for
`arklight new`.

`arklight android build` (Stage 2 -- shells out to the generated
project's `./gradlew assembleDebug`, requires a JDK) is a separate,
not-yet-implemented command; this module only produces the project
shell, it never invokes Gradle.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from arklight.backend.android import runtime
from arklight.config import ConfigError, load_config, section

# Defaults for every key `arklight.config.py`'s `"android"` section
# may set -- see docs/Foundational/DESIGN-NOTES.md's "App identity
# metadata" subsection for the full key list. A project with no
# `arklight.config.py` at all (or one with no `"android"` section)
# still scaffolds a buildable, if generically named and unbranded, app.
_DEFAULTS: dict[str, object] = {
    "app_name": "ARKlight App",
    "package_id": "com.arklight.app",
    "version_name": "1.0.0",
    "version_code": 1,
    "icon": None,
    "splash": None,
    "orientation": "portrait",
    "edge_to_edge": False,
}

# Config-file `orientation` values -> `android:screenOrientation`
# manifest attribute values (see `runtime.py`'s `project_files`
# docstring: "already resolved to its Android manifest value, e.g.
# 'fullSensor', not the config file's 'sensor'"). "sensor" maps to
# "fullSensor" (all 4 rotations, including upside-down) since that's
# what "let it rotate freely" means in practice for a full-window
# WebView app, not the narrower `sensor` attribute value (which
# excludes the upside-down orientation).
_ORIENTATIONS: dict[str, str] = {
    "portrait": "portrait",
    "landscape": "landscape",
    "sensor": "fullSensor",
    "unspecified": "unspecified",
}

# Package/application IDs are dotted Java-style identifiers: >= 2
# segments, each starting with a letter or underscore, alphanumerics/
# underscores only after that -- what Gradle's own `applicationId`
# validation requires.
_PACKAGE_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")

# Extensions this stage accepts for a raw icon/splash image -- kept
# narrow and explicit rather than accepting anything Android's
# res/drawable/ folder can technically hold, since a mismatched/exotic
# extension here would silently produce a resource file name Gradle's
# resource compiler rejects. See runtime.py's "v1" note on this being
# deliberately unrefined (no cropping/rasterization) for now.
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class AndroidError(Exception):
    """Raised when a build directory can't be scaffolded into an Android project."""


@dataclass
class ScaffoldResult:
    project_dir: Path
    written_paths: list[Path] = field(default_factory=list)
    app_name: str = ""
    package_id: str = ""


def _validate_package_id(package_id: str) -> None:
    if not isinstance(package_id, str) or not _PACKAGE_ID_RE.match(package_id):
        raise AndroidError(
            f"Invalid android.package_id {package_id!r} -- must be a dotted "
            f"Java-style identifier with at least two segments (letters, "
            f"digits, underscores only; no segment may start with a digit), "
            f"e.g. 'com.example.myapp'."
        )


def _validate_version_code(version_code: object) -> int:
    if not isinstance(version_code, int) or isinstance(version_code, bool):
        raise AndroidError(f"android.version_code must be an int, got {version_code!r}.")
    return version_code


def _resolve_orientation(value: object) -> str:
    if value not in _ORIENTATIONS:
        valid = ", ".join(sorted(_ORIENTATIONS))
        raise AndroidError(f"Unknown android.orientation {value!r} -- valid values: {valid}.")
    return _ORIENTATIONS[value]  # type: ignore[index]


def _resolve_asset(build_dir: Path, rel_path: object, key: str) -> Path:
    """
    Resolve `android.icon`/`android.splash`'s value to a real file
    under `build_dir` -- relative to the build directory root, same
    convention `arklight pwa --icon SRC:...` already uses, since by
    the time `arklight android scaffold` runs, `arklight build` has
    already copied a project's `assets/` into the build output.
    """
    if not isinstance(rel_path, str) or not rel_path:
        raise AndroidError(f"android.{key} must be a non-empty string path, got {rel_path!r}.")

    candidate = (build_dir / rel_path).resolve()
    try:
        candidate.relative_to(build_dir.resolve())
    except ValueError:
        raise AndroidError(
            f"android.{key} {rel_path!r} must stay inside the build directory."
        ) from None

    if not candidate.is_file():
        raise AndroidError(
            f"android.{key} {rel_path!r} not found in {build_dir} -- this path "
            f"is relative to the build directory root, same as `arklight pwa`'s "
            f"--icon."
        )
    if candidate.suffix.lower() not in _IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(_IMAGE_EXTENSIONS))
        raise AndroidError(
            f"android.{key} {rel_path!r} has an unsupported extension "
            f"{candidate.suffix!r} -- supported: {allowed}."
        )
    return candidate


def _copy_tree(src: Path, dst: Path) -> list[Path]:
    """Copy every file under `src` into `dst`, preserving relative
    structure. Returns the list of files written."""
    written: list[Path] = []
    for item in sorted(src.rglob("*")):
        target = dst / item.relative_to(src)
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, target)
            written.append(target)
    return written


def scaffold_project(
    build_dir: str | Path,
    *,
    output_dir: str | Path,
) -> ScaffoldResult:
    """
    Scaffold an Application-mode Android Studio / Gradle project at
    `output_dir` from an existing `arklight build` output directory
    (`build_dir`). Reads app identity from `arklight.config.py`'s
    `"android"` section, found next to `build_dir` (i.e. `build_dir`'s
    parent directory -- the same directory a project's `site.py`
    conventionally lives in, one level up from a build output like
    `ARK/`).

    Raises AndroidError for a missing/malformed build directory, a
    non-empty `output_dir`, an invalid/malformed `"android"` config
    section, or a missing/unsupported icon or splash image.
    """
    build_dir = Path(build_dir)
    if not build_dir.is_dir():
        raise AndroidError(f"Build directory not found: {build_dir}")
    if not (build_dir / "index.html").is_file():
        raise AndroidError(
            f"{build_dir} has no index.html at its root -- run `arklight build` "
            f"first, then scaffold its output directory. Application mode loads "
            f"exactly one fixed entry page, index.html."
        )

    project_dir = Path(output_dir)
    if project_dir.exists():
        if not project_dir.is_dir():
            raise AndroidError(f"{project_dir} already exists and is not a directory.")
        if any(project_dir.iterdir()):
            raise AndroidError(
                f"{project_dir} already exists and is not empty. Choose a "
                f"different -o directory, or clear it first."
            )

    try:
        config = load_config(build_dir.parent)
    except ConfigError as exc:
        raise AndroidError(str(exc)) from exc
    android_cfg = section(config, "android", _DEFAULTS)

    app_name = android_cfg["app_name"]
    if not isinstance(app_name, str) or not app_name.strip():
        raise AndroidError(f"android.app_name must be a non-empty string, got {app_name!r}.")

    package_id = android_cfg["package_id"]
    _validate_package_id(package_id)

    version_name = android_cfg["version_name"]
    if not isinstance(version_name, str) or not version_name.strip():
        raise AndroidError(
            f"android.version_name must be a non-empty string, got {version_name!r}."
        )

    version_code = _validate_version_code(android_cfg["version_code"])
    orientation = _resolve_orientation(android_cfg["orientation"])
    edge_to_edge = bool(android_cfg["edge_to_edge"])

    icon_path = (
        _resolve_asset(build_dir, android_cfg["icon"], "icon")
        if android_cfg["icon"] is not None
        else None
    )
    splash_path = (
        _resolve_asset(build_dir, android_cfg["splash"], "splash")
        if android_cfg["splash"] is not None
        else None
    )

    files = runtime.project_files(
        app_name=app_name,
        package_id=package_id,
        version_name=version_name,
        version_code=version_code,
        orientation=orientation,
        edge_to_edge=edge_to_edge,
        has_custom_icon=icon_path is not None,
        has_splash=splash_path is not None,
    )

    written: list[Path] = []
    for rel_path, contents in files.items():
        dest = project_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(contents, encoding="utf-8")
        written.append(dest)

    drawable_dir = project_dir / "app/src/main/res/drawable"
    if icon_path is not None:
        dest = drawable_dir / f"ic_launcher_custom{icon_path.suffix.lower()}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(icon_path, dest)
        written.append(dest)
    if splash_path is not None:
        dest = drawable_dir / f"splash_image{splash_path.suffix.lower()}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(splash_path, dest)
        written.append(dest)

    assets_dest = project_dir / "app/src/main/assets"
    written.extend(_copy_tree(build_dir, assets_dest))

    return ScaffoldResult(
        project_dir=project_dir,
        written_paths=sorted(written),
        app_name=app_name,
        package_id=package_id,
    )
