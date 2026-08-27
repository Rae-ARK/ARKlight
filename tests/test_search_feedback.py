import textwrap

import pytest

from arklight.compiler.pipeline import CompileError, compile_site_file
from arklight.search.engine import SearchEngine
from arklight.search.feedback import (
    parse_undefined_component_name,
    parse_unknown_component_type,
    record_name_error_feedback,
    record_validation_feedback,
)
from arklight.search.stats import is_known_confusion


# ---------------------------------------------------------------------
# parse_unknown_component_type -- the ValidationError shape
# ---------------------------------------------------------------------


def test_parse_unknown_component_type_extracts_the_typo():
    message = (
        "Unknown component type 'Headingg' at root.0. "
        "Known component types are: Article, Aside, Button."
    )
    assert parse_unknown_component_type(message) == "Headingg"


def test_parse_unknown_component_type_returns_none_for_other_validation_errors():
    message = "'Heading' at root.0 is missing required prop 'text'."
    assert parse_unknown_component_type(message) is None


def test_parse_unknown_component_type_handles_quotes_in_the_name():
    message = "Unknown component type 'Head\\'ing' at root.0. Known component types are: X."
    assert parse_unknown_component_type(message) == "Head'ing"


# ---------------------------------------------------------------------
# parse_undefined_component_name -- the real, live NameError shape
# ---------------------------------------------------------------------


def test_parse_undefined_component_name_extracts_the_typo():
    assert parse_undefined_component_name("name 'Headingg' is not defined") == "Headingg"


def test_parse_undefined_component_name_returns_none_for_unrelated_messages():
    assert parse_undefined_component_name("division by zero") is None
    assert parse_undefined_component_name("'NoneType' object is not callable") is None


def test_parse_undefined_component_name_rejects_dotted_names():
    # Attribute-access typos (`foo.bar`) raise AttributeError, not
    # NameError, and aren't a component-name typo in the same sense --
    # this parser only recognizes the bare-identifier NameError shape.
    assert parse_undefined_component_name("name 'foo.bar' is not defined") is None


# ---------------------------------------------------------------------
# record_validation_feedback / record_name_error_feedback
# ---------------------------------------------------------------------


def _write_usage_example(tmp_path):
    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / "site.py").write_text(
        textwrap.dedent(
            """
            from arklight import Heading, Text

            def page():
                return Heading(Text("hi"), level=1)
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


def test_record_validation_feedback_records_a_confusion(engine):
    message = (
        "Unknown component type 'Headingg' at root.0. "
        "Known component types are: Heading, Text."
    )
    record_validation_feedback(message, engine)
    assert is_known_confusion(engine.stats, "Headingg", "Heading")


def test_record_validation_feedback_ignores_unrelated_errors(engine):
    record_validation_feedback("'Heading' at root.0 is missing required prop 'text'.", engine)
    assert not is_known_confusion(engine.stats, "Heading", "Heading")


def test_record_name_error_feedback_records_a_confusion(engine):
    record_name_error_feedback("name 'Headingg' is not defined", engine)
    assert is_known_confusion(engine.stats, "Headingg", "Heading")


def test_record_name_error_feedback_ignores_unrelated_errors(engine):
    record_name_error_feedback("division by zero", engine)
    # No candidate typo extracted, so nothing should be recorded for
    # any name.
    assert not is_known_confusion(engine.stats, "Headingg", "Heading")


def test_record_name_error_feedback_records_nothing_without_a_candidate(engine):
    # A "typo" with no plausible suggestion at all shouldn't record a
    # guess -- same "no candidate, no record" rule as the
    # ValidationError path.
    record_name_error_feedback("name 'zzz_totally_unrelated_zzz' is not defined", engine)
    row = engine.stats.execute("SELECT 1 FROM confusions LIMIT 1").fetchone()
    assert row is None


# ---------------------------------------------------------------------
# End-to-end: a real typo'd build now actually records the confusion
# ---------------------------------------------------------------------


def test_a_real_component_typo_build_records_a_confusion(tmp_path, monkeypatch):
    # This is the exact repro from the bug report: scaffold a site,
    # typo `Heading` as `Headingg`, build it, and confirm the
    # feedback loop actually fires -- not just in theory.
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "site.py").write_text(
        textwrap.dedent(
            """
            from arklight import *

            site = Site()

            @site.page("/")
            def home():
                return Page(Headingg(Text("hi"), level=1))
            """
        )
    )

    db_path = tmp_path / "search.sqlite3"
    monkeypatch.setattr(
        "arklight.compiler.pipeline.default_engine",
        lambda: SearchEngine(roots=[tmp_path / "examples"], db_path=db_path),
    )

    with pytest.raises(CompileError, match="Headingg"):
        compile_site_file(site_dir / "site.py")

    check_engine = SearchEngine(db_path=db_path)
    try:
        assert is_known_confusion(check_engine.stats, "Headingg", "Heading")
    finally:
        check_engine.close()
