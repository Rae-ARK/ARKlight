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
    # v0.0035: page-scoped reactive state declared via `State(...)`,
    # extracted from the Page node's children rather than living as a
    # prop on some other node -- state belongs to the page, the same
    # way `title` does. Empty for pages that declare no state.
    state: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebsiteIR:
    """The full compiled site: every route, mapped to its IR tree."""

    site_name: str
    pages: list[IRPage] = field(default_factory=list)
    # v0.042: site-wide custom CSS classes registered via `Site.style(...)`
    # -- name -> {css-property: value}. Structured input only (a plain
    # dict), never a raw CSS string, same boundary the rest of the
    # project holds. Empty for sites that never call `site.style(...)`.
    custom_styles: dict[str, dict[str, str]] = field(default_factory=dict)
    # CSS backend refactor: `--ark-*` custom property overrides
    # registered via `Site(max_width=..., bg=...)` -- var name (e.g.
    # "--ark-max-width") -> value. Empty for sites that pass neither,
    # in which case `CSSBackend` falls back to its own defaults.
    css_var_overrides: dict[str, str] = field(default_factory=dict)


def _ark_node_to_ir_node(node: ARKNode) -> IRNode:
    children: list[IRNode | str] = []
    for child in node.children:
        if isinstance(child, ARKNode):
            children.append(_ark_node_to_ir_node(child))
        else:
            children.append(str(child))
    return IRNode(type=node.type, props=dict(node.props), children=children)


def _extract_page_state(page: ARKNode) -> tuple[dict[str, Any], list]:
    """
    Split a validated Page node's children into (state, remaining
    children). `State(...)` nodes are declarations, not renderable
    content -- they must never reach the HTML backend as a child.
    """
    state: dict[str, Any] = {}
    remaining: list = []
    for child in page.children:
        if isinstance(child, ARKNode) and child.type == "State":
            state[child.props["name"]] = child.props.get("initial")
        else:
            remaining.append(child)
    return state, remaining


def build_website_ir(
    site_name: str,
    pages: dict[str, ARKNode],
    *,
    custom_styles: dict[str, dict[str, str]] | None = None,
    css_var_overrides: dict[str, str] | None = None,
) -> WebsiteIR:
    """
    Build the Website IR from a normalized + validated ARK AST.

    Callers are expected to have already run `normalize_ark_ast` and
    `validate_ark_ast` on `pages` before calling this. `custom_styles`
    (v0.042) and `css_var_overrides` (CSS backend refactor) are both
    optional and default to empty -- existing callers that only pass
    `site_name`/`pages` are unaffected.
    """
    ir_pages = []
    for route, page in pages.items():
        state, remaining_children = _extract_page_state(page)
        root_page = ARKNode(type=page.type, props=page.props, children=remaining_children)
        ir_pages.append(IRPage(route=route, root=_ark_node_to_ir_node(root_page), state=state))
    return WebsiteIR(
        site_name=site_name,
        pages=ir_pages,
        custom_styles=dict(custom_styles) if custom_styles else {},
        css_var_overrides=dict(css_var_overrides) if css_var_overrides else {},
    )
