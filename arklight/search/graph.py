from __future__ import annotations

import ast
from pathlib import Path


def _default_roots() -> list[Path]:
    """Best-effort discovery of this checkout's `examples/`/`tests/`
    directories, so graphs are built from the repo's own real usage.

    `examples/` and `tests/` are deliberately not part of the shipped
    package (see `pyproject.toml`'s `[tool.setuptools.packages.find]`),
    so a real `pip install` of a built wheel won't have them on disk
    next to the installed package. In that case this returns an empty
    list, and callers get an empty (not wrong, not crashing) graph.
    """
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "pyproject.toml").is_file():
            roots = [candidate / "examples", candidate / "tests"]
            return [root for root in roots if root.is_dir()]
    return []


class _UsageVisitor(ast.NodeVisitor):
    """Walks one module's AST, recording a weighted parent -> child
    edge each time a known component's `Call` is syntactically nested
    inside another known component's `Call`."""

    def __init__(self, known_names: set[str]) -> None:
        self.known_names = known_names
        self._stack: list[str] = []
        self.edges: dict[str, dict[str, int]] = {}

    def visit_Call(self, node: ast.Call) -> None:
        name = None
        if isinstance(node.func, ast.Name) and node.func.id in self.known_names:
            name = node.func.id

        if name is None:
            self.generic_visit(node)
            return

        if self._stack:
            parent = self._stack[-1]
            bucket = self.edges.setdefault(parent, {})
            bucket[name] = bucket.get(name, 0) + 1

        self._stack.append(name)
        self.generic_visit(node)
        self._stack.pop()


def build_usage_graph(
    known_names: set[str],
    roots: list[Path] | None = None,
) -> dict[str, dict[str, int]]:
    """Scan `.py` files under `roots` for real, syntactic component
    nesting and return it as a weighted directed graph:
    `graph[parent][child] == number of times child was called
    directly inside parent` across all scanned files.

    Grounded in facts already sitting in the repo -- no synthetic
    graph, no guessing at relationships that aren't actually used
    anywhere. `roots` defaults to this checkout's `examples/`/`tests/`
    directories when present (see `_default_roots`).
    """
    if roots is None:
        roots = _default_roots()

    merged: dict[str, dict[str, int]] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(path))
            except (SyntaxError, UnicodeDecodeError, OSError):
                continue

            visitor = _UsageVisitor(known_names)
            visitor.visit(tree)

            for parent, children in visitor.edges.items():
                bucket = merged.setdefault(parent, {})
                for child, weight in children.items():
                    bucket[child] = bucket.get(child, 0) + weight

    return merged


def _collect_nodes(graph: dict[str, dict[str, int]]) -> list[str]:
    nodes: set[str] = set(graph)
    for targets in graph.values():
        nodes.update(targets)
    return sorted(nodes)


def pagerank(
    graph: dict[str, dict[str, int]],
    *,
    damping: float = 0.85,
    iterations: int = 40,
) -> dict[str, float]:
    """Plain, deterministic power-iteration PageRank over `graph`'s
    weighted edges: "if a symbol is connected to many important
    symbols, increase its importance." Nodes and edges are always
    visited in sorted order, so the same graph always produces the
    same scores -- no randomness, no external solver, no dependency
    on hash-seed-dependent set iteration order.

    Dangling nodes (no outgoing edges) redistribute their score
    uniformly across all nodes each iteration, the standard fix for
    keeping total rank conserved.
    """
    nodes = _collect_nodes(graph)
    if not nodes:
        return {}

    n = len(nodes)
    scores = {node: 1.0 / n for node in nodes}
    out_weight = {node: sum(graph.get(node, {}).values()) for node in nodes}

    for _ in range(iterations):
        new_scores = {node: (1.0 - damping) / n for node in nodes}
        for src in nodes:
            total_out = out_weight[src]
            if total_out == 0:
                share = damping * scores[src] / n
                for node in nodes:
                    new_scores[node] += share
                continue
            for dst in sorted(graph.get(src, {})):
                weight = graph[src][dst]
                new_scores[dst] += damping * scores[src] * (weight / total_out)
        scores = new_scores

    return scores


def personalized_pagerank(
    graph: dict[str, dict[str, int]],
    seed: str,
    *,
    damping: float = 0.85,
    iterations: int = 40,
) -> dict[str, float]:
    """Same deterministic iteration as `pagerank`, but restarts (both
    the initial teleport mass and every dangling node's redistributed
    score) concentrate on `seed` instead of spreading uniformly --
    makes results context-aware around wherever the user currently
    is, per the idea doc's "Personalized PageRank... begins from the
    user's current editing context" section.

    Raises `ValueError` if `seed` isn't a node in `graph` at all,
    rather than silently falling back to plain PageRank.
    """
    nodes = _collect_nodes(graph)
    if seed not in nodes:
        raise ValueError(f"{seed!r} is not a known symbol in this graph")

    n = len(nodes)
    scores = {node: 1.0 / n for node in nodes}
    out_weight = {node: sum(graph.get(node, {}).values()) for node in nodes}

    for _ in range(iterations):
        new_scores = {node: 0.0 for node in nodes}
        new_scores[seed] += 1.0 - damping
        for src in nodes:
            total_out = out_weight[src]
            if total_out == 0:
                new_scores[seed] += damping * scores[src]
                continue
            for dst in sorted(graph.get(src, {})):
                weight = graph[src][dst]
                new_scores[dst] += damping * scores[src] * (weight / total_out)
        scores = new_scores

    return scores
