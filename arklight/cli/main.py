"""
ARKlight CLI.

    arklight build site.py -o ARK

Beginner-friendly by design: one subcommand, sensible defaults
(builds AND opens the result in your browser), and error messages that
point at exactly what went wrong (parse error, missing Site(), unknown
component, etc.) rather than a raw traceback.
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from arklight import __version__
from arklight.compiler.pipeline import BuildResult, CompileError, build


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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
