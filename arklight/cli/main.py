"""
ARKlight CLI.

    arklight new my-site
    arklight build site.py -o ARK
    arklight pack ARK -o site.ark
    arklight unpack site.ark -o ARK
    arklight pwa ARK --name "My Site"

Beginner-friendly by design: a handful of subcommands, sensible
defaults (builds AND opens the result in your browser), and error
messages that point at exactly what went wrong (parse error, missing
Site(), unknown component, etc.) rather than a raw traceback.
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from arklight import __version__
from arklight.cli.scaffold import ScaffoldError, new_project
from arklight.cli.templates import TEMPLATES
from arklight.compiler.pipeline import BuildResult, CompileError, build
from arklight.packer.bundle import PackError, pack, unpack
from arklight.pwa import PWAError, enable_pwa


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


def _cmd_build(args: argparse.Namespace) -> int:
    try:
        result = build(args.entry, args.output)
    except CompileError as exc:
        print(f"ARKlight build failed: {exc}", file=sys.stderr)
        return 1

    print(f"ARKlight v{__version__} built {len(result.written_paths)} file(s) -> {args.output}/")
    for path in result.written_paths:
        print(f"  {path}")

    if args.open:
        opened = open_in_browser(result, args.output)
        if opened:
            print("Opened in your default browser.")

    return 0


def _cmd_pack(args: argparse.Namespace) -> int:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arklight", description="Python-first static site compiler.")
    parser.add_argument("--version", action="version", version=f"arklight {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
