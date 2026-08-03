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
