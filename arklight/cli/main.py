"""
ARKlight CLI.

    arklight new my-site
    arklight build site.py -o ARK
    arklight pack ARK -o site.ark
    arklight unpack site.ark -o ARK
    arklight pwa ARK --name "My Site" --icon assets/icon-192.png:192x192
    arklight search Picture

Beginner-friendly by design: a handful of subcommands, sensible
defaults (builds AND opens the result in your browser), and error
messages that point at exactly what went wrong (parse error, missing
Site(), unknown component, etc.) rather than a raw traceback.
"""

from __future__ import annotations

import argparse
import mimetypes
import re
import sys
import traceback
import warnings
import webbrowser
from pathlib import Path

from arklight import __version__
from arklight.cli.scaffold import ScaffoldError, new_project
from arklight.cli.search import search_component
from arklight.cli.templates import TEMPLATES
from arklight.compiler.pipeline import BuildResult, CompileError, build
from arklight.packer.bundle import PackError, pack, unpack
from arklight.pwa import PWAError, enable_pwa

# Prefix every `--verbose`/`--debug` stage line gets, so pipeline
# progress reads as ARKlight "thinking out loud" rather than bare,
# unattributed text mixed in with normal build output.
_STAGE_PREFIX = "[ARKlight]"

# Short nudge printed after every `production`-template scaffold --
# the template's layout (components/ pages/ content/) already puts
# this into practice, but a first-time user staring at four new
# directories benefits from being told *why*, not just handed the
# files. Points at `--explain-architecture` rather than dumping the
# full guide inline, so the normal `arklight new` output stays short.
_PRODUCTION_ARCHITECTURE_NOTE = (
    "Recommended: keep this project service-oriented and separated by "
    "concern (routes thin, content/markup/logic in their own modules) "
    "-- minimal boilerplate, not a framework to fight. Run `arklight "
    "new --explain-architecture` to see how."
)

# The `--explain-architecture` guide itself -- concrete, tied to the
# actual `production` template layout (site.py/components/pages/
# content/assets), not generic architecture advice. Printed standalone
# (`arklight new --explain-architecture`, no `name` needed) or after a
# fresh `production` scaffold when the flag is passed alongside a name.
_ARCHITECTURE_GUIDE = """\
ARKlight production layout: service-oriented, separated by concern
--------------------------------------------------------------------

  site.py           routes only -- @site.page(...) decorators that
                     each delegate to one function in pages/. Nothing
                     else belongs here.
  pages/*.py        one module per route. Builds that page's Page(...)
                     tree by composing components/ + content/ --
                     no markup lives inline in site.py.
  components/*.py   reusable pieces (nav, footer, cards, ...) as plain
                     functions. No special "component" mechanism --
                     ordinary composition, so there's nothing framework-
                     specific to learn.
  content/*.py      copy/text/config constants, kept out of both
                     components/ and pages/ so wording can change
                     without touching markup or logic.
  assets/           images, fonts, favicons -- copied into the build
                     output automatically.

Why this shape:
  - Each concern (routing, page assembly, presentation, content) lives
    in exactly one place, so a change to wording, layout, or a shared
    nav touches exactly one file, not several.
  - "Service-oriented" here just means: pages/ and components/ are
    plain functions with a clear input/output contract (return
    Page(...) or a node) -- swap, test, or reuse them independently,
    the same way you'd treat any small service.
  - It stays minimal-boilerplate on purpose -- no base classes, no
    config beyond content/, no generated files to keep in sync by
    hand. Every file above is something you'd write anyway; this is
    just where it goes.

How to extend it:
  1. New page: add pages/<name>.py returning Page(...), then wire a
     @site.page("/<route>") decorator in site.py that calls it. The
     decorator must live in site.py -- ARKlight discovers routes by
     statically scanning the entry file's own source, not files it
     imports.
  2. New shared piece (nav, card, footer, ...): add it to components/
     as a plain function, import it from whichever pages/ use it.
  3. New copy/config: add it to content/, import from pages/ or
     components/ rather than hardcoding strings in either.

Scaffold this layout with: arklight new <name> --template production
"""


def open_in_browser(result: BuildResult, output_dir: str | Path) -> bool:
    """
    Open the site's home page ("/") in the default browser as a
    `file://` URL. Internal links are already rewritten to relative
    file paths by the HTML backend, so navigating between pages works
    correctly straight off disk -- no local server required.

    Returns True if a browser launch was attempted, False if there was
    nothing to open (e.g. no "/" route). Swallows browser-launch
    failures (e.g. headless environments) rather than failing the
    build -- the files are already written either way.
    """
    index_path = Path(output_dir) / "index.html"
    if not index_path.exists():
        return False
    try:
        webbrowser.open(index_path.resolve().as_uri())
    except Exception:  # noqa: BLE001 -- opening a browser is best-effort
        return False
    return True


def _stage_logger(message: str) -> None:
    """`on_stage` callback for `build()` -- prints each pipeline stage
    as it starts, prefixed like the rest of ARKlight's CLI output.
    Wired up only when `--verbose`/`--debug` is passed (see
    `_cmd_build`); the pipeline itself never prints anything on its own."""
    print(f"{_STAGE_PREFIX} {message}")


# v0.0431 emergency patch: marker prefix `arklight.backend.html.render`
# puts on every known-alpha-limitation warning (see UNROUTED_REFERENCE_ATTRS
# there). Matched here so the CLI can surface these clearly and always --
# not gated behind --verbose, and not dependent on Python's default
# warning filters (which only show a `UserWarning` once per call site,
# and not at all if the caller has warnings configured/silenced) --
# without touching unrelated warnings a site's own code might raise.
_ALPHA_WARNING_MARKER = "[ARKlight ALPHA]"


def _print_alpha_warnings(caught: list[warnings.WarningMessage]) -> None:
    """Print every captured `[ARKlight ALPHA]`-marked warning from a
    build, framed as a known, non-fatal alpha limitation -- not a build
    failure, but not silent either. This is the graceful-degradation
    path: the feature the site author used isn't broken by ARKlight
    refusing to build, it's flagged as "may not work everywhere yet"
    with a pointer to the patch tracking it.
    """
    alpha_warnings = [w for w in caught if _ALPHA_WARNING_MARKER in str(w.message)]
    if not alpha_warnings:
        return

    print(
        f"{_STAGE_PREFIX} NOTE: this alpha build is under active maintenance. "
        f"{len(alpha_warnings)} known limitation(s) were hit during this build "
        f"-- the site was still built, but the feature(s) below may not work "
        f"correctly everywhere. Please wait for (or update to) the emergency "
        f"patch series (v0.043x) to have these handled gracefully:",
        file=sys.stderr,
    )
    for w in alpha_warnings:
        print(f"  - {w.message}", file=sys.stderr)


def _cmd_build(args: argparse.Namespace) -> int:
    # --debug implies --verbose: tracing compiler errors is much easier
    # with the stage-by-stage narration already on screen above the
    # traceback, so there's no reason to ask for both separately.
    verbose = args.verbose or args.debug
    on_stage = _stage_logger if verbose else None

    # --max-width/--bg let the *build invocation* set a design token
    # without touching the site file's Site(...) call -- e.g. CI
    # producing a widescreen variant of a site that otherwise ships
    # with a narrower Site(max_width=...) default. Only the flags the
    # user actually passed are forwarded, so leaving both off changes
    # nothing (falls straight through to the site file's own value, or
    # ARKlight's stock default if it set none either).
    css_var_overrides: dict[str, str] = {}
    if args.max_width is not None:
        css_var_overrides["--ark-max-width"] = args.max_width
    if args.bg is not None:
        css_var_overrides["--ark-bg"] = args.bg
    if args.font_family is not None:
        css_var_overrides["--ark-font-family"] = args.font_family
    if args.button_text is not None:
        css_var_overrides["--ark-button-text"] = args.button_text

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = build(
                args.entry,
                args.output,
                on_stage=on_stage,
                css_var_overrides=css_var_overrides or None,
                lang=args.lang,
            )
    except CompileError as exc:
        if args.debug:
            # Full chained traceback (CompileError's __cause__ is the
            # original stage exception -- see arklight.compiler.pipeline)
            # instead of the short one-line message, so the exact
            # Python frame/line that failed is visible rather than just
            # which pipeline stage wrapped it.
            print(f"{_STAGE_PREFIX} Build failed -- full trace (--debug):", file=sys.stderr)
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
        else:
            print(f"ARKlight build failed: {exc}", file=sys.stderr)
            print("Re-run with --debug for the full traceback.", file=sys.stderr)
        return 1

    print(f"ARKlight v{__version__} built {len(result.written_paths)} file(s) -> {args.output}/")
    for path in result.written_paths:
        print(f"  {path}")

    _print_alpha_warnings(caught)

    if args.open:
        opened = open_in_browser(result, args.output)
        if opened:
            print("Opened in your default browser.")

    return 0


def _cmd_pack(args: argparse.Namespace) -> int:
    if args.passphrase:
        print(
            "Heads up: passing --passphrase on the command line is not the "
            "recommended way to do this -- it can end up in your shell "
            "history and in process listings visible to other users on this "
            "machine. Prefer an interactive prompt or an environment "
            "variable in scripted/CI use.",
            file=sys.stderr,
        )

    try:
        result = pack(
            args.build_dir,
            args.output,
            sealed=not args.plain,
            passphrase=args.passphrase,
        )
    except PackError as exc:
        print(f"ARKlight pack failed: {exc}", file=sys.stderr)
        return 1

    print(f"ARKlight v{__version__} packed {len(result.packed_paths)} file(s) -> {result.output_path}")
    for path in result.packed_paths:
        print(f"  {path}")
    print(
        "Note: .ark is ARKlight's own bundle format, not something a browser "
        "opens directly -- double-clicking it will offer to open it as a "
        "generic ZIP/archive, not as a site. Run `arklight unpack "
        f"{result.output_path}` to get a build/ directory back, then open "
        "that directory's index.html in a browser (or serve it)."
    )

    if not result.sealed:
        print(
            "Archive half is PLAIN -- openable/inspectable/editable by any "
            "generic ZIP tool. Drop --plain (the default) to seal it instead."
        )
    elif result.passphrase_protected:
        print(
            "Archive half is SEALED with your passphrase -- keep it, "
            "`arklight unpack` will need the same one to open this bundle."
        )
    else:
        print(
            "Archive half is SEALED (embedded key) -- opaque to generic archive "
            "tools, but `arklight unpack` can always open it with no extra input. "
            "For real secrecy against someone who also has ARKlight, use --passphrase."
        )

    return 0


def _cmd_unpack(args: argparse.Namespace) -> int:
    try:
        result = unpack(args.bundle, args.output, passphrase=args.passphrase)
    except PackError as exc:
        print(f"ARKlight unpack failed: {exc}", file=sys.stderr)
        return 1

    kind = "sealed" if result.was_sealed else "plain"
    print(
        f"ARKlight v{__version__} unpacked {len(result.extracted_paths)} file(s) "
        f"from a {kind} bundle -> {result.output_dir}/"
    )
    for path in result.extracted_paths:
        print(f"  {path}")

    return 0


_ICON_SIZES_RE = re.compile(r"^(\d+x\d+|any)$")


def _parse_icon_spec(spec: str) -> dict[str, str]:
    """
    Parse one `--icon SRC:SIZES[:TYPE]` value into a manifest icon dict
    (`{"src": ..., "sizes": ..., "type": ...}`), same shape
    `enable_pwa(icons=...)` already accepts.

    `SRC` is a path relative to the build directory root (same as
    `manifest.json` itself), e.g. an icon already copied into the
    build under `assets/`. `SIZES` is `WIDTHxHEIGHT` (e.g. `192x192`)
    or `any`. `TYPE` is optional and inferred from `SRC`'s extension
    via `mimetypes` when omitted -- pass it explicitly for anything
    `mimetypes` doesn't resolve.

    Raises `ValueError` (caught by `_cmd_pwa` and reported as a normal
    CLI error) on anything malformed.
    """
    parts = spec.split(":")
    if len(parts) not in (2, 3):
        raise ValueError(
            f"Invalid --icon value {spec!r} -- expected SRC:SIZES or "
            f"SRC:SIZES:TYPE, e.g. --icon assets/icon-192.png:192x192"
        )

    src, sizes = parts[0], parts[1]
    mime_type = parts[2] if len(parts) == 3 else None

    if not src:
        raise ValueError(f"Invalid --icon value {spec!r} -- SRC is empty")
    if not _ICON_SIZES_RE.match(sizes):
        raise ValueError(
            f"Invalid --icon value {spec!r} -- SIZES must look like "
            f"WIDTHxHEIGHT (e.g. 192x192) or 'any', got {sizes!r}"
        )

    if mime_type is None:
        guessed, _ = mimetypes.guess_type(src)
        if guessed is None:
            raise ValueError(
                f"Invalid --icon value {spec!r} -- couldn't infer a MIME type "
                f"from {src!r}; pass one explicitly as SRC:SIZES:TYPE"
            )
        mime_type = guessed

    return {"src": src, "sizes": sizes, "type": mime_type}


def _cmd_pwa(args: argparse.Namespace) -> int:
    try:
        icons = [_parse_icon_spec(spec) for spec in (args.icon or [])]
    except ValueError as exc:
        print(f"ARKlight pwa failed: {exc}", file=sys.stderr)
        return 1

    try:
        result = enable_pwa(
            args.build_dir,
            name=args.name,
            short_name=args.short_name,
            start_url=args.start_url,
            theme_color=args.theme_color,
            background_color=args.background_color,
            display=args.display,
            icons=icons,
        )
    except PWAError as exc:
        print(f"ARKlight pwa failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"ARKlight v{__version__} enabled PWA support in {result.build_dir}/ "
        f"({len(result.cached_paths)} file(s) precached, cache {result.cache_name})"
    )
    print(f"  {result.manifest_path.relative_to(result.build_dir)}")
    print(f"  {result.service_worker_path.relative_to(result.build_dir)}")
    if icons:
        print(f"  {len(icons)} icon(s) registered in the manifest")
    else:
        print(
            "  no --icon given -- manifest has an empty icons list; "
            "browsers may decline to prompt an install"
        )
    for path in result.updated_pages:
        print(f"  {path} (manifest link + SW registration injected)")
    print(
        "Re-run `arklight pwa` on this directory after every `arklight build` "
        "to keep the manifest/service worker/precache list in sync -- it's "
        "idempotent, so this is always safe."
    )

    return 0


def _cmd_new(args: argparse.Namespace) -> int:
    # `--explain-architecture` is informational and doesn't require a
    # project name -- `arklight new --explain-architecture` alone just
    # prints the guide and exits, so it can be run before ever
    # scaffolding anything. If a name *is* given alongside it, fall
    # through and scaffold as normal, then print the guide after.
    if args.explain_architecture and args.name is None:
        print(_ARCHITECTURE_GUIDE)
        return 0

    if args.name is None:
        print("ARKlight new failed: the following arguments are required: name", file=sys.stderr)
        return 1

    try:
        result = new_project(args.name, template=args.template, dest_dir=args.dir)
    except ScaffoldError as exc:
        print(f"ARKlight new failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"ARKlight v{__version__} scaffolded a {result.template!r} project "
        f"-> {result.project_dir}/"
    )
    for path in result.written_paths:
        print(f"  {path}")
    print()
    print("Next steps:")
    print(f"  cd {result.project_dir}")
    print("  arklight build site.py -o ARK")

    if result.template == "production":
        print()
        print(_PRODUCTION_ARCHITECTURE_NOTE)
        if args.explain_architecture:
            print()
            print(_ARCHITECTURE_GUIDE)

    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    print(search_component(args.name))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arklight", description="Python-first static site compiler.")
    parser.add_argument("--version", action="version", version=f"arklight {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=False)

    build_parser = subparsers.add_parser("build", help="Compile a site file to static HTML + CSS.")
    build_parser.add_argument("entry", help="Path to the Python site file (e.g. site.py)")
    build_parser.add_argument(
        "-o", "--output", default="ARK", help="Output directory (default: ARK)"
    )
    open_group = build_parser.add_mutually_exclusive_group()
    open_group.add_argument(
        "--open",
        dest="open",
        action="store_true",
        default=True,
        help="Open the built site in your default browser after building (default).",
    )
    open_group.add_argument(
        "--no-open",
        dest="open",
        action="store_false",
        help="Don't open a browser after building.",
    )
    build_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Print each compiler pipeline stage as it runs (discovery, "
        "normalization, validation, IR build, each backend, ...) -- "
        "useful for seeing exactly where a slow or failing build is spending time.",
    )
    build_parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Like --verbose, plus print the full chained traceback (instead of "
        "a short message) if the build fails -- for tracing a compiler "
        "error back to the exact stage and Python frame that raised it.",
    )
    build_parser.add_argument(
        "--max-width",
        dest="max_width",
        default=None,
        metavar="VALUE",
        help="Override the page's max content width (--ark-max-width), e.g. "
        "'90rem', '1400px', '100%%'. Takes precedence over Site(max_width=...) "
        "in the site file, without requiring an edit to it. Default: "
        "ARKlight's fluid min(100%% - 3rem, 75rem).",
    )
    build_parser.add_argument(
        "--bg",
        dest="bg",
        default=None,
        metavar="VALUE",
        help="Override the page background (--ark-bg), e.g. '#0f0f1a'. Takes "
        "precedence over Site(bg=...) in the site file, without requiring an "
        "edit to it.",
    )
    build_parser.add_argument(
        "--font-family",
        dest="font_family",
        default=None,
        metavar="VALUE",
        help="Override the page font stack (--ark-font-family), e.g. "
        "'Georgia, serif' or '\"Inter\", sans-serif'. Takes precedence over "
        "Site(font_family=...) in the site file, without requiring an edit "
        "to it. Default: ARKlight's stock system-font stack.",
    )
    build_parser.add_argument(
        "--lang",
        dest="lang",
        default=None,
        metavar="TAG",
        help="Override the <html lang=\"...\"> tag, e.g. 'es', 'ta', 'fr-CA'. "
        "Overrides Site(lang=...) without requiring a site-file edit -- a "
        "page's own Page(lang=...), if it sets one, still wins for that page. "
        "Default: 'en'.",
    )
    build_parser.add_argument(
        "--button-text",
        dest="button_text",
        default=None,
        metavar="VALUE",
        help="Override button text color (--ark-button-text), e.g. '#111827'. "
        "Takes precedence over Site(button_text=...) in the site file. "
        "Default: '#ffffff' -- worth setting explicitly if you also choose a "
        "light --ark-accent, since button background follows accent.",
    )
    build_parser.set_defaults(func=_cmd_build)

    pack_parser = subparsers.add_parser(
        "pack",
        help="Pack a build directory into a single .ark bundle (sealed by default).",
    )
    pack_parser.add_argument("build_dir", help="Path to an `arklight build` output directory (e.g. ARK)")
    pack_parser.add_argument(
        "-o", "--output", default="site.ark", help="Output bundle path (default: site.ark)"
    )
    pack_parser.add_argument(
        "--plain",
        action="store_true",
        default=False,
        help=(
            "Leave the archive half a plain, generically-openable ZIP "
            "(the original v1 behavior) instead of sealing it. Off by default."
        ),
    )
    pack_parser.add_argument(
        "--passphrase",
        default=None,
        help=(
            "Seal with a passphrase-derived key instead of an embedded one, for "
            "real confidentiality (the same passphrase is required to unpack later). "
            "Ignored with --plain. Note: shell history/process listings may expose "
            "a passphrase passed this way."
        ),
    )
    pack_parser.set_defaults(func=_cmd_pack)

    unpack_parser = subparsers.add_parser(
        "unpack", help="Extract a .ark bundle's archive half back into a build directory."
    )
    unpack_parser.add_argument("bundle", help="Path to a .ark bundle produced by `arklight pack`")
    unpack_parser.add_argument(
        "-o", "--output", default="ARK", help="Output directory (default: ARK)"
    )
    unpack_parser.add_argument(
        "--passphrase",
        default=None,
        help="Passphrase the bundle was sealed with (only needed for passphrase-sealed bundles).",
    )
    unpack_parser.set_defaults(func=_cmd_unpack)

    pwa_parser = subparsers.add_parser(
        "pwa",
        help="Turn a build directory into an installable PWA (manifest + service worker).",
    )
    pwa_parser.add_argument(
        "build_dir", help="Path to an `arklight build` output directory (e.g. ARK)"
    )
    pwa_parser.add_argument("--name", required=True, help="Full app name for the manifest")
    pwa_parser.add_argument(
        "--short-name",
        default=None,
        help="Short app name for the manifest (default: first 12 chars of --name)",
    )
    pwa_parser.add_argument(
        "--start-url",
        default="index.html",
        help="Manifest start_url, relative to the build directory (default: index.html)",
    )
    pwa_parser.add_argument(
        "--theme-color", default="#000000", help="Manifest/meta theme color (default: #000000)"
    )
    pwa_parser.add_argument(
        "--background-color",
        default="#ffffff",
        help="Manifest background color (default: #ffffff)",
    )
    pwa_parser.add_argument(
        "--display",
        default="standalone",
        choices=["standalone", "fullscreen", "minimal-ui", "browser"],
        help="Manifest display mode (default: standalone)",
    )
    pwa_parser.add_argument(
        "--icon",
        action="append",
        dest="icon",
        metavar="SRC:SIZES[:TYPE]",
        help=(
            "Add an icon to the manifest's icons list. SRC is a path relative "
            "to the build directory (e.g. an icon already under assets/), "
            "SIZES is WIDTHxHEIGHT or 'any', and TYPE is an optional MIME "
            "type (inferred from SRC's extension if omitted). Repeatable, "
            "e.g. --icon assets/icon-192.png:192x192 --icon "
            "assets/icon-512.png:512x512."
        ),
    )
    pwa_parser.set_defaults(func=_cmd_pwa)

    new_parser = subparsers.add_parser(
        "new", help="Scaffold a new ARKlight project from a built-in template."
    )
    new_parser.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Name of the new project (also the directory created for it). "
        "Optional only when used with --explain-architecture alone.",
    )
    new_parser.add_argument(
        "--template",
        choices=sorted(TEMPLATES),
        default="simple",
        help="Project template to scaffold (default: simple)",
    )
    new_parser.add_argument(
        "--dir",
        default=None,
        help="Directory to create the project in (default: current directory)",
    )
    new_parser.add_argument(
        "--explain-architecture",
        action="store_true",
        default=False,
        help="Print guidance on structuring an ARKlight project as "
        "service-oriented, separated-by-concern modules with minimal "
        "boilerplate (routes/pages/components/content), and how to extend "
        "that layout. Run alone (no name) to just read the guide, or "
        "alongside a --template production scaffold to print it right after.",
    )
    new_parser.set_defaults(func=_cmd_new)

    search_parser = subparsers.add_parser(
        "search",
        help="Look up a built-in component's schema by name (required props, children rules).",
    )
    search_parser.add_argument("name", help="Component name to look up, e.g. Picture")
    search_parser.set_defaults(func=_cmd_search)

    args = parser.parse_args(argv)

    if args.command is None:
        # `arklight` with no subcommand -- print the same usage/help
        # text `arklight --help` shows (subcommands, flags, short
        # description of each) rather than argparse's terser
        # "error: the following arguments are required: command".
        # A first-time user typing just `arklight` should see how to
        # get started, not a bare error.
        parser.print_help()
        return 0

    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 -- last-resort safety net, see below
        # Every subcommand above already catches its own typed error
        # (CompileError, PackError, PWAError, ScaffoldError) and prints a
        # clean message. Reaching this handler means something outside
        # those known, handled failure modes happened -- uncharted
        # territory ARKlight hasn't specifically anticipated or tested
        # for. Rather than dumping a raw traceback (which used to be the
        # only thing that could happen here), say so plainly, and be
        # explicit that whatever was being produced (a build/, a .ark
        # bundle, a scaffolded project) may be incomplete or unreliable.
        print(
            f"ARKlight hit an unexpected error while running `arklight "
            f"{args.command}` -- this is outside its known, handled "
            f"failure modes, so treat any partial output as untrustworthy:\n"
            f"  {type(exc).__name__}: {exc}\n"
            f"This isn't a documented/recommended failure path -- if you "
            f"can reproduce it, please file an issue at "
            f"https://github.com/Rae-ARK/ARKlight/issues with the exact "
            f"command you ran.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
