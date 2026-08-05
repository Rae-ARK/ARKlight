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
        "active",
        "visited",
        "disabled",
        "checked",
        "first-child",
        "last-child",
    }
)

# Characters that would let a "value" break out of its declaration and
# inject a second declaration, a new selector, or close/reopen a rule
# block (e.g. {"color": "red; } .evil { color"}). `site.style(...)`
# rules are meant to be one property/value pair each, not a raw CSS
# string, so any of these in a value is a syntax error, not something
# to pass through.
_CSS_VALUE_INJECTION_CHARS = frozenset("{};\n")


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
