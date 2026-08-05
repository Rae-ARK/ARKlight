from __future__ import annotations

import difflib

from arklight.search._tokenize import tokenize
from arklight.search.knowledge import SymbolFact


def retrieve_candidates(
    query: str,
    knowledge: dict[str, SymbolFact],
    *,
    fuzzy_limit: int = 10,
) -> set[str]:
    """Cheap, high-recall candidate generation over `knowledge`.

    Combines exact/case-insensitive match, prefix match, substring
    match, token overlap, and `difflib` close-match into a single
    candidate set. This layer's job is to shrink the full symbol space
    down to "plausibly relevant" -- ranking is what narrows and orders
    it from here.
    """
    if not query:
        return set()

    lowered_query = query.lower()
    query_tokens = set(tokenize(query))

    candidates: set[str] = set()

    for name, fact in knowledge.items():
        lowered_name = name.lower()

        if lowered_name == lowered_query:
            candidates.add(name)
            continue

        if lowered_name.startswith(lowered_query):
            candidates.add(name)
            continue

        # Query-starts-with-name only counts as a prefix match once the
        # name has enough characters to be a meaningful prefix (>=3) --
        # otherwise a two-letter component name (e.g. "Q", "Rt", "Em")
        # is a "prefix" of nearly any query that happens to start with
        # the same letter(s), turning this into an accidental catch-all
        # rather than a real match.
        if len(lowered_name) >= 3 and lowered_query.startswith(lowered_name):
            candidates.add(name)
            continue

        if lowered_query in lowered_name:
            candidates.add(name)
            continue

        if query_tokens and query_tokens & set(fact.tokens):
            candidates.add(name)

    close = difflib.get_close_matches(
        query, list(knowledge), n=fuzzy_limit, cutoff=0.55
    )
    candidates.update(close)

    return candidates
