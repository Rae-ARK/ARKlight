"""
Shared component schema.

A small, single source of truth for facts about each built-in component
type that more than one pipeline stage needs to agree on. Right now
that's just "does this component only ever hold plain text?" -- both
Normalization (should a bare string become a Text node, or stay a plain
string?) and Validation (is a nested component here even allowed?) need
to agree on the answer, so it lives here instead of being duplicated.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NodeSpec:
    required_props: tuple[str, ...] = field(default_factory=tuple)
    text_only_children: bool = False
    allow_children: bool = True


# v0.001 built-in component schema. Extending this dict is how future
# milestones add new component types without touching normalize/validate
# logic.
SCHEMA: dict[str, NodeSpec] = {
    "Page": NodeSpec(),
    "Container": NodeSpec(),
    "Heading": NodeSpec(text_only_children=True),
    "Text": NodeSpec(text_only_children=True),
    "Button": NodeSpec(text_only_children=True),
    "Link": NodeSpec(required_props=("href",), text_only_children=True),
    "Image": NodeSpec(required_props=("src",), allow_children=False),
    "List": NodeSpec(),
    "Item": NodeSpec(text_only_children=True),
    # ------------------------------------------------------------------
    # v0.003: vocabulary extension. These don't change how the compiler
    # pipeline *works* -- normalize/validate/build/backends are all
    # driven entirely off this dict and TEXT_ONLY_TYPES below -- they
    # just give users more of standard HTML to reach for. Grouped by
    # what they're commonly used for in a real static site; see
    # docs/DESIGN-NOTES.md for how this addresses the v0.003 ceiling.
    # ------------------------------------------------------------------
    # Semantic page/section layout (HTML5 sectioning + grouping content).
    "Header": NodeSpec(),
    "Footer": NodeSpec(),
    "Main": NodeSpec(),
    "Nav": NodeSpec(),
    "Section": NodeSpec(),
    "Article": NodeSpec(),
    "Aside": NodeSpec(),
    "Figure": NodeSpec(),
    "FigCaption": NodeSpec(text_only_children=True),
    # <details>/<summary>: a native, browser-built disclosure widget --
    # an accordion/expand-collapse that needs *zero* JS, not even the
    # `toggle` behavior. `Details` takes an optional `open=True` prop.
    "Details": NodeSpec(),
    "Summary": NodeSpec(text_only_children=True),
    # Text-level semantics.
    "Strong": NodeSpec(text_only_children=True),
    "Em": NodeSpec(text_only_children=True),
    "Small": NodeSpec(text_only_children=True),
    "Mark": NodeSpec(text_only_children=True),
    "Code": NodeSpec(text_only_children=True),
    "Cite": NodeSpec(text_only_children=True),
    "Abbr": NodeSpec(text_only_children=True),
    "Sub": NodeSpec(text_only_children=True),
    "Sup": NodeSpec(text_only_children=True),
    "Span": NodeSpec(text_only_children=True),
    "Time": NodeSpec(text_only_children=True),
    "HorizontalRule": NodeSpec(allow_children=False),
    "LineBreak": NodeSpec(allow_children=False),
    # `Pre` is a real container (not text-only) so the standard
    # `Pre(Code("..."))` pairing works -- a code block is a `<pre>`
    # wrapping a `<code>`, not raw text.
    "Pre": NodeSpec(),
    "Blockquote": NodeSpec(),
    # Forms.
    "Form": NodeSpec(),
    "Input": NodeSpec(allow_children=False),
    "Textarea": NodeSpec(text_only_children=True),
    "Select": NodeSpec(),
    "Option": NodeSpec(text_only_children=True),
    "OptGroup": NodeSpec(),
    "Label": NodeSpec(text_only_children=True),
    "FieldSet": NodeSpec(),
    "Legend": NodeSpec(text_only_children=True),
    # Tables. Cells are left as real containers (not text-only) since
    # real table cells routinely hold a `Link`, `Strong`, etc., not
    # just plain text.
    "Table": NodeSpec(),
    "TableHead": NodeSpec(),
    "TableBody": NodeSpec(),
    "TableFoot": NodeSpec(),
    "TableRow": NodeSpec(),
    "TableHeaderCell": NodeSpec(),
    "TableCell": NodeSpec(),
    "Caption": NodeSpec(text_only_children=True),
    # Media.
    "Video": NodeSpec(),
    "Audio": NodeSpec(),
    "Source": NodeSpec(required_props=("src",), allow_children=False),
    # ------------------------------------------------------------------
    # v0.003: second vocabulary addendum ("even more vocabulary"). Same
    # deal as the addendum above -- pure data in SCHEMA (+ TAG_MAP/
    # PASSTHROUGH_ATTRS/VOID_TAGS in the HTML backend), no compiler
    # logic touched. This batch fills in the "long tail" of standard,
    # production-grade static-site HTML that the first addendum left
    # out: numbered/description lists, art-directed responsive images,
    # native form/progress widgets, a zero-JS dialog, the rest of
    # HTML's text-level semantics (including bidi + ruby), table
    # column grouping, video captions, image maps, iframes, and a
    # <noscript> fallback. See docs/DESIGN-NOTES.md and CHANGELOG.md
    # for the full rationale per group.
    # ------------------------------------------------------------------
    # Lists: v0.003's first pass only ever produced <ul> (via `List`).
    # `OrderedList` is a genuine gap, not a niche one -- there was no
    # numbered list at all. `DescriptionList` covers key/value and
    # glossary content (specs, FAQs, metadata blocks) that a <ul> can't
    # express semantically.
    "OrderedList": NodeSpec(),
    "DescriptionList": NodeSpec(),
    # Short, like `Item` -- a term is a label, not a place for a
    # nested Container/Figure/etc.
    "DescriptionTerm": NodeSpec(text_only_children=True),
    # Real container (like `TableCell`) -- a definition routinely holds
    # a `Link`, `Strong`, or multiple `Text` paragraphs, not just a
    # bare string.
    "DescriptionDetails": NodeSpec(),
    # Responsive images: art-direction (a different crop/format per
    # viewport, via `<source media=... srcset=...>`), the image half of
    # "responsive design" that the first addendum's CSS-only utilities
    # didn't touch at all.
    "Picture": NodeSpec(),
    # Distinct from the existing `Source` (which is for Video/Audio and
    # requires `src`) -- a <picture>'s <source> takes `srcset`/`sizes`/
    # `media`/`type` instead, so it gets its own required prop.
    "PictureSource": NodeSpec(required_props=("srcset",), allow_children=False),
    # Native, zero-JS widgets: progress bars, gauges, autocomplete lists,
    # and calculation output are all built into the browser already.
    "Progress": NodeSpec(text_only_children=True),
    "Meter": NodeSpec(text_only_children=True),
    "Datalist": NodeSpec(),
    "Output": NodeSpec(text_only_children=True),
    # <dialog open>: renders open with zero JS, and
    # `Form(method="dialog")` closes it natively (a browser behavior,
    # not a script) -- genuinely clever within the "no arbitrary JS"
    # constraint for a static confirmation/FAQ modal. Programmatically
    # opening it from an arbitrary trigger would need JS and stays out
    # of scope, same as the rest of v0.003.
    "Dialog": NodeSpec(),
    # More text-level semantics.
    "Kbd": NodeSpec(text_only_children=True),
    "Samp": NodeSpec(text_only_children=True),
    "Var": NodeSpec(text_only_children=True),
    "Data": NodeSpec(required_props=("value",), text_only_children=True),
    # `Ins`/`Del` are real containers (not text-only): HTML5 allows them
    # to wrap block content (e.g. a whole edited paragraph), same
    # reasoning as `Blockquote`.
    "Ins": NodeSpec(),
    "Del": NodeSpec(),
    "Q": NodeSpec(text_only_children=True),
    "Dfn": NodeSpec(text_only_children=True),
    # Real container -- postal/contact info commonly mixes plain text
    # with a `Link` (mailto:) or `LineBreak`s.
    "Address": NodeSpec(),
    "Wbr": NodeSpec(allow_children=False),
    # Bidirectional text isolation/override -- a real, production i18n
    # need (mixed LTR/RTL content: names, prices, or user-generated
    # text embedded in an RTL page, or vice versa), not just theory.
    "Bdi": NodeSpec(text_only_children=True),
    "Bdo": NodeSpec(text_only_children=True),
    # Ruby annotations (furigana/pinyin-style glosses) -- a real,
    # standard part of production East-Asian-language typography, and
    # a genuine gap: nothing above could express it at all.
    "Ruby": NodeSpec(),
    "Rt": NodeSpec(text_only_children=True),
    "Rp": NodeSpec(text_only_children=True),
    # Table extras: column-level styling/grouping without repeating a
    # style on every cell in the column.
    "ColGroup": NodeSpec(),
    "Col": NodeSpec(allow_children=False),
    # Media: caption/subtitle tracks -- accessibility, not decoration.
    "Track": NodeSpec(required_props=("src",), allow_children=False),
    # Image maps: multiple clickable regions on one image.
    "Map": NodeSpec(required_props=("name",)),
    "Area": NodeSpec(allow_children=False),
    # Embeds: the single most common "extra functionality" a static
    # site reaches for that plain markup can't provide on its own --
    # embedding a map, a video host player, or another site's widget --
    # while still being pure declarative HTML (no JS involved in the
    # embed itself).
    "IFrame": NodeSpec(required_props=("src",), allow_children=False),
    # Fallback content for the (rare, but real) visitor with JavaScript
    # disabled -- pairs naturally with ARKlight's own small JS runtime:
    # anything gated behind a `toggle`/`copy`/`dismiss` behavior can
    # have a `NoScript` sibling explaining what's missing.
    "NoScript": NodeSpec(),
}

# Types whose raw string children should stay raw strings during
# normalization rather than being auto-wrapped in a Text node.
TEXT_ONLY_TYPES = frozenset(
    type_name for type_name, spec in SCHEMA.items() if spec.text_only_children
)

# v0.003 (+v0.003): named client-side behaviors any component may opt
# into via `on_click="<name>"` (plus `behavior_target="<css selector>"`
# and, for `toggle`, an optional `toggle_class`). Named `behavior_target`
# rather than `target` on purpose: `target` is already a real HTML
# attribute (`<a target="_blank">`), and reusing it for a CSS selector
# would be a silent footgun the moment someone wanted both on the same
# element.
#
# This is a closed set on purpose -- ARKlight ships a tiny vanilla-JS
# runtime that implements exactly these behaviors (see
# arklight.backend.js), rather than letting users embed arbitrary JS
# strings. That keeps "the browser never executes Python" true in
# spirit (it never executes anything ARKlight didn't ship) and keeps to
# "one obvious way": there's a fixed, discoverable vocabulary instead
# of a new ad-hoc DSL per site.
#
# v0.003 added `copy` and `dismiss` -- both still stateless in the same
# sense as `toggle`/`scroll-to`: each is a pure function of the DOM at
# click time (clipboard write, or a one-way class add), with no value
# retained in JS across events. Nothing here introduces app state.
#
# This lives here (not in arklight.backend.js) so the Validation stage
# can check `on_click` values against it without importing a backend --
# ir/ stays backend-agnostic; arklight.backend.js imports FROM here to
# stay in sync instead of the other way around.
# v0.0035: behaviors are a registry, not a hardcoded dispatch table.
#
# `BehaviorSpec` documents what a behavior needs the same way `NodeSpec`
# documents what an HTML component needs: `extra_props` are optional
# extra props (beyond the universal `on_click`/`behavior_target` pair)
# a behavior reads -- e.g. `toggle`'s `toggle_class`.
@dataclass
class BehaviorSpec:
    extra_props: tuple[str, ...] = field(default_factory=tuple)


BEHAVIOR_REGISTRY: dict[str, BehaviorSpec] = {
    "toggle": BehaviorSpec(extra_props=("toggle_class",)),
    "scroll-to": BehaviorSpec(),
    "copy": BehaviorSpec(),
    "dismiss": BehaviorSpec(extra_props=("toggle_class",)),
}

# Derived, not hand-maintained -- Validation's existing
# `on_click in KNOWN_BEHAVIORS` check doesn't need to change shape.
KNOWN_BEHAVIORS = frozenset(BEHAVIOR_REGISTRY)


# v0.0035: a real `State` primitive with a closed *action* vocabulary,
# on top of (not instead of) the named-behavior vocabulary above.
# `State("count", 0)` declared inside `Page(...)` and `Bind("count")`
# used wherever a literal value is accepted give components a way to
# read reactive state; `Action.set/increment/toggle_bool` (structured
# `ActionRef` objects, see arklight.ast.nodes) give them a closed way
# to *change* it from `on_click=`. `ActionSpec.args` documents the
# keyword arguments a given action's `ActionRef.args` dict is expected
# to carry (e.g. `increment`'s `delta`), the same role `extra_props`
# plays for `BehaviorSpec` above.
#
# Still a closed, described vocabulary, same discipline as
# `BEHAVIOR_REGISTRY`: adding a new action later is a new registry
# entry plus a new JS fragment in `arklight/backend/js/actions/`, never
# a string of JS or Python handed to the browser to execute.
@dataclass
class ActionSpec:
    args: tuple[str, ...] = field(default_factory=tuple)


ACTION_REGISTRY: dict[str, ActionSpec] = {
    "set": ActionSpec(args=("value",)),
    "increment": ActionSpec(args=("delta",)),
    "toggle_bool": ActionSpec(),
    # ------------------------------------------------------------------
    # v0.0035: stateful-JS vocabulary addendum. Same discipline as the
    # v0.003 HTML vocabulary addendum above -- these fill in the two
    # gaps real usage hits almost immediately (a counter needs a `-1`
    # as much as a `+1`; a form/counter/toggle demo needs a "put it
    # back the way it started" control), rather than every site
    # re-deriving them from `set`/`increment` by hand. Only the most
    # commonly needed additions land here; see docs/DESIGN-NOTES.md
    # ("v0.0035: stateful JS vocabulary addendum") for the rest of the
    # candidates (list append/remove, derived/computed state, debounced
    # actions, input-bound `set`) deliberately left for a future
    # version instead of growing this addendum further.
    # ------------------------------------------------------------------
    "decrement": ActionSpec(args=("delta",)),
    "reset": ActionSpec(),
    # ------------------------------------------------------------------
    # v0.0035: stateful-JS vocabulary addendum II. The first actions
    # that assume a list-valued `State(...)` rather than a scalar one
    # -- deliberately just the two minimal list mutations (append one
    # value, remove by index), not a full list-editing vocabulary. See
    # docs/DESIGN-NOTES.md for what's still left for a future version.
    # ------------------------------------------------------------------
    "append": ActionSpec(args=("value",)),
    "remove": ActionSpec(args=("index",)),
}

KNOWN_ACTIONS = frozenset(ACTION_REGISTRY)


# Stage 3 of "Reactive-core vdom staging" (see docs/DESIGN-NOTES.md):
# event modifiers -- a timing/dispatch concern orthogonal to what an
# action does, so it's solved once as a wrapper around the click
# dispatcher rather than duplicated into every `ACTION_REGISTRY` entry.
# `Action.set(...).with_modifiers("prevent", "stop", "once")` and
# `Action.set(...).debounce(300)` / `.throttle(300)` attach these to an
# `ActionRef` (see `ActionRef.modifiers` in arklight.ast.nodes); the
# Validation stage checks each token here the same way it checks
# `action.action` against `ACTION_REGISTRY` above.
#
# `has_param` distinguishes plain boolean modifiers (`prevent`, `stop`,
# `once`) from ones that carry a millisecond value serialized as
# `"<name>:<ms>"` (`debounce`, `throttle`) -- same shape distinction
# `ActionSpec.args` draws for actions, just for the modifier token
# itself rather than the action's argument dict.
@dataclass
class ModifierSpec:
    has_param: bool = False


MODIFIER_REGISTRY: dict[str, ModifierSpec] = {
    "prevent": ModifierSpec(),
    "stop": ModifierSpec(),
    "once": ModifierSpec(),
    "debounce": ModifierSpec(has_param=True),
    "throttle": ModifierSpec(has_param=True),
}

KNOWN_MODIFIERS = frozenset(MODIFIER_REGISTRY)
