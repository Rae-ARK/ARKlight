"""
Regression tests for `arklight.cli.live_streaming`.

Deliberately unit-level rather than spinning up the actual server/watch
loop in every test (that's covered by manual end-to-end verification --
see CHANGELOG) -- these lock the pieces most likely to silently break:
reload-script injection, the registry file's read/write/prune
lifecycle, and session lookup/disambiguation.
"""

from __future__ import annotations

import json

import pytest

from arklight.cli import live_streaming as ls


class _FakeIR:
    pass


def test_live_reload_backend_injects_script_before_closing_body():
    backend = ls._LiveReloadBackend()
    out = backend.postprocess({"index.html": "<html><body>hi</body></html>"})
    assert ls._CLIENT_JS_PATH in out["index.html"]
    assert out["index.html"].index(ls._CLIENT_JS_PATH) < out["index.html"].index("</html>")


def test_live_reload_backend_appends_if_no_closing_body_tag():
    backend = ls._LiveReloadBackend()
    out = backend.postprocess({"index.html": "<html>no body tag</html>"})
    assert out["index.html"].endswith(f'<script src="{ls._CLIENT_JS_PATH}"></script>')


def test_live_reload_backend_leaves_non_html_files_untouched():
    backend = ls._LiveReloadBackend()
    out = backend.postprocess({"styles.css": "body { color: red; }"})
    assert out["styles.css"] == "body { color: red; }"


def test_live_reload_backend_render_contributes_no_files():
    backend = ls._LiveReloadBackend()
    assert backend.render(_FakeIR()) == {}


def test_registry_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "_REGISTRY_DIR", tmp_path / "live_streaming")
    monkeypatch.setattr(ls, "_REGISTRY_PATH", tmp_path / "live_streaming" / "registry.json")

    assert ls._read_registry() == {}

    registry = {"/tmp/site.py": {"pid": 12345, "host": "127.0.0.1", "port": 8347}}
    ls._write_registry(registry)
    assert ls._read_registry() == registry


def test_read_registry_survives_corrupt_json(tmp_path, monkeypatch):
    reg_dir = tmp_path / "live_streaming"
    reg_dir.mkdir()
    reg_path = reg_dir / "registry.json"
    reg_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(ls, "_REGISTRY_DIR", reg_dir)
    monkeypatch.setattr(ls, "_REGISTRY_PATH", reg_path)

    assert ls._read_registry() == {}


def test_prune_dead_sessions_removes_unreachable_pids(monkeypatch):
    # PID 1 is conventionally init/launchd and always alive; a made-up
    # very large PID is (barring astronomical bad luck) not.
    registry = {"alive": {"pid": 1}, "dead": {"pid": 999_999_999}}
    removed = ls._prune_dead_sessions(registry)
    assert removed is True
    assert "alive" in registry
    assert "dead" not in registry


def test_find_session_by_explicit_entry_path(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "_REGISTRY_DIR", tmp_path)
    monkeypatch.setattr(ls, "_REGISTRY_PATH", tmp_path / "registry.json")
    entry = tmp_path / "site.py"
    entry.write_text("", encoding="utf-8")
    key = ls._entry_key(entry)
    ls._write_registry({key: {"pid": 1, "entry": str(entry)}})

    found = ls._find_session(entry)
    assert found is not None
    assert found[0] == key


def test_find_session_disambiguates_only_when_exactly_one(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "_REGISTRY_DIR", tmp_path)
    monkeypatch.setattr(ls, "_REGISTRY_PATH", tmp_path / "registry.json")

    # Zero sessions -> None regardless.
    ls._write_registry({})
    assert ls._find_session(None) is None

    # Exactly one -> resolvable without an explicit path.
    ls._write_registry({"/a/site.py": {"pid": 1, "entry": "/a/site.py"}})
    found = ls._find_session(None)
    assert found is not None
    assert found[0] == "/a/site.py"

    # More than one -> None; caller must disambiguate explicitly.
    ls._write_registry(
        {
            "/a/site.py": {"pid": 1, "entry": "/a/site.py"},
            "/b/site.py": {"pid": 1, "entry": "/b/site.py"},
        }
    )
    assert ls._find_session(None) is None


def test_changed_path_detects_modified_file():
    before = {"a.py": 1.0, "b.py": 2.0}
    after = {"a.py": 1.0, "b.py": 3.0}
    assert ls._changed_path(before, after) == "b.py"


def test_changed_path_detects_deleted_file():
    before = {"a.py": 1.0}
    after = {}
    assert ls._changed_path(before, after) == "a.py"


def test_changed_path_none_when_unchanged():
    snapshot = {"a.py": 1.0}
    assert ls._changed_path(snapshot, dict(snapshot)) is None
