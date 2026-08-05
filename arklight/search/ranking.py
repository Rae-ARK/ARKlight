"""
Ranking layer: turns a set of candidate symbol names (Stage 2's
`retrieve_candidates`) into an ordered, explainable list of results by
combining four independent, individually-inspectable signals:

  - lexical similarity   -- whole-string ratio + token overlap against
                             the query (`arklight.search._tokenize`)
  - structural importance -- from Stage 3's `pagerank`/
                             `personalized_pagerank` over the repo's
                             own real usage graph, normalized within
                             the candidate set
  - usage score           -- from Stage 4's `arklight.search.stats`
                             (frequency + recency decay), already
                             bounded to [0, 1)
  - known typo             -- Stage 8's addendum: 1.0 if `(query, name)`
                             is a recorded compile-error confusion pair
                             this project has actually seen before
                             (`arklight.search.stats.is_known_confusion`),
                             else 0.0

This is the "attention conceptually, not a Transformer" layer the idea
doc describes: fixed, named weights over a handful of inspectable
signals, not a learned/opaque model. Every `RankedResult.signals` dict
is the full, honest breakdown of how its score was produced -- nothing
is folded away.

Determinism: given the same query, candidates, knowledge, importance,
and stats snapshot, `rank()` always returns byte-identical output --
no wall-clock dependence unless the caller omits `now` (see its
docstring), no randomness, no reliance on dict/set iteration order
(ties are broken by name).
"""

from __future__ import annotations

import difflib
import time
from dataclasses import dataclass, field

from arklight.search._tokenize import tokenize
from arklight.search.knowledge import SymbolFact
from arklight.search.stats import is_known_confusion as _stats_is_known_confusion
from arklight.search.stats import usage_score as _stats_usage_score

# Default per-signal weights, summing to 1.0. Lexical similarity is
# weighted highest since it's the most direct signal of "does this
# name plausibly match what was typed" -- structural importance and
# usage score exist to break ties/reorder among otherwise-plausible
# matches, not to override an obviously-wrong lexical match.
#
# `known_typo` (Stage 8) gets a deliberately small weight: it's this
# project's own compile-error history outranking generic lexical
# distance for a *specific misspelling it has already seen resolved
# before* -- a real, strong signal when it fires, but one that fires
# rarely (only on an exact previously-recorded typo), so it shouldn't
# dominate the other three signals when it doesn't. Reducing the other
# three proportionally (by 0.9x) keeps their old *relative* balance
# intact while making room for it.
DEFAULT_WEIGHTS: dict[str, float] = {
    "lexical": 0.45,
    "structural": 0.27,
    "usage": 0.18,
    "known_typo": 0.10,
}


@dataclass(frozen=True)
class RankedResult:
    """One scored candidate. `signals` holds every individual signal
    value (`lexical`, `structural`, `usage`, each already in `[0, 1]`)
    that went into `score`, so a result is always inspectable after
    the fact -- never a bare number with no explanation. The weights
    actually applied are available separately via `weights_used`."""

    name: str
    score: float
    signals: dict[str, float] = field(default_factory=dict)
    weights_used: dict[str, float] = field(default_factory=dict)


def _lexical_similarity(query: str, name: str, tokens: tuple[str, ...]) -> float:
    """Whole-string ratio (`difflib.SequenceMatcher`) blended with
    token-set overlap (Jaccard), each in `[0, 1]`, combined `0.6/0.4`.
    Whole-string ratio catches typos/substrings; token overlap catches
    multi-word matches where the substrings don't line up character-
    for-character (e.g. `"row tbl"` vs `"TableRow"`)."""
    whole = difflib.SequenceMatcher(None, query.lower(), name.lower()).ratio()

    query_tokens = set(tokenize(query))
    name_tokens = set(tokens)
    if query_tokens or name_tokens:
        union = query_tokens | name_tokens
        jaccard = len(query_tokens & name_tokens) / len(union) if union else 0.0
    else:
        jaccard = 0.0

    return (0.6 * whole) + (0.4 * jaccard)


def _normalized_importance(
    candidates: list[str], importance: dict[str, float]
) -> dict[str, float]:
    """Min-max-against-zero normalization of `importance` *within this
    candidate set*: the top-importance candidate present gets 1.0,
    everything else scales relative to it. Normalizing per query
    (rather than relying on raw PageRank mass, which sums to ~1 across
    the *entire* graph and shrinks as the graph grows) keeps this
    signal meaningful regardless of how large the full symbol graph
    is. A candidate absent from `importance` (never seen in any scanned
    usage) scores 0.0, not an error."""
    raw = {name: max(0.0, importance.get(name, 0.0)) for name in candidates}
    peak = max(raw.values(), default=0.0)
    if peak <= 0.0:
        return {name: 0.0 for name in candidates}
    return {name: value / peak for name, value in raw.items()}


def rank(
    query: str,
    candidates: set[str] | list[str],
    knowledge: dict[str, SymbolFact],
    importance: dict[str, float],
    stats,
    *,
    weights: dict[str, float] | None = None,
    now: float | None = None,
) -> list[RankedResult]:
    """Score and order `candidates` for `query`.

    Parameters mirror the earlier stages directly:
      - `knowledge`: `arklight.search.knowledge.build_knowledge_base()`
        output -- used for each candidate's `tokens`.
      - `importance`: `arklight.search.graph.pagerank`/
        `personalized_pagerank` output -- structural signal, normalized
        within this candidate set (see `_normalized_importance`).
      - `stats`: an open `sqlite3.Connection` as returned by
        `arklight.search.stats.open_store` -- passed straight through
        to `arklight.search.stats.usage_score` and
        `arklight.search.stats.is_known_confusion` per candidate.
        `None` is accepted and treated as "no usage/confusion history
        yet" (both signals 0.0 for every candidate) so callers without
        a store open yet (e.g. tests, or a first-ever run) don't need
        to special-case anything.

    `now` defaults to `time.time()` if omitted -- pass an explicit
    value (as `arklight.search.stats.usage_score` itself allows) for
    reproducible/testable output, since usage score decays with
    wall-clock time otherwise.

    Ties (equal final score) are broken by name, ascending -- so
    output order is always fully determined by the inputs, never by
    incidental set/dict iteration order.
    """
    resolved_weights = dict(DEFAULT_WEIGHTS if weights is None else weights)
    if now is None:
        now = time.time()

    candidate_list = sorted(candidates)
    normalized_structural = _normalized_importance(candidate_list, importance)

    results: list[RankedResult] = []
    for name in candidate_list:
        fact = knowledge.get(name)
        tokens = fact.tokens if fact is not None else tuple(tokenize(name))

        lexical = _lexical_similarity(query, name, tokens)
        structural = normalized_structural.get(name, 0.0)
        usage = 0.0 if stats is None else _stats_usage_score(stats, name, now=now)
        known_typo = (
            0.0 if stats is None else float(_stats_is_known_confusion(stats, query, name))
        )

        score = (
            resolved_weights.get("lexical", 0.0) * lexical
            + resolved_weights.get("structural", 0.0) * structural
            + resolved_weights.get("usage", 0.0) * usage
            + resolved_weights.get("known_typo", 0.0) * known_typo
        )

        results.append(
            RankedResult(
                name=name,
                score=score,
                signals={
                    "lexical": lexical,
                    "structural": structural,
                    "usage": usage,
                    "known_typo": known_typo,
                },
                weights_used=dict(resolved_weights),
            )
        )

    results.sort(key=lambda result: (-result.score, result.name))
    return results
