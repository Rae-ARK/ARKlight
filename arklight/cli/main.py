"""
ARKlight CLI.

    arklight new my-site
    arklight build site.py -o ARK
    arklight pack ARK -o site.ark

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
from arklight.packer.bundle import PackError, pack


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
        result = pack(args.build_dir, args.output)
    except PackError as exc:
        print(f"ARKlight pack failed: {exc}", file=sys.stderr)
        return 1

    print(f"ARKlight v{__version__} packed {len(result.packed_paths)} file(s) -> {result.output_path}")
    for path in result.packed_paths:
        print(f"  {path}")

    if result.skipped_paths:
        print(
            f"Skipped {len(result.skipped_paths)} non-html/css/js file(s) "
            f"(asset bundling lands in a future version):"
        )
        for path in result.skipped_paths:
            print(f"  {path}")

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
        "pack", help="Pack a build directory into a single .ark bundle (HTML/ZIP polyglot)."
    )
    pack_parser.add_argument("build_dir", help="Path to an `arklight build` output directory (e.g. ARK)")
    pack_parser.add_argument(
        "-o", "--output", default="site.ark", help="Output bundle path (default: site.ark)"
    )
    pack_parser.set_defaults(func=_cmd_pack)

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
