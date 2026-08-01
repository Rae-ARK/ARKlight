"""
Public ARKlight API.

`from arklight import *` gives users:

- `Site`       -- the app object, holds page registrations
- `Page`       -- the root node every page function must return
- Built-in components: `Heading`, `Text`, `Button`, `Container`, `Link`, `Image`, `List`, `Item`,
  plus the v0.003 vocabulary extension and its "even more vocabulary" addendum below.

Everything a user calls here returns an `ARKNode` (see arklight.ast.nodes),
except `Site`, which is a small registry object.
"""

from __future__ import annotations

from typing import Any, Callable

from arklight.ast.nodes import ARKNode, node

# ---------------------------------------------------------------------------
# Built-in components
#
# Each of these is a plain Python function. Calling one does not render
# anything -- it just builds an ARKNode. The real rendering happens later,
# in the compiler pipeline, once every page has been collected.
# ---------------------------------------------------------------------------

Page = node("Page")
Heading = node("Heading")
Text = node("Text")
Button = node("Button")
Container = node("Container")
Link = node("Link")
Image = node("Image")
List = node("List")
Item = node("Item")

# ---------------------------------------------------------------------------
# v0.003 vocabulary extension.
#
# Same mechanism as everything above -- each is `node("SomeType")`, a thin
# ARKNode-building wrapper, nothing more. Grouped to match arklight.ir.schema:
# semantic layout, text-level semantics, forms, tables, media. See
# arklight.ir.schema.SCHEMA for the authoritative list of what each one
# allows (required props, text-only-children, etc.) and
# docs/DESIGN-NOTES.md for why these specifically.
# ---------------------------------------------------------------------------

# Semantic page/section layout.
Header = node("Header")
Footer = node("Footer")
Main = node("Main")
Nav = node("Nav")
Section = node("Section")
Article = node("Article")
Aside = node("Aside")
Figure = node("Figure")
FigCaption = node("FigCaption")
Details = node("Details")
Summary = node("Summary")

# Text-level semantics.
Strong = node("Strong")
Em = node("Em")
Small = node("Small")
Mark = node("Mark")
Code = node("Code")
Cite = node("Cite")
Abbr = node("Abbr")
Sub = node("Sub")
Sup = node("Sup")
Span = node("Span")
Time = node("Time")
HorizontalRule = node("HorizontalRule")
LineBreak = node("LineBreak")
Pre = node("Pre")
Blockquote = node("Blockquote")

# Forms.
Form = node("Form")
Input = node("Input")
Textarea = node("Textarea")
Select = node("Select")
Option = node("Option")
OptGroup = node("OptGroup")
Label = node("Label")
FieldSet = node("FieldSet")
Legend = node("Legend")

# Tables.
Table = node("Table")
TableHead = node("TableHead")
TableBody = node("TableBody")
TableFoot = node("TableFoot")
TableRow = node("TableRow")
TableHeaderCell = node("TableHeaderCell")
TableCell = node("TableCell")
Caption = node("Caption")

# Media.
Video = node("Video")
Audio = node("Audio")
Source = node("Source")

# ---------------------------------------------------------------------------
# v0.003 second vocabulary extension addendum ("even more vocabulary").
#
# Same mechanism as everything above -- each is `node("SomeType")`. See
# arklight.ir.schema.SCHEMA for what each one allows and CHANGELOG.md /
# docs/DESIGN-NOTES.md for why these specifically.
# ---------------------------------------------------------------------------

# Lists.
OrderedList = node("OrderedList")
DescriptionList = node("DescriptionList")
DescriptionTerm = node("DescriptionTerm")
DescriptionDetails = node("DescriptionDetails")

# Responsive images.
Picture = node("Picture")
PictureSource = node("PictureSource")

# Native widgets.
Progress = node("Progress")
Meter = node("Meter")
Datalist = node("Datalist")
Output = node("Output")

# Dialog.
Dialog = node("Dialog")

# More text-level semantics.
Kbd = node("Kbd")
Samp = node("Samp")
Var = node("Var")
Data = node("Data")
Ins = node("Ins")
Del = node("Del")
Q = node("Q")
Dfn = node("Dfn")
Address = node("Address")
Wbr = node("Wbr")
Bdi = node("Bdi")
Bdo = node("Bdo")

# Ruby annotations.
Ruby = node("Ruby")
Rt = node("Rt")
Rp = node("Rp")

# Table extras.
ColGroup = node("ColGroup")
Col = node("Col")

# Media.
Track = node("Track")

# Image maps.
Map = node("Map")
Area = node("Area")

# Embeds.
IFrame = node("IFrame")

# Fallback content for no-JS visitors.
NoScript = node("NoScript")

BUILTIN_COMPONENTS = {
    "Page": Page,
    "Heading": Heading,
    "Text": Text,
    "Button": Button,
    "Container": Container,
    "Link": Link,
    "Image": Image,
    "List": List,
    "Item": Item,
    "Header": Header,
    "Footer": Footer,
    "Main": Main,
    "Nav": Nav,
    "Section": Section,
    "Article": Article,
    "Aside": Aside,
    "Figure": Figure,
    "FigCaption": FigCaption,
    "Details": Details,
    "Summary": Summary,
    "Strong": Strong,
    "Em": Em,
    "Small": Small,
    "Mark": Mark,
    "Code": Code,
    "Cite": Cite,
    "Abbr": Abbr,
    "Sub": Sub,
    "Sup": Sup,
    "Span": Span,
    "Time": Time,
    "HorizontalRule": HorizontalRule,
    "LineBreak": LineBreak,
    "Pre": Pre,
    "Blockquote": Blockquote,
    "Form": Form,
    "Input": Input,
    "Textarea": Textarea,
    "Select": Select,
    "Option": Option,
    "OptGroup": OptGroup,
    "Label": Label,
    "FieldSet": FieldSet,
    "Legend": Legend,
    "Table": Table,
    "TableHead": TableHead,
    "TableBody": TableBody,
    "TableFoot": TableFoot,
    "TableRow": TableRow,
    "TableHeaderCell": TableHeaderCell,
    "TableCell": TableCell,
    "Caption": Caption,
    "Video": Video,
    "Audio": Audio,
    "Source": Source,
    "OrderedList": OrderedList,
    "DescriptionList": DescriptionList,
    "DescriptionTerm": DescriptionTerm,
    "DescriptionDetails": DescriptionDetails,
    "Picture": Picture,
    "PictureSource": PictureSource,
    "Progress": Progress,
    "Meter": Meter,
    "Datalist": Datalist,
    "Output": Output,
    "Dialog": Dialog,
    "Kbd": Kbd,
    "Samp": Samp,
    "Var": Var,
    "Data": Data,
    "Ins": Ins,
    "Del": Del,
    "Q": Q,
    "Dfn": Dfn,
    "Address": Address,
    "Wbr": Wbr,
    "Bdi": Bdi,
    "Bdo": Bdo,
    "Ruby": Ruby,
    "Rt": Rt,
    "Rp": Rp,
    "ColGroup": ColGroup,
    "Col": Col,
    "Track": Track,
    "Map": Map,
    "Area": Area,
    "IFrame": IFrame,
    "NoScript": NoScript,
}


class Site:
    """
    The application object.

    Usage:

        site = Site()

        @site.page("/")
        def home():
            return Page(Heading("Hello"))

    `site.page(route)` is a decorator that registers a page function
    under a route. Nothing is executed or compiled at registration time
    -- the compiler pipeline calls each registered function later, when
    it builds the ARK AST for the whole site.
    """

    def __init__(self, name: str = "arklight-site") -> None:
        self.name = name
        # route -> page function
        self.routes: dict[str, Callable[[], ARKNode]] = {}

    def page(self, route: str) -> Callable[[Callable[[], ARKNode]], Callable[[], ARKNode]]:
        if not route.startswith("/"):
            raise ValueError(f"Route {route!r} must start with '/'")

        def decorator(fn: Callable[[], ARKNode]) -> Callable[[], ARKNode]:
            if route in self.routes:
                raise ValueError(f"Route {route!r} is already registered")
            self.routes[route] = fn
            return fn

        return decorator

    def build_ark_ast(self) -> dict[str, ARKNode]:
        """
        Call every registered page function and collect the resulting
        ARK AST, keyed by route. This is the moment the "Python source"
        actually turns into "ARK AST" objects.
        """
        ark_ast: dict[str, ARKNode] = {}
        for route, fn in self.routes.items():
            result = fn()
            if not isinstance(result, ARKNode):
                raise TypeError(
                    f"Page function for route {route!r} must return a Page(...) node, "
                    f"got {type(result).__name__!r} instead."
                )
            ark_ast[route] = result
        return ark_ast


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
    "ARKNode",
]
