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
KNOWN_BEHAVIORS = frozenset({"toggle", "scroll-to", "copy", "dismiss"})
