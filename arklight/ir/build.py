"""
Website IR.

The Website IR is deliberately a *separate* data structure from the ARK
AST, even though in v0.001 they look structurally similar
(`type` / `props` / `children`). The distinction matters going forward:

- ARK AST is "what the user's Python called" -- it's shaped by the
  public API's function-call ergonomics.
- Website IR is "what the website *means*" -- backend-independent
  intent that any backend (HTML today; CSS/JS/Vue/Svelte later) can
  consume without knowing anything about ARKlight's Python API.

Keeping them separate now means later milestones can let the IR diverge
from the ARK AST (e.g. one ARK node expanding into several IR nodes, or
site-wide concerns like navigation being synthesized into the IR) without
disturbing the public API or the validator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from arklight.ast.nodes import ARKNode


@dataclass
class IRNode:
    """A single node in the Website IR."""

    type: str
    props: dict[str, Any] = field(default_factory=dict)
    children: list["IRNode | str"] = field(default_factory=list)


@dataclass
class IRPage:
    route: str
    root: IRNode


@dataclass
class WebsiteIR:
    """The full compiled site: every route, mapped to its IR tree."""

    site_name: str
    pages: list[IRPage] = field(default_factory=list)


def _ark_node_to_ir_node(node: ARKNode) -> IRNode:
    children: list[IRNode | str] = []
    for child in node.children:
        if isinstance(child, ARKNode):
            children.append(_ark_node_to_ir_node(child))
        else:
            children.append(str(child))
    return IRNode(type=node.type, props=dict(node.props), children=children)


def build_website_ir(site_name: str, pages: dict[str, ARKNode]) -> WebsiteIR:
    """
    Build the Website IR from a normalized + validated ARK AST.

    Callers are expected to have already run `normalize_ark_ast` and
    `validate_ark_ast` on `pages` before calling this.
    """
    ir_pages = [
        IRPage(route=route, root=_ark_node_to_ir_node(page)) for route, page in pages.items()
    ]
    return WebsiteIR(site_name=site_name, pages=ir_pages)
