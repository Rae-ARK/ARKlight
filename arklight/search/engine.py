"""
Engine façade: wraps the Stage 2-5 pipeline (retrieval -> structural
importance -> ranking, on top of the Stage 1 knowledge base and Stage
4 usage stats) into the two operations everything else actually needs:

    engine.search(query, limit=5, near=None) -> list[RankedResult]
    engine.accept(name)                      -> None

Callers (the Stage 7 CLI, the Stage 9 IDE endpoint) never touch
`knowledge.py`/`retrieval.py`/`graph.py`/`ranking.py`/`stats.py`
directly -- `SearchEngine` is the one seam between "the ranking
pipeline" and "everything that uses it".
"""

from __future__ import annotations

import functools
import sqlite3
from pathlib import Path

from arklight.search.graph import build_usage_graph, pagerank, personalized_pagerank
from arklight.search.knowledge import SymbolFact, build_knowledge_base
from arklight.search.ranking import RankedResult, rank
from arklight.search.retrieval import retrieve_candidates
from arklight.search.stats import open_store, record_acceptance


class SearchEngineError(Exception):
    """Raised for engine-level failures that aren't any individual
    stage's fault to explain on its own -- e.g. `near=` naming a
    symbol the usage graph has never seen. Callers (CLI/endpoint) are
    expected to catch this and print `str(exc)` as a clean message,
    same convention as CompileError/PackError/PWAError/ScaffoldError/
    UpgradeError elsewhere in the codebase."""


class SearchEngine:
    """Lazily builds and caches the knowledge base, usage graph, and
    plain (non-personalized) PageRank once per instance -- repeated
    `.search()` calls in the same process don't pay that cost twice.
    Also caches ranked *results* per `(query, limit, near, now)` via
    `functools.lru_cache` (stdlib): a pure function of its inputs, so
    caching changes nothing about what a call returns, only how many
    times the work to produce it actually runs. `now=None` (the
    common case -- see `search()`) is itself part of the cache key,
    which means a cached hit doesn't re-evaluate wall-clock usage-
    score decay on every repeat query; Stage 4's decay half-life is
    30 days by default, so this is a deliberate, negligible precision
    trade for repeated-query speed, not an oversight.

    The cache is cleared by anything that changes what a future
    ranking call would produce: `.accept()` today (usage stats
    changed); the Stage 8 compile-error feedback hook will clear it
    too once it lands (the confusion table changing is the same kind
    of event).
    """

    def __init__(
        self,
        *,
        roots: list[Path] | None = None,
        db_path: Path | None = None,
        cache_size: int = 256,
    ) -> None:
        # `roots`/`db_path` exist mainly for tests -- production
        # callers use the defaults (this checkout's examples/tests,
        # and the platform user-data path from stats.default_db_path).
        self._roots = roots
        self._db_path = db_path

        self._knowledge: dict[str, SymbolFact] | None = None
        self._graph: dict[str, dict[str, int]] | None = None
        self._pagerank: dict[str, float] | None = None
        self._stats_conn: sqlite3.Connection | None = None

        # Built per-instance (not a module-level @lru_cache) so
        # separate SearchEngine instances -- e.g. in tests -- never
        # share cache entries, and so `.accept()` only ever clears
        # *this* engine's cache.
        self._cached_search = functools.lru_cache(maxsize=cache_size)(self._search_uncached)

    # -- lazily-built, cached-once state --------------------------------

    @property
    def knowledge(self) -> dict[str, SymbolFact]:
        if self._knowledge is None:
            self._knowledge = build_knowledge_base()
        return self._knowledge

    @property
    def graph(self) -> dict[str, dict[str, int]]:
        if self._graph is None:
            self._graph = build_usage_graph(set(self.knowledge), self._roots)
        return self._graph

    @property
    def stats(self) -> sqlite3.Connection:
        if self._stats_conn is None:
            self._stats_conn = open_store(self._db_path)
        return self._stats_conn

    def _importance(self, near: str | None) -> dict[str, float]:
        if near is None:
            if self._pagerank is None:
                self._pagerank = pagerank(self.graph)
            return self._pagerank
        try:
            # Not cached per-seed: personalized runs are cheap relative
            # to plain pagerank being reused across an entire session,
            # and caching every seed ever passed would grow unbounded
            # over a long-lived process for no real benefit.
            return personalized_pagerank(self.graph, near)
        except ValueError as exc:
            raise SearchEngineError(
                f"--near {near!r}: not a known symbol in this project's usage "
                f"graph (no scanned example/test calls it). Try a plain "
                f"`arklight search {near}` first to confirm the name, or omit "
                f"--near to rank without a structural bias."
            ) from exc

    # -- public API -------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 5,
        near: str | None = None,
        *,
        now: float | None = None,
    ) -> list[RankedResult]:
        """Rank `query` against every known component, returning the
        top `limit` results. `near` re-centers structural importance
        on itself (personalized PageRank restart concentrated on
        `near` -- see `arklight.search.graph.personalized_pagerank`),
        which in turn also raises the relative importance of whatever
        `near` frequently calls, since that's where its own boosted
        mass flows on each iteration. Raises `SearchEngineError` if
        `near` isn't a symbol the usage graph has ever seen.

        `now` is forwarded to Stage 5's `rank()` for usage-score
        recency; leave it `None` in normal use (real wall-clock time),
        pass an explicit value only for reproducible tests.
        """
        return list(self._cached_search(query, limit, near, now))

    def _search_uncached(
        self, query: str, limit: int, near: str | None, now: float | None
    ) -> tuple[RankedResult, ...]:
        candidates = retrieve_candidates(query, self.knowledge)
        importance = self._importance(near)
        results = rank(query, candidates, self.knowledge, importance, self.stats, now=now)
        return tuple(results[:limit])

    def accept(self, name: str) -> None:
        """Record that `name` was accepted for some prior query, and
        invalidate the result cache -- future `.search()` calls should
        reflect the updated usage stats immediately, not stay stale
        until the process restarts."""
        record_acceptance(self.stats, name)
        self._cached_search.cache_clear()

    def close(self) -> None:
        """Release the open stats connection, if any. Optional --
        short CLI invocations that exit right after don't strictly
        need this, but a long-lived process (the Stage 9 endpoint)
        should call it on shutdown."""
        if self._stats_conn is not None:
            self._stats_conn.close()
            self._stats_conn = None


_default_engine: SearchEngine | None = None


def default_engine() -> SearchEngine:
    """Process-wide lazily-constructed `SearchEngine` singleton, so
    repeated `arklight search` invocations within one process (or a
    long-lived host like the Stage 9 endpoint) share one knowledge
    base / usage graph / stats connection rather than rebuilding per
    call. Mostly moot for today's one-shot CLI process, but is exactly
    what a long-lived caller needs without having to manage the
    instance itself."""
    global _default_engine
    if _default_engine is None:
        _default_engine = SearchEngine()
    return _default_engine
