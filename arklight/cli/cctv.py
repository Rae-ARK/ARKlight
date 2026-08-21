"""
CCTV -- the state-channel building blocks behind `arklight
live-streaming --channel`.

This used to be its own `arklight cctv` subcommand; it's now folded
into `arklight live-streaming` as an opt-in flag instead of a second
CLI entry point (see `arklight.cli.live_streaming`'s module docstring
for the unified surface: `--channel [PORT]`). The concepts here are
unchanged, only where they're invoked from:

    arklight live-streaming --subscribe site.py --channel        # random free port
    arklight live-streaming --subscribe site.py --channel 2172   # bind exactly 2172

Python port of carklight's `CCTV-BACKEND-PROPOSAL.md` -- the same
concepts (a long-running state object, SSE channels, per-field
fragments, one-way field-exclusion promotion) the C project designed
for `carklight`, ported onto CPython's stdlib instead of raw C
sockets and a hand-rolled HTTP/SSE parser. Same prior art
(`State-Driven-UI-Streaming-Prototype`, Rae-ARK) as the C version;
this is not a wrapper around either the C build or the JS prototype --
a from-scratch Python implementation of the same protocol, using
`http.server`/`socketserver` -- the same building blocks
`arklight.cli.live_streaming` already uses for its own dev server, so
this introduces no new stdlib surface to the project.

This module still isn't `arklight live-streaming`'s own auto-rebuild +
browser-reload server -- it's the second, independent server
`live-streaming --channel` binds *alongside* it. The state object built
here is seeded once from the selected page's declared `State(...)` at
session start and is never reset by a rebuild; it serves that one
page's fields live over SSE to *any* HTTP client -- a Flask app, curl,
a second browser tab -- for the lifetime of the `--subscribe` session.
Two servers, two different jobs, matching the distinction
CCTV-BACKEND-PROPOSAL.md draws in its own SS1/SS2.

Two halves, same split the C proposal calls for (SS2/SS3):

  - `_CCTVBackend` (`Backend` subclass, same contract every other
    backend implements) is the one-shot half: `render()` walks the
    selected page's `IRPage.state` dict and emits `cctv.js` (a small
    SSE client, same "fixed vocabulary" spirit as the JS backend's own
    generated runtime) plus a state-schema descriptor. Registered as
    an *optional* extra backend, the same way
    `live_streaming._LiveReloadBackend` is -- not part of
    `default_backends()`.
  - The actual server (the `_CCTVHTTPServer`/`_make_handler` pair
    below) is a separate, long-running object `live_streaming`'s
    `--channel` handling binds and serves on its own thread --
    never inside a `postprocess()` that's expected to return (the C
    proposal's SS3 makes the same distinction for the same reason: a
    build pipeline stage that never returns blocks every backend
    registered behind it). Port selection (an exact `--channel PORT`
    vs. a random free one for bare `--channel`) is `live_streaming`'s
    job, not this module's -- see `live_streaming._bind_channel_server`.

Routes (mirrors the JS prototype's `index.js` route list, and the C
proposal's SS4/SS5):

    GET  /state/stream      SSE: full-state snapshot on every change
    GET  /fragment/stream   SSE: per-field events; ?client_id=... lets
                             a connection later be excluded via
                             POST /fragment/exclude
    GET  /state             legacy poll: current state as JSON
    POST /state             JSON body merged (shallow) into state
    POST /state/bump        {"field": ..., "by": N} -- numeric += N
    POST /fragment/exclude  {"client_id": ..., "fields": [...]} --
                             that connection stops receiving those
                             fields' fragment events (one-way; there is
                             no un-exclude, matching the prototype)

CPython embedding, ARKVM.js-style client latency logic, persistence,
auth, and multi-route/site_name support are explicitly out of scope
here too -- same reasoning as CCTV-BACKEND-PROPOSAL.md SS6. This module
also inherits the C proposal's single-root scaffold gap (SS6, "A
route/site_name concept"): one `--channel` session serves exactly one
page's state, selectable with `--route` but defaulting to the site's
first page.
"""

from __future__ import annotations

import http.server
import json
import socketserver
import threading
import time
import uuid
from queue import Empty, Queue
from typing import Any

from arklight.backend.base import Backend
from arklight.ir.build import IRPage, WebsiteIR

_QUEUE_POLL_SECONDS = 1.0

_CLIENT_JS_PATH = "/__arklight_cctv__/client.js"

_CLIENT_JS = """\
// ARKlight CCTV client -- listens on /state/stream, dispatches a
// CustomEvent("arklight:state", { detail: <state> }) on window for
// page code to subscribe to. Deliberately dumb: no DOM writes of its
// own -- ARKVM.js-style field-promotion/latency logic is explicitly
// out of scope for cctv itself (CCTV-BACKEND-PROPOSAL.md \xa76).
(function () {
  var es = new EventSource("/state/stream");
  es.addEventListener("state", function (ev) {
    var state = JSON.parse(ev.data);
    window.dispatchEvent(new CustomEvent("arklight:state", { detail: state }));
  });
})();
"""


# --------------------------------------------------------------------
# State -- mirrors carklight's proposed state.c: one mutable struct,
# one lock, shallow-merge updates. No persistence -- a restart resets
# it, same as both the JS prototype and the C proposal (SS4).
# --------------------------------------------------------------------


class _State:
    def __init__(self, initial: dict[str, Any]) -> None:
        self._lock = threading.Lock()
        self._fields: dict[str, Any] = dict(initial)
        self.updated_at = time.time()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._fields)

    def merge(self, patch: dict[str, Any]) -> dict[str, Any]:
        """Shallow-merge `patch` into state; returns only the keys that
        actually changed value, so callers (broadcast_fragment) don't
        push no-op events for fields set to their existing value."""
        with self._lock:
            changed: dict[str, Any] = {}
            for key, value in patch.items():
                if self._fields.get(key) != value:
                    self._fields[key] = value
                    changed[key] = value
            if changed:
                self.updated_at = time.time()
            return changed

    def bump(self, field: str, by: float) -> dict[str, Any]:
        with self._lock:
            current = self._fields.get(field, 0)
            if not isinstance(current, (int, float)) or isinstance(current, bool):
                raise TypeError(f"cannot bump non-numeric field {field!r} (value: {current!r})")
            new_value = current + by
            self._fields[field] = new_value
            self.updated_at = time.time()
            return {field: new_value}


# --------------------------------------------------------------------
# SSE channel hub -- mirrors carklight's proposed sse.c: tracks open
# subscriber queues per channel, broadcasts state/fragment events, and
# supports the prototype's one-way field-exclusion (a connection
# that's had a field promoted off the bus path stops receiving that
# field's fragment events) as a per-connection set -- the same
# simplification the C proposal calls out as a bitset instead of JS's
# `Map<res, Set<field>>` (SS4).
# --------------------------------------------------------------------


class _Subscriber:
    def __init__(self, client_id: str) -> None:
        self.client_id = client_id
        self.queue: Queue[tuple[str, dict[str, Any]]] = Queue()
        self.excluded_fields: set[str] = set()


class _SSEHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._channels: dict[str, dict[str, _Subscriber]] = {"state": {}, "fragment": {}}

    def subscribe(self, channel: str, client_id: str) -> _Subscriber:
        sub = _Subscriber(client_id)
        with self._lock:
            self._channels[channel][client_id] = sub
        return sub

    def unsubscribe(self, channel: str, client_id: str) -> None:
        with self._lock:
            self._channels[channel].pop(client_id, None)

    def exclude_fields(self, client_id: str, fields: list[str]) -> bool:
        """One-way: adds to the exclusion set, never removes. Applies
        to the `fragment` channel only, matching the prototype's own
        promotion semantics (CCTV-BACKEND-PROPOSAL.md SS4). Returns
        False if `client_id` has no open /fragment/stream connection
        -- the caller (do_POST) turns that into a 404."""
        with self._lock:
            sub = self._channels["fragment"].get(client_id)
            if sub is None:
                return False
            sub.excluded_fields.update(fields)
            return True

    def broadcast_state(self, state: dict[str, Any]) -> int:
        with self._lock:
            subs = list(self._channels["state"].values())
        for sub in subs:
            sub.queue.put(("state", state))
        return len(subs)

    def broadcast_fragment(self, changed: dict[str, Any]) -> int:
        with self._lock:
            subs = list(self._channels["fragment"].values())
        notified = 0
        for sub in subs:
            visible = {k: v for k, v in changed.items() if k not in sub.excluded_fields}
            if visible:
                sub.queue.put(("fragment", visible))
                notified += 1
        return notified

    def subscriber_count(self, channel: str) -> int:
        with self._lock:
            return len(self._channels[channel])


# --------------------------------------------------------------------
# `_CCTVBackend` -- the one-shot `render()` half. See module docstring
# and CCTV-BACKEND-PROPOSAL.md SS2/SS3 for why this is intentionally
# thin: it contributes static scaffolding only, never the server.
# --------------------------------------------------------------------


class _CCTVBackend(Backend):
    name = "cctv"

    def __init__(self, route: str | None = None) -> None:
        self._route = route

    def render(self, ir: WebsiteIR) -> dict[str, str]:
        page = select_page(ir, self._route)
        schema = {
            "route": page.route if page else None,
            "fields": page.state if page else {},
        }
        return {
            _CLIENT_JS_PATH.lstrip("/"): _CLIENT_JS,
            "__cctv_schema__.json": json.dumps(schema, indent=2, sort_keys=True),
        }


def select_page(ir: WebsiteIR, route: str | None) -> IRPage | None:
    """Single-root scaffold (CCTV-BACKEND-PROPOSAL.md SS6): pick one page
    to serve. Explicit `route` must match exactly or this raises,
    rather than silently falling back -- same "honest failure over
    silent wrong behavior" convention `--tune` uses for port binding
    (SS5)."""
    if not ir.pages:
        return None
    if route is None:
        return ir.pages[0]
    for page in ir.pages:
        if page.route == route:
            return page
    known = ", ".join(p.route for p in ir.pages) or "(no pages)"
    raise ValueError(f"cctv: no page with route {route!r} in this site -- known routes: {known}")


# --------------------------------------------------------------------
# HTTP/SSE server
# --------------------------------------------------------------------


class _CCTVHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _make_handler(
    state: _State, hub: _SSEHub
) -> type[http.server.BaseHTTPRequestHandler]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return  # quiet -- the CLI prints its own startup/broadcast lines

        # -- helpers ----------------------------------------------------

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> dict[str, Any] | None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length == 0:
                return {}
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return None
            return data if isinstance(data, dict) else None

        def _query_param(self, name: str) -> str | None:
            if "?" not in self.path:
                return None
            _, _, qs = self.path.partition("?")
            for pair in qs.split("&"):
                key, _, value = pair.partition("=")
                if key == name:
                    return value
            return None

        def _stream(self, channel: str) -> None:
            client_id = self._query_param("client_id") or uuid.uuid4().hex
            sub = hub.subscribe(channel, client_id)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-ARKlight-CCTV-Client-Id", client_id)
            self.end_headers()
            try:
                if channel == "state":
                    frame = f"event: state\ndata: {json.dumps(state.snapshot())}\n\n"
                    self.wfile.write(frame.encode("utf-8"))
                    self.wfile.flush()
                while True:
                    try:
                        event_name, payload = sub.queue.get(timeout=_QUEUE_POLL_SECONDS)
                    except Empty:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                        continue
                    frame = f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"
                    self.wfile.write(frame.encode("utf-8"))
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                hub.unsubscribe(channel, client_id)

        # -- routes -------------------------------------------------------

        def do_GET(self) -> None:  # noqa: N802 -- stdlib method name
            path = self.path.split("?", 1)[0]

            if path == _CLIENT_JS_PATH:
                body = _CLIENT_JS.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "/state/stream":
                self._stream("state")
                return

            if path == "/fragment/stream":
                self._stream("fragment")
                return

            if path == "/state":
                self._send_json(200, state.snapshot())
                return

            self._send_json(404, {"error": f"no such route: GET {path}"})

        def do_POST(self) -> None:  # noqa: N802 -- stdlib method name
            path = self.path.split("?", 1)[0]
            body = self._read_json_body()
            if body is None:
                self._send_json(400, {"error": "request body must be a JSON object"})
                return

            if path == "/state":
                changed = state.merge(body)
                if changed:
                    hub.broadcast_state(state.snapshot())
                    hub.broadcast_fragment(changed)
                self._send_json(200, {"changed": changed})
                return

            if path == "/state/bump":
                field = body.get("field")
                by = body.get("by", 1)
                if not isinstance(field, str):
                    self._send_json(400, {"error": "'field' must be a string"})
                    return
                try:
                    changed = state.bump(field, by)
                except TypeError as exc:
                    self._send_json(400, {"error": str(exc)})
                    return
                hub.broadcast_state(state.snapshot())
                hub.broadcast_fragment(changed)
                self._send_json(200, {"changed": changed})
                return

            if path == "/fragment/exclude":
                client_id = body.get("client_id")
                fields = body.get("fields")
                if not isinstance(client_id, str) or not isinstance(fields, list):
                    self._send_json(
                        400, {"error": "expected {'client_id': str, 'fields': [str, ...]}"}
                    )
                    return
                ok = hub.exclude_fields(client_id, fields)
                if not ok:
                    self._send_json(
                        404, {"error": f"no open /fragment/stream connection for {client_id!r}"}
                    )
                    return
                self._send_json(200, {"excluded": fields})
                return

            self._send_json(404, {"error": f"no such route: POST {path}"})

    return Handler
