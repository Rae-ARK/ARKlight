"""
ARKlight -- a Python-first compiler for building static websites.

    from arklight import *

    site = Site()

    @site.page("/")
    def home():
        return Page(
            Heading("ARKlight"),
            Text("Build websites with Python."),
            Button("Get Started"),
        )

Users write Python. ARKlight compiles it to standard HTML.
The browser never executes Python.
"""

from arklight.api import (
    Site,
    Page,
    Heading,
    Text,
    Button,
    Container,
    Link,
    Image,
    List,
    Item,
    ARKNode,
)

__version__ = "0.003"

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
    "__version__",
]
