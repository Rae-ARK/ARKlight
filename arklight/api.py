"""
Public ARKlight API.

`from arklight import *` gives users:

- `Site`       -- the app object, holds page registrations
- `Page`       -- the root node every page function must return
- Built-in components: `Heading`, `Text`, `Button`, `Container`, `Link`, `Image`, `List`, `Item`

Everything a user calls here returns an `ARKNode` (see arklight.ast.nodes),
except `Site`, which is a small registry object.
"""

from __future__ import annotations

from typing import Any, Callable

from arklight.ast.nodes import ARKNode, node

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

    def __init__(self, name: str = "arklight-site") -> None:
        self.name = name
        # route -> page function
        self.routes: dict[str, Callable[[], ARKNode]] = {}

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
    "ARKNode",
]
