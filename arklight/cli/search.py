"""
`arklight --search <name>` -- component schema lookup (v0.042).

Read-only reflection over `arklight.ir.schema.SCHEMA`, the single
source of truth every compiler stage already reads from -- no new data
format, no compiler-pipeline changes. Exists so remembering "does
`Picture` take `sources=` or `srcs=`" doesn't require opening
`schema.py` by hand once the vocabulary is 80+ names deep.

The typo-tolerant fallback (`_suggest`) is the same stdlib-only
technique (`difflib.get_close_matches` over a camelCase-aware
tokenizer) used for "did you mean" suggestions elsewhere in the
ARKlight tooling ecosystem -- no external dependency, no network call,
just `difflib` + `re` from the standard library.
"""

from __future__ import annotations

import difflib
import re

from arklight.ir.schema import SCHEMA, NodeSpec

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _tokenize(name: str) -> list[str]:
    """Split `PascalCase`/`camelCase`/`snake_case` into lowercase tokens."""
    spaced = _CAMEL_BOUNDARY.sub(" ", name).replace("_", " ").replace("-", " ")
    return [t.lower() for t in spaced.split() if t]


def _suggest(query: str, limit: int = 5) -> list[str]:
    """
    Typo-tolerant "did you mean" suggestions for `query` against every
    known component name in `SCHEMA`, ranked by a blend of whole-name
    similarity and token overlap (so `"pic"` -> `Picture` and
    `"tbl-row"` -> `TableRow` both work, not just single-typo cases).
    """
    names = sorted(SCHEMA)
    query_tokens = set(_tokenize(query))

    scored: list[tuple[float, str]] = []
    for candidate in names:
        whole = difflib.SequenceMatcher(None, query.lower(), candidate.lower()).ratio()
        overlap = len(query_tokens & set(_tokenize(candidate)))
        score = whole + (overlap * 0.5)
        # Require either a reasonably close whole-name match (catches
        # typos like "Pictur") or at least one shared token (catches
        # multi-word names like "tbl-row" -> TableRow) -- prevents
        # unrelated short/common-letter names from scoring above the
        # cutoff just from SequenceMatcher noise.
        if score > 0.3 and (whole > 0.55 or overlap > 0):
            scored.append((score, candidate))

    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [name for _score, name in scored[:limit]]


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


def search_component(query: str) -> str:
    """
    Look `query` up in `SCHEMA` and return a formatted schema summary.

    Exact match (case-insensitive) wins outright. Otherwise, returns a
    "not found" message with up to 5 typo-tolerant suggestions -- or
    says plainly that nothing close was found, rather than guessing.
    """
    exact = SCHEMA.get(query)
    if exact is not None:
        return _format_spec(query, exact)

    # Case-insensitive exact match (e.g. "picture" -> "Picture").
    lowered = {name.lower(): name for name in SCHEMA}
    if query.lower() in lowered:
        canonical = lowered[query.lower()]
        return _format_spec(canonical, SCHEMA[canonical])

    suggestions = _suggest(query)
    if not suggestions:
        return (
            f"No component named {query!r} found, and nothing close enough "
            f"to suggest. Run `arklight --search <partial-name>` with a "
            f"shorter fragment, or see docs/ARCHITECTURE.md for the full "
            f"component list."
        )

    suggestion_list = ", ".join(suggestions)
    return f"No component named {query!r} found. Did you mean: {suggestion_list}?"
