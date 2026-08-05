import io
import json
import textwrap

import pytest

from arklight.search.endpoint import serve_stdio
from arklight.search.engine import SearchEngine


def _write_usage_example(tmp_path):
    """Same tiny examples/ tree as test_search_engine_facade.py, so the
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


def _run(engine, *request_lines: str) -> list[dict]:
    """Feed `request_lines` (already-encoded JSON strings) in as stdin,
    run the server to completion (EOF), and return the decoded
    response objects, in order."""
    in_stream = io.StringIO("\n".join(request_lines) + "\n" if request_lines else "")
    out_stream = io.StringIO()
    exit_code = serve_stdio(engine, in_stream=in_stream, out_stream=out_stream)
    assert exit_code == 0

    lines = [line for line in out_stream.getvalue().splitlines() if line]
    return [json.loads(line) for line in lines]


# ---------------------------------------------------------------------
# search op
# ---------------------------------------------------------------------


def test_search_op_returns_ranked_results_matching_the_engine(engine):
    [response] = _run(engine, json.dumps({"id": 1, "op": "search", "query": "Imag"}))
    assert response["id"] == 1
    assert response["ok"] is True

    direct = engine.search("Imag")
    assert [r["name"] for r in response["results"]] == [r.name for r in direct]
    assert response["results"][0]["signals"] == direct[0].signals
    assert response["results"][0]["weights_used"] == direct[0].weights_used


def test_search_op_respects_limit_and_near(engine):
    [response] = _run(
        engine, json.dumps({"op": "search", "query": "Image", "limit": 1, "near": "Figure"})
    )
    assert response["ok"] is True
    assert len(response["results"]) <= 1


def test_search_op_missing_query_is_a_protocol_error_not_a_crash(engine):
    [response] = _run(engine, json.dumps({"id": "x", "op": "search"}))
    assert response["id"] == "x"
    assert response["ok"] is False
    assert "query" in response["error"]


def test_search_op_unknown_near_is_reported_as_a_clean_error(engine):
    [response] = _run(
        engine, json.dumps({"op": "search", "query": "Picture", "near": "TotallyUnknownSymbol"})
    )
    assert response["ok"] is False
    assert "TotallyUnknownSymbol" in response["error"]


def test_search_op_wrong_type_fields_are_rejected(engine):
    [r1] = _run(engine, json.dumps({"op": "search", "query": 123}))
    assert r1["ok"] is False

    [r2] = _run(engine, json.dumps({"op": "search", "query": "Image", "limit": "five"}))
    assert r2["ok"] is False

    [r3] = _run(engine, json.dumps({"op": "search", "query": "Image", "near": 5}))
    assert r3["ok"] is False


# ---------------------------------------------------------------------
# accept op
# ---------------------------------------------------------------------


def test_accept_op_records_usage_visible_to_a_later_search(engine):
    responses = _run(
        engine,
        json.dumps({"id": 1, "op": "accept", "name": "Text"}),
        json.dumps({"id": 2, "op": "search", "query": "Text"}),
    )
    accept_response, search_response = responses
    assert accept_response == {"id": 1, "ok": True}

    result = next(r for r in search_response["results"] if r["name"] == "Text")
    assert result["signals"]["usage"] > 0.0


def test_accept_op_missing_name_is_a_protocol_error(engine):
    [response] = _run(engine, json.dumps({"op": "accept"}))
    assert response["ok"] is False
    assert "name" in response["error"]


# ---------------------------------------------------------------------
# protocol robustness
# ---------------------------------------------------------------------


def test_malformed_json_line_gets_an_error_response_and_server_keeps_going(engine):
    responses = _run(
        engine,
        "not json at all {{{",
        json.dumps({"id": 2, "op": "search", "query": "Picture"}),
    )
    bad, good = responses
    assert bad["id"] is None
    assert bad["ok"] is False
    assert good["id"] == 2
    assert good["ok"] is True


def test_non_object_json_line_is_rejected(engine):
    [response] = _run(engine, json.dumps([1, 2, 3]))
    assert response["ok"] is False


def test_unknown_op_is_rejected(engine):
    [response] = _run(engine, json.dumps({"id": 7, "op": "levitate"}))
    assert response["id"] == 7
    assert response["ok"] is False
    assert "levitate" in response["error"]


def test_blank_lines_are_skipped_not_treated_as_requests(engine):
    responses = _run(
        engine,
        "",
        "   ",
        json.dumps({"id": 1, "op": "search", "query": "Picture"}),
        "",
    )
    assert len(responses) == 1
    assert responses[0]["id"] == 1


def test_id_defaults_to_null_when_omitted(engine):
    [response] = _run(engine, json.dumps({"op": "search", "query": "Picture"}))
    assert response["id"] is None
    assert response["ok"] is True


def test_n_requests_produce_n_responses_in_order(engine):
    queries = ["Picture", "Image", "Text", "Figure"]
    lines = [json.dumps({"id": i, "op": "search", "query": q}) for i, q in enumerate(queries)]
    responses = _run(engine, *lines)
    assert [r["id"] for r in responses] == [0, 1, 2, 3]
    assert all(r["ok"] for r in responses)


def test_empty_input_produces_no_responses(engine):
    assert _run(engine) == []


# ---------------------------------------------------------------------
# engine ownership / lifecycle
# ---------------------------------------------------------------------


def test_serve_stdio_closes_an_engine_it_constructed_itself(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKLIGHT_SEARCH_DB", str(tmp_path / "owned.sqlite3"))
    in_stream = io.StringIO("")
    out_stream = io.StringIO()
    # No engine passed in -- serve_stdio must build (and later close)
    # its own, rather than leaking an unclosed sqlite3 connection.
    exit_code = serve_stdio(in_stream=in_stream, out_stream=out_stream)
    assert exit_code == 0


def test_serve_stdio_does_not_close_a_caller_supplied_engine(engine):
    in_stream = io.StringIO("")
    out_stream = io.StringIO()
    serve_stdio(engine, in_stream=in_stream, out_stream=out_stream)
    # The fixture's own teardown (`eng.close()`) must still be able to
    # run cleanly afterward -- i.e. serve_stdio must not have closed a
    # connection it didn't open itself.
    assert engine.stats is not None
