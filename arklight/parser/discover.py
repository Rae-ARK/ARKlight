"""
Python Source -> Python AST stage.

Before ARKlight ever executes a user's site file, it parses the source
with the standard library `ast` module and statically discovers:

- every `Site(...)` instantiation (by variable name)
- every `@<site_var>.page("/route")` decorated function

This is pure static analysis: no user code runs here. It exists so the
compiler (and future tooling -- a `arklight routes` CLI command, linting,
etc.) can reason about a site's shape without side effects, and so we
have a genuine "Python AST" stage in the pipeline rather than jumping
straight from source text to execution.

The actual ARK AST (the ARKNode trees) is still produced by executing
the module -- see `arklight.parser.loader`. This module only discovers
*structure* (which routes exist, which functions back them), not the
node trees themselves.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass
class DiscoveredPage:
    route: str
    function_name: str
    lineno: int


@dataclass
class DiscoveredSite:
    variable_name: str
    pages: list[DiscoveredPage]


class _SiteVisitor(ast.NodeVisitor):
    """Walks a module's AST looking for `Site()` assignments and
    `@<name>.page(...)` decorated function defs."""

    def __init__(self) -> None:
        self.site_variable_names: set[str] = set()
        self.pages: list[DiscoveredPage] = []

    def visit_Assign(self, node: ast.Assign) -> None:
        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "Site"
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.site_variable_names.add(target.id)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_decorators(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_decorators(node)
        self.generic_visit(node)

    def _check_decorators(self, node) -> None:
        for dec in node.decorator_list:
            route = self._match_page_decorator(dec)
            if route is not None:
                self.pages.append(
                    DiscoveredPage(route=route, function_name=node.name, lineno=node.lineno)
                )

    def _match_page_decorator(self, dec: ast.expr) -> str | None:
        # Matches: <site_var>.page("<route>")
        if not isinstance(dec, ast.Call):
            return None
        if not isinstance(dec.func, ast.Attribute) or dec.func.attr != "page":
            return None
        if not isinstance(dec.func.value, ast.Name):
            return None
        if dec.func.value.id not in self.site_variable_names:
            return None
        if not dec.args or not isinstance(dec.args[0], ast.Constant):
            return None
        if not isinstance(dec.args[0].value, str):
            return None
        return dec.args[0].value


def discover(source: str, filename: str = "<arklight-site>") -> DiscoveredSite:
    """
    Statically analyze `source` and return the discovered Site variable
    name and page routes, without executing any user code.

    Raises SyntaxError if the source does not parse.
    """
    tree = ast.parse(source, filename=filename)
    visitor = _SiteVisitor()
    visitor.visit(tree)

    if not visitor.site_variable_names:
        raise ValueError(
            "No `Site()` instantiation found. ARKlight site files must "
            "create a Site object, e.g. `site = Site()`."
        )

    # There should realistically be exactly one Site per file for v0.001.
    variable_name = sorted(visitor.site_variable_names)[0]

    if not visitor.pages:
        raise ValueError(
            f"No pages registered on `{variable_name}`. Add at least one "
            f'`@{variable_name}.page("/")` function.'
        )

    return DiscoveredSite(variable_name=variable_name, pages=visitor.pages)
