"""
Regression tests for `arklight.cli.cctv`.

Deliberately unit-level, same philosophy as test_live_streaming.py:
these lock the pieces most likely to silently break (state merge/bump
semantics, SSE broadcast + one-way field exclusion, page selection,
port-binding fallback behavior, CLI wiring) rather than spinning up a
real server/socket in every test -- that's covered by manual
end-to-end verification.
"""

from __future__ import annotations

import pytest

from arklight.cli import cctv
from arklight.ir.build import IRPage, IRNode, WebsiteIR


# --------------------------------------------------------------------
# _State
# --------------------------------------------------------------------


def test_state_snapshot_is_a_copy_not_a_live_view():
    state = cctv._State({"count": 0})
    snap = state.snapshot()
    snap["count"] = 999
    assert state.snapshot()["count"] == 0


def test_state_merge_returns_only_changed_keys():
    state = cctv._State({"count": 0, "name": "a"})
    changed = state.merge({"count": 0, "name": "b"})
    assert changed == {"name": "b"}
    assert state.snapshot() == {"count": 0, "name": "b"}


def test_state_merge_adds_new_keys():
    state = cctv._State({})
    changed = state.merge({"count": 1})
    assert changed == {"count": 1}


def test_state_merge_no_op_returns_empty_dict():
    state = cctv._State({"count": 5})
    assert state.merge({"count": 5}) == {}


def test_state_bump_adds_to_numeric_field():
    state = cctv._State({"count": 3})
    changed = state.bump("count", 2)
    assert changed == {"count": 5}
    assert state.snapshot()["count"] == 5


def test_state_bump_defaults_missing_field_to_zero():
    state = cctv._State({})
    changed = state.bump("count", 1)
    assert changed == {"count": 1}


def test_state_bump_rejects_non_numeric_field():
    state = cctv._State({"name": "abc"})
    with pytest.raises(TypeError):
        state.bump("name", 1)


def test_state_bump_rejects_bool_field():
    # bool is technically an int subclass in Python -- explicitly excluded
    # since "bumping" a flag field is almost certainly a mistake, not intent.
    state = cctv._State({"flag": True})
    with pytest.raises(TypeError):
        state.bump("flag", 1)


# --------------------------------------------------------------------
# _SSEHub
# --------------------------------------------------------------------


def test_hub_broadcast_state_reaches_all_state_subscribers():
    hub = cctv._SSEHub()
    sub_a = hub.subscribe("state", "a")
    sub_b = hub.subscribe("state", "b")
    notified = hub.broadcast_state({"count": 1})
    assert notified == 2
    assert sub_a.queue.get_nowait() == ("state", {"count": 1})
    assert sub_b.queue.get_nowait() == ("state", {"count": 1})


def test_hub_broadcast_fragment_skips_empty_after_exclusion():
    hub = cctv._SSEHub()
    sub = hub.subscribe("fragment", "a")
    hub.exclude_fields("a", ["count"])
    notified = hub.broadcast_fragment({"count": 1})
    assert notified == 0
    assert sub.queue.empty()


def test_hub_broadcast_fragment_delivers_unexcluded_fields():
    hub = cctv._SSEHub()
    sub = hub.subscribe("fragment", "a")
    hub.exclude_fields("a", ["count"])
    notified = hub.broadcast_fragment({"count": 1, "name": "x"})
    assert notified == 1
    assert sub.queue.get_nowait() == ("fragment", {"name": "x"})


def test_hub_exclude_fields_is_one_way():
    hub = cctv._SSEHub()
    hub.subscribe("fragment", "a")
    hub.exclude_fields("a", ["count"])
    hub.exclude_fields("a", [])  # no-op call shouldn't un-exclude anything
    notified = hub.broadcast_fragment({"count": 1})
    assert notified == 0


def test_hub_exclude_fields_returns_false_for_unknown_client():
    hub = cctv._SSEHub()
    assert hub.exclude_fields("nope", ["count"]) is False


def test_hub_unsubscribe_stops_further_broadcasts():
    hub = cctv._SSEHub()
    sub = hub.subscribe("state", "a")
    hub.unsubscribe("state", "a")
    notified = hub.broadcast_state({"count": 1})
    assert notified == 0
    assert sub.queue.empty()


def test_hub_subscriber_count():
    hub = cctv._SSEHub()
    assert hub.subscriber_count("state") == 0
    hub.subscribe("state", "a")
    hub.subscribe("state", "b")
    assert hub.subscriber_count("state") == 2


# --------------------------------------------------------------------
# select_page -- single-root scaffold (CCTV-BACKEND-PROPOSAL.md SS6)
# --------------------------------------------------------------------


def _fake_ir(*routes: str) -> WebsiteIR:
    pages = [IRPage(route=r, root=IRNode(type="Page"), state={"count": 0}) for r in routes]
    return WebsiteIR(site_name="test", pages=pages)


def test_select_page_defaults_to_first_page():
    ir = _fake_ir("/", "/about")
    page = cctv.select_page(ir, None)
    assert page is not None
    assert page.route == "/"


def test_select_page_finds_explicit_route():
    ir = _fake_ir("/", "/about")
    page = cctv.select_page(ir, "/about")
    assert page is not None
    assert page.route == "/about"


def test_select_page_raises_on_unknown_route():
    ir = _fake_ir("/", "/about")
    with pytest.raises(ValueError, match="no page with route"):
        cctv.select_page(ir, "/missing")


def test_select_page_returns_none_for_empty_site():
    ir = WebsiteIR(site_name="empty", pages=[])
    assert cctv.select_page(ir, None) is None


# --------------------------------------------------------------------
# _CCTVBackend -- render() contract (Backend.render never touches disk)
# --------------------------------------------------------------------


def test_backend_render_emits_client_js_and_schema():
    ir = _fake_ir("/")
    backend = cctv._CCTVBackend()
    out = backend.render(ir)
    assert cctv._CLIENT_JS_PATH.lstrip("/") in out
    assert "__cctv_schema__.json" in out
    assert "EventSource" in out[cctv._CLIENT_JS_PATH.lstrip("/")]


def test_backend_render_schema_reflects_selected_page_state():
    ir = _fake_ir("/", "/about")
    backend = cctv._CCTVBackend(route="/about")
    out = backend.render(ir)
    assert '"route": "/about"' in out["__cctv_schema__.json"]


def test_backend_render_on_empty_site_still_returns_files():
    ir = WebsiteIR(site_name="empty", pages=[])
    backend = cctv._CCTVBackend()
    out = backend.render(ir)
    assert cctv._CLIENT_JS_PATH.lstrip("/") in out
    assert '"route": null' in out["__cctv_schema__.json"]


# --------------------------------------------------------------------
# Port binding -- SS5's "scan on default, fail-loud on --tune"
# --------------------------------------------------------------------


def test_bind_server_tune_fails_loud_on_collision():
    handler_cls = cctv._make_handler(cctv._State({}), cctv._SSEHub())
    blocker, _ = cctv._bind_server(handler_cls, "127.0.0.1", None)
    try:
        port = blocker.server_address[1]
        with pytest.raises(OSError, match="--tune"):
            cctv._bind_server(handler_cls, "127.0.0.1", port)
    finally:
        blocker.server_close()


def test_bind_server_default_scans_forward_on_collision(monkeypatch):
    handler_cls = cctv._make_handler(cctv._State({}), cctv._SSEHub())
    # Pin the module's default port to a high, unlikely-to-collide-with-
    # anything-real port for this test, then occupy it first so the scan
    # is forced to move to default+1.
    monkeypatch.setattr(cctv, "_DEFAULT_PORT", 41242)
    blocker, _ = cctv._bind_server(handler_cls, "127.0.0.1", 41242)
    try:
        server, bumped = cctv._bind_server(handler_cls, "127.0.0.1", None)
        try:
            assert bumped is True
            assert server.server_address[1] == 41243
        finally:
            server.server_close()
    finally:
        blocker.server_close()


# --------------------------------------------------------------------
# CLI wiring
# --------------------------------------------------------------------


def test_add_subparser_registers_cctv_command():
    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    cctv.add_subparser(subparsers)

    args = parser.parse_args(["cctv", "site.py", "--tune", "9999"])
    assert args.command == "cctv"
    assert args.entry == "site.py"
    assert args.tune == 9999
    assert args.func is cctv._cmd_cctv


def test_add_subparser_default_tune_is_none():
    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    cctv.add_subparser(subparsers)

    args = parser.parse_args(["cctv", "site.py"])
    assert args.tune is None
    assert args.host == cctv._DEFAULT_HOST
    assert args.output == "ARK"


def test_cmd_cctv_fails_cleanly_on_missing_entry(tmp_path, capsys):
    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    cctv.add_subparser(subparsers)
    args = parser.parse_args(["cctv", str(tmp_path / "nope.py")])

    exit_code = cctv._cmd_cctv(args)
    assert exit_code == 1
    assert "no such file" in capsys.readouterr().err
