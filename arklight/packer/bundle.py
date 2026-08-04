"""
ARK Bundle packer -- v0.037 ("ARK Bundle spec v1" + sealing).

Packs an already-built ARKlight output directory (whatever `arklight
build` wrote to disk) into a single `.ark` file: an HTML/[sealed or
plain ZIP] polyglot. See docs/DESIGN-NOTES.md, "v0.036: ARK Bundle
spec v1" and "v0.037: sealed bundles", for the full format writeup and
rationale.

This module only ever reads files a normal build already produced --
it does not import or touch the compiler pipeline (parser/ir/backend).
That keeps packing a step *after* `arklight build`, not a new pipeline
stage fused into it.

    [ inlined entry page ][ sealed OR plain archive of the build files ]

- HTML parsers stop at `</html>` and never reach the bytes after it,
  so opening the `.ark` file in a browser just renders the page,
  regardless of what the archive half contains.
- **Sealed (default):** the archive half is encrypted (see
  `arklight.packer.seal`) -- a generic archive tool, "rename to .zip",
  or hex editor sees only opaque bytes, not a ZIP, so nothing can
  casually inspect or splice its contents. `arklight unpack` reverses
  this.
- **Plain (opt-in via `sealed=False` / `--plain`):** the original v1
  behavior -- a real, generically-openable ZIP tail. ZIP readers seek
  to the End-Of-Central-Directory record near the end of the file
  rather than assuming the archive starts at byte 0, so any archive
  tool opens the same bytes as a normal ZIP. Kept as an explicit choice
  for anyone who *wants* the extracted build to be freely inspectable
  or re-editable without ARKlight installed.

v1 archive scope (applies to both sealed and plain): `.html`/`.css`/
`.js` files are read as text so the entry page can be inlined (see
`_inline_entry_page`). Every other file found in the build directory --
most notably an `assets/` folder with images, audio, video, or other
files -- is carried into the archive too, as raw bytes with no attempt
to read or transform their contents. Only the *inlined front-matter
page* is unaffected: it still references `assets/...` by relative
path, which only resolves once the bundle is unpacked next to those
files, not when the `.ark` is opened directly in a browser as a
polyglot.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from arklight.packer.seal import SealError, SEALED_MAGICS, seal, unseal

STYLESHEET_NAME = "styles.css"
SCRIPT_NAME = "arklight.js"
ENTRY_HTML_NAME = "index.html"
HTML_END_MARKER = b"</html>\n"

# These file types are read as text (needed to inline the entry page --
# see _inline_entry_page). Everything else in the build directory is
# still packed into the ZIP half, just as raw bytes instead of text --
# see PackResult.packed_paths / _PACKED_SUFFIXES is no longer a filter,
# only a hint for which files get text-mode handling.
_TEXT_SUFFIXES = {".html", ".css", ".js"}

# Matches the exact tags the HTML backend emits for the entry page
# (arklight/backend/html/render.py: _render_page). Whitespace between
# attributes is tolerated in case that backend's formatting shifts
# slightly; the attribute values themselves are not.
_LINK_RE = re.compile(
    r'<link\s+rel="stylesheet"\s+href="' + re.escape(STYLESHEET_NAME) + r'"\s*/?>'
)
_SCRIPT_RE = re.compile(
    r'<script\s+src="' + re.escape(SCRIPT_NAME) + r'"\s+defer\s*></script>'
)


class PackError(Exception):
    """Raised when a build directory can't be packed into a .ark bundle,
    or a .ark bundle can't be unpacked back out."""


@dataclass
class PackResult:
    output_path: Path
    packed_paths: list[str] = field(default_factory=list)
    skipped_paths: list[str] = field(default_factory=list)
    sealed: bool = True
    passphrase_protected: bool = False


@dataclass
class UnpackResult:
    output_dir: Path
    extracted_paths: list[str] = field(default_factory=list)
    was_sealed: bool = False


def _inline_entry_page(entry_html: str, css: str, js: str) -> str:
    """
    Return `entry_html` with its stylesheet <link> and behavior-runtime
    <script src> swapped for their actual contents, inlined. This is
    the "self-contained entry page" half of the polyglot -- everything
    needed to render the page is now inside this one HTML document.
    """
    if not _LINK_RE.search(entry_html):
        raise PackError(
            f'Could not find the expected <link rel="stylesheet" href="{STYLESHEET_NAME}"> '
            f"tag in {ENTRY_HTML_NAME} -- is this an ARKlight build output directory?"
        )
    if not _SCRIPT_RE.search(entry_html):
        raise PackError(
            f'Could not find the expected <script src="{SCRIPT_NAME}" defer></script> '
            f"tag in {ENTRY_HTML_NAME} -- is this an ARKlight build output directory?"
        )

    # A `</script>` sequence inside the inlined JS would otherwise close
    # the tag early. ARKlight's JS backend only ever emits its own fixed
    # runtime (no arbitrary user JS strings are accepted -- see
    # docs/DESIGN-NOTES.md), so this should never trigger in practice;
    # it's a defensive escape, not a workaround for a known case.
    safe_js = js.replace("</script>", "<\\/script>")

    inlined = _LINK_RE.sub(lambda _: f"<style>\n{css}\n</style>", entry_html, count=1)
    inlined = _SCRIPT_RE.sub(lambda _: f"<script>\n{safe_js}\n</script>", inlined, count=1)
    return inlined


def pack(
    build_dir: str | Path,
    output_path: str | Path,
    *,
    sealed: bool = True,
    passphrase: str | None = None,
) -> PackResult:
    """
    Pack the ARKlight build output in `build_dir` into a `.ark` bundle
    at `output_path`.

    `build_dir` must be an existing `arklight build` output directory
    (i.e. it contains index.html, styles.css, and arklight.js at its
    root). Raises PackError with a clear message if it doesn't look
    like one.

    `sealed` (default True) encrypts the archive half so a generic
    archive tool can't open or splice it -- see `arklight.packer.seal`
    for the format and the honest limits of embedded-key mode (no
    `passphrase` given). Pass `sealed=False` to get the original v1
    plain-ZIP-tail bundle instead, fully openable by any archive tool.

    `passphrase`, if given, is only valid with `sealed=True`: it
    switches sealing from embedded-key mode (convenient, not secret)
    to passphrase-derived-key mode (real confidentiality -- the same
    passphrase must be supplied to `unpack()` later).
    """
    if passphrase is not None and not sealed:
        raise PackError(
            "`passphrase` only applies to sealed bundles -- pass sealed=True "
            "(the default), or drop the passphrase for a plain bundle."
        )

    build_dir = Path(build_dir)
    output_path = Path(output_path)

    if not build_dir.is_dir():
        raise PackError(f"Build directory not found: {build_dir}")

    entry_path = build_dir / ENTRY_HTML_NAME
    stylesheet_path = build_dir / STYLESHEET_NAME
    script_path = build_dir / SCRIPT_NAME

    for required_path, label in (
        (entry_path, ENTRY_HTML_NAME),
        (stylesheet_path, STYLESHEET_NAME),
        (script_path, SCRIPT_NAME),
    ):
        if not required_path.is_file():
            raise PackError(
                f"{label} not found in {build_dir} -- run `arklight build` first, "
                f"then pack its output directory."
            )

    entry_html = entry_path.read_text(encoding="utf-8")
    css = stylesheet_path.read_text(encoding="utf-8")
    js = script_path.read_text(encoding="utf-8")

    inlined_html = _inline_entry_page(entry_html, css, js)
    prefix_bytes = inlined_html.encode("utf-8")

    all_files = sorted(p for p in build_dir.rglob("*") if p.is_file())
    packed = all_files
    skipped: list[Path] = []

    # Build the ZIP entirely in memory first -- offsets zipfile writes
    # are always relative to wherever it started writing, so a ZIP
    # built into a fresh buffer at offset 0 is byte-for-byte the same
    # archive as one built by appending after prefix bytes in a real
    # file. That's what makes both the plain (concat-and-done) and
    # sealed (encrypt-then-concat) paths below correct: neither one
    # patches a single ZIP header by hand.
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in packed:
            arcname = path.relative_to(build_dir).as_posix()
            zf.write(path, arcname)
    zip_bytes = zip_buffer.getvalue()

    if sealed:
        archive_bytes = seal(zip_bytes, passphrase=passphrase)
    else:
        archive_bytes = zip_bytes

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(prefix_bytes + archive_bytes)

    return PackResult(
        output_path=output_path,
        packed_paths=[p.relative_to(build_dir).as_posix() for p in packed],
        skipped_paths=[p.relative_to(build_dir).as_posix() for p in skipped],
        sealed=sealed,
        passphrase_protected=sealed and passphrase is not None,
    )


def _find_archive_start(data: bytes) -> int:
    """
    The archive half (sealed or plain) begins immediately after the
    inlined front-matter page's `</html>\n` -- exactly what the HTML
    backend always emits to close the document (see
    arklight/backend/html/render.py). Locating it this way (rather
    than searching for the seal MAGIC, which plain bundles never have)
    works identically for both bundle kinds.
    """
    idx = data.find(HTML_END_MARKER)
    if idx == -1:
        raise PackError(
            "Could not locate the end of the inlined HTML front matter "
            "(`</html>`) -- is this a valid .ark bundle?"
        )
    return idx + len(HTML_END_MARKER)


def unpack(
    bundle_path: str | Path,
    output_dir: str | Path,
    *,
    passphrase: str | None = None,
) -> UnpackResult:
    """
    Reverse of `pack()`: extract a `.ark` bundle's archive half back
    into a normal ARKlight build directory at `output_dir`.

    Auto-detects sealed vs. plain bundles -- `passphrase` is only
    needed (and only used) if the bundle was sealed with one. Raises
    PackError if the bundle can't be read, is missing/wrong
    passphrase, or its archive half fails the integrity check (see
    `arklight.packer.seal.unseal`).
    """
    bundle_path = Path(bundle_path)
    output_dir = Path(output_dir)

    if not bundle_path.is_file():
        raise PackError(f"Bundle file not found: {bundle_path}")

    data = bundle_path.read_bytes()
    archive_bytes = data[_find_archive_start(data):]

    was_sealed = archive_bytes.startswith(SEALED_MAGICS)
    if was_sealed:
        try:
            zip_bytes = unseal(archive_bytes, passphrase=passphrase)
        except SealError as exc:
            raise PackError(str(exc)) from exc
    else:
        zip_bytes = archive_bytes

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(output_dir)
            extracted = zf.namelist()
    except zipfile.BadZipFile as exc:
        raise PackError(
            f"Bundle's archive half isn't a valid ZIP once unsealed: {exc}"
        ) from exc

    return UnpackResult(
        output_dir=output_dir,
        extracted_paths=sorted(extracted),
        was_sealed=was_sealed,
    )
