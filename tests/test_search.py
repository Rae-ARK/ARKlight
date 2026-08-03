from arklight.cli.search import search_component
from arklight.ir.schema import SCHEMA


def test_search_exact_match_for_every_schema_entry():
    # Every real component name must resolve without falling back to
    # the "not found" / suggestion path.
    for name in SCHEMA:
        result = search_component(name)
        assert result.startswith(name)
        assert "No component named" not in result


def test_search_reports_no_children_when_children_disallowed():
    result = search_component("Image")
    assert "allows children: no" in result


def test_search_reports_required_props():
    result = search_component("Image")
    assert "src" in result


def test_search_reports_none_for_no_required_props():
    result = search_component("Container")
    assert "(none)" in result


def test_search_unknown_name_returns_suggestions():
    result = search_component("Butto")
    assert "No component named 'Butto' found" in result
    assert "Button" in result


def test_search_completely_unrelated_query_has_no_suggestions():
    result = search_component("qzxjklw_totally_unrelated")
    assert "nothing close enough to suggest" in result
