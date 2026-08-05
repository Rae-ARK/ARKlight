from __future__ import annotations

import difflib
import sqlite3

from arklight.search._tokenize import tokenize
from arklight.search.knowledge import SymbolFact
from arklight.search.stats import resolved_for_typo


def retrieve_candidates(
    query: str,
    knowledge: dict[str, SymbolFact],
    *,
    fuzzy_limit: int = 10,
    stats: sqlite3.Connection | None = None,
) -> set[str]:
    """Cheap, high-recall candidate generation over `knowledge`.

    Combines exact/case-insensitive match, prefix match, substring
    match, token overlap, `difflib` close-match, and (Stage 8's
    addendum) this project's own recorded compile-error typos into a
    single candidate set. This layer's job is to shrink the full
    symbol space down to "plausibly relevant" -- ranking is what
    narrows and orders it from here.

    `stats`, if given, is an open `sqlite3.Connection` (as returned by
    `arklight.search.stats.open_store`) -- if `query` exactly matches
    a `typo` this project's own compile-error history has already
    recorded (see `arklight.search.feedback`), its resolved name is
    unioned in even if none of the heuristics above would have
    surfaced it (e.g. an edit distance too large for `difflib`'s
    default cutoff, but one this exact project has already proved is
    what people mean). `None` (the default) skips this check entirely,
    same as every other stage that accepts an optional stats
    connection.
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

    if stats is not None:
        typo_resolution = resolved_for_typo(stats, query)
        if typo_resolution is not None:
            candidates.add(typo_resolution)

    return candidates
