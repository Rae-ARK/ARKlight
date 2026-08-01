"""
Normalization stage.

Raw ARK AST, as produced by calling component functions, can be messy:

- children may be nested lists (e.g. from a list comprehension:
  `Container([Text(x) for x in items])`)
- children may be bare Python strings, ints, or floats instead of
  ARKNode instances -- *except* inside components that are themselves
  text-only (Heading, Text, Button, Link, Item), where a bare string is
  already the correct, final shape and must NOT be wrapped again.
- `None` may appear where a conditional expression produced nothing
  (e.g. `cond and Text("shown")` when `cond` is False)

Normalization walks the whole ARK AST and produces a *clean* tree where
every child is either an ARKNode or (inside text-only components) a
plain string, ready for validation.
"""

from __future__ import annotations

from arklight.ast.nodes import ARKNode
from arklight.ir.schema import TEXT_ONLY_TYPES

TEXT_LIKE = (str, int, float)


def normalize_children(children: list, *, parent_type: str | None = None) -> list:
    """
    Flatten nested lists and drop Nones/Falses.

    If `parent_type` is one of the text-only component types, bare
    strings/numbers are kept as plain strings (that's what text-only
    components expect). Otherwise they're wrapped in a Text node so
    container-like components always hold a uniform list of ARKNodes.
    """
    text_only_parent = parent_type in TEXT_ONLY_TYPES
    flat: list = []
    for child in children:
        if child is None or child is False:
            # Common pattern: `cond and Component(...)` yields False/None when falsy.
            continue
        if isinstance(child, list):
            flat.extend(normalize_children(child, parent_type=parent_type))
        elif isinstance(child, ARKNode):
            flat.append(normalize_node(child))
        elif isinstance(child, TEXT_LIKE):
            if text_only_parent:
                flat.append(str(child))
            else:
                flat.append(ARKNode(type="Text", props={}, children=[str(child)]))
        else:
            raise TypeError(
                f"Unsupported child of type {type(child).__name__!r}: {child!r}. "
                "Children must be ARKNode components, strings, numbers, lists of "
                "the above, or None/False."
            )
    return flat


def normalize_node(node: ARKNode) -> ARKNode:
    """Return a new ARKNode with normalized children (recursively)."""
    return ARKNode(
        type=node.type,
        props=dict(node.props),
        children=normalize_children(node.children, parent_type=node.type),
    )


def normalize_ark_ast(pages: dict) -> dict:
    """Normalize every page's ARK AST tree."""
    return {route: normalize_node(page) for route, page in pages.items()}
