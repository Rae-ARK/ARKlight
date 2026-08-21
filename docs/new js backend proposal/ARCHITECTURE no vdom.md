# ARCHITECTURE.md — Vanilla OOP Reimplementation Notes

This document explains how the `oop-blog/` project reaches **Svelte-compiled-level
runtime performance** using plain HTML/CSS/JS, and how the Gang-of-Four (GoF)
design patterns are mapped onto that goal. "Non-functional parity" here means:
comparable bundle size, comparable paint/interaction latency, and comparable
DOM-update efficiency — not necessarily every feature of the original app.

## 1. Why vanilla JS *can* match a Svelte build

Svelte's advantage over React/Vue isn't a virtual DOM — it has none. The
Svelte **compiler** turns each `.svelte` file into imperative JS that:

1. Creates DOM nodes once, up front.
2. Keeps direct references to the nodes that can change.
3. On state change, writes only to those specific nodes/attributes —
   no diffing, no tree walk.
4. Ships zero framework runtime; only your compiled component code.

A hand-written vanilla implementation can hit the same profile if it
follows the same three rules: **build once, hold references, patch
directly.** The patterns below are simply disciplined ways of doing that
by hand instead of via a compiler.

## 2. Pattern-by-pattern mapping to performance

| Concern | GoF Pattern | File | Performance role |
|---|---|---|---|
| Single source of truth for data | **Singleton** | `services/Database.js` | Avoids duplicate state / redundant re-fetching, like Svelte's single reactive store graph. |
| Cross-cutting API concerns (auth, caching) | **Proxy** | `services/ApiProxy.js` | In-memory `Map` cache means repeated `list()` calls are O(1) instead of re-reading `localStorage`/re-hydrating models — mirrors Svelte's derived-store memoization. |
| App-wide pub/sub without prop-drilling | **Observer** | `core/EventBus.js` | Only the components that subscribed to a changed event re-render, not the whole page — analogous to Svelte's fine-grained dependency tracking. |
| Route → Page construction | **Abstract Factory / Factory Method** | `patterns/Factory.js` | Pages are only instantiated on navigation (lazy), keeping the initial script-evaluation cost near zero — mirrors SvelteKit's route-based code organization. |
| Layered page behavior (loading, auth guard, error boundary) | **Decorator** | `patterns/Decorators.js` | Cross-cutting logic is composed at wiring time, not baked into every page's hot path, keeping each page's `render()` lean. |
| Declarative-feeling DOM construction | **Builder** | `patterns/ElementBuilder.js` | Produces real nodes directly (`createElement`/`appendChild`), no template-string re-parsing (`innerHTML`) on the hot path once mounted. |
| Skeleton every page follows | **Template Method** | `core/Page.js` | Fixes the `mount → render → unmount` lifecycle so nothing does redundant work (e.g. re-querying `document.title` logic per page). |
| Reversible admin mutations | **Command** | `patterns/Command.js` | Encapsulated `execute()/undo()` avoid re-fetching the full list after every action — the command mutates the cached slice directly. |
| Form-specific validation | **Strategy** | `patterns/ValidationStrategies.js` | Swaps validation algorithm per form without branching logic bloating a shared validator. |
| Storage-shape → view-shape translation | **Adapter** | `patterns/ViewAdapters.js` | Precomputes derived view data (author name, tag list, formatted date) once per render instead of recomputing inline in markup, same as a Svelte `$:` reactive computation. |
| One router owns the visible page | **Singleton** | `core/Router.js` | Prevents duplicate listeners / duplicate mounted trees, which is what actually causes jank in hand-rolled SPAs. |

## 3. The core performance rules this codebase follows

1. **No virtual DOM, no diffing.** Components build nodes once via
   `ElementBuilder` and mutate properties/attributes directly when data
   changes (see `components/Header.js` re-rendering only its own subtree
   on `auth:changed`).
2. **Event delegation over per-node listeners** where a list is involved
   (comment lists, tag filters, admin tables) — one listener on the
   container, not N listeners on N rows.
3. **Cache reads, invalidate writes.** `ApiProxy` caches `list()` results
   and clears only the affected cache bucket on mutation, so read-heavy
   pages (the post list) do not re-hydrate model instances on every
   navigation.
4. **Lazy page instantiation.** `PageFactory` never eagerly constructs
   every page; only the active route's class runs, similar to
   SvelteKit's per-route JS chunks.
5. **CSS is static and scoped by convention** (BEM-ish class names in
   `src/css/style.css`), so there is no runtime style computation —
   the browser's own cascade does the work, same as Svelte's compiled
   `<style>` scoping.
6. **Minimal reflows.** Builders append fully-constructed subtrees in one
   `appendChild` call rather than incrementally mutating a mounted tree
   node-by-node.

## 4. Build pipeline → `dist/`

SvelteKit's `vite build` compiles `.svelte` files, tree-shakes, code-splits
per route, and emits static/hashed assets into `build/` (or
`.svelte-kit/output/client` in library mode). This project reproduces
that output shape without a compiler, using **esbuild** purely as a
bundler/minifier (no framework runtime is added to the bundle):

```
oop-blog/
├── src/
│   ├── js/            # ES modules, entry: js/app.js
│   ├── css/style.css
│   ├── index.html
│   └── assets/        # svg/image assets
├── build.mjs           # esbuild script (bundle + minify + hash)
└── dist/                # ← BUILD OUTPUT, ships to any static host
    ├── index.html
    ├── assets/
    │   └── app.[hash].js
    │   └── style.[hash].css
    └── assets/*.svg
```

`build.mjs` (esbuild) performs, in order:

1. **Bundle** all ES modules from `src/js/app.js` into one graph,
   resolving imports (equivalent to Vite/Rollup's module graph step).
2. **Minify + tree-shake** dead code (unused exports, e.g. unused
   Command subclasses) — same optimization Vite applies to Svelte's
   compiled output.
3. **Hash filenames** (`app.[contenthash].js`) for long-term
   cache-busting, matching SvelteKit's asset hashing.
4. **Inline critical CSS reference** into `index.html` and copy the
   rest of `static/`-equivalent assets verbatim.
5. Output everything into `dist/`, which is what actually gets
   deployed — nothing in `src/` needs to reach the browser.

Every artifact a Svelte build would emit (hashed JS, hashed CSS, copied
static assets, a single `index.html` entry point) has a direct
counterpart here; the only thing missing is the *compiler step* itself,
which the pattern-based hand-written code substitutes for.

## 5. What "non-functional parity" does and doesn't cover

**Covered:** initial load size, time-to-interactive, update latency,
memory profile of DOM node churn, caching behavior, code-splitting by
route.

**Not covered / out of scope:** SSR (this build is client-rendered only),
real server-side auth/session security (the `AuthService` here is a
client-side demo using `sessionStorage`, not a substitute for the
original app's server-verified sessions), and a real database (EdgeDB is
replaced by a `localStorage`-backed mock `Database` singleton for demo
purposes only).
