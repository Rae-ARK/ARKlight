"""
One-time license acceptance gate for the ARKlight CLI.

Why this lives here and not in `pip install` / `setup.py`: modern pip
does not reliably run arbitrary interactive code during install --
wheel installs skip `setup.py` entirely, and even an sdist-triggered
prompt would hang or fail any non-interactive install (CI, Docker,
`pip install -r requirements.txt`). A first-run gate on the CLI
itself is the place this can actually work everywhere pip can't
guarantee it will.

Behavior:
    - The first time any `arklight <command>` runs, print the
      additional-terms summary (see LICENSE) and ask the user to
      type "agree" to continue.
    - Acceptance is recorded in a small marker file
      (~/.arklight/license-accepted by default, override with
      ARKLIGHT_HOME) so the prompt only happens once per machine/user.
    - ARKLIGHT_ACCEPT_LICENSE=1 skips the prompt outright (CI/Docker/
      scripted use) -- set it only after actually reading the terms.
    - If stdin isn't a TTY (piped input, CI without the env var set,
      etc.) there's nothing to prompt: this prints instructions for
      the two ways to unblock it and refuses to proceed, rather than
      hanging on a read that will never get input.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

ACCEPT_ENV_VAR = "ARKLIGHT_ACCEPT_LICENSE"
HOME_ENV_VAR = "ARKLIGHT_HOME"

NOTICE_TEXT = """\
ARKlight is licensed under the GNU GPLv3 (or later), with additional
terms added under GPLv3 Section 7 -- see the LICENSE file for the
full text. In short, those additional terms require:

  1. Copies you convey of ARKlight's own source (or a work based on
     it) keep a visible "Based on ARKlight" / "Powered by ARKlight"
     attribution, alongside the copyright notices GPLv3 already
     requires.
  2. Copies of ARKlight's own runtime file(s) it embeds in generated
     output (e.g. arklight.js) keep their attribution comment intact.

These terms do NOT apply to your own site's source or to the HTML/CSS
output `arklight build` produces from it -- only to ARKlight's own
code and runtime files, as described above and in LICENSE.
"""


def _marker_path() -> Path:
    home = os.environ.get(HOME_ENV_VAR)
    base = Path(home) if home else Path.home() / ".arklight"
    return base / "license-accepted"


def _env_says_accept() -> bool:
    return os.environ.get(ACCEPT_ENV_VAR, "").strip().lower() in ("1", "true", "yes")


def ensure_license_accepted(
    *,
    stream_in: TextIO | None = None,
    stream_out: TextIO | None = None,
) -> bool:
    """
    Returns True if the user has already accepted (or just accepted)
    ARKlight's license terms; False if they declined or couldn't be
    asked (non-interactive with no env var set). Callers should treat
    False as "do not proceed."
    """
    stream_in = stream_in if stream_in is not None else sys.stdin
    stream_out = stream_out if stream_out is not None else sys.stdout

    marker = _marker_path()
    if marker.exists() or _env_says_accept():
        return True

    if not stream_in.isatty():
        print(
            f"ARKlight license terms haven't been accepted yet, and input "
            f"isn't interactive here to ask.\n"
            f"Either run an interactive `arklight <command>` once to accept "
            f"them, or set {ACCEPT_ENV_VAR}=1 (after reading LICENSE) for "
            f"CI/scripted use.",
            file=sys.stderr,
        )
        return False

    print(NOTICE_TEXT, file=stream_out)
    stream_out.write("Type 'agree' to accept and continue: ")
    stream_out.flush()
    response = stream_in.readline().strip().lower()

    if response != "agree":
        print("Terms not accepted -- exiting.", file=stream_out)
        return False

    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        f"accepted {datetime.now(timezone.utc).isoformat()}\n", encoding="utf-8"
    )
    return True
