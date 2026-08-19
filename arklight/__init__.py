"""
ARKlight -- a Python-first compiler for building static websites.

    from arklight import *

    site = Site()

    @site.page("/")
    def home():
        return Page(
            Heading("ARKlight"),
            Text("Build websites with Python."),
            Button("Get Started"),
        )

Users write Python. ARKlight compiles it to standard HTML.
The browser never executes Python.
"""

from arklight.api import (
    Site,
    Page,
    Heading,
    Text,
    Button,
    Container,
    Link,
    Image,
    List,
    Item,
    Header,
    Footer,
    Main,
    Nav,
    Section,
    Article,
    Aside,
    Figure,
    FigCaption,
    Details,
    Summary,
    Strong,
    Em,
    Small,
    Mark,
    Code,
    Cite,
    Abbr,
    Sub,
    Sup,
    Span,
    Time,
    HorizontalRule,
    LineBreak,
    Pre,
    Blockquote,
    Form,
    Input,
    Textarea,
    Select,
    Option,
    OptGroup,
    Label,
    FieldSet,
    Legend,
    Table,
    TableHead,
    TableBody,
    TableFoot,
    TableRow,
    TableHeaderCell,
    TableCell,
    Caption,
    Video,
    Audio,
    Source,
    # v0.003 second vocabulary extension addendum ("even more
    # vocabulary") -- previously defined in arklight/api.py but missing
    # from this package's `import` list, so `from arklight import *`
    # couldn't reach them even though `from arklight.api import Picture`
    # (etc.) worked. See docs/DESIGN-NOTES.md, "v0.004: CLI scaffolding
    # (`arklight new`)", for how this was found.
    OrderedList,
    DescriptionList,
    DescriptionTerm,
    DescriptionDetails,
    Picture,
    PictureSource,
    Progress,
    Meter,
    Datalist,
    Output,
    Dialog,
    Kbd,
    Samp,
    Var,
    Data,
    Ins,
    Del,
    Q,
    Dfn,
    Address,
    Wbr,
    Bdi,
    Bdo,
    Ruby,
    Rt,
    Rp,
    ColGroup,
    Col,
    Track,
    Map,
    Area,
    IFrame,
    NoScript,
    State,
    Bind,
    Action,
    ActionRef,
    ARKNode,
)

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _installed_version

# Single source of truth is `pyproject.toml`'s `[project] version` --
# this reads it back from the installed package's own metadata instead
# of duplicating the string here. Duplicating it is exactly how a
# shipped release ended up with `pip show arklight` and `arklight
# --version` disagreeing (0.37 vs 0.038-internal): pyproject.toml got
# bumped for the release but this constant didn't, because nothing
# forced the two to move together. Reading it back from metadata
# instead of hardcoding it removes the second copy entirely, so there
# is no longer a place for the two to go out of sync.
try:
    __version__ = _installed_version("arklight")
except PackageNotFoundError:  # pragma: no cover -- only when running from
    # a source checkout that was never `pip install`-ed (editable or
    # otherwise), e.g. a bare `python -c "import arklight"` against a
    # git clone with no install step first. Degrade to an explicit
    # sentinel rather than raising, since import-time failure here
    # would break every test/tool that just wants the components.
    __version__ = "0+unknown"

# Which branch/edition of ARKlight this install's *code* is, as opposed
# to `__version__` (which milestone it is). Deliberately a static,
# hardcoded string per branch -- NOT detected via `git branch`/`.git`
# inspection at import time. A git-based check would silently go blank
# (or lie) for the common case of a real `pip install arklight`, which
# has no `.git` directory at all -- fragile for something call sites
# may treat as authoritative. `main` and `alpha` diverge enough in
# available subsystems (search engine, PWA, license gate, JS reactive
# core, ...) that a tool wired into both trees -- e.g. a live-reload
# dev server -- needs a reliable, install-method-independent way to ask
# "which feature set do I actually have here", without maintaining a
# parallel list of per-subsystem capability flags. This is that answer.
# Bump/change this value only when cutting the string over to a
# different branch's checkout -- same one-line-per-branch discipline as
# every other branch-specific constant in this file.
CHANNEL = "main"

__all__ = [
    "Site",
    "Page",
    "Heading",
    "Text",
    "Button",
    "Container",
    "Link",
    "Image",
    "List",
    "Item",
    "Header",
    "Footer",
    "Main",
    "Nav",
    "Section",
    "Article",
    "Aside",
    "Figure",
    "FigCaption",
    "Details",
    "Summary",
    "Strong",
    "Em",
    "Small",
    "Mark",
    "Code",
    "Cite",
    "Abbr",
    "Sub",
    "Sup",
    "Span",
    "Time",
    "HorizontalRule",
    "LineBreak",
    "Pre",
    "Blockquote",
    "Form",
    "Input",
    "Textarea",
    "Select",
    "Option",
    "OptGroup",
    "Label",
    "FieldSet",
    "Legend",
    "Table",
    "TableHead",
    "TableBody",
    "TableFoot",
    "TableRow",
    "TableHeaderCell",
    "TableCell",
    "Caption",
    "Video",
    "Audio",
    "Source",
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
    "State",
    "Bind",
    "Action",
    "ActionRef",
    "ARKNode",
    "__version__",
    "CHANNEL",
]
