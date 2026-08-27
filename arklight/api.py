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

import re
from typing import Any, Callable

from arklight import experimental
from arklight.ast.nodes import ActionRef, ARKNode, ClassBindSpec, node
from arklight.backend.css import selectors as css_selectors

# v0.042: custom CSS class names must look like a real, single CSS class
# identifier -- letters/digits/hyphens/underscores, not starting with a
# digit. Deliberately conservative (no escaped Unicode class names,
# no leading '.', no combinators) since this becomes a literal `.name {`
# selector in generated CSS with no further validation downstream.
_CSS_CLASS_NAME_RE = re.compile(r"^-?[A-Za-z_][A-Za-z0-9_-]*$")

# CSS Backend, pseudo-class shorthand (see docs/CSS-BACKEND-REFACTOR.md
# "Stage 2"): a `site.style(...)` rules key is either a plain property
# ("background") or a pseudo-class-scoped property (":hover:background"),
# letting a class express a simple interactive state without opening up
# raw CSS/selector strings. Plain property names allow a leading "--"
# (custom properties) or a single leading "-" (vendor prefixes, e.g.
# "-webkit-appearance"); pseudo names are letters/hyphens only and must
# be one of `ALLOWED_PSEUDO_CLASSES` below.
_CSS_PROPERTY_NAME_RE = re.compile(r"^(--[A-Za-z0-9-]+|-?[A-Za-z][A-Za-z0-9-]*)$")
_CSS_PSEUDO_RULE_RE = re.compile(
    r"^:(?P<pseudo>[A-Za-z-]+):(?P<prop>--[A-Za-z0-9-]+|-?[A-Za-z][A-Za-z0-9-]*)$"
)

# Deliberately a fixed, curated set rather than "any :whatever the user
# types" -- same reasoning as `_CSS_CLASS_NAME_RE`: this becomes a
# literal `.name:pseudo { ... }` selector with no further validation
# downstream, so an open-ended pseudo name would reopen the "no
# arbitrary CSS/selector strings" boundary `site.style(...)` otherwise
# holds. Extend this set (not the regex) if a new pseudo-class is
# needed later.
ALLOWED_PSEUDO_CLASSES = frozenset(
    {
        "hover",
        "focus",
        "focus-visible",
        "focus-within",
        "active",
        "visited",
        "link",
        "target",
        "disabled",
        "enabled",
        "checked",
        "indeterminate",
        "default",
        "required",
        "optional",
        "valid",
        "invalid",
        "in-range",
        "out-of-range",
        "read-only",
        "read-write",
        "placeholder-shown",
        "root",
        "empty",
        "first-child",
        "last-child",
        "only-child",
        "first-of-type",
        "last-of-type",
        "only-of-type",
    }
)

# Characters that would let a "value" break out of its declaration and
# inject a second declaration, a new selector, or close/reopen a rule
# block (e.g. {"color": "red; } .evil { color"}). `site.style(...)`
# rules are meant to be one property/value pair each, not a raw CSS
# string, so any of these in a value is a syntax error, not something
# to pass through.
_CSS_VALUE_INJECTION_CHARS = frozenset("{};\n")


# Recognized `@page` pseudo-classes for `Site.page_rule(..., pseudo=...)`
# -- same fixed-set discipline as `ALLOWED_PSEUDO_CLASSES` above.
ALLOWED_PAGE_PSEUDOS = frozenset({"first", "left", "right", "blank"})

# Recognized `src` formats for `Site.font_face(...)` -- matches the
# `format(...)` keywords browsers actually recognize in an `@font-face`
# `src` descriptor.
ALLOWED_FONT_FACE_FORMATS = frozenset(
    {"woff2", "woff", "truetype", "opentype", "embedded-opentype", "svg"}
)

# `@keyframes` stop keys: `from`/`to` or a percentage like "50%".
_KEYFRAME_STOP_RE = re.compile(r"^(from|to|\d{1,3}(\.\d+)?%)$")

# `Site.container_query(..., name=...)`'s optional container-name --
# a CSS custom-ident, same charset as `_CSS_CLASS_NAME_RE` (no leading
# digit).
_CSS_IDENT_RE = re.compile(r"^-?[A-Za-z_][A-Za-z0-9_-]*$")


class CSSSyntaxError(ValueError):
    """
    Raised by `Site.style(...)` when a rules key or value isn't valid
    CSS syntax for the shape ARKlight accepts -- an unknown pseudo-class
    in a ":pseudo:property" key, a malformed property name, or a value
    that would break out of its declaration. Subclasses `ValueError` so
    existing `except ValueError` call sites keep working unchanged; this
    exists as its own type so callers that want to distinguish "bad CSS
    syntax" from other `Site.style(...)` argument errors (bad class
    name, wrong dict shape) can catch it specifically.
    """

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

# ---------------------------------------------------------------------------
# v0.0035: stateful JS -- capability, not vocabulary.
#
# `State`/`Bind`/`Action` are the reactivity primitives: a page declares
# state, components read it via `Bind`, and `on_click=` mutates it via a
# closed, described set of `Action.*` helpers (never an arbitrary JS/Python
# string -- see arklight.ir.schema.ACTION_REGISTRY and
# docs/DESIGN-NOTES.md, "v0.0035: stateful JS -- capability, not
# vocabulary", for the full design).
# ---------------------------------------------------------------------------


def State(name: str, initial: Any = None) -> ARKNode:
    """
    Declare page-scoped reactive state: `State("count", 0)`.

    Must appear as a direct child of `Page(...)` -- state belongs to the
    page, the same way `title=` does -- and is compiled into the
    Website IR's `IRPage.state`, never rendered as an HTML element
    itself. Validation checks every `Bind(...)`/`Action.*(...)` on the
    page references a `name` declared here.
    """
    return ARKNode(type="State", props={"name": name, "initial": initial}, children=[])


def Bind(name: str) -> ARKNode:
    """
    Reference a `State(...)` value from wherever a literal value is
    accepted today, e.g. `Text(Bind("count"))`. Compiled to a small
    `data-ark-bind="<name>"` element the shipped runtime keeps in sync
    with state -- never a template string evaluated at runtime.
    """
    return ARKNode(type="Bind", props={"name": name}, children=[])


def _bind_when(state: str, class_name: str) -> ClassBindSpec:
    """
    Reactive class binding (Stage 2 of "Reactive-core vdom staging" --
    see docs/DESIGN-NOTES.md): `bind_class=Bind.when("active", "is-active")`
    toggles `class_name` on/off as `state`'s truthiness changes,
    without ever touching the element's other static classes. A small
    structured `ClassBindSpec`, not a string -- validated against the
    page's declared `State(...)` names at compile time, same discipline
    `Action.*(...)` already established for `on_click=`.

        State("active", False)
        Container(class_name="card", bind_class=Bind.when("active", "is-active"))
    """
    return ClassBindSpec(state=state, class_name=class_name)


Bind.when = _bind_when


class Action:
    """
    A closed vocabulary of state-mutating actions for `on_click=`,
    alongside today's named behaviors (`on_click="toggle"`). Each
    returns a small structured `ActionRef` -- validated against
    `arklight.ir.schema.ACTION_REGISTRY` at compile time -- never a
    string of JavaScript or Python.

        Button("+1", on_click=Action.increment("count"))
        Button("-1", on_click=Action.decrement("count"))
        Button("Reset", on_click=Action.reset("count"))
        Button("Toggle", on_click=Action.toggle_bool("is_open"))

    v0.0035 vocabulary addendum: `decrement` and `reset` fill the two
    gaps most sites hit right away -- a counter's `-1` counterpart to
    `increment`, and "put this state back the way it started" without
    hardcoding the initial value again at every call site (`reset`
    reads the store's own captured initial value). Only the most
    commonly needed additions; see docs/DESIGN-NOTES.md for what's
    deliberately left for a future version.
    """

    @staticmethod
    def set(name: str, value: Any) -> ActionRef:
        return ActionRef(action="set", state=name, args={"value": value})

    @staticmethod
    def increment(name: str, delta: Any = 1) -> ActionRef:
        return ActionRef(action="increment", state=name, args={"delta": delta})

    @staticmethod
    def decrement(name: str, delta: Any = 1) -> ActionRef:
        return ActionRef(action="decrement", state=name, args={"delta": delta})

    @staticmethod
    def toggle_bool(name: str) -> ActionRef:
        return ActionRef(action="toggle_bool", state=name, args={})

    @staticmethod
    def reset(name: str) -> ActionRef:
        return ActionRef(action="reset", state=name, args={})

    @staticmethod
    def append(name: str, value: Any) -> ActionRef:
        """Appends `value` to a list-valued `State(...)`."""
        return ActionRef(action="append", state=name, args={"value": value})

    @staticmethod
    def remove(name: str, index: Any) -> ActionRef:
        """Removes the element at `index` from a list-valued `State(...)`."""
        return ActionRef(action="remove", state=name, args={"index": index})


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

    def __init__(
        self,
        name: str = "arklight-site",
        *,
        max_width: str | None = None,
        bg: str | None = None,
        font_family: str | None = None,
        button_text: str | None = None,
        lang: str = "en",
        stack_space: str | None = None,
        cluster_space: str | None = None,
        sidebar_space: str | None = None,
        sidebar_width: str | None = None,
        switcher_space: str | None = None,
        switcher_threshold: str | None = None,
        grid_min: str | None = None,
        grid_space: str | None = None,
        center_gutter: str | None = None,
        reel_space: str | None = None,
    ) -> None:
        self.name = name
        # <html lang="..."> for every page this site builds, unless a
        # page overrides it with its own Page(lang=...). Previously
        # hardcoded to "en" in the HTML backend with no override path
        # at all -- see WebsiteIR.lang's comment in arklight/ir/build.py.
        if not isinstance(lang, str) or not lang.strip():
            raise ValueError(f"Site(lang=...) needs a non-empty language tag string, got {lang!r}.")
        self.lang = lang
        # route -> page function
        self.routes: dict[str, Callable[[], ARKNode]] = {}
        # v0.042: name -> {css-property: value}, registered via
        # `site.style(...)`. Structured input only -- see `style()` below
        # for why this isn't a raw CSS string.
        self.custom_styles: dict[str, dict[str, str]] = {}
        # Experimental (docs/EXPERIMENTAL-APIS.md): (condition, class_name,
        # rules) triples registered via `site.media_query(...)`, kept
        # separate from `custom_styles` above rather than overloading
        # `style()`'s key syntax -- an experimental escape hatch gets its
        # own explicit opt-in surface, not a silently-expanded standard one.
        self.custom_media_queries: list[tuple[str, str, dict[str, str]]] = []
        # Every `ExperimentalUsage` recorded by an opt-in call
        # (`media_query()` so far) on this Site, in call order --
        # `arklight.compiler.pipeline` drains this to print the inline
        # "[EXPERIMENTAL FEATURE ACTIVE]" banner and, deduplicated, the
        # end-of-build summary block.
        self.experimental_usages: list = []
        # CSS backend refactor: `max_width`/`bg` override two of the
        # `:root`-declared `--ark-*` custom properties that `CSSBackend`
        # used to bake in as constants. Both are read by `body`'s *own*
        # rule (`max-width: var(--ark-max-width)`, `background:
        # var(--ark-bg)`) -- see docs/CONTAINER-WIDTH-BUG.md and the CSS
        # backend architecture notes for why that specifically makes them
        # unreachable from any wrapper/descendant override: a CSS custom
        # property only cascades *downward*, and `body` resolves its own
        # rule before any site-authored wrapper div exists to override it
        # on. `Site(max_width=..., bg=...)` is the fix -- these become
        # real constructor kwargs, threaded through Website IR to
        # `CSSBackend`, which now generates `:root` instead of hardcoding
        # it (see `arklight/backend/css/render.py`). Both stay `None` by
        # default, so a site that doesn't pass either gets ARKlight's
        # stock defaults, unchanged.
        self.css_var_overrides: dict[str, str] = {}
        if max_width is not None:
            self._set_css_var_override("max_width", "--ark-max-width", max_width)
        if bg is not None:
            self._set_css_var_override("bg", "--ark-bg", bg)
        if font_family is not None:
            # Same unreachable-value bug class `max_width`/`bg` above
            # already fix -- see design_tokens.py's `--ark-font-family`
            # comment. `body` reads this directly, so before this a
            # site author had no way to change the font at all.
            self._set_css_var_override("font_family", "--ark-font-family", font_family)
        if button_text is not None:
            # Fixes the button-text-color/accent-color decoupling --
            # see design_tokens.py's `--ark-button-text` comment.
            self._set_css_var_override("button_text", "--ark-button-text", button_text)

        # Layout-primitive tokens (Stack/Cluster/Sidebar/Switcher/Grid/
        # Reel spacing + Sidebar's fixed-column width + Switcher's
        # stack/row breakpoint). These already had a `var(--ark-x,
        # fallback)` fallback at their point of use in BASE_CSS, so a
        # *per-instance* wrapper `style=` override already worked --
        # what was missing was a sitewide path, same shape as
        # `max_width`/`bg` above. All default to `None` (unset), so a
        # site passing none of these gets ARKlight's stock per-use
        # defaults, unchanged.
        for kwarg_name, var_name, value in (
            ("stack_space", "--ark-stack-space", stack_space),
            ("cluster_space", "--ark-cluster-space", cluster_space),
            ("sidebar_space", "--ark-sidebar-space", sidebar_space),
            ("sidebar_width", "--ark-sidebar-width", sidebar_width),
            ("switcher_space", "--ark-switcher-space", switcher_space),
            ("switcher_threshold", "--ark-switcher-threshold", switcher_threshold),
            ("grid_min", "--ark-grid-min", grid_min),
            ("grid_space", "--ark-grid-space", grid_space),
            ("center_gutter", "--ark-center-gutter", center_gutter),
            ("reel_space", "--ark-reel-space", reel_space),
        ):
            if value is not None:
                self._set_css_var_override(kwarg_name, var_name, value)

        # Structural addendum (see docs/DESIGN-NOTES.md "CSS selector
        # algebra + at-rule vocabulary"): storage for the new
        # `Site.style_selector`/`keyframes`/`font_face`/
        # `container_query`/`supports`/`page_rule`/`import_style`
        # registrations. Each is its own list/dict, same "don't
        # overload one structure with several unrelated shapes"
        # reasoning `custom_media_queries` already documents against
        # `custom_styles` above -- a selector rule, a keyframes
        # definition, and an `@import` url are different enough shapes
        # that folding them together would just move the type-checking
        # into the reader instead of the type system.
        self.selector_rules: list[tuple[str, dict[str, str]]] = []
        self.custom_keyframes: dict[str, dict[str, dict[str, str]]] = {}
        self.font_faces: list[dict[str, str]] = []
        self.container_queries: list[tuple[str | None, str, str, dict[str, str]]] = []
        self.supports_rules: list[tuple[str, str, dict[str, str]]] = []
        self.page_rules: list[tuple[str | None, dict[str, str]]] = []
        self.style_imports: list[str] = []

    def _set_css_var_override(self, kwarg_name: str, var_name: str, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Site({kwarg_name}=...) needs a non-empty CSS value string, "
                f"got {value!r}."
            )
        self.css_var_overrides[var_name] = value

    def style(self, name: str, rules: dict[str, str]) -> None:
        """
        Register a real, named, reusable CSS class -- `class_name="name"`
        anywhere in the site then picks up `rules` from the generated
        stylesheet, instead of repeating a `style={...}` dict on every
        node that needs it.

        `rules` is a plain `{css-property: value}` dict, the same shape
        already used for the per-node `style={...}` prop -- deliberately
        not a raw CSS string, so this doesn't reopen the "no arbitrary
        CSS/HTML strings" boundary the rest of ARKlight holds. Calling
        this again with a name that's already registered overwrites the
        previous rules for that name (last call wins), which lets a site
        redefine a class as it's built up without needing a separate
        "update" method.

        A key may also be a pseudo-class-scoped property, written
        ":<pseudo>:<property>" (e.g. ":hover:background"), to reach a
        simple interactive state -- `site.style("btn", {"background":
        "blue", ":hover:background": "red"})` renders both `.btn { ... }`
        and `.btn:hover { background: red; }`. `<pseudo>` must be one of
        `ALLOWED_PSEUDO_CLASSES`; anything else raises `CSSSyntaxError`.
        """
        if not isinstance(name, str) or not _CSS_CLASS_NAME_RE.match(name):
            raise ValueError(
                f"site.style({name!r}, ...) needs a valid CSS class name -- "
                f"letters, digits, hyphens, and underscores only, and it "
                f"can't start with a digit."
            )
        if not isinstance(rules, dict) or not rules:
            raise ValueError(
                f"site.style({name!r}, rules) needs a non-empty dict of "
                f"{{css-property: value}}, e.g. {{'color': 'red'}}."
            )
        for prop, value in rules.items():
            if not isinstance(prop, str) or not prop.strip():
                raise ValueError(
                    f"site.style({name!r}, ...) has a non-string or empty "
                    f"CSS property name: {prop!r}."
                )
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"site.style({name!r}, ...) property {prop!r} needs a "
                    f"non-empty string value, got {value!r}."
                )
            self._validate_css_syntax(name, prop, value)
        self.custom_styles[name] = dict(rules)

    def media_query(self, condition: str, class_name: str, rules: dict[str, str]) -> None:
        """
        EXPERIMENTAL (see `docs/EXPERIMENTAL-APIS.md`) -- register a
        `@media` block: `.class_name { ... }` rendered inside
        `@media (condition) { ... }` in the generated stylesheet.

        This is a deliberate, opt-in escape hatch from ARKlight's
        intrinsic layout model, not a peer of `style()` -- viewport-
        keyed rules are exactly the thing `.stack`/`.cluster`/
        `.switcher`/`.grid`/`.sidebar` exist to make unnecessary, and
        they're markedly less reliable on Android's device spread
        (foldables, OEM WebViews, non-standard aspect ratios) than the
        "phone vs desktop" case breakpoint intuition is usually built
        around. Every call is flagged: an `[EXPERIMENTAL FEATURE
        ACTIVE]` banner prints the moment the build detects it, and a
        summary block prints again at the end of the build. Prefer an
        intrinsic layout primitive first; reach for this only when the
        design genuinely cannot be expressed without a viewport-keyed
        rule.

        `condition` is the raw text that goes inside `@media (...)`
        (e.g. `"max-width: 600px"` or `"orientation: landscape"`) --
        not validated beyond "non-empty string", since the space of
        valid media-feature syntax is large; a malformed condition
        surfaces as broken generated CSS, the same failure mode
        hand-written `@media` would have. `class_name`/`rules` are
        validated exactly like `style()`.
        """
        if not isinstance(condition, str) or not condition.strip():
            raise ValueError(
                f"site.media_query(condition, ...) needs a non-empty media "
                f"condition string, e.g. 'max-width: 600px', got {condition!r}."
            )
        if not isinstance(class_name, str) or not _CSS_CLASS_NAME_RE.match(class_name):
            raise ValueError(
                f"site.media_query(..., {class_name!r}, ...) needs a valid CSS "
                f"class name -- letters, digits, hyphens, and underscores "
                f"only, and it can't start with a digit."
            )
        if not isinstance(rules, dict) or not rules:
            raise ValueError(
                f"site.media_query(..., {class_name!r}, rules) needs a "
                f"non-empty dict of {{css-property: value}}, e.g. "
                f"{{'flex-direction': 'column'}}."
            )
        for prop, value in rules.items():
            if not isinstance(prop, str) or not prop.strip() or prop.startswith(":"):
                raise ValueError(
                    f"site.media_query(..., {class_name!r}, ...) has an "
                    f"invalid CSS property name: {prop!r} (pseudo-class keys "
                    f"aren't supported inside a media query block)."
                )
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"site.media_query(..., {class_name!r}, ...) property "
                    f"{prop!r} needs a non-empty string value, got {value!r}."
                )
            self._validate_css_syntax(class_name, prop, value)

        self.custom_media_queries.append((condition.strip(), class_name, dict(rules)))
        self.experimental_usages.append(
            experimental.emit("css-media-queries")
        )

    def _validate_css_syntax(self, name: str, prop: str, value: str) -> None:
        """
        Syntax-check one `site.style(...)` (property, value) pair --
        called after the non-empty/is-a-string checks in `style()`
        above, so `prop`/`value` are already known to be non-empty
        strings here. Raises `CSSSyntaxError` (a `ValueError` subclass)
        on anything that isn't valid CSS syntax for the shape ARKlight
        accepts; returns `None` on a valid pair.
        """
        if prop.startswith(":"):
            match = _CSS_PSEUDO_RULE_RE.match(prop)
            if not match:
                raise CSSSyntaxError(
                    f"site.style({name!r}, ...) has an invalid pseudo-class "
                    f"rule key {prop!r} -- expected the form "
                    f"':pseudo:property', e.g. ':hover:background'."
                )
            pseudo = match.group("pseudo")
            if pseudo not in ALLOWED_PSEUDO_CLASSES:
                raise CSSSyntaxError(
                    f"site.style({name!r}, ...) uses unsupported pseudo-class "
                    f"{pseudo!r} in {prop!r}. Supported: "
                    f"{', '.join(sorted(ALLOWED_PSEUDO_CLASSES))}."
                )
        elif not _CSS_PROPERTY_NAME_RE.match(prop):
            raise CSSSyntaxError(
                f"site.style({name!r}, ...) has an invalid CSS property name "
                f"{prop!r} -- letters, digits, and hyphens only (or a "
                f"'--custom-property'), and it can't start with a digit."
            )

        if any(ch in value for ch in _CSS_VALUE_INJECTION_CHARS):
            raise CSSSyntaxError(
                f"site.style({name!r}, ...) property {prop!r} has a value "
                f"{value!r} containing '{{', '}}', or a newline -- that would "
                f"break out of its declaration. Use one property/value pair "
                f"per key instead of a raw CSS block."
            )

    def _validate_plain_rules(self, context: str, rules: dict[str, str]) -> dict[str, str]:
        """
        Shared validation for the "flat `{property: value}` dict, no
        pseudo-class shorthand" shape used by `container_query`,
        `supports`, and `page_rule` below (`style_selector` needs its
        own variant, since it also has to recognize `&`-nested dict
        values -- see `_expand_style_selector_rules`). `context` is a
        short description used in error messages (e.g. the selector or
        `"@page"`), not re-validated itself.
        """
        if not isinstance(rules, dict) or not rules:
            raise ValueError(
                f"{context} needs a non-empty dict of {{css-property: value}}, "
                f"e.g. {{'color': 'red'}}."
            )
        clean: dict[str, str] = {}
        for prop, value in rules.items():
            if not isinstance(prop, str) or not prop.strip() or prop.startswith(":"):
                raise ValueError(
                    f"{context} has an invalid CSS property name {prop!r} "
                    f"(pseudo-class shorthand keys aren't supported here -- "
                    f"put the pseudo-class in the selector itself)."
                )
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{context} property {prop!r} needs a non-empty string "
                    f"value, got {value!r}."
                )
            self._validate_css_syntax(context, prop, value)
            clean[prop] = value
        return clean

    def _expand_style_selector_rules(
        self, selector_text: str, selector_ast, rules: dict
    ) -> list[tuple[str, dict[str, str]]]:
        """
        Validate `rules` for `style_selector(selector_text, rules)` and
        expand any `&`-nested dict values into their own fully-resolved
        (selector, rules) pairs -- see `style_selector`'s docstring for
        the nesting shapes accepted. Recurses for multi-level nesting.
        """
        if not isinstance(rules, dict) or not rules:
            raise ValueError(
                f"site.style_selector({selector_text!r}, rules) needs a "
                f"non-empty dict of {{css-property: value}} (values may "
                f"also be a nested '&'-prefixed rules dict), got {rules!r}."
            )

        plain: dict[str, str] = {}
        nested: list[tuple[str, dict]] = []
        for key, value in rules.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(
                    f"site.style_selector({selector_text!r}, ...) has a "
                    f"non-string or empty rule key: {key!r}."
                )
            if key.startswith("&"):
                if not isinstance(value, dict) or not value:
                    raise ValueError(
                        f"site.style_selector({selector_text!r}, ...) "
                        f"nested key {key!r} needs a non-empty rules dict, "
                        f"got {value!r}."
                    )
                nested.append((key, value))
                continue
            if key.startswith(":"):
                raise CSSSyntaxError(
                    f"site.style_selector({selector_text!r}, ...) doesn't "
                    f"support the ':pseudo:property' shorthand -- put the "
                    f"pseudo-class in the selector itself, e.g. "
                    f"style_selector({selector_text!r} + ':hover', ...)."
                )
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"site.style_selector({selector_text!r}, ...) property "
                    f"{key!r} needs a non-empty string value, got {value!r}."
                )
            self._validate_css_syntax(selector_text, key, value)
            plain[key] = value

        results: list[tuple[str, dict[str, str]]] = []
        if plain:
            results.append((selector_text, plain))
        for key, nested_rules in nested:
            nested_selector_text = self._resolve_nested_selector(selector_text, selector_ast, key)
            try:
                nested_ast = css_selectors.parse_selector_list(nested_selector_text)
            except css_selectors.CSSSelectorSyntaxError as exc:
                raise CSSSyntaxError(str(exc)) from exc
            results.extend(
                self._expand_style_selector_rules(nested_selector_text, nested_ast, nested_rules)
            )
        return results

    @staticmethod
    def _resolve_nested_selector(selector_text: str, selector_ast, key: str) -> str:
        """
        Resolve one `&`-prefixed nested key (e.g. `"&:hover"`,
        `"& .child"`, `"& > .child"`) against `selector_text` into a
        fully-written selector string -- desugared at author time into
        a flat selector, not emitted as real CSS nesting syntax (`&`),
        so the generated stylesheet stays readable in browsers that
        predate CSS nesting support. Only defined for a single base
        selector (not a grouped `a, b` list): a group would make "the
        parent" ambiguous, so a grouped base selector must be nested
        against one branch at a time via separate `style_selector` calls.
        """
        if len(selector_ast) != 1:
            raise CSSSyntaxError(
                f"site.style_selector({selector_text!r}, ...) nested key "
                f"{key!r} needs a single base selector, not a grouped "
                f"selector list -- register each branch of the group with "
                f"its own style_selector(...) call."
            )
        remainder = key[1:]
        if not remainder:
            raise CSSSyntaxError(
                "site.style_selector(...) nested key '&' needs something "
                "after '&', e.g. '&:hover' or '& .child'."
            )
        first = remainder[0]
        if first in (">", "+", "~"):
            return f"{selector_text} {first} {remainder[1:].strip()}"
        if first.isspace():
            return f"{selector_text} {remainder.strip()}"
        if first in (":", ".", "["):
            return f"{selector_text}{remainder}"
        raise CSSSyntaxError(
            f"site.style_selector(...) nested key {key!r} isn't a "
            f"recognized '&'-nesting shape -- expected '&:pseudo', "
            f"'&.class', '&[attr]', '& .child' (descendant), or "
            f"'& > .child' / '& + .child' / '& ~ .child' (combinator)."
        )

    def style_selector(self, selector: str, rules: dict) -> None:
        """
        Register CSS rules against an arbitrary *structural* selector --
        combinators (`.a > .b`), grouped selectors (`h1, h2`), a bare
        tag override (`blockquote`, no `class_name=` needed on every
        node), attribute selectors (`[type="email"]`), pseudo-elements
        (`::before`), and parameterized pseudo-classes (`:not(.a)`,
        `:has(> .icon)`, `:is(...)`, `:where(...)`, `:nth-child(2n+1)`)
        -- everything `Site.style(...)`'s single flat `.name { }` block
        can't reach. See docs/DESIGN-NOTES.md ("CSS selector algebra +
        at-rule vocabulary") for why this is a separate method rather
        than widening `style()` itself.

        `selector` is parsed by `arklight.backend.css.selectors
        .parse_selector_list` -- a closed grammar, not a raw CSS
        string: anything outside pseudo-classes/pseudo-elements/
        attribute operators this module recognizes raises
        `CSSSyntaxError` rather than being passed through. A bare tag
        selector must be a real HTML tag ARKlight's HTML backend can
        emit (`arklight.backend.css.selectors.KNOWN_HTML_TAGS`).

        `rules` is normally a flat `{css-property: value}` dict, same
        shape as `style()`/`style={...}`. A key may also be a
        `&`-prefixed nested rules dict to reach a related selector
        without re-typing the base selector -- `&:hover` (pseudo-class
        on the same element), `&.active` / `&[data-open]` (compound
        extension), `& .child` (descendant), `& > .child` / `&
        + .child` / `& ~ .child` (combinator). Nesting is resolved at
        author time into a fully-written selector (see
        `_resolve_nested_selector`), not emitted as real CSS `&`
        nesting syntax, and only supported against a single base
        selector (not a grouped `a, b` list -- register each branch
        separately). The `:pseudo:property` shorthand `style()` uses
        isn't accepted here; put the pseudo-class in the selector
        string (or a `&`-nested key) instead.

        Example:

            site.style_selector(".card", {
                "padding": "1rem",
                "&:hover": {"box-shadow": "0 2px 8px rgba(0,0,0,.15)"},
                "& > img": {"border-radius": "8px 8px 0 0"},
            })
            site.style_selector("blockquote", {"font-style": "italic"})
            site.style_selector("h1, h2, h3", {"font-family": "var(--ark-font-family)"})
            site.style_selector('[data-state="open"] .panel', {"display": "block"})
        """
        if not isinstance(selector, str) or not selector.strip():
            raise ValueError(
                f"site.style_selector(selector, ...) needs a non-empty "
                f"selector string, got {selector!r}."
            )
        try:
            selector_ast = css_selectors.parse_selector_list(selector)
        except css_selectors.CSSSelectorSyntaxError as exc:
            raise CSSSyntaxError(str(exc)) from exc
        canonical_selector = css_selectors.render_selector_list(selector_ast)

        expanded = self._expand_style_selector_rules(canonical_selector, selector_ast, rules)
        self.selector_rules.extend((sel, dict(r)) for sel, r in expanded)

    def keyframes(self, name: str, frames: dict[str, dict[str, str]]) -> None:
        """
        Register a real `@keyframes name { ... }` block -- one of the
        gaps explicitly deferred in earlier design notes ("not silently
        dropped", see docs/DESIGN-NOTES.md). `transition` itself
        already worked (it's just a property value inside `style=`),
        but there was no way to *define* a keyframe sequence to
        transition/animate through.

        `name` is a CSS custom-ident (letters/digits/hyphens/
        underscores, no leading digit) -- referenced from any node's
        `style={"animation": "name 2s ease infinite"}` the same way any
        other `animation-name` value would be, since inline `style=` is
        already unrestricted for property *values*.

        `frames` is `{stop: {property: value}}`, where each `stop` is
        `"from"`, `"to"`, or a percentage like `"50%"` -- structured
        data, not a raw `@keyframes` block string. Stops are re-sorted
        (from -> ascending percentages -> to) regardless of the dict's
        insertion order, so `{"100%": ..., "0%": ...}` and `{"0%":
        ..., "100%": ...}` produce identical output.

        Example:

            site.keyframes("fade-in", {
                "from": {"opacity": "0"},
                "to": {"opacity": "1"},
            })
        """
        if not isinstance(name, str) or not _CSS_IDENT_RE.match(name):
            raise ValueError(
                f"site.keyframes({name!r}, ...) needs a valid animation "
                f"name -- letters, digits, hyphens, and underscores only, "
                f"and it can't start with a digit."
            )
        if not isinstance(frames, dict) or not frames:
            raise ValueError(
                f"site.keyframes({name!r}, frames) needs a non-empty dict "
                f"of {{stop: {{property: value}}}}, e.g. {{'from': "
                f"{{'opacity': '0'}}, 'to': {{'opacity': '1'}}}}."
            )

        normalized: dict[str, dict[str, str]] = {}
        for stop, rules in frames.items():
            if not isinstance(stop, str) or not _KEYFRAME_STOP_RE.match(stop.strip()):
                raise CSSSyntaxError(
                    f"site.keyframes({name!r}, ...) has an invalid stop "
                    f"{stop!r} -- expected 'from', 'to', or a percentage "
                    f"like '50%'."
                )
            normalized[stop.strip()] = self._validate_plain_rules(
                f"site.keyframes({name!r}, ...) stop {stop!r}", rules
            )

        def _sort_key(stop: str) -> float:
            if stop == "from":
                return -1.0
            if stop == "to":
                return 101.0
            return float(stop[:-1])

        self.custom_keyframes[name] = {
            stop: normalized[stop] for stop in sorted(normalized, key=_sort_key)
        }

    def font_face(
        self, family: str, src: str | list[dict[str, str]], **descriptors: str
    ) -> None:
        """
        Register a real `@font-face { ... }` block -- the other gap
        explicitly deferred in earlier design notes. Previously a
        self-hosted webfont was entirely unreachable; an external one
        was only reachable indirectly via `Page(links=[{"rel":
        "stylesheet", "href": "https://fonts.googleapis.com/..."}])`.

        `family` becomes the `font-family` descriptor (quoted
        automatically). `src` is either a single url string, or a list
        of `{"url": ..., "format": "woff2"}` dicts for a multi-format
        fallback chain (`format` is optional; when given, it must be
        one of `ALLOWED_FONT_FACE_FORMATS`). Extra keyword arguments
        become other `@font-face` descriptors (`font_weight="700"` ->
        `font-weight: 700;`, `font_display="swap"`, `font_style=...`,
        `unicode_range=...`, etc.) -- underscores convert to hyphens,
        same convention `style={...}`/`responsive_style={...}` already
        use for prop names.

        Example:

            site.font_face(
                "Inter",
                [
                    {"url": "/assets/inter.woff2", "format": "woff2"},
                    {"url": "/assets/inter.woff", "format": "woff"},
                ],
                font_weight="400 700",
                font_display="swap",
            )
        """
        if not isinstance(family, str) or not family.strip():
            raise ValueError(
                f"site.font_face(family, ...) needs a non-empty font "
                f"family name string, got {family!r}."
            )
        if any(ch in family for ch in _CSS_VALUE_INJECTION_CHARS) or '"' in family:
            raise CSSSyntaxError(
                f"site.font_face({family!r}, ...) has a family name that "
                f"isn't safe to emit -- quotes, braces, semicolons, and "
                f"newlines aren't allowed."
            )

        if isinstance(src, str):
            src_entries: list[dict[str, str]] = [{"url": src}]
        elif isinstance(src, list) and src:
            src_entries = src
        else:
            raise ValueError(
                f"site.font_face({family!r}, src, ...) needs `src` to be a "
                f"non-empty url string or a non-empty list of "
                f"{{'url': ..., 'format': ...}} dicts, got {src!r}."
            )

        src_parts: list[str] = []
        for entry in src_entries:
            if not isinstance(entry, dict) or "url" not in entry:
                raise ValueError(
                    f"site.font_face({family!r}, ...) has a src entry that "
                    f"isn't a dict with at least a 'url' key: {entry!r}."
                )
            url = entry["url"]
            if (
                not isinstance(url, str)
                or not url.strip()
                or any(ch in url for ch in _CSS_VALUE_INJECTION_CHARS)
                or '"' in url
            ):
                raise CSSSyntaxError(
                    f"site.font_face({family!r}, ...) has a src url that "
                    f"isn't safe to emit: {url!r}."
                )
            fmt = entry.get("format")
            if fmt is None:
                src_parts.append(f'url("{url}")')
            else:
                if fmt not in ALLOWED_FONT_FACE_FORMATS:
                    raise CSSSyntaxError(
                        f"site.font_face({family!r}, ...) has unsupported "
                        f"src format {fmt!r}. Supported: "
                        f"{', '.join(sorted(ALLOWED_FONT_FACE_FORMATS))}."
                    )
                src_parts.append(f'url("{url}") format("{fmt}")')

        descriptor_rules: dict[str, str] = {
            "font-family": f'"{family}"',
            "src": ", ".join(src_parts),
        }
        for desc_name, desc_value in descriptors.items():
            css_desc_name = desc_name.replace("_", "-")
            if not isinstance(desc_value, str) or not desc_value.strip():
                raise ValueError(
                    f"site.font_face({family!r}, ...) descriptor "
                    f"{desc_name!r} needs a non-empty string value, got "
                    f"{desc_value!r}."
                )
            self._validate_css_syntax(family, css_desc_name, desc_value)
            descriptor_rules[css_desc_name] = desc_value

        self.font_faces.append(descriptor_rules)

    def container_query(
        self, condition: str, selector: str, rules: dict, *, name: str | None = None
    ) -> None:
        """
        Register a real `@container (condition) { selector { ... } }`
        block (optionally `@container name (condition) { ... }` when a
        specific named container is targeted) -- one of the structural
        gaps `site.media_query(...)` can't reach, since a container
        query is keyed to an ancestor element's size, not the viewport.

        Unlike `site.media_query(...)`, this isn't flagged as an
        ARKlight "viewport-keyed, prefer intrinsic layout" EXPERIMENTAL
        escape hatch: a container query is compatible with (and often
        used alongside) intrinsic layout, since it reacts to an actual
        ancestor's size rather than assuming a "phone vs desktop"
        breakpoint intuition about the whole viewport.

        A site declares the container context itself via the existing,
        unrestricted `style={...}` prop -- `style={"container-type":
        "inline-size", "container-name": "sidebar"}` on the ancestor
        node -- no new mechanism needed there.

        `condition` is the raw text inside the required parentheses
        (e.g. `"min-width: 400px"`), validated the same
        non-empty/no-injection-characters way `site.media_query(...)`'s
        `condition` already is. `selector`/`rules` go through the same
        grammar/validation as `style_selector(...)`.
        """
        if not isinstance(condition, str) or not condition.strip():
            raise ValueError(
                f"site.container_query(condition, ...) needs a non-empty "
                f"container condition string, e.g. 'min-width: 400px', "
                f"got {condition!r}."
            )
        if any(ch in condition for ch in _CSS_VALUE_INJECTION_CHARS):
            raise CSSSyntaxError(
                f"site.container_query({condition!r}, ...) has a "
                f"condition that isn't safe to emit -- braces, "
                f"semicolons, and newlines aren't allowed."
            )
        if name is not None and (not isinstance(name, str) or not _CSS_IDENT_RE.match(name)):
            raise ValueError(
                f"site.container_query(..., name={name!r}) needs a valid "
                f"container name -- letters, digits, hyphens, and "
                f"underscores only, and it can't start with a digit."
            )
        try:
            selector_ast = css_selectors.parse_selector_list(selector)
        except css_selectors.CSSSelectorSyntaxError as exc:
            raise CSSSyntaxError(str(exc)) from exc
        canonical_selector = css_selectors.render_selector_list(selector_ast)
        clean_rules = self._validate_plain_rules(
            f"site.container_query(..., {canonical_selector!r}, ...)", rules
        )
        self.container_queries.append((name, condition.strip(), canonical_selector, clean_rules))

    def supports(self, condition: str, selector: str, rules: dict) -> None:
        """
        Register a real `@supports (condition) { selector { ... } }`
        feature-query block -- a progressive-enhancement gate ARKlight
        previously had no authoring surface for at all.

        `condition` is the raw text inside the required parentheses
        (e.g. `"display: grid"`, or a compound condition like
        `"(display: grid) and (gap: 1rem)"`), validated the same
        non-empty/no-injection-characters way `site.media_query(...)`'s
        `condition` is -- the space of valid feature-query syntax is
        large, so (like `media_query`) this doesn't parse it beyond
        that; a malformed condition surfaces as broken generated CSS,
        the same failure mode hand-written `@supports` would have.
        `selector`/`rules` go through the same grammar/validation as
        `style_selector(...)`.
        """
        if not isinstance(condition, str) or not condition.strip():
            raise ValueError(
                f"site.supports(condition, ...) needs a non-empty feature "
                f"condition string, e.g. 'display: grid', got {condition!r}."
            )
        if any(ch in condition for ch in _CSS_VALUE_INJECTION_CHARS):
            raise CSSSyntaxError(
                f"site.supports({condition!r}, ...) has a condition that "
                f"isn't safe to emit -- braces, semicolons, and newlines "
                f"aren't allowed."
            )
        try:
            selector_ast = css_selectors.parse_selector_list(selector)
        except css_selectors.CSSSelectorSyntaxError as exc:
            raise CSSSyntaxError(str(exc)) from exc
        canonical_selector = css_selectors.render_selector_list(selector_ast)
        clean_rules = self._validate_plain_rules(
            f"site.supports(..., {canonical_selector!r}, ...)", rules
        )
        self.supports_rules.append((condition.strip(), canonical_selector, clean_rules))

    def page_rule(self, rules: dict, *, pseudo: str | None = None) -> None:
        """
        Register a real `@page { ... }` (or `@page :pseudo { ... }`)
        print-layout rule. `pseudo`, if given, must be one of
        `ALLOWED_PAGE_PSEUDOS` (`"first"`, `"left"`, `"right"`,
        `"blank"`) -- same fixed-set discipline as
        `ALLOWED_PSEUDO_CLASSES`. `rules` goes through the same plain
        `{property: value}` validation `container_query`/`supports` use.

        Example:

            site.page_rule({"margin": "2cm"})
            site.page_rule({"margin-top": "4cm"}, pseudo="first")
        """
        if pseudo is not None and pseudo not in ALLOWED_PAGE_PSEUDOS:
            raise CSSSyntaxError(
                f"site.page_rule(..., pseudo={pseudo!r}) isn't supported. "
                f"Supported: {', '.join(sorted(ALLOWED_PAGE_PSEUDOS))}."
            )
        clean_rules = self._validate_plain_rules("site.page_rule(...)", rules)
        self.page_rules.append((pseudo, clean_rules))

    def import_style(self, url: str) -> None:
        """
        Register a sitewide `@import url("...");` statement, emitted
        first in the generated stylesheet (required -- `@import` must
        precede every other rule per the CSS spec, aside from
        `@charset`). Mainly useful for an external stylesheet/webfont
        host that isn't reachable via `Page(links=[...])` for some
        reason; prefer `links=` for the common case (it doesn't block
        the CSS Object Model the way `@import` does).
        """
        if not isinstance(url, str) or not url.strip():
            raise ValueError(
                f"site.import_style(url) needs a non-empty url string, "
                f"got {url!r}."
            )
        if any(ch in url for ch in _CSS_VALUE_INJECTION_CHARS) or '"' in url:
            raise CSSSyntaxError(
                f"site.import_style({url!r}) isn't safe to emit -- quotes, "
                f"braces, semicolons, and newlines aren't allowed."
            )
        self.style_imports.append(url.strip())

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
    "State",
    "Bind",
    "Action",
    "ActionRef",
    "ARKNode",
]
