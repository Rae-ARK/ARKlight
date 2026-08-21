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

from arklight.cli import cctv, live_streaming as ls


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


# --------------------------------------------------------------------
# --channel -- the unified CLI surface for what used to be the
# separate `arklight cctv` subcommand (see test_cctv.py for the
# state/hub/backend/page-selection building blocks this drives).
# --------------------------------------------------------------------


def test_add_subparser_channel_defaults_to_disabled():
    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    ls.add_subparser(subparsers)

    args = parser.parse_args(["live-streaming", "--subscribe", "site.py"])
    assert args.channel is None
    assert args.route is None


def test_add_subparser_bare_channel_is_const_zero():
    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    ls.add_subparser(subparsers)

    args = parser.parse_args(["live-streaming", "--subscribe", "site.py", "--channel"])
    assert args.channel == 0


def test_add_subparser_channel_accepts_explicit_port():
    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    ls.add_subparser(subparsers)

    args = parser.parse_args(
        ["live-streaming", "--subscribe", "site.py", "--channel", "2172", "--route", "/about"]
    )
    assert args.channel == 2172
    assert args.route == "/about"


def test_bind_channel_server_explicit_port_fails_loud_on_collision():
    handler_cls = cctv._make_handler(cctv._State({}), cctv._SSEHub())
    blocker = ls._bind_channel_server(handler_cls, "127.0.0.1", 0)
    try:
        port = blocker.server_address[1]
        with pytest.raises(OSError, match="--channel"):
            ls._bind_channel_server(handler_cls, "127.0.0.1", port)
    finally:
        blocker.server_close()


def test_bind_channel_server_bare_flag_gets_a_free_port():
    handler_cls = cctv._make_handler(cctv._State({}), cctv._SSEHub())
    server = ls._bind_channel_server(handler_cls, "127.0.0.1", 0)
    try:
        # Port 0 asks the OS for any free port -- confirm we got a real,
        # concrete one back rather than the literal sentinel.
        assert server.server_address[1] != 0
    finally:
        server.server_close()


def test_rebuild_returns_none_on_compile_error(tmp_path, monkeypatch):
    from arklight.compiler.pipeline import CompileError

    def _fake_build(*_args, **_kwargs):
        raise CompileError("boom")

    monkeypatch.setattr(ls, "build", _fake_build)
    result = ls._rebuild(tmp_path / "site.py", tmp_path / "ARK", [])
    assert result is None
