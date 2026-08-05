import sqlite3

import pytest

from arklight.search import stats


# ---------------------------------------------------------------------
# default_db_path
# ---------------------------------------------------------------------


def test_default_db_path_respects_arklight_search_db_env_var(monkeypatch, tmp_path):
    target = tmp_path / "custom" / "search.sqlite3"
    monkeypatch.setenv("ARKLIGHT_SEARCH_DB", str(target))
    assert stats.default_db_path() == target


def test_default_db_path_respects_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.delenv("ARKLIGHT_SEARCH_DB", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert stats.default_db_path() == tmp_path / "arklight" / "search.sqlite3"


# ---------------------------------------------------------------------
# open_store: lazy creation, not install-time creation
# ---------------------------------------------------------------------


def test_open_store_creates_file_and_parent_dirs_on_first_use(tmp_path):
    db_path = tmp_path / "nested" / "does" / "not" / "exist" / "search.sqlite3"
    assert not db_path.exists()

    conn = stats.open_store(db_path)
    conn.close()

    assert db_path.exists()


def test_open_store_stamps_current_schema_version_on_fresh_db(tmp_path):
    db_path = tmp_path / "search.sqlite3"
    conn = stats.open_store(db_path)
    version = stats._read_schema_version(conn)
    conn.close()
    assert version == stats.SCHEMA_VERSION


def test_open_store_default_reuses_existing_data_without_any_flag(tmp_path):
    db_path = tmp_path / "search.sqlite3"

    conn = stats.open_store(db_path)
    stats.record_acceptance(conn, "Button", now=1000.0)
    conn.close()

    # Re-open with no special flag -- this is the "default behavior is
    # reuse-with-auto-migration, not reuse-behind-a-flag" decision.
    conn2 = stats.open_store(db_path)
    assert stats.get_usage(conn2, "Button") == (1, 1000.0)
    conn2.close()


def test_open_store_force_rebuild_wipes_existing_data(tmp_path):
    db_path = tmp_path / "search.sqlite3"

    conn = stats.open_store(db_path)
    stats.record_acceptance(conn, "Button", now=1000.0)
    conn.close()

    conn2 = stats.open_store(db_path, force_rebuild=True)
    assert stats.get_usage(conn2, "Button") is None
    conn2.close()


def test_open_store_auto_rebuilds_on_unknown_schema_version(tmp_path, capsys):
    db_path = tmp_path / "search.sqlite3"

    conn = stats.open_store(db_path)
    stats.record_acceptance(conn, "Button", now=1000.0)
    conn.execute(
        "UPDATE schema_meta SET value = '999' WHERE key = 'schema_version'"
    )
    conn.commit()
    conn.close()

    # No flag passed -- must not raise, must recover on its own.
    conn2 = stats.open_store(db_path)
    assert stats._read_schema_version(conn2) == stats.SCHEMA_VERSION
    assert stats.get_usage(conn2, "Button") is None
    conn2.close()

    assert "rebuilding it fresh" in capsys.readouterr().err


# ---------------------------------------------------------------------
# record_acceptance / get_usage
# ---------------------------------------------------------------------


def test_get_usage_returns_none_for_unknown_symbol(tmp_path):
    conn = stats.open_store(tmp_path / "search.sqlite3")
    assert stats.get_usage(conn, "NeverSeen") is None
    conn.close()


def test_record_acceptance_increments_count_on_repeat_calls(tmp_path):
    conn = stats.open_store(tmp_path / "search.sqlite3")
    stats.record_acceptance(conn, "Button", now=1.0)
    stats.record_acceptance(conn, "Button", now=2.0)
    stats.record_acceptance(conn, "Button", now=3.0)

    count, last_seen = stats.get_usage(conn, "Button")
    assert count == 3
    assert last_seen == 3.0
    conn.close()


def test_record_acceptance_is_isolated_per_symbol(tmp_path):
    conn = stats.open_store(tmp_path / "search.sqlite3")
    stats.record_acceptance(conn, "Button", now=1.0)
    stats.record_acceptance(conn, "Text", now=1.0)
    stats.record_acceptance(conn, "Text", now=2.0)

    assert stats.get_usage(conn, "Button")[0] == 1
    assert stats.get_usage(conn, "Text")[0] == 2
    conn.close()


# ---------------------------------------------------------------------
# usage_score
# ---------------------------------------------------------------------


def test_usage_score_is_zero_for_unseen_symbol(tmp_path):
    conn = stats.open_store(tmp_path / "search.sqlite3")
    assert stats.usage_score(conn, "NeverSeen", now=0.0) == 0.0
    conn.close()


def test_usage_score_is_bounded_between_zero_and_one(tmp_path):
    conn = stats.open_store(tmp_path / "search.sqlite3")
    for _ in range(50):
        stats.record_acceptance(conn, "Button", now=1000.0)
    score = stats.usage_score(conn, "Button", now=1000.0)
    assert 0.0 <= score < 1.0
    conn.close()


def test_usage_score_decays_with_age(tmp_path):
    conn = stats.open_store(tmp_path / "search.sqlite3")
    stats.record_acceptance(conn, "Button", now=0.0)

    fresh = stats.usage_score(conn, "Button", now=0.0, half_life_days=30.0)
    one_half_life_later = stats.usage_score(
        conn, "Button", now=30.0 * 86400.0, half_life_days=30.0
    )
    much_later = stats.usage_score(
        conn, "Button", now=365.0 * 86400.0, half_life_days=30.0
    )

    assert fresh > one_half_life_later > much_later


def test_usage_score_increases_with_more_acceptances_at_same_time(tmp_path):
    conn = stats.open_store(tmp_path / "search.sqlite3")
    stats.record_acceptance(conn, "Rare", now=1000.0)
    for _ in range(10):
        stats.record_acceptance(conn, "Common", now=1000.0)

    assert stats.usage_score(conn, "Common", now=1000.0) > stats.usage_score(
        conn, "Rare", now=1000.0
    )
    conn.close()


def test_usage_score_is_deterministic_for_fixed_now(tmp_path):
    conn = stats.open_store(tmp_path / "search.sqlite3")
    stats.record_acceptance(conn, "Button", now=1000.0)

    first = stats.usage_score(conn, "Button", now=2000.0)
    second = stats.usage_score(conn, "Button", now=2000.0)
    assert first == second
    conn.close()
