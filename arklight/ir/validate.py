"""
Validation stage.

Once the ARK AST is normalized, ARKlight checks it against a small
schema of known node types before it's allowed to become Website IR.
This is the main guardrail that keeps ARKlight "beginner friendly": bad
trees fail loudly and specifically, at build time, in Python -- never
silently in the browser.

Checks performed:

1. The node `type` is a recognized built-in (arklight.ir.schema.SCHEMA).
2. Required props for that type are present (e.g. `Link` needs `href`,
   `Image` needs `src`).
3. Node types that require plain-text-only children (e.g. `Text`,
   `Button`) don't contain nested component nodes -- except `Bind(...)`,
   which is a value reference, not a component (see below).
4. `on_click`, if present, is either a known behavior name (paired with
   a `behavior_target` selector -- arklight.ir.schema.KNOWN_BEHAVIORS)
   or an `Action.*(...)` reference (arklight.ir.schema.ACTION_REGISTRY)
   whose `state` targets a `State(...)` declared on the same page.
5. `State(...)` may only appear as a direct child of `Page(...)` --
   state belongs to the page, not to an arbitrary nested component --
   and every `Bind(...)` anywhere on the page must name a `State(...)`
   actually declared there.
6. The tree's root is a `Page` node.
7. Recurses into every child.
"""

from __future__ import annotations

from arklight.ast.nodes import ActionRef, ARKNode
from arklight.ir.schema import ACTION_REGISTRY, KNOWN_BEHAVIORS, SCHEMA


class ValidationError(Exception):
    """Raised when an ARK AST tree fails validation."""


def _validate_bind(node: ARKNode, *, path: str, page_state: frozenset[str]) -> None:
    name = node.props.get("name")
    if not isinstance(name, str) or not name:
        raise ValidationError(f"Bind(...) at {path} needs a non-empty string name.")
    if name not in page_state:
        known = ", ".join(sorted(page_state)) or "(none declared)"
        raise ValidationError(
            f"Bind({name!r}) at {path} references state that isn't declared "
            f"on this page. State declared on this page: {known}."
        )


def _validate_action(action: ActionRef, *, path: str, page_state: frozenset[str]) -> None:
    if action.action not in ACTION_REGISTRY:
        known = ", ".join(sorted(ACTION_REGISTRY))
        raise ValidationError(
            f"on_click at {path} uses unknown action {action.action!r}. "
            f"Known actions are: {known}."
        )
    if action.state not in page_state:
        known = ", ".join(sorted(page_state)) or "(none declared)"
        raise ValidationError(
            f"on_click at {path} ({action.action!r}) targets state "
            f"{action.state!r}, which isn't declared on this page. State "
            f"declared on this page: {known}."
        )


def _validate_behavior_props(node: ARKNode, *, path: str, page_state: frozenset[str]) -> None:
    on_click = node.props.get("on_click")
    if on_click is None:
        return

    if isinstance(on_click, ActionRef):
        _validate_action(on_click, path=path, page_state=page_state)
        return

    if on_click not in KNOWN_BEHAVIORS:
        known = ", ".join(sorted(KNOWN_BEHAVIORS))
        raise ValidationError(
            f"{node.type!r} at {path} has on_click={on_click!r}, which isn't a "
            f"recognized behavior or Action.*(...) reference. Known behaviors "
            f"are: {known}."
        )
    if "behavior_target" not in node.props:
        raise ValidationError(
            f"{node.type!r} at {path} has on_click={on_click!r} but no "
            f"`behavior_target` prop (a CSS selector for the element(s) it "
            f"should act on)."
        )


def _validate_state_declaration(node: ARKNode, *, path: str, parent_is_page: bool) -> None:
    if not parent_is_page:
        raise ValidationError(
            f"State(...) at {path} may only be declared as a direct child of "
            f"Page(...) -- state belongs to the page, not to a nested "
            f"component. Move it up to the top level of Page(...)."
        )
    name = node.props.get("name")
    if not isinstance(name, str) or not name:
        raise ValidationError(f"State(...) at {path} needs a non-empty string name.")


def validate_node(
    node: ARKNode,
    *,
    path: str = "root",
    page_state: frozenset[str] = frozenset(),
    parent_is_page: bool = False,
) -> None:
    if node.type == "Bind":
        _validate_bind(node, path=path, page_state=page_state)
        return

    if node.type == "State":
        _validate_state_declaration(node, path=path, parent_is_page=parent_is_page)
        return

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

    _validate_behavior_props(node, path=path, page_state=page_state)

    if not spec.allow_children and node.children:
        raise ValidationError(f"{node.type!r} at {path} must not have children.")

    if spec.text_only_children:
        for i, child in enumerate(node.children):
            if isinstance(child, ARKNode):
                if child.type == "Bind":
                    _validate_bind(child, path=f"{path}/children[{i}]", page_state=page_state)
                    continue
                raise ValidationError(
                    f"{node.type!r} at {path} can only contain text (or "
                    f"Bind(...)), but found a nested {child.type!r} component "
                    f"at {path}/children[{i}]. Move the {child.type!r} outside "
                    f"of {node.type!r}."
                )
            if not isinstance(child, str):
                raise ValidationError(
                    f"{node.type!r} at {path} expected a string child, got "
                    f"{type(child).__name__!r}."
                )
        return

    for i, child in enumerate(node.children):
        if isinstance(child, ARKNode):
            validate_node(
                child,
                path=f"{path}/{child.type}[{i}]",
                page_state=page_state,
                parent_is_page=(node.type == "Page"),
            )
        elif not isinstance(child, str):
            raise ValidationError(
                f"{node.type!r} at {path} has an unexpected child of type "
                f"{type(child).__name__!r} at position {i}."
            )


def _collect_declared_state(page: ARKNode, route: str) -> frozenset[str]:
    names: set[str] = set()
    for child in page.children:
        if isinstance(child, ARKNode) and child.type == "State":
            name = child.props.get("name")
            if not isinstance(name, str) or not name:
                raise ValidationError(
                    f"State(...) on page {route!r} needs a non-empty string name."
                )
            if name in names:
                raise ValidationError(
                    f"State {name!r} is declared more than once on page {route!r}."
                )
            names.add(name)
    return frozenset(names)


def validate_page(route: str, page: ARKNode) -> None:
    if page.type != "Page":
        raise ValidationError(
            f"Page function for route {route!r} must return Page(...) as its "
            f"root node, got {page.type!r} instead."
        )
    page_state = _collect_declared_state(page, route)
    validate_node(page, path=f"page:{route}", page_state=page_state, parent_is_page=False)


def validate_ark_ast(pages: dict[str, ARKNode]) -> None:
    """Validate every page. Raises ValidationError on the first problem found."""
    for route, page in pages.items():
        validate_page(route, page)
