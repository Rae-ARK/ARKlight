from arklight.search import stats as stats_mod
from arklight.search.knowledge import SymbolFact
from arklight.search.ranking import DEFAULT_WEIGHTS, RankedResult, rank

# ---------------------------------------------------------------------
# fixtures -- small, hand-built, independent of the real SCHEMA/graph
# ---------------------------------------------------------------------


def _knowledge() -> dict[str, SymbolFact]:
    return {
        "Picture": SymbolFact(name="Picture", tokens=("picture",)),
        "PictureFrame": SymbolFact(name="PictureFrame", tokens=("picture", "frame")),
        "TableRow": SymbolFact(name="TableRow", tokens=("table", "row")),
        "Text": SymbolFact(name="Text", tokens=("text",)),
    }


# ---------------------------------------------------------------------
# basic shape / determinism
# ---------------------------------------------------------------------


def test_rank_returns_a_result_per_candidate():
    knowledge = _knowledge()
    results = rank("Picture", {"Picture", "PictureFrame"}, knowledge, {}, None)
    assert {r.name for r in results} == {"Picture", "PictureFrame"}
    assert all(isinstance(r, RankedResult) for r in results)


def test_rank_is_sorted_best_first():
    knowledge = _knowledge()
    results = rank("Picture", set(knowledge), knowledge, {}, None)
    assert results[0].name == "Picture"  # exact match should win
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_rank_output_is_byte_identical_across_repeated_calls():
    knowledge = _knowledge()
    importance = {"Picture": 0.4, "PictureFrame": 0.1}
    first = rank("pic", set(knowledge), knowledge, importance, None, now=1_000.0)
    second = rank("pic", set(knowledge), knowledge, importance, None, now=1_000.0)
    assert first == second


def test_rank_ties_broken_by_name():
    # Two candidates with identical tokens/lexical distance from an
    # empty query and no importance/usage data -- everything zero, so
    # the tiebreak (name, ascending) is the only thing determining order.
    knowledge = {
        "Alpha": SymbolFact(name="Alpha", tokens=("alpha",)),
        "Beta": SymbolFact(name="Beta", tokens=("beta",)),
    }
    results = rank("zzz-no-match-zzz", {"Alpha", "Beta"}, knowledge, {}, None)
    assert [r.name for r in results] == ["Alpha", "Beta"]


def test_rank_empty_candidates_returns_empty_list():
    knowledge = _knowledge()
    assert rank("Picture", set(), knowledge, {}, None) == []


# ---------------------------------------------------------------------
# lexical signal
# ---------------------------------------------------------------------


def test_exact_name_match_scores_higher_than_unrelated_candidate():
    knowledge = _knowledge()
    results = rank("Text", {"Text", "TableRow"}, knowledge, {}, None)
    by_name = {r.name: r for r in results}
    assert by_name["Text"].signals["lexical"] > by_name["TableRow"].signals["lexical"]


def test_token_overlap_helps_multiword_match():
    knowledge = _knowledge()
    results = rank("row table", {"TableRow", "Text"}, knowledge, {}, None)
    by_name = {r.name: r for r in results}
    # "row table" doesn't character-match "TableRow" well, but shares
    # both tokens -- token overlap should still pull it ahead of an
    # unrelated candidate.
    assert by_name["TableRow"].signals["lexical"] > by_name["Text"].signals["lexical"]


def test_missing_knowledge_entry_falls_back_to_tokenizing_the_name():
    # A candidate that Stage 2 surfaced (e.g. via difflib) but that
    # isn't in `knowledge` shouldn't crash -- ranking should still
    # produce a usable (if token-poor) lexical signal for it.
    results = rank("PictureFrame", {"PictureFrame"}, {}, {}, None)
    assert len(results) == 1
    assert results[0].signals["lexical"] > 0.0


# ---------------------------------------------------------------------
# structural signal
# ---------------------------------------------------------------------


def test_structural_importance_is_normalized_within_candidate_set():
    knowledge = _knowledge()
    importance = {"Picture": 0.8, "PictureFrame": 0.4, "Text": 0.0}
    results = rank(
        "zzz-no-lexical-match-zzz",
        {"Picture", "PictureFrame", "Text"},
        knowledge,
        importance,
        None,
    )
    by_name = {r.name: r for r in results}
    assert by_name["Picture"].signals["structural"] == 1.0  # peak of this set
    assert by_name["PictureFrame"].signals["structural"] == 0.5
    assert by_name["Text"].signals["structural"] == 0.0


def test_candidate_absent_from_importance_scores_zero_structural():
    knowledge = _knowledge()
    results = rank("Text", {"Text"}, knowledge, {"SomeOtherComponent": 0.9}, None)
    assert results[0].signals["structural"] == 0.0


def test_all_zero_importance_does_not_divide_by_zero():
    knowledge = _knowledge()
    results = rank("Text", {"Text", "Picture"}, knowledge, {}, None)
    assert all(r.signals["structural"] == 0.0 for r in results)


# ---------------------------------------------------------------------
# usage signal
# ---------------------------------------------------------------------


def test_stats_none_yields_zero_usage_signal():
    knowledge = _knowledge()
    results = rank("Text", {"Text"}, knowledge, {}, None)
    assert results[0].signals["usage"] == 0.0


def test_stats_connection_feeds_real_usage_score(tmp_path):
    knowledge = _knowledge()
    conn = stats_mod.open_store(tmp_path / "search.sqlite3")
    stats_mod.record_acceptance(conn, "Text", now=1_000.0)

    results = rank("Text", {"Text", "Picture"}, knowledge, {}, conn, now=1_000.0)
    by_name = {r.name: r for r in results}

    assert by_name["Text"].signals["usage"] > 0.0
    assert by_name["Picture"].signals["usage"] == 0.0
    conn.close()


# ---------------------------------------------------------------------
# weights
# ---------------------------------------------------------------------


def test_default_weights_sum_to_one():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


def test_custom_weights_are_applied_and_recorded():
    knowledge = _knowledge()
    importance = {"Picture": 1.0}
    custom = {"lexical": 0.0, "structural": 1.0, "usage": 0.0}
    results = rank("zzz", {"Picture", "Text"}, knowledge, importance, None, weights=custom)
    by_name = {r.name: r for r in results}

    # With lexical/usage zeroed out, score should equal the structural
    # signal exactly (weight 1.0 on it, everything else 0.0).
    assert by_name["Picture"].score == by_name["Picture"].signals["structural"]
    assert by_name["Picture"].weights_used == custom


def test_weights_missing_a_key_treated_as_zero_for_that_signal():
    knowledge = _knowledge()
    # Only "lexical" provided -- structural/usage contribute nothing,
    # rather than raising a KeyError.
    results = rank("Text", {"Text"}, knowledge, {"Text": 1.0}, None, weights={"lexical": 1.0})
    assert results[0].score == results[0].signals["lexical"]
