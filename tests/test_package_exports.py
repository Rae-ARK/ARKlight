"""
Regression test: `arklight/__init__.py` previously omitted the v0.003
"second vocabulary extension addendum" (Picture, OrderedList, Dialog,
etc.) -- those were defined in `arklight/api.py` and reachable via
`arklight.api.Picture`, but not via `from arklight import *`, which is
the documented way users are told to import everything. Found while
building the `production` scaffold template for `arklight new`, whose
generated site.py relies on `from arklight import *` exclusively (see
docs/DESIGN-NOTES.md, "v0.004: CLI scaffolding").
"""

import arklight

_SECOND_ADDENDUM_NAMES = [
    "OrderedList",
    "DescriptionList",
    "DescriptionTerm",
    "DescriptionDetails",
    "Picture",
    "PictureSource",
    "Progress",
    "Meter",
    "Datalist",
    "Output",
    "Dialog",
    "Kbd",
    "Samp",
    "Var",
    "Data",
    "Ins",
    "Del",
    "Q",
    "Dfn",
    "Address",
    "Wbr",
    "Bdi",
    "Bdo",
    "Ruby",
    "Rt",
    "Rp",
    "ColGroup",
    "Col",
    "Track",
    "Map",
    "Area",
    "IFrame",
    "NoScript",
]


def test_second_addendum_names_are_attributes_of_arklight_package():
    for name in _SECOND_ADDENDUM_NAMES:
        assert hasattr(arklight, name), f"arklight.{name} missing"


def test_second_addendum_names_are_in_dunder_all():
    for name in _SECOND_ADDENDUM_NAMES:
        assert name in arklight.__all__, f"{name!r} missing from arklight.__all__"


def test_second_addendum_names_build_ark_nodes():
    # A couple of representative spot checks that these are real,
    # working node factories once imported the `from arklight import *`
    # way, not just present as attributes.
    namespace: dict = {}
    exec("from arklight import *", namespace)  # noqa: S102 -- test-only
    picture = namespace["Picture"]()
    dialog = namespace["Dialog"]()
    assert picture.type == "Picture"
    assert dialog.type == "Dialog"
