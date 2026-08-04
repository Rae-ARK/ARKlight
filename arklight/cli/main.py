"""
ARKlight CLI.

    arklight new my-site
    arklight build site.py -o ARK
    arklight pack ARK -o site.ark
    arklight unpack site.ark -o ARK
    arklight pwa ARK --name "My Site"
    arklight search Picture

Beginner-friendly by design: a handful of subcommands, sensible
defaults (builds AND opens the result in your browser), and error
messages that point at exactly what went wrong (parse error, missing
Site(), unknown component, etc.) rather than a raw traceback.
"""

from __future__ import annotations

import argparse
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

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = build(args.entry, args.output, on_stage=on_stage)
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


def _cmd_pwa(args: argparse.Namespace) -> int:
    try:
        result = enable_pwa(
            args.build_dir,
            name=args.name,
            short_name=args.short_name,
            start_url=args.start_url,
            theme_color=args.theme_color,
            background_color=args.background_color,
            display=args.display,
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
    for path in result.updated_pages:
        print(f"  {path} (manifest link + SW registration injected)")
    print(
        "Re-run `arklight pwa` on this directory after every `arklight build` "
        "to keep the manifest/service worker/precache list in sync -- it's "
        "idempotent, so this is always safe."
    )

    return 0


def _cmd_new(args: argparse.Namespace) -> int:
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
    pwa_parser.set_defaults(func=_cmd_pwa)

    new_parser = subparsers.add_parser(
        "new", help="Scaffold a new ARKlight project from a built-in template."
    )
    new_parser.add_argument("name", help="Name of the new project (also the directory created for it)")
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
