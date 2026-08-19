"""
Stage 0 entry point.

Not real install logic yet — just proves the Neutralino shell can shell
out to Python and get structured output back. This is the seam that
Stage 1 replaces with real calls into detect.py / install.py.

Contract: always print exactly one JSON object to stdout, nothing else.
Errors go to stderr with a non-zero exit code so the JS side can tell
"ran and failed" apart from "didn't run."
"""

import json
import sys


def ping() -> dict:
    return {"ok": True, "stage": 0, "message": "python backend reachable"}


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "ping"

    if command == "ping":
        print(json.dumps(ping()))
        return 0

    print(f"unknown command: {command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
