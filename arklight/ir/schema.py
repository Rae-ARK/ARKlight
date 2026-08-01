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
}

# Types whose raw string children should stay raw strings during
# normalization rather than being auto-wrapped in a Text node.
TEXT_ONLY_TYPES = frozenset(
    type_name for type_name, spec in SCHEMA.items() if spec.text_only_children
)

# v0.003: named client-side behaviors any component may opt into via
# `on_click="<name>"` (plus `behavior_target="<css selector>"` and, for
# `toggle`, an optional `toggle_class`). Named `behavior_target` rather
# than `target` on purpose: `target` is already a real HTML attribute
# (`<a target="_blank">`), and reusing it for a CSS selector would be a
# silent footgun the moment someone wanted both on the same element.
#
# This is a closed set on purpose -- ARKlight ships a tiny vanilla-JS
# runtime that implements exactly these behaviors (see
# arklight.backend.js), rather than letting users embed arbitrary JS
# strings. That keeps "the browser never executes Python" true in
# spirit (it never executes anything ARKlight didn't ship) and keeps to
# "one obvious way": there's a fixed, discoverable vocabulary instead
# of a new ad-hoc DSL per site.
#
# This lives here (not in arklight.backend.js) so the Validation stage
# can check `on_click` values against it without importing a backend --
# ir/ stays backend-agnostic; arklight.backend.js imports FROM here to
# stay in sync instead of the other way around.
KNOWN_BEHAVIORS = frozenset({"toggle", "scroll-to"})
