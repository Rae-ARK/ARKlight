"""
Validation stage.

Once the ARK AST is normalized, ARKlight checks it against a small
schema of known node types before it's allowed to become Website IR.
This is the main guardrail that keeps ARKlight "beginner friendly": bad
trees fail loudly and specifically, at build time, in Python -- never
silently in the browser.

Checks performed (v0.001):

1. The node `type` is a recognized built-in (arklight.ir.schema.SCHEMA).
2. Required props for that type are present (e.g. `Link` needs `href`,
   `Image` needs `src`).
3. Node types that require plain-text-only children (e.g. `Text`,
   `Button`) don't contain nested component nodes.
4. The tree's root is a `Page` node.
5. Recurses into every child.
"""

from __future__ import annotations

from arklight.ast.nodes import ARKNode
from arklight.ir.schema import SCHEMA


class ValidationError(Exception):
    """Raised when an ARK AST tree fails validation."""


def validate_node(node: ARKNode, *, path: str = "root") -> None:
    spec = SCHEMA.get(node.type)
    if spec is None:
        known = ", ".join(sorted(SCHEMA))
        raise ValidationError(
            f"Unknown component type {node.type!r} at {path}. "
            f"Known component types are: {known}."
        )

    for prop_name in spec.required_props:
        if prop_name not in node.props:
            raise ValidationError(
                f"{node.type!r} at {path} is missing required prop {prop_name!r}."
            )

    if not spec.allow_children and node.children:
        raise ValidationError(f"{node.type!r} at {path} must not have children.")

    if spec.text_only_children:
        for i, child in enumerate(node.children):
            if isinstance(child, ARKNode):
                raise ValidationError(
                    f"{node.type!r} at {path} can only contain text, but found a "
                    f"nested {child.type!r} component at {path}/children[{i}]. "
                    f"Move the {child.type!r} outside of {node.type!r}."
                )
            if not isinstance(child, str):
                raise ValidationError(
                    f"{node.type!r} at {path} expected a string child, got "
                    f"{type(child).__name__!r}."
                )
        return

    for i, child in enumerate(node.children):
        if isinstance(child, ARKNode):
            validate_node(child, path=f"{path}/{child.type}[{i}]")
        elif not isinstance(child, str):
            raise ValidationError(
                f"{node.type!r} at {path} has an unexpected child of type "
                f"{type(child).__name__!r} at position {i}."
            )


def validate_page(route: str, page: ARKNode) -> None:
    if page.type != "Page":
        raise ValidationError(
            f"Page function for route {route!r} must return Page(...) as its "
            f"root node, got {page.type!r} instead."
        )
    validate_node(page, path=f"page:{route}")


def validate_ark_ast(pages: dict[str, ARKNode]) -> None:
    """Validate every page. Raises ValidationError on the first problem found."""
    for route, page in pages.items():
        validate_page(route, page)
