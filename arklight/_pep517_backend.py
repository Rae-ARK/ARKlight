"""
PEP 517 build-backend wrapper for ARKlight.

Why this exists: `arklight/cli/license_gate.py` gates on first *use*
of the CLI, precisely because pip cannot be trusted to run arbitrary
interactive code at *install* time -- a wheel install from PyPI skips
setup.py (and any other project code) entirely, so `pip install
arklight` on its own currently installs the package with **no**
license-acceptance step at all. That's fine for the common case (the
CLI gate still catches it on first run), but it leaves one path
genuinely uncovered: pip *does* call back into project code whenever
it builds a distribution from source -- `pip install .`,
`pip install -e .`, `pip install git+https://...`, or building the
sdist that ends up on PyPI in the first place. This module is the
hook for that path.

It is a thin wrapper around `setuptools.build_meta`: every hook is
forwarded unchanged except the three that actually produce a
distribution (`build_wheel`, `build_sdist`, `build_editable`), which
first check that the license terms have been accepted before
delegating to setuptools. Hooks that only resolve build requirements
or metadata (no files installed yet) are left untouched so pip's
normal resolution flow isn't disrupted.

Acceptance for a *source* build is either:

    1. `ARKLIGHT_ACCEPT_LICENSE=1` (the same variable the CLI gate
       honors), or
    2. the config setting pip passes through to the build backend:
       `pip install . --config-settings=yes-i-agree-to-arklight-license=1`

Neither is required to install a pre-built wheel from PyPI -- that
path never calls this file, and relies on the CLI gate instead.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Mapping, Optional

from setuptools import build_meta as _orig

CONFIG_SETTING_KEY = "yes-i-agree-to-arklight-license"
ENV_VAR = "ARKLIGHT_ACCEPT_LICENSE"

NOTICE = """\
ARKlight is licensed under the GNU GPLv3 (or later), with additional
terms added under GPLv3 Section 7 -- see the LICENSE file for the
full text. In short, those additional terms require attribution to
be kept intact on copies of ARKlight's own source and on its runtime
file(s) embedded in generated output; they do NOT apply to your own
site's source or to the HTML/CSS/JS `arklight build` produces from
it. Read LICENSE for the full text.

pip is building ARKlight from source, and hasn't been told these
terms are accepted. To proceed, either:

  1. Pass the flag through pip's build-backend config settings:
       pip install . --config-settings=yes-i-agree-to-arklight-license=1
     (add -e for an editable install)

  2. Or set the environment variable (after actually reading LICENSE):
       ARKLIGHT_ACCEPT_LICENSE=1 pip install .

Installing a pre-built wheel instead of building from source (the
normal `pip install arklight` from PyPI) does not run this check --
in that case, `arklight <command>` itself asks the first time you
run it interactively, or honors the same ARKLIGHT_ACCEPT_LICENSE
variable non-interactively.
"""


def _truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes")


def _accepted(config_settings: Optional[Mapping[str, Any]]) -> bool:
    if _truthy(os.environ.get(ENV_VAR)):
        return True
    if config_settings:
        value = config_settings.get(CONFIG_SETTING_KEY)
        if isinstance(value, list):  # pip may pass repeated --config-settings as a list
            value = value[-1] if value else None
        if _truthy(value):
            return True
    return False


def _require_acceptance(config_settings: Optional[Mapping[str, Any]]) -> None:
    if not _accepted(config_settings):
        print(NOTICE, file=sys.stderr)
        raise SystemExit(
            "ARKlight: license terms not accepted for this source build "
            "-- see message above."
        )


# --- PEP 517 hooks that produce a distribution: gated. ---


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    _require_acceptance(config_settings)
    return _orig.build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    _require_acceptance(config_settings)
    return _orig.build_sdist(sdist_directory, config_settings)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    _require_acceptance(config_settings)
    return _orig.build_editable(wheel_directory, config_settings, metadata_directory)


# --- Everything else: forwarded as-is, no gating (no files installed yet). ---

get_requires_for_build_wheel = _orig.get_requires_for_build_wheel
get_requires_for_build_sdist = _orig.get_requires_for_build_sdist
prepare_metadata_for_build_wheel = _orig.prepare_metadata_for_build_wheel

if hasattr(_orig, "get_requires_for_build_editable"):
    get_requires_for_build_editable = _orig.get_requires_for_build_editable
if hasattr(_orig, "prepare_metadata_for_build_editable"):
    prepare_metadata_for_build_editable = _orig.prepare_metadata_for_build_editable
