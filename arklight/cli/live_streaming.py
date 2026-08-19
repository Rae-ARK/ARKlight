"""
`arklight live-streaming` -- a dev-only auto-rebuild + browser-reload
server. Alpha-only (see `arklight.CHANNEL`): this is exactly the kind
of experimental, moving-fast dev tool alpha exists for.

    arklight live-streaming --subscribe site.py [-o ARK] [--host H] [--port P]
    arklight live-streaming --status [site.py] [--status-pin]
    arklight live-streaming --unsubscribe [site.py]

Two halves, deliberately not overlapping in responsibility:

  - This module (stdlib-only Python -- ARKlight ships zero third-party
    runtime dependencies, see pyproject.toml) watches the entry file's
    directory for changes via mtime polling, re-runs the normal
    `arklight.compiler.pipeline.build()` pipeline on change, and serves
    the build output over plain `http.server`/`socketserver`, plus one
    extra endpoint (`/__arklight_live__/events`, Server-Sent Events)
    that pushes a `reload` event to connected browser tabs after each
    rebuild.
  - `_CLIENT_JS` (served at `/__arklight_live__/client.js`, injected
    into every HTML page by `_LiveReloadBackend.postprocess` below) is
    the only piece of JS involved, and it does nothing but listen on
    that SSE endpoint and call `location.reload()`. It has no
    filesystem access and can't invoke the compiler -- it is purely
    the passive receiving end of what this module pushes.

`--subscribe` runs in the *foreground*: it blocks the terminal it's
launched from and streams rebuild logs there directly (the same stage
narration `arklight build --verbose` prints, via the existing
`_stage_logger` convention), bookended by an
`[ARKlight] Live-streaming: ...` line per rebuild. `--unsubscribe` and
`--status` are separate, later invocations from another terminal --
they talk to the running session via a small on-disk registry + PID
signal, never a second in-process channel.
"""

from __future__ import annotations

import argparse
import atexit
import http.server
import json
import os
import signal
import socketserver
import sys
import threading
import time
import traceback
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from arklight.backend.base import Backend
from arklight.compiler.pipeline import CompileError, build, default_backends
from arklight.config import ConfigError, load_config, section
from arklight.ir.build import WebsiteIR

_STAGE_PREFIX = "[ARKlight]"
_LIVE_PREFIX = "[ARKlight] Live-streaming:"

# One-time banner printed at the start of every --subscribe session --
# impossible to miss, same [ARKlight]-prefixed style as the rest of
# the CLI, matching the existing [ARKlight ALPHA] warning-marker
# convention for "this is not a silent/ordinary code path."
_DEV_ONLY_BANNER = (
    f"{_STAGE_PREFIX} Live-streaming is a development tool only "
    f"-- do not run it in production/CI."
)

_LIVE_ROOT_PREFIX = "/__arklight_live__"
_EVENTS_PATH = f"{_LIVE_ROOT_PREFIX}/events"
_CLIENT_JS_PATH = f"{_LIVE_ROOT_PREFIX}/client.js"

# Registry lives outside any project directory -- it tracks every
# running --subscribe session on this machine, keyed by the absolute
# path of the entry file, so --status/--unsubscribe from any directory
# can find the right one. `~/.arklight` rather than a repo-local dotdir
# on purpose: a live-streaming session belongs to *this machine*, not
# to anything that should ever be committed.
_REGISTRY_DIR = Path.home() / ".arklight" / "live_streaming"
_REGISTRY_PATH = _REGISTRY_DIR / "registry.json"

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8347
_DEFAULT_POLL_INTERVAL = 0.5  # seconds

_WATCHED_SUFFIXES = {".py"}
_WATCHED_DIR_NAMES = {"assets"}


# --------------------------------------------------------------------
# Registry -- small JSON file recording every live --subscribe session
# on this machine, keyed by the entry file's absolute path (a project
# can only have one live session at a time, which is also what makes
# --subscribe idempotent).
# --------------------------------------------------------------------


def _read_registry() -> dict[str, dict[str, Any]]:
    if not _REGISTRY_PATH.is_file():
        return {}
    try:
        return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A corrupt/partially-written registry shouldn't wedge every
        # future --subscribe/--status/--unsubscribe call -- treat it
        # as empty and let the next successful write repair it.
        return {}


def _write_registry(registry: dict[str, dict[str, Any]]) -> None:
    _REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = _REGISTRY_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    tmp_path.replace(_REGISTRY_PATH)  # atomic on POSIX + Windows


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but owned by someone else -- still alive.
        return True
    return True


def _prune_dead_sessions(registry: dict[str, dict[str, Any]]) -> bool:
    """Drop any registry entry whose PID is no longer running (e.g. the
    process was killed rather than cleanly --unsubscribe'd). Returns
    True if anything was removed."""
    dead = [key for key, entry in registry.items() if not _pid_is_alive(entry["pid"])]
    for key in dead:
        del registry[key]
    return bool(dead)


def _entry_key(entry_path: str | Path) -> str:
    return str(Path(entry_path).resolve())


def _find_session(entry_path: str | Path | None) -> tuple[str, dict[str, Any]] | None:
    """Resolve which registry session `--status`/`--unsubscribe` means.
    If `entry_path` is given, look up that exact key. If omitted, only
    succeed when there's exactly one live session on this machine --
    with more than one, the caller must disambiguate by passing the
    entry path explicitly, since guessing which one they meant would
    silently act on the wrong project.
    """
    registry = _read_registry()
    if _prune_dead_sessions(registry):
        _write_registry(registry)

    if entry_path is not None:
        key = _entry_key(entry_path)
        entry = registry.get(key)
        return (key, entry) if entry else None

    if len(registry) == 1:
        ((key, entry),) = registry.items()
        return key, entry
    return None


# --------------------------------------------------------------------
# Reload injection -- an additive Backend, wired into `backends=[...]`
# alongside the normal HTML/CSS/JS backends (see `Backend.postprocess`
# docstring: "injecting analytics/OG tags ... without editing that
# backend's source" -- this is the same extension point). `render()`
# contributes no files of its own; `postprocess()` appends a <script>
# tag pointing at the live-reload client to every HTML page already
# rendered by HTMLBackend. This means the injected tag exists only in
# a live-streaming build's in-memory output, never in a plain
# `arklight build`'s output on disk.
# --------------------------------------------------------------------


class _LiveReloadBackend(Backend):
    name = "live-reload"

    def render(self, ir: WebsiteIR) -> dict[str, str]:  # noqa: ARG002
        return {}

    def postprocess(self, output_files: dict[str, str]) -> dict[str, str]:
        tag = f'<script src="{_CLIENT_JS_PATH}"></script>'
        updated = dict(output_files)
        for path, contents in output_files.items():
            if not path.endswith(".html"):
                continue
            if "</body>" in contents:
                updated[path] = contents.replace("</body>", f"{tag}</body>", 1)
            else:
                updated[path] = contents + tag
        return updated


# Vendored client script -- the only JS involved on the browser side.
# Deliberately tiny: connect to the SSE endpoint, reload on the one
# event type the server ever sends. No polling fallback is included on
# purpose -- SSE reconnection (the browser's built-in EventSource
# retry) already covers a server restart mid-session.
_CLIENT_JS = f"""\
(function () {{
  var source = new EventSource("{_EVENTS_PATH}");
  source.addEventListener("reload", function () {{
    location.reload();
  }});
}})();
"""


# --------------------------------------------------------------------
# HTTP server -- static file serving (the normal build output) plus
# the two `/__arklight_live__/*` routes above. `ThreadingHTTPServer`
# because the SSE endpoint holds its connection open indefinitely,
# which would otherwise block every other request on a single-threaded
# server.
# --------------------------------------------------------------------


class _LiveHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _Session:
    """Shared mutable state between the watcher loop (main thread) and
    the HTTP server's request-handling threads: which clients are
    connected, and rebuild/status counters `--status --status-pin`
    reads back out."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self._clients: list[Any] = []
        self._lock = threading.Lock()
        self.rebuild_count = 0
        self.last_rebuild_at: float | None = None
        self.started_at = time.time()

    def add_client(self, wfile: Any) -> None:
        with self._lock:
            self._clients.append(wfile)

    def remove_client(self, wfile: Any) -> None:
        with self._lock:
            if wfile in self._clients:
                self._clients.remove(wfile)

    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def broadcast_reload(self) -> int:
        with self._lock:
            clients = list(self._clients)
        sent = 0
        for wfile in clients:
            try:
                wfile.write(b"event: reload\ndata: reload\n\n")
                wfile.flush()
                sent += 1
            except OSError:
                self.remove_client(wfile)
        return sent


def _make_handler(session: _Session) -> type[http.server.SimpleHTTPRequestHandler]:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(session.output_dir), **kwargs)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return  # quiet -- rebuild/reload lines already narrate activity

        def do_GET(self) -> None:  # noqa: N802 -- stdlib method name
            if self.path == _CLIENT_JS_PATH:
                body = _CLIENT_JS.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return

            if self.path == _EVENTS_PATH:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                session.add_client(self.wfile)
                try:
                    # Block this thread for the connection's lifetime,
                    # sending a periodic comment as a keep-alive ping
                    # so intermediary proxies/browsers don't time the
                    # connection out. Actual reload events are pushed
                    # from the watcher thread via session.broadcast_reload().
                    while True:
                        time.sleep(15)
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    session.remove_client(self.wfile)
                return

            super().do_GET()

    return Handler


# --------------------------------------------------------------------
# Watcher + rebuild
# --------------------------------------------------------------------


def _watched_files(watch_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in watch_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in _WATCHED_SUFFIXES or path.parent.name in _WATCHED_DIR_NAMES:
            files.append(path)
    return files


def _snapshot_mtimes(watch_root: Path) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for path in _watched_files(watch_root):
        try:
            snapshot[str(path)] = path.stat().st_mtime
        except OSError:
            continue
    return snapshot


def _changed_path(before: dict[str, float], after: dict[str, float]) -> str | None:
    """Return one representative changed path (for the log line) if
    `before` and `after` differ, else None. Doesn't try to enumerate
    every change -- with a poll interval of a few hundred ms, a save-
    everything editor action can touch several files in one tick, and
    the log line only needs to point at *a* trigger, not all of them.
    """
    for path, mtime in after.items():
        if before.get(path) != mtime:
            return path
    for path in before:
        if path not in after:
            return path
    return None


def _stage_logger(message: str) -> None:
    if message.startswith("\u26a0"):
        print(message)
    else:
        print(f"{_STAGE_PREFIX} {message}")


def _print_alpha_warnings(caught: list[warnings.WarningMessage]) -> None:
    alpha_warnings = [w for w in caught if "[ARKlight ALPHA]" in str(w.message)]
    for w in alpha_warnings:
        print(f"  - {w.message}", file=sys.stderr)


def _rebuild(entry: Path, output: Path, backends: list[Backend]) -> bool:
    """Run one build. Returns True on success, False on a caught
    CompileError (already reported to stderr) -- either way the
    watcher loop keeps running; a broken build during live-streaming
    shouldn't kill the whole session, since the whole point is that
    the next save might fix it.
    """
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            build(entry, output, on_stage=_stage_logger, backends=backends)
    except CompileError as exc:
        print(f"{_LIVE_PREFIX} build failed -- {exc}", file=sys.stderr)
        return False
    except Exception as exc:  # noqa: BLE001 -- keep the watch loop alive regardless
        print(f"{_LIVE_PREFIX} unexpected error during rebuild -- {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return False

    _print_alpha_warnings(caught)
    return True


# --------------------------------------------------------------------
# --subscribe
# --------------------------------------------------------------------


@dataclass
class _RunningSession:
    session: _Session
    server: _LiveHTTPServer
    stop_event: threading.Event = field(default_factory=threading.Event)


def _cmd_subscribe(args: argparse.Namespace) -> int:
    entry = Path(args.entry).resolve()
    if not entry.is_file():
        print(f"ARKlight live-streaming failed: no such file -- {entry}", file=sys.stderr)
        return 1

    key = _entry_key(entry)
    registry = _read_registry()
    _prune_dead_sessions(registry)
    if key in registry:
        existing = registry[key]
        print(
            f"{_LIVE_PREFIX} already subscribed to {entry} "
            f"(pid={existing['pid']}, http://{existing['host']}:{existing['port']}/) "
            f"-- nothing to do.",
        )
        return 0

    try:
        project_config = load_config(entry.parent)
    except ConfigError as exc:
        print(f"ARKlight live-streaming failed: {exc}", file=sys.stderr)
        return 1
    live_cfg = section(
        project_config,
        "live_streaming",
        {"host": _DEFAULT_HOST, "port": _DEFAULT_PORT, "poll_interval": _DEFAULT_POLL_INTERVAL},
    )
    host = args.host or live_cfg["host"]
    port = args.port or live_cfg["port"]
    poll_interval = live_cfg["poll_interval"]

    output = Path(args.output).resolve()
    backends = [*default_backends(), _LiveReloadBackend()]

    print(_DEV_ONLY_BANNER)

    if not _rebuild(entry, output, backends):
        print(
            f"{_LIVE_PREFIX} initial build failed -- fix the error above and save "
            f"again; the session is still starting so it can pick up the fix.",
            file=sys.stderr,
        )

    session = _Session(output_dir=output)
    handler_cls = _make_handler(session)
    try:
        server = _LiveHTTPServer((host, port), handler_cls)
    except OSError as exc:
        print(
            f"ARKlight live-streaming failed: couldn't bind {host}:{port} -- {exc}. "
            f"Pass --port to use a different one.",
            file=sys.stderr,
        )
        return 1

    running = _RunningSession(session=session, server=server)

    registry[key] = {
        "pid": os.getpid(),
        "entry": str(entry),
        "output": str(output),
        "host": host,
        "port": port,
        "started_at": session.started_at,
    }
    _write_registry(registry)

    def _cleanup() -> None:
        reg = _read_registry()
        if reg.pop(key, None) is not None:
            _write_registry(reg)
        running.server.shutdown()

    def _handle_signal(signum: int, _frame: Any) -> None:  # noqa: ARG001
        print(f"\n{_LIVE_PREFIX} shutting down (signal {signum}).")
        running.stop_event.set()

    atexit.register(_cleanup)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    server_thread = threading.Thread(target=running.server.serve_forever, daemon=True)
    server_thread.start()
    print(f"{_LIVE_PREFIX} serving {output}/ at http://{host}:{port}/ (pid={os.getpid()})")

    watch_root = entry.parent
    last_snapshot = _snapshot_mtimes(watch_root)

    try:
        while not running.stop_event.is_set():
            time.sleep(poll_interval)
            snapshot = _snapshot_mtimes(watch_root)
            changed = _changed_path(last_snapshot, snapshot)
            if changed is None:
                continue
            last_snapshot = snapshot

            print(f"{_LIVE_PREFIX} change detected in {changed} -> rebuilding")
            ok = _rebuild(entry, output, backends)
            session.rebuild_count += 1
            session.last_rebuild_at = time.time()
            if ok:
                notified = session.broadcast_reload()
                print(f"{_LIVE_PREFIX} rebuilt, notified {notified} client(s).")
    except KeyboardInterrupt:
        print(f"\n{_LIVE_PREFIX} shutting down (keyboard interrupt).")
    finally:
        _cleanup()
        server_thread.join(timeout=5)

    return 0


# --------------------------------------------------------------------
# --unsubscribe
# --------------------------------------------------------------------


def _cmd_unsubscribe(args: argparse.Namespace) -> int:
    found = _find_session(args.entry)
    if found is None:
        if args.entry is None:
            registry = _read_registry()
            if len(registry) > 1:
                print(
                    "ARKlight live-streaming failed: multiple sessions running -- "
                    "pass the entry file to disambiguate, e.g. "
                    "`arklight live-streaming --unsubscribe site.py`.",
                    file=sys.stderr,
                )
                return 1
        print(f"{_LIVE_PREFIX} not subscribed -- nothing to do.")
        return 0

    key, entry_info = found
    pid = entry_info["pid"]
    os.kill(pid, signal.SIGTERM)

    deadline = time.time() + 5
    while time.time() < deadline:
        registry = _read_registry()
        if key not in registry:
            print(f"{_LIVE_PREFIX} unsubscribed from {entry_info['entry']}.")
            return 0
        time.sleep(0.1)

    print(
        f"{_LIVE_PREFIX} sent shutdown signal to pid={pid} but it hasn't confirmed yet "
        f"-- it may still be finishing a rebuild.",
        file=sys.stderr,
    )
    return 0


# --------------------------------------------------------------------
# --status
# --------------------------------------------------------------------


def _cmd_status(args: argparse.Namespace) -> int:
    found = _find_session(args.entry)
    if found is None:
        registry = _read_registry()
        if args.entry is None and len(registry) > 1:
            print(
                "ARKlight live-streaming: multiple sessions running -- pass the "
                "entry file to see one, e.g. `arklight live-streaming --status site.py`.",
            )
            for entry_info in registry.values():
                print(f"  {entry_info['entry']} (pid={entry_info['pid']})")
            return 0
        print(f"{_LIVE_PREFIX} not subscribed.")
        return 0

    _key, entry_info = found
    uptime = time.time() - entry_info["started_at"]

    if not args.status_pin:
        print(
            f"{_LIVE_PREFIX} subscribed to {entry_info['entry']} "
            f"(pid={entry_info['pid']}, up {uptime:.0f}s, "
            f"http://{entry_info['host']}:{entry_info['port']}/)",
        )
        return 0

    # --status-pin: verbose form. Applies only to *this* --status call
    # -- it's never written into the registry, so it doesn't change
    # what the running --subscribe session logs, and it isn't
    # remembered for the next plain --status call either.
    print(f"{_LIVE_PREFIX} status (verbose)")
    print(f"  entry:        {entry_info['entry']}")
    print(f"  output:       {entry_info['output']}")
    print(f"  pid:          {entry_info['pid']}")
    print(f"  serving:      http://{entry_info['host']}:{entry_info['port']}/")
    print(f"  uptime:       {uptime:.0f}s")
    return 0


# --------------------------------------------------------------------
# argparse wiring
# --------------------------------------------------------------------


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "live-streaming",
        help="Alpha-only dev tool: auto-rebuild + browser auto-reload on file change.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--subscribe",
        dest="entry_subscribe",
        metavar="ENTRY",
        default=None,
        help="Start a live-streaming session for ENTRY (e.g. site.py). Blocks in "
        "this terminal, streaming rebuild logs, until stopped with Ctrl-C or "
        "`arklight live-streaming --unsubscribe`.",
    )
    mode.add_argument(
        "--unsubscribe",
        dest="entry_unsubscribe",
        metavar="ENTRY",
        nargs="?",
        const="",
        default=None,
        help="Stop a running live-streaming session. ENTRY may be omitted if "
        "exactly one session is running.",
    )
    mode.add_argument(
        "--status",
        dest="entry_status",
        metavar="ENTRY",
        nargs="?",
        const="",
        default=None,
        help="Show whether a live-streaming session is running. ENTRY may be "
        "omitted if exactly one session is running.",
    )
    parser.add_argument(
        "-o", "--output", default="ARK", help="Output directory for --subscribe (default: ARK)"
    )
    parser.add_argument(
        "--host", default=None, help="Host to bind for --subscribe (default: 127.0.0.1, or "
        "arklight.config.py's live_streaming.host)",
    )
    parser.add_argument(
        "--port", type=int, default=None, help="Port to bind for --subscribe (default: 8347, "
        "or arklight.config.py's live_streaming.port)",
    )
    parser.add_argument(
        "--status-pin",
        action="store_true",
        default=False,
        help="With --status: show verbose session details instead of a one-line "
        "summary. Applies only to this invocation -- not remembered for next "
        "time, and has no effect on the running --subscribe session.",
    )
    parser.set_defaults(func=_cmd_live_streaming)


def _cmd_live_streaming(args: argparse.Namespace) -> int:
    if args.entry_subscribe is not None:
        args.entry = args.entry_subscribe
        return _cmd_subscribe(args)
    if args.entry_unsubscribe is not None:
        args.entry = args.entry_unsubscribe or None
        return _cmd_unsubscribe(args)
    args.entry = args.entry_status or None
    return _cmd_status(args)
