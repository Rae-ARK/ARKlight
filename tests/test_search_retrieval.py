from arklight.search.knowledge import build_knowledge_base
from arklight.search.retrieval import retrieve_candidates


def test_empty_query_returns_no_candidates():
    kb = build_knowledge_base()
    assert retrieve_candidates("", kb) == set()


def test_exact_match_case_insensitive_is_a_candidate():
    kb = build_knowledge_base()
    candidates = retrieve_candidates("container", kb)
    assert "Container" in candidates


def test_prefix_match_is_a_candidate():
    kb = build_knowledge_base()
    candidates = retrieve_candidates("But", kb)
    assert "Button" in candidates


def test_substring_match_is_a_candidate():
    kb = build_knowledge_base()
    candidates = retrieve_candidates("Row", kb)
    assert "TableRow" in candidates


def test_token_overlap_match_is_a_candidate():
    kb = build_knowledge_base()
    candidates = retrieve_candidates("row table", kb)
    assert "TableRow" in candidates


def test_fuzzy_typo_is_a_candidate():
    kb = build_knowledge_base()
    candidates = retrieve_candidates("Buttn", kb)
    assert "Button" in candidates


def test_completely_unrelated_query_yields_no_or_few_candidates():
    kb = build_knowledge_base()
    candidates = retrieve_candidates("qzxjklw_totally_unrelated", kb)
    assert "Button" not in candidates
    assert "Container" not in candidates


def test_retrieve_candidates_only_returns_known_names():
    kb = build_knowledge_base()
    candidates = retrieve_candidates("Ta", kb)
    assert candidates <= set(kb)
