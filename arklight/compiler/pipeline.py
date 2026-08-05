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

`build()` also copies a top-level `assets/` folder (next to the site's
entry file) into `<output_dir>/assets` automatically, if one exists --
see `_copy_assets` below.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from arklight import experimental
from arklight.backend.base import Backend
from arklight.backend.css.render import CSSBackend
from arklight.backend.html.render import HTMLBackend
from arklight.backend.js.render import JSBackend
from arklight.ir.build import WebsiteIR, build_website_ir
from arklight.ir.normalize import normalize_ark_ast
from arklight.ir.validate import ValidationError, validate_ark_ast
from arklight.parser.loader import SiteLoadError, load_site

# A stage callback: called with a short, human-readable message every
# time the pipeline moves into a new stage (site discovery, AST build,
# normalization, validation, IR build, each backend's render/
# postprocess, writing output, copying assets, ...). `compile_site_file`
# and `build` both default this to a no-op, so calling either exactly
# as before is unaffected -- passing `on_stage=` is purely additive.
# The CLI's `--verbose`/`--debug` flags are what actually supply one
# (see `arklight.cli.main`); nothing in this module ever prints on its
# own, keeping stage reporting a presentation concern, not a pipeline one.
StageLogger = Callable[[str], None]


def _noop_stage_logger(_message: str) -> None:
    return None

# Name of the top-level, next-to-`site.py` folder ARKlight auto-copies
# into the output directory (verbatim, recursively) if it exists. Fixes
# the "404 images" gotcha documented in docs/DESIGN-NOTES.md: previously
# a site's `assets/` (images, fonts, favicons, ...) had to be copied by
# hand with `cp -r assets ARK/assets` after every build.
ASSETS_DIR_NAME = "assets"


def default_backends() -> list[Backend]:
    """The backends a normal `arklight build` runs: HTML + CSS + JS."""
    return [HTMLBackend(), CSSBackend(), JSBackend()]


@dataclass
class BuildResult:
    ir: WebsiteIR
    output_files: dict[str, str]
    written_paths: list[Path]


class CompileError(RuntimeError):
    """Raised when any pipeline stage fails. Wraps the underlying error."""


def compile_site_file(
    entry_path: str | Path,
    *,
    on_stage: StageLogger | None = None,
    css_var_overrides: dict[str, str] | None = None,
    lang: str | None = None,
) -> WebsiteIR:
    """
    Run every stage up to (and including) Website IR construction, but
    do not render or write files. Useful for tooling that just wants
    the IR (linting, additional backends, tests).

    `on_stage`, if given, is called once per stage with a short message
    describing what's about to run -- purely for observability (e.g.
    the CLI's `--verbose`/`--debug` output); it has no effect on the
    result and defaults to a no-op.

    `css_var_overrides`, if given, is merged *over* whatever the site
    file itself set via `Site(max_width=..., bg=...)` -- i.e. this is
    an outer override, for callers (the CLI's `--max-width`/`--bg`
    flags) that need to set a design token without editing the site
    file. Defaults to `None` (no additional overrides), so calling
    `compile_site_file` exactly as before is unaffected.

    `lang`, if given, overrides the site file's own `Site(lang=...)`
    (or its "en" default) the same way -- for the CLI's `--lang` flag.
    """
    log = on_stage or _noop_stage_logger

    log("Discovering site and compiling AST trees...")
    try:
        site, _discovered = load_site(entry_path)
    except SiteLoadError as exc:
        raise CompileError(str(exc)) from exc

    try:
        ark_ast = site.build_ark_ast()
    except Exception as exc:  # noqa: BLE001 -- surface page-function errors clearly
        raise CompileError(f"Error while building page(s): {exc}") from exc

    log("Normalizing AST...")
    try:
        normalized = normalize_ark_ast(ark_ast)
    except TypeError as exc:
        raise CompileError(str(exc)) from exc

    log("Running validation...")
    try:
        validate_ark_ast(normalized)
    except ValidationError as exc:
        raise CompileError(str(exc)) from exc

    # Experimental API warnings (docs/EXPERIMENTAL-APIS.md): every
    # opt-in call the site made (currently just `site.media_query(...)`)
    # was already recorded on `site.experimental_usages` at call time --
    # print the inline "[EXPERIMENTAL FEATURE ACTIVE]" banner for each
    # one now, right after validation succeeds, so it's interleaved with
    # stage narration instead of only showing up in an end-of-build
    # summary. Not gated behind `on_stage`/`--verbose` being set for
    # anything else: an experimental-feature warning always prints if
    # a logger was supplied at all.
    for usage in site.experimental_usages:
        log(experimental.format_inline_banner(usage))

    log("Building website IR...")
    merged_css_var_overrides = dict(site.css_var_overrides)
    if css_var_overrides:
        merged_css_var_overrides.update(css_var_overrides)

    return build_website_ir(
        site.name,
        normalized,
        custom_styles=site.custom_styles,
        media_queries=site.custom_media_queries,
        experimental_usages=site.experimental_usages,
        css_var_overrides=merged_css_var_overrides,
        lang=lang if lang is not None else site.lang,
    )


def build(
    entry_path: str | Path,
    output_dir: str | Path,
    *,
    backends: list[Backend] | None = None,
    on_stage: StageLogger | None = None,
    css_var_overrides: dict[str, str] | None = None,
    lang: str | None = None,
) -> BuildResult:
    """
    Full pipeline: Python source file -> rendered files written to `output_dir`.

    Runs every backend in `backends` (default: HTML + CSS) over the
    same Website IR and merges their output files before writing.

    `on_stage`, if given, is called once per stage (site discovery/AST,
    normalization, validation, IR build, each backend's render/
    postprocess, writing files, copying assets) with a short message --
    see `compile_site_file` above. Defaults to a no-op; purely additive.

    `css_var_overrides`/`lang`, if given, are forwarded to
    `compile_site_file` (see there) -- this is how the CLI's
    `--max-width`/`--bg`/`--font-family`/`--lang` flags reach the
    design tokens and `<html lang>` without requiring a site-file edit.
    """
    log = on_stage or _noop_stage_logger
    backends = backends if backends is not None else default_backends()

    ir = compile_site_file(
        entry_path, on_stage=log, css_var_overrides=css_var_overrides, lang=lang
    )

    output_files: dict[str, str] = {}
    for backend in backends:
        log(f"Rendering backend {backend.name!r}...")
        try:
            rendered = backend.render(ir)
        except Exception as exc:  # noqa: BLE001 -- surface backend errors clearly
            raise CompileError(f"Backend {backend.name!r} failed to render: {exc}") from exc
        output_files.update(rendered)

    # Second pass: each backend gets a chance to transform the *combined*
    # output of every backend's render(), in the same order. Default
    # Backend.postprocess() is a no-op, so this changes nothing unless a
    # backend explicitly overrides it -- see arklight.backend.base.Backend.
    for backend in backends:
        log(f"Postprocessing backend {backend.name!r}...")
        try:
            output_files = backend.postprocess(output_files)
        except Exception as exc:  # noqa: BLE001 -- surface backend errors clearly
            raise CompileError(f"Backend {backend.name!r} failed to postprocess: {exc}") from exc

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    log(f"Writing {len(output_files)} file(s) -> {out_dir}/...")
    written: list[Path] = []
    try:
        for rel_path, contents in output_files.items():
            dest = out_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(contents, encoding="utf-8")
            written.append(dest)
    except OSError as exc:
        # Uncharted territory: nothing above this validates disk space,
        # permissions, or a mid-write disconnect (e.g. a network drive).
        # Say plainly how much of the build did land, since `out_dir` is
        # now a mix of complete and missing files, not a clean failure.
        raise CompileError(
            f"Failed while writing output to {out_dir}/ "
            f"({len(written)}/{len(output_files)} file(s) written before "
            f"the failure -- the output directory is now incomplete): {exc}"
        ) from exc

    log("Copying assets...")
    try:
        written.extend(_copy_assets(entry_path, out_dir))
    except OSError as exc:
        raise CompileError(
            f"Failed while copying assets/ into {out_dir}/assets/ -- "
            f"{len(written)} page file(s) were already written successfully, "
            f"so the build is partially complete: {exc}"
        ) from exc

    log(f"Build complete -> {out_dir}/index.html")
    return BuildResult(ir=ir, output_files=output_files, written_paths=written)


def _copy_assets(entry_path: str | Path, out_dir: Path) -> list[Path]:
    """
    Copy a top-level `assets/` folder (sitting next to the site's entry
    file) into `<output_dir>/assets`, recursively, if one exists.

    This was previously a manual, easy-to-forget step (`cp -r assets
    ARK/assets`) -- a real gap, not a template-only concern, per
    docs/DESIGN-NOTES.md. No-op (returns an empty list) when there's no
    `assets/` folder to copy.
    """
    assets_src = Path(entry_path).resolve().parent / ASSETS_DIR_NAME
    if not assets_src.is_dir():
        return []

    assets_dest = out_dir / ASSETS_DIR_NAME
    shutil.copytree(assets_src, assets_dest, dirs_exist_ok=True)
    return sorted(p for p in assets_dest.rglob("*") if p.is_file())
