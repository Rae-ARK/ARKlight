"""
Guards against the exact bug found in the published 0.37 release:
`pyproject.toml`'s version and `arklight.__version__` had drifted to
two different strings (0.037 vs 0.038), because both were separately
hardcoded and nothing forced them to move together.

`arklight.__version__` is no longer a hardcoded second copy -- it's
read back from the installed package's own metadata (which comes from
`pyproject.toml`'s `[project] version` at build time), so this test is
really checking "the single source of truth is actually being read",
not comparing two independent numbers.
"""

from importlib.metadata import version as installed_version

import arklight


def test_dunder_version_matches_installed_package_metadata():
    assert arklight.__version__ == installed_version("arklight")


def test_dunder_version_is_not_the_missing_package_sentinel():
    # If this ever reads "0+unknown", either arklight wasn't installed
    # (a bare source checkout with no `pip install`) or the metadata
    # lookup silently broke -- either way, worth failing loudly rather
    # than shipping a CLI that prints a fake version.
    assert arklight.__version__ != "0+unknown"


def test_channel_is_the_static_per_branch_string():
    # CHANNEL is a hardcoded-per-branch constant, not something derived
    # from git or installed metadata (see arklight/__init__.py for why)
    # -- so this just locks the value this branch is supposed to ship,
    # the same way test_dunder_version_* lock __version__'s source.
    assert arklight.CHANNEL == "main"


def test_channel_is_exported_from_dunder_all():
    assert "CHANNEL" in arklight.__all__
