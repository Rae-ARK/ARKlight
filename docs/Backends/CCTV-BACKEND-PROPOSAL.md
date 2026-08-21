# ARKlight — `cctv`, a live-channel dev-server backend (Python port)

Companion to `C_ARKlight`'s own `docs/CCTV-BACKEND-PROPOSAL.md`, which
this ports concept-for-concept onto CPython. That document is the
design source of truth for *why* cctv is shaped the way it is (channel
naming, the `render()`/server split, out-of-scope items); this one
only covers what differs in the Python implementation and why it's
smaller than the C version.

Implementation: `arklight/cli/cctv.py`. Tests: `tests/test_cctv.py`.
Status: implemented, alpha-only (this branch).

---

## Why this is a smaller module in Python than in C

The C proposal's §4 has to design a state struct + mutex, a
subscriber hash table, and — the largest piece — "raw POSIX sockets +
a minimal request-line/header parser," because C has none of that in
the standard library. CPython does: `arklight.cli.live_streaming`
already runs its own dev server on `http.server` +
`socketserver.ThreadingMixIn`, so `cctv` reuses exactly that
machinery rather than introducing anything new to the project. The
"pure C, zero new build-time dependency" constraint the C proposal is
built around doesn't apply here in the same way — the equivalent
constraint already holds trivially, since `http.server`/`socketserver`
are stdlib.

Net effect: the same four responsibilities the C proposal lists in §4
(state, channel hub, HTTP/SSE surface, protocol-level interop) reduce
to two classes (`_State`, `_SSEHub`) plus one `http.server` request
handler — no socket lifecycle code, no request-line parser, no manual
`epoll`/`poll` decision (§8.2 in the C proposal) to make, since
`ThreadingMixIn` already gives each connection its own thread.

## What ported directly

- **The two-piece split** (§2/§3 of the C proposal): `_CCTVBackend`
  is a normal `Backend` subclass — `render()` only, one-shot, no
  different from `HTMLBackend`/`CSSBackend`/`JSBackend`. The actual
  server (`_serve` via `_cmd_cctv`) is a separate blocking call the
  `arklight cctv` subcommand runs after a normal `build()` — never
  inside `postprocess()`, for the same reason the C proposal gives:
  a pipeline stage that doesn't return blocks everything registered
  behind it.
- **Route/channel names, verbatim**: `GET /state/stream`,
  `GET /fragment/stream`, `GET /state`, `POST /state`,
  `POST /state/bump`, `POST /fragment/exclude` — same five routes,
  same semantics, including one-way field exclusion (a client that's
  excluded a field never gets it back without reconnecting).
- **`--tune` semantics** (§5): no flag scans forward from a default
  port on collision (`vite`/`next dev`-style); `--tune <port>` binds
  that exact port or fails loudly rather than silently falling back —
  ported as `argparse`'s `type=int` rather than a hand-rolled
  `--tune-8080` form, for the same "standard, unambiguous" reasoning
  the C proposal gives for preferring `getopt_long`.
- **The startup printout** (§5) — same three-line channel block.
- **Everything in §6 (explicitly out of scope)**: no CPython-embedding
  analog needed here (this *is* already Python), no ARKVM.js-style
  client latency logic, no persistence/auth/multi-process fan-out, and
  the same single-root scaffold gap — one running `cctv` process
  serves one page's `State(...)`.

## What changed in the port

- **State source**: the C proposal's `render()` "derives the field set
  from the IR." In this codebase that's concrete and already exists —
  `IRPage.state: dict[str, Any]`, populated by `State(...)` calls in a
  page (`arklight/ir/build.py`). `cctv.render()` reads that dict
  directly; no new IR concept was needed.
- **Page selection**: since `WebsiteIR` here is explicitly multi-page
  (`pages: list[IRPage]`, one per `@site.page(...)` route) rather than
  a single implicit root, `select_page()` adds a `--route` flag to
  choose which page's state to serve, defaulting to the site's first
  page. The C proposal's §6 caveat ("no route/site_name concept... one
  state object for one site root") becomes, concretely here: *you can
  pick which one, but still only one at a time.*
- **Client identity for `/fragment/exclude`**: the C proposal doesn't
  fully specify how a stateless `POST /fragment/exclude` call reaches
  an already-open `/fragment/stream` connection (its own §8.3 flags
  the wire format as an open question). This implementation resolves
  it with an explicit `?client_id=` query param on `/fragment/stream`
  (server-generated if omitted, echoed back via an
  `X-ARKlight-CCTV-Client-Id` response header) that `POST
  /fragment/exclude` then references by the same id.
- **Concurrency model**: `ThreadingMixIn` gives one thread per
  connection, so the C proposal's §8.2 tradeoff (thread-per-connection
  vs. a `poll`/`epoll` event loop) resolves itself — CPython's GIL and
  stdlib make thread-per-connection the obvious, low-code choice here,
  where in C it was a genuine design decision with a real cost on
  either side.
- **`INADDR_LOOPBACK` vs `INADDR_ANY`** (§8.1): resolved the same way
  either implementation should — `--host` defaults to `127.0.0.1`,
  with an explicit `--host` escape hatch to widen it, not a build-time
  choice.

## Explicitly not carried over

- **CPython embedding** (§6 in the C proposal) doesn't apply — this
  code already runs in CPython. The interop story is unchanged either
  way: `cctv` speaks HTTP+SSE only, and anything that can `POST` JSON
  (a Flask app, a FastAPI app, curl) can drive it, exactly as the C
  proposal specifies.
