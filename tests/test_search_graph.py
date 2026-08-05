import math

import pytest

from arklight.ir.schema import SCHEMA
from arklight.search.graph import build_usage_graph, pagerank, personalized_pagerank


# ---------------------------------------------------------------------
# build_usage_graph
# ---------------------------------------------------------------------


def test_build_usage_graph_finds_real_nesting_in_this_checkout():
    # Grounded in the repo's actual examples/tests -- Container(Link(...))
    # and Container(Text(...)) both appear for real (e.g. the shared nav
    # bar in examples/hello_site/site.py), so this must not be empty.
    graph = build_usage_graph(set(SCHEMA))
    assert "Container" in graph
    assert graph["Container"].get("Link", 0) >= 1
    assert graph["Container"].get("Text", 0) >= 1


def test_build_usage_graph_only_records_known_names():
    graph = build_usage_graph(set(SCHEMA))
    for parent, children in graph.items():
        assert parent in SCHEMA
        for child in children:
            assert child in SCHEMA


def test_build_usage_graph_edge_weights_are_positive_ints():
    graph = build_usage_graph(set(SCHEMA))
    for children in graph.values():
        for weight in children.values():
            assert isinstance(weight, int)
            assert weight > 0


def test_build_usage_graph_is_deterministic_across_calls():
    first = build_usage_graph(set(SCHEMA))
    second = build_usage_graph(set(SCHEMA))
    assert first == second


def test_build_usage_graph_scoped_to_tmp_dir_only_sees_given_files(tmp_path):
    module = tmp_path / "site.py"
    module.write_text(
        "from arklight import Container, Text, Button\n"
        "Container(Text('a'), Button('b'), Container(Text('c')))\n"
    )
    graph = build_usage_graph({"Container", "Text", "Button"}, roots=[tmp_path])
    assert graph == {
        "Container": {"Text": 2, "Button": 1, "Container": 1},
    }


def test_build_usage_graph_skips_unparseable_files(tmp_path):
    (tmp_path / "broken.py").write_text("def f(:\n")
    (tmp_path / "fine.py").write_text("from arklight import Text\nText('ok')\n")
    graph = build_usage_graph({"Text"}, roots=[tmp_path])
    # Must not raise, and must still process the valid file.
    assert graph == {}


def test_build_usage_graph_missing_root_is_ignored(tmp_path):
    missing = tmp_path / "does_not_exist"
    graph = build_usage_graph(set(SCHEMA), roots=[missing])
    assert graph == {}


# ---------------------------------------------------------------------
# pagerank
# ---------------------------------------------------------------------


def test_pagerank_empty_graph_returns_empty_dict():
    assert pagerank({}) == {}


def test_pagerank_two_node_symmetric_cycle_converges_to_equal_split():
    graph = {"A": {"B": 1}, "B": {"A": 1}}
    scores = pagerank(graph, iterations=100)
    assert scores["A"] == pytest.approx(scores["B"], abs=1e-9)
    assert scores["A"] == pytest.approx(0.5, abs=1e-6)


def test_pagerank_scores_sum_to_approximately_one():
    graph = {"A": {"B": 1, "C": 1}, "B": {"C": 1}, "C": {"A": 1}}
    scores = pagerank(graph, iterations=100)
    assert sum(scores.values()) == pytest.approx(1.0, abs=1e-6)


def test_pagerank_node_with_more_incoming_weight_ranks_higher():
    # Everyone points to "Popular"; it should end up ranked above any
    # single one of the nodes pointing to it.
    graph = {
        "A": {"Popular": 1},
        "B": {"Popular": 1},
        "C": {"Popular": 1},
        "Popular": {"A": 1},
    }
    scores = pagerank(graph, iterations=100)
    assert scores["Popular"] > scores["A"]
    assert scores["Popular"] > scores["B"]
    assert scores["Popular"] > scores["C"]


def test_pagerank_dangling_node_does_not_crash_and_conserves_mass():
    # "Leaf" has no outgoing edges at all.
    graph = {"A": {"Leaf": 1}}
    scores = pagerank(graph, iterations=50)
    assert set(scores) == {"A", "Leaf"}
    assert sum(scores.values()) == pytest.approx(1.0, abs=1e-6)


def test_pagerank_is_bit_for_bit_deterministic_across_calls():
    graph = {"A": {"B": 3, "C": 1}, "B": {"C": 2}, "C": {"A": 1, "B": 1}}
    first = pagerank(graph, iterations=40)
    second = pagerank(graph, iterations=40)
    assert first == second  # exact equality, not approx -- same floats every time


def test_pagerank_on_real_component_graph_does_not_crash():
    graph = build_usage_graph(set(SCHEMA))
    scores = pagerank(graph)
    assert set(scores) <= set(SCHEMA)
    assert all(math.isfinite(v) for v in scores.values())


# ---------------------------------------------------------------------
# personalized_pagerank
# ---------------------------------------------------------------------


def test_personalized_pagerank_unknown_seed_raises():
    graph = {"A": {"B": 1}}
    with pytest.raises(ValueError):
        personalized_pagerank(graph, "NotInGraph")


def test_personalized_pagerank_boosts_seed_relative_to_plain_pagerank():
    graph = {"A": {"B": 1}, "B": {"C": 1}, "C": {"A": 1}}
    plain = pagerank(graph, iterations=100)
    personalized = personalized_pagerank(graph, "C", iterations=100)
    assert personalized["C"] > plain["C"]


def test_personalized_pagerank_scores_sum_to_approximately_one():
    graph = {"A": {"B": 1}, "B": {"C": 1}, "C": {"A": 1}}
    scores = personalized_pagerank(graph, "A", iterations=100)
    assert sum(scores.values()) == pytest.approx(1.0, abs=1e-6)
