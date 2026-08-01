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
