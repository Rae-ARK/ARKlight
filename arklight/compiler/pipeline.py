"""
Compiler Pipeline.

Ties every stage together, matching the architecture doc exactly:

    Python Source
        -> Python AST         (arklight.parser.discover, static analysis)
        -> ARK AST            (arklight.parser.loader executes the module;
                                 Site.build_ark_ast() calls each page fn)
        -> Normalization      (arklight.ir.normalize)
        -> Validation         (arklight.ir.validate)
        -> Website IR         (arklight.ir.build)
        -> Backend Interface  (arklight.backend.base.Backend)
        -> HTML + CSS Backends (arklight.backend.html / arklight.backend.css)
        -> index.html, styles.css (+ other routes)

As of v0.002, `build()` runs *multiple* backends over the same Website
IR by default (HTML and CSS) and merges their output files -- this is
exactly the "Backend Interface" fan-out the architecture doc describes
under "Future: CSS, JavaScript, Vue, Svelte": each backend consumes the
same IR and contributes its own output files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from arklight.backend.base import Backend
from arklight.backend.css.render import CSSBackend
from arklight.backend.html.render import HTMLBackend
from arklight.ir.build import WebsiteIR, build_website_ir
from arklight.ir.normalize import normalize_ark_ast
from arklight.ir.validate import ValidationError, validate_ark_ast
from arklight.parser.loader import SiteLoadError, load_site


def default_backends() -> list[Backend]:
    """The backends a normal `arklight build` runs: HTML + CSS."""
    return [HTMLBackend(), CSSBackend()]


@dataclass
class BuildResult:
    ir: WebsiteIR
    output_files: dict[str, str]
    written_paths: list[Path]


class CompileError(RuntimeError):
    """Raised when any pipeline stage fails. Wraps the underlying error."""


def compile_site_file(entry_path: str | Path) -> WebsiteIR:
    """
    Run every stage up to (and including) Website IR construction, but
    do not render or write files. Useful for tooling that just wants
    the IR (linting, additional backends, tests).
    """
    try:
        site, _discovered = load_site(entry_path)
    except SiteLoadError as exc:
        raise CompileError(str(exc)) from exc

    try:
        ark_ast = site.build_ark_ast()
    except Exception as exc:  # noqa: BLE001 -- surface page-function errors clearly
        raise CompileError(f"Error while building page(s): {exc}") from exc

    try:
        normalized = normalize_ark_ast(ark_ast)
    except TypeError as exc:
        raise CompileError(str(exc)) from exc

    try:
        validate_ark_ast(normalized)
    except ValidationError as exc:
        raise CompileError(str(exc)) from exc

    return build_website_ir(site.name, normalized)


def build(
    entry_path: str | Path,
    output_dir: str | Path,
    *,
    backends: list[Backend] | None = None,
) -> BuildResult:
    """
    Full pipeline: Python source file -> rendered files written to `output_dir`.

    Runs every backend in `backends` (default: HTML + CSS) over the
    same Website IR and merges their output files before writing.
    """
    backends = backends if backends is not None else default_backends()

    ir = compile_site_file(entry_path)

    output_files: dict[str, str] = {}
    for backend in backends:
        try:
            rendered = backend.render(ir)
        except Exception as exc:  # noqa: BLE001 -- surface backend errors clearly
            raise CompileError(f"Backend {backend.name!r} failed to render: {exc}") from exc
        output_files.update(rendered)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for rel_path, contents in output_files.items():
        dest = out_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(contents, encoding="utf-8")
        written.append(dest)

    return BuildResult(ir=ir, output_files=output_files, written_paths=written)
