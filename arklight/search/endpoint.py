"""
Stage 9 -- IDE Interface Endpoint.

A separate, long-lived process the compiler never imports or depends
on -- mirrors the Language Server Protocol split (editor/IDE <-> a
language-intelligence server implemented and distributed independently
of the core tool). `arklight build` has zero dependency on this module;
only an editor extension that chooses to start it (via the new
`arklight search --serve` CLI flag, added alongside this module) ever
touches it.

Transport: line-delimited JSON over stdio -- one JSON object per line
in on stdin, one JSON object per line out on stdout, both flushed
immediately. Same transport shape as an LSP server (request in,
response out); not an HTTP server, so there's no port to manage and no
localhost attack surface -- the same reasoning LSP servers use stdio by
default.

This module is a thin transport wrapper around the Stage 6
`SearchEngine` -- it never re-implements retrieval/ranking/stats
itself, only decodes a request, calls the one matching `SearchEngine`
method, and encodes the result.

Request shape (`{...}\\n`, one per line):

    {"id": <any-json-value>, "op": "search", "query": "Imag",
     "limit": 5, "near": null}
    {"id": <any-json-value>, "op": "accept", "name": "Image"}

`id` is optional and echoed back verbatim (or `null` if omitted) --
same purpose as JSON-RPC's `id`: lets a caller match responses to
requests over a single shared stream without needing to serialize one
request at a time and block.

Response shape:

    {"id": <echoed id>, "ok": true, "results": [
        {"name": "Image", "score": 0.91,
         "signals": {"lexical": 0.95, "structural": 0.4,
                     "usage": 0.1, "known_typo": 0.0},
         "weights_used": {"lexical": 0.45, "structural": 0.27,
                           "usage": 0.18, "known_typo": 0.1}}
    ]}                                                  # op: search
    {"id": <echoed id>, "ok": true}                      # op: accept
    {"id": <echoed id or null>, "ok": false, "error": "..."}  # any failure

One malformed/unrecognized line never brings the server down: it's
reported back as an `"ok": false` response (with `"id": null` if the
line couldn't even be parsed far enough to find one) and the loop
keeps reading. The only ways this function returns are real end of
input (stdin closed) or an unrecoverable stream error -- never a bad
request.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from typing import Any, TextIO

from arklight.search.engine import SearchEngine, SearchEngineError

# Keys `op: "search"` accepts beyond `id`/`op`. Anything else in the
# request object is ignored rather than rejected -- forwards-compatible
# with a future client sending extra fields this version doesn't know
# about yet, same "unknown things are ignored, not fatal" posture as
# `_attr_string`'s data-* fallback in the HTML backend.
_SEARCH_FIELDS = ("query", "limit", "near")


class _ProtocolError(Exception):
    """A request line was well-formed JSON but not a valid request --
    e.g. missing `op`, unknown `op`, or `op: "search"` missing
    `query`. Caught once, centrally, in `_handle_request`, and turned
    into an `"ok": false` response; never escapes `serve_stdio`."""


def _parse_request(raw_line: str) -> dict[str, Any]:
    try:
        request = json.loads(raw_line)
    except json.JSONDecodeError as exc:
        raise _ProtocolError(f"invalid JSON: {exc}") from exc

    if not isinstance(request, dict):
        raise _ProtocolError(f"request must be a JSON object, got {type(request).__name__}")

    return request


def _handle_search(request: dict[str, Any], engine: SearchEngine) -> dict[str, Any]:
    if "query" not in request:
        raise _ProtocolError("op 'search' requires a 'query' field")
    query = request["query"]
    if not isinstance(query, str):
        raise _ProtocolError("'query' must be a string")

    limit = request.get("limit", 5)
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise _ProtocolError("'limit' must be an integer")

    near = request.get("near")
    if near is not None and not isinstance(near, str):
        raise _ProtocolError("'near' must be a string or null")

    try:
        results = engine.search(query, limit=limit, near=near)
    except SearchEngineError as exc:
        raise _ProtocolError(str(exc)) from exc

    return {"results": [asdict(result) for result in results]}


def _handle_accept(request: dict[str, Any], engine: SearchEngine) -> dict[str, Any]:
    if "name" not in request:
        raise _ProtocolError("op 'accept' requires a 'name' field")
    name = request["name"]
    if not isinstance(name, str):
        raise _ProtocolError("'name' must be a string")

    engine.accept(name)
    return {}


_HANDLERS = {
    "search": _handle_search,
    "accept": _handle_accept,
}


def _handle_request(request: dict[str, Any], engine: SearchEngine) -> dict[str, Any]:
    """Dispatch one already-parsed request object to its handler and
    build the full response envelope (`id` + `ok` + payload/`error`).
    Never raises -- any `_ProtocolError` (or an engine-side
    `SearchEngineError`, already translated to one by the handlers
    above) is caught here and turned into an `"ok": false` response."""
    request_id = request.get("id")

    op = request.get("op")
    handler = _HANDLERS.get(op) if isinstance(op, str) else None
    if handler is None:
        known = ", ".join(sorted(_HANDLERS))
        return {
            "id": request_id,
            "ok": False,
            "error": f"unknown or missing 'op' {op!r} -- expected one of: {known}",
        }

    try:
        payload = handler(request, engine)
    except _ProtocolError as exc:
        return {"id": request_id, "ok": False, "error": str(exc)}

    return {"id": request_id, "ok": True, **payload}


def serve_stdio(
    engine: SearchEngine | None = None,
    *,
    in_stream: TextIO = sys.stdin,
    out_stream: TextIO = sys.stdout,
) -> int:
    """Run the line-delimited JSON stdio server until `in_stream`
    closes (normal shutdown -- the host process closing our stdin,
    same convention an LSP server relies on), returning `0`.

    `engine` defaults to a fresh, non-shared `SearchEngine()` -- pass
    an existing instance (e.g. `arklight.search.engine.default_engine()`)
    to reuse one already warmed up, or for tests to inject one pointed
    at an isolated `db_path`/`roots`. The engine is closed on the way
    out either way.

    Blank/whitespace-only lines are silently skipped (not an error --
    keeps this liberal about how a client frames its stream, e.g. one
    that always appends a trailing newline producing one empty final
    read). Every other line always produces exactly one response line,
    whether or not the request was valid, so a caller that writes N
    non-blank request lines can always expect exactly N response lines
    back, in order -- request/response ordering on this single stream
    is otherwise unspecified beyond "response N corresponds to request
    N", which is what the echoed `id` is for if a caller needs to be
    sure rather than relying on ordering.
    """
    owns_engine = engine is None
    if engine is None:
        engine = SearchEngine()

    try:
        for raw_line in in_stream:
            line = raw_line.strip()
            if not line:
                continue

            try:
                request = _parse_request(line)
            except _ProtocolError as exc:
                response = {"id": None, "ok": False, "error": str(exc)}
            else:
                response = _handle_request(request, engine)

            out_stream.write(json.dumps(response))
            out_stream.write("\n")
            out_stream.flush()
    finally:
        if owns_engine:
            engine.close()

    return 0
