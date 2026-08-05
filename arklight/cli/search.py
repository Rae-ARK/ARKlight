"""
`arklight search <name>` -- component schema lookup, backed by the
Stage 1-6 deterministic ranking pipeline (`arklight.search.engine`).

Read-only reflection over `arklight.ir.schema.SCHEMA`, the single
source of truth every compiler stage already reads from -- no new data
format, no compiler-pipeline changes. Exists so remembering "does
`Picture` take `sources=` or `srcs=`" doesn't require opening
`schema.py` by hand once the vocabulary is 80+ names deep.

The typo-tolerant fallback (`_suggest`) now calls `SearchEngine.search`
(retrieval -> structural importance -> ranking, see
DETERMINISTIC_RANKING_PLAN.md) instead of bare `difflib`, but still
returns a plain `list[str]` in the same order/shape it always has --
`search_component()`'s exact-match branch, its message text, and
`tests/test_search.py` are all unchanged by this.
"""

from __future__ import annotations

from arklight.ir.schema import SCHEMA, NodeSpec
from arklight.search.engine import default_engine


def _suggest(query: str, limit: int = 5, near: str | None = None) -> list[str]:
    """
    Typo-tolerant "did you mean" suggestions for `query`, ranked by
    the Stage 5 pipeline (lexical similarity + structural importance +
    usage history) over every known component name in `SCHEMA`. Same
    external contract as the old `difflib`-only version: a plain,
    already-ordered `list[str]`.
    """
    results = default_engine().search(query, limit=limit, near=near)
    return [result.name for result in results]


def record_acceptance(name: str) -> None:
    """Thin wrapper around `SearchEngine.accept` -- records that
    `name` was the symbol the user actually wanted, closing the
    learning loop from the CLI's `--accept` flag."""
    default_engine().accept(name)


def resolve_exact(query: str) -> str | None:
    """Case-insensitive exact-match lookup against `SCHEMA`, returning
    the canonical (correctly-cased) name or `None`. Shared by
    `search_component()`'s own exact-match branch and the CLI's
    `--accept` flag, so "what counts as an exact match" has exactly
    one definition."""
    exact = SCHEMA.get(query)
    if exact is not None:
        return query

    lowered = {name.lower(): name for name in SCHEMA}
    return lowered.get(query.lower())


def _format_spec(name: str, spec: NodeSpec) -> str:
    lines = [f"{name}"]

    if spec.required_props:
        props = ", ".join(spec.required_props)
        lines.append(f"  required props : {props}")
    else:
        lines.append("  required props : (none)")

    lines.append(f"  allows children: {'yes' if spec.allow_children else 'no'}")

    if spec.text_only_children:
        lines.append(
            "  children       : text only (Bind(...) is also allowed here --"
            " see docs/DESIGN-NOTES.md, 'stateful JS')"
        )
    elif spec.allow_children:
        lines.append("  children       : any nested component")

    return "\n".join(lines)


def search_component(query: str, *, limit: int = 5, near: str | None = None) -> str:
    """
    Look `query` up in `SCHEMA` and return a formatted schema summary.

    Exact match (case-insensitive) wins outright. Otherwise, returns a
    "not found" message with up to `limit` ranked suggestions -- or
    says plainly that nothing close was found, rather than guessing.
    `near` optionally biases suggestion ranking toward symbols
    structurally close to `near` (personalized PageRank seed); default
    behavior (`near=None`) is unchanged from before Stage 7.
    """
    canonical = resolve_exact(query)
    if canonical is not None:
        return _format_spec(canonical, SCHEMA[canonical])

    suggestions = _suggest(query, limit=limit, near=near)
    if not suggestions:
        return (
            f"No component named {query!r} found, and nothing close enough "
            f"to suggest. Run `arklight --search <partial-name>` with a "
            f"shorter fragment, or see docs/ARCHITECTURE.md for the full "
            f"component list."
        )

    suggestion_list = ", ".join(suggestions)
    return f"No component named {query!r} found. Did you mean: {suggestion_list}?"
