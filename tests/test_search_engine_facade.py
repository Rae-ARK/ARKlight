import textwrap

import pytest

from arklight.search.engine import SearchEngine, SearchEngineError, default_engine


def _write_usage_example(tmp_path):
    """A tiny examples/ tree with real, syntactic component nesting
    (using actual SCHEMA names -- Figure > Image, Text), so the
    engine's usage graph/pagerank aren't empty in these tests."""
    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / "site.py").write_text(
        textwrap.dedent(
            """
            from arklight import Figure, Image, Text

            def page():
                return Figure(Image(src="a.png"), Text("caption"))
            """
        )
    )
    return [examples]


@pytest.fixture
def engine(tmp_path):
    roots = _write_usage_example(tmp_path)
    db_path = tmp_path / "search.sqlite3"
    eng = SearchEngine(roots=roots, db_path=db_path)
    yield eng
    eng.close()


# ---------------------------------------------------------------------
# basic search
# ---------------------------------------------------------------------


def test_search_returns_ranked_results(engine):
    results = engine.search("Picture")
    assert results
    assert results[0].name == "Picture"


def test_search_respects_limit(engine):
    results = engine.search("Pic", limit=2)
    assert len(results) <= 2


def test_search_unknown_query_returns_empty_or_low_confidence(engine):
    results = engine.search("zzz-definitely-not-a-component-zzz")
    # No hard guarantee of emptiness (difflib may still surface noise),
    # but nothing should score suspiciously high.
    assert all(r.score < 0.9 for r in results)


# ---------------------------------------------------------------------
# lazy build-once behavior
# ---------------------------------------------------------------------


def test_knowledge_base_is_built_once(engine):
    first = engine.knowledge
    second = engine.knowledge
    assert first is second


def test_graph_is_built_once(engine):
    first = engine.graph
    second = engine.graph
    assert first is second


def test_usage_graph_reflects_the_scanned_examples(engine):
    graph = engine.graph
    assert graph.get("Figure", {}).get("Image") == 1


# ---------------------------------------------------------------------
# near / personalized pagerank
# ---------------------------------------------------------------------


def test_near_concentrates_raw_importance_on_the_seed_itself(engine):
    # personalized_pagerank's restart mass concentrates ON the seed
    # each iteration (see arklight/search/graph.py) -- so `near=X`
    # should raise X's *own* raw importance relative to plain, uniform-
    # restart PageRank, not its neighbors'. Checked pre-normalization
    # (Stage 5 normalizes structural score to 1.0 for the top candidate
    # in any candidate set, which would mask this at the RankedResult
    # level).
    plain_importance = engine._importance(None)
    biased_importance = engine._importance("Figure")
    assert biased_importance["Figure"] > plain_importance["Figure"]


def test_search_with_near_still_surfaces_the_biased_symbol(engine):
    results = engine.search("Image", near="Figure")
    assert any(r.name == "Image" for r in results)


def test_search_with_unknown_near_raises_search_engine_error(engine):
    with pytest.raises(SearchEngineError):
        engine.search("Picture", near="TotallyUnknownSymbol")


# ---------------------------------------------------------------------
# accept() / usage feedback + cache invalidation
# ---------------------------------------------------------------------


def test_accept_updates_future_usage_signal(engine):
    before = {r.name: r for r in engine.search("Text", now=1_000.0)}
    assert before["Text"].signals["usage"] == 0.0

    engine.accept("Text")

    after = {r.name: r for r in engine.search("Text", now=1_000.0)}
    assert after["Text"].signals["usage"] > 0.0


def test_repeated_identical_search_hits_the_cache(engine):
    first = engine.search("Picture", now=1_000.0)
    second = engine.search("Picture", now=1_000.0)
    assert first == second
    info = engine._cached_search.cache_info()
    assert info.hits >= 1


def test_accept_clears_the_cache(engine):
    engine.search("Text", now=1_000.0)
    info_before = engine._cached_search.cache_info()
    assert info_before.currsize >= 1

    engine.accept("Text")

    info_after = engine._cached_search.cache_info()
    assert info_after.currsize == 0


# ---------------------------------------------------------------------
# stats connection lifecycle
# ---------------------------------------------------------------------


def test_stats_connection_is_lazy_and_reused(engine):
    assert engine._stats_conn is None
    conn_first = engine.stats
    conn_second = engine.stats
    assert conn_first is conn_second


def test_close_releases_the_stats_connection(tmp_path):
    roots = _write_usage_example(tmp_path)
    eng = SearchEngine(roots=roots, db_path=tmp_path / "search.sqlite3")
    eng.search("Picture")  # opens the stats connection
    assert eng._stats_conn is not None
    eng.close()
    assert eng._stats_conn is None


# ---------------------------------------------------------------------
# default_engine() singleton
# ---------------------------------------------------------------------


def test_default_engine_returns_the_same_instance():
    first = default_engine()
    second = default_engine()
    assert first is second
