"""
ARK AST node definitions.

When a user writes:

    Heading("ARKlight")

ARKlight does NOT execute a template engine. It calls a plain Python
function named `Heading`, which returns an `ARKNode` instance. The tree
of `ARKNode` objects returned by a page function *is* the ARK AST.

This is intentionally a thin, uniform structure:

    ARKNode(type, props, children)

- `type`     : str   -- the node kind, e.g. "Heading", "Page", "Button"
- `props`    : dict  -- keyword arguments passed to the component
- `children` : list  -- positional arguments passed to the component
                        (may contain strings, ARKNode instances, or
                        lists of either -- normalization flattens this)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ClassBindSpec:
    """
    A reference to a state-driven CSS class toggle -- e.g.
    `Bind.when("active", "is-active")`. Used as a `bind_class=` prop
    value (alongside a component's ordinary `class_name=`) once a page
    declares `State(...)`.

    Mirrors `ActionRef`'s shape: a small structured object, not a
    string, validated against the page's declared `State(...)` names at
    compile time (an unknown `state` target fails the build) and never
    a class-name string built by concatenation at runtime. See
    docs/DESIGN-NOTES.md ("Reactive-core vdom staging", Stage 2).
    """

    state: str
    class_name: str


@dataclass(frozen=True)
class ActionRef:
    """
    A reference to a closed-vocabulary, state-mutating action -- e.g.
    `Action.increment("count")`. Used as an `on_click=` value (alongside
    or instead of a named behavior string) once a page declares
    `State(...)`.

    Deliberately a small structured object, not a string: it is
    validated against `arklight.ir.schema.ACTION_REGISTRY` at compile
    time (unknown action name, or a `state` target that isn't declared
    on the page, both fail the build) and never becomes a JS/Python
    string that gets executed. See docs/DESIGN-NOTES.md ("v0.0035:
    stateful JS -- capability, not vocabulary").
    """

    action: str
    state: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ARKNode:
    """A single node in the ARK AST."""

    type: str
    props: dict[str, Any] = field(default_factory=dict)
    children: list[Any] = field(default_factory=list)

    def __repr__(self) -> str:  # pragma: no cover - debug convenience
        return f"ARKNode({self.type!r}, props={self.props!r}, children={len(self.children)})"


def node(type_name: str):
    """
    Factory that builds a component function for a given ARK node type.

    This is how every built-in component (Heading, Text, Button, ...)
    is defined: they are all thin wrappers that build an ARKNode with
    positional args as children and keyword args as props.

        Heading = node("Heading")
        Heading("ARKlight", id="title")
        # -> ARKNode("Heading", props={"id": "title"}, children=["ARKlight"])
    """

    def factory(*children: Any, **props: Any) -> ARKNode:
        return ARKNode(type=type_name, props=props, children=list(children))

    factory.__name__ = type_name
    factory.__qualname__ = type_name
    return factory
