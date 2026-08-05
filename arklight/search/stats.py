from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path

# Bumped whenever `_SCHEMA_SQL` changes shape. `_open_or_initialize`
# uses this to decide, on every open, whether an existing on-disk
# store can just be reused as-is, needs an in-place migration, or is
# from an incompatible/unknown version and should be rebuilt fresh --
# see DETERMINISTIC_RANKING_PLAN.md, "Stage 10" for why reuse is the
# silent default and rebuilding is the explicit, opt-in path rather
# than the other way around.
SCHEMA_VERSION = 1

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS usage_stats (
    name TEXT PRIMARY KEY,
    count INTEGER NOT NULL,
    last_seen REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Migrations from one schema version to the next, keyed by the
# version being migrated *from*. Empty today (nothing predates
# version 1) -- future stages add entries here instead of redesigning
# the open/reuse logic.
_MIGRATIONS: dict[int, "callable[[sqlite3.Connection], None]"] = {}


def default_db_path() -> Path:
    """Where the store lives when the caller doesn't pick a path.

    Resolution order: `ARKLIGHT_SEARCH_DB` env var (exact path,
    mainly for hermetic tests) -> `XDG_DATA_HOME` -> platform default
    user-data directory. Never inside the installed package itself --
    see the "why not install-time creation" reasoning in
    DETERMINISTIC_RANKING_PLAN.md.
    """
    override = os.environ.get("ARKLIGHT_SEARCH_DB")
    if override:
        return Path(override)

    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        base = Path(xdg)
    elif os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    else:
        base = Path.home() / ".local" / "share"

    return base / "arklight" / "search.sqlite3"


def _read_schema_version(conn: sqlite3.Connection) -> int | None:
    try:
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return int(row[0]) if row is not None else None


def _initialize_fresh(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)
    conn.execute("DELETE FROM usage_stats")
    conn.execute("DELETE FROM schema_meta")
    conn.execute(
        "INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def _open_or_initialize(conn: sqlite3.Connection, *, force_rebuild: bool) -> None:
    conn.executescript(_SCHEMA_SQL)
    conn.commit()

    if force_rebuild:
        _initialize_fresh(conn)
        return

    version = _read_schema_version(conn)

    if version is None:
        # Freshly created file (schema_meta has no row yet) -- normal
        # first-use lazy creation, not an error.
        _initialize_fresh(conn)
        return

    if version == SCHEMA_VERSION:
        return  # silent reuse: the common, default path

    if version < SCHEMA_VERSION and version in _MIGRATIONS:
        _MIGRATIONS[version](conn)
        conn.execute(
            "UPDATE schema_meta SET value = ? WHERE key = 'schema_version'",
            (str(SCHEMA_VERSION),),
        )
        conn.commit()
        return

    # Older-but-unmigratable, or newer/unknown -- can't safely reuse.
    # Rebuild automatically rather than crashing or requiring the
    # user to pass a flag just to get a working store back.
    print(
        f"arklight search: stored index is schema version {version}, "
        f"expected {SCHEMA_VERSION} -- rebuilding it fresh.",
        file=sys.stderr,
    )
    _initialize_fresh(conn)


def open_store(
    db_path: Path | None = None,
    *,
    force_rebuild: bool = False,
) -> sqlite3.Connection:
    """Open (creating on first use if absent) the usage-stats store.

    Default behavior is reuse: an existing, current-version store is
    left exactly as it is. `force_rebuild=True` is the explicit,
    uncommon-case opt-in for wiping it and starting over (wired to a
    CLI flag in a later stage) -- not something the common "just use
    what's already there" path needs to ask for.
    """
    if db_path is None:
        db_path = default_db_path()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    _open_or_initialize(conn, force_rebuild=force_rebuild)
    return conn


def record_acceptance(
    conn: sqlite3.Connection,
    name: str,
    *,
    now: float | None = None,
) -> None:
    """Record that `name` was accepted, incrementing its count and
    stamping recency. The only "learning" this engine does: updating
    deterministic counters, no model, no training."""
    if now is None:
        now = time.time()

    conn.execute(
        """
        INSERT INTO usage_stats (name, count, last_seen)
        VALUES (?, 1, ?)
        ON CONFLICT(name) DO UPDATE SET
            count = count + 1,
            last_seen = excluded.last_seen
        """,
        (name, now),
    )
    conn.commit()


def get_usage(conn: sqlite3.Connection, name: str) -> tuple[int, float] | None:
    """Raw `(count, last_seen_epoch_seconds)` for `name`, or `None`
    if it's never been accepted."""
    row = conn.execute(
        "SELECT count, last_seen FROM usage_stats WHERE name = ?", (name,)
    ).fetchone()
    if row is None:
        return None
    return int(row[0]), float(row[1])


def usage_score(
    conn: sqlite3.Connection,
    name: str,
    *,
    now: float | None = None,
    half_life_days: float = 30.0,
) -> float:
    """Deterministic frequency + exponential recency decay, squashed
    to `[0, 1)`. Zero for a symbol that's never been accepted.
    Monotonically increasing in count, monotonically decreasing in
    age -- explainable by construction, no black box."""
    if now is None:
        now = time.time()

    row = get_usage(conn, name)
    if row is None:
        return 0.0

    count, last_seen = row
    age_days = max(0.0, (now - last_seen) / 86400.0)
    decayed = count * (0.5 ** (age_days / half_life_days))
    return decayed / (decayed + 1.0)
