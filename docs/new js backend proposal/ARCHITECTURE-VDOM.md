# ARCHITECTURE-VDOM.md — Snabbdom-Clone Reimplementation Notes

This document is a companion to `ARCHITECTURE.md`. It describes an
alternate build of the same `oop-blog/` app on top of a **hand-cloned
snabbdom core** instead of the original "no virtual DOM, patch nodes
directly by hand" approach.

**This document assumes a vdom dependency.** Concretely, it assumes the
project vendors (or reimplements from scratch) snabbdom's four pieces:
`h()` hyperscript, the `vnode` data structure, `init()`/`patch()`, and a
small set of modules (`class`, `props`, `attributes`, `style`,
`eventlisteners`). Nothing here works without that core in place first.

## 0. Relationship to ARCHITECTURE.md

The original document targets Svelte-level performance *without* a vdom,
by hand-writing the three disciplines a compiler would otherwise give you
for free: build once, hold references, patch directly. That is
legitimate, but it means every component author is personally responsible
for correctness — miss a reference, forget to detach a listener, patch
the wrong node, and you get silent bugs with no framework to catch them.

Cloning snabbdom's core **inverts that trade-off**: you pay for a small
diffing algorithm once, and in exchange every component gets correctness
"for free" by describing *what* the DOM should look like (a vnode tree)
rather than *how* to mutate it. This is why the vdom version of this
architecture is meaningfully **easier to write and reason about** than
the zero-vdom version, even though it is not the more "high-performance"
choice in the abstract — snabbdom's diff/patch is doing real work that
`ARCHITECTURE.md`'s hand-rolled builders were specifically designed to
avoid. Non-functional parity claims from the original document (bundle
size, TTI) do not automatically carry over; see §5.

## 1. What "cloning snabbdom's core" means here

Snabbdom itself is ~200 lines of core plus small modules. The clone
needed for this project reproduces:

1. **`h(sel, data, children)`** — a hyperscript function that returns
   plain JS objects (`vnode`s: `{ sel, data, children, text, elm, key }`),
   not real DOM nodes. Nothing touches the DOM at creation time.
2. **`vnode`** — the plain-object description of an element: tag/selector,
   `data` (props, attrs, class, style, event handlers, `key`), and either
   `children` (array of vnodes) or `text`.
3. **`init(modules)`** — a factory that wires up which modules run during
   patch (mirrors snabbdom's `init([classModule, propsModule, ...])`) and
   returns a `patch(oldVnode, newVnode)` function.
4. **`patch(oldVnode, newVnode)`** — the diffing algorithm:
   - Same `sel` + `key` → reuse the real DOM node, patch its data/children
     in place.
   - Different `sel`/`key` → create a new real node, replace the old one.
   - Keyed children reconciliation (snabbdom's classic longest-stable-
     subsequence-style algorithm) to avoid unnecessary node
     recreation/reordering in lists (comment threads, tag lists, admin
     tables).
5. **Modules** — small hooks run by `patch` on `create`/`update`/`remove`:
   `attributesModule`, `classModule`, `stylesModule`, `propsModule`,
   `eventlistenersModule`. Each module owns one concern, same separation
   snabbdom uses upstream.

Everything above lives in `core/vdom/` and has zero framework
dependency — it is the "compiler runtime" this project vendors instead of
generating.

## 2. Pattern-by-pattern mapping (vdom version)

| Concern | GoF Pattern | File | Role once a vdom exists |
|---|---|---|---|
| Single source of truth for data | **Singleton** | `services/Database.js` | Unchanged from `ARCHITECTURE.md` — the vdom layer doesn't touch state ownership. |
| Cross-cutting API concerns (auth, caching) | **Proxy** | `services/ApiProxy.js` | Unchanged. Cache invalidation now simply triggers a re-render call (`patch(oldVnode, view(state))`) instead of a manual DOM write. |
| App-wide pub/sub without prop-drilling | **Observer** | `core/EventBus.js` | Subscribers now re-run a `view(state) → vnode` function and call `patch()`, instead of hand-patching specific nodes — the diff algorithm decides what actually changes. |
| Route → Page construction | **Abstract Factory / Factory Method** | `patterns/Factory.js` | Unchanged: pages are still lazily instantiated per route. |
| Layered page behavior (loading, auth guard, error boundary) | **Decorator** | `patterns/Decorators.js` | Decorators now wrap a page's `view()` function (vnode → vnode) instead of wrapping DOM-mutating `render()` calls — composable at the vnode-tree level. |
| Declarative-feeling DOM construction | **Builder → replaced by `h()`** | `patterns/ElementBuilder.js` (deprecated) | `ElementBuilder` is no longer needed; `h()` *is* the declarative builder, and it never touches real nodes until `patch()` runs. This is the biggest simplification vs. the original doc. |
| Skeleton every page follows | **Template Method** | `core/Page.js` | Lifecycle becomes `mount → view() → patch(null, vnode) → unmount`; "render" is now pure (state in, vnode out), no imperative node mutation inside a page class at all. |
| Reversible admin mutations | **Command** | `patterns/Command.js` | Unchanged in intent; `execute()`/`undo()` still mutate the cached slice, then trigger a `view()`+`patch()` cycle instead of a manual DOM edit. |
| Form-specific validation | **Strategy** | `patterns/ValidationStrategies.js` | Unchanged — orthogonal to rendering. |
| Storage-shape → view-shape translation | **Adapter** | `patterns/ViewAdapters.js` | Unchanged in purpose; output now feeds `h()` calls instead of template strings/`ElementBuilder` calls. |
| One router owns the visible page | **Singleton** | `core/Router.js` | Unchanged: still exactly one mounted tree, now expressed as one root vnode kept in a module-level variable for the next `patch()` call. |
| Diffing/reconciliation | **(new) Strategy-shaped internals** | `core/vdom/patch.js` | Not present at all in `ARCHITECTURE.md`. This is the new responsibility this document adds. |

## 3. Why this is easier to architect than the zero-vdom version

1. **No manual reference bookkeeping.** `ARCHITECTURE.md` requires every
   component to hold and track direct DOM references so it can patch the
   right node later. With a vdom, components just describe the desired
   tree every render; `patch()` figures out the minimal set of real
   mutations. There is no reference-tracking bug class to even write.
2. **List diffing is solved once, centrally.** The original architecture
   leans on event delegation and hand-written list patching per page. The
   snabbdom clone's keyed-children algorithm handles comment lists, tag
   filters, and admin tables uniformly, in one place (`core/vdom/patch.js`),
   instead of once per feature.
3. **`view()` functions are pure.** State in, vnode tree out. This removes
   an entire category of ordering bugs (did I patch before or after
   updating the cache?) because rendering is idempotent and side-effect
   free; only `patch()` touches the real DOM.
4. **Composability of Decorators improves.** Wrapping a `view()` function
   (vnode → vnode) is simpler and more testable than wrapping an
   imperative `render()` that mutates a live subtree, since the decorator
   can be unit-tested by inspecting the returned vnode tree with no DOM at
   all.
5. **Trade-off, stated plainly:** none of this is free. The clone adds a
   diff/patch pass on every update that the original architecture
   specifically avoided ("no virtual DOM, no diffing" was rule #1 there).
   This document is optimizing for *implementation and maintenance
   simplicity*, not for matching `ARCHITECTURE.md`'s stricter
   performance rule set.

## 4. Build pipeline → `dist/`

Unchanged in shape from `ARCHITECTURE.md` §4 — same `esbuild`-based
bundle/minify/hash pipeline, same `dist/` output layout. The only
difference is what's inside the bundle: `core/vdom/` (the snabbdom clone:
`h.js`, `vnode.js`, `init.js`, `patch.js`, `modules/`) ships as part of
the app code, since it is hand-written, not pulled from `node_modules`.
Tree-shaking still removes unused Command subclasses and unused vdom
modules (e.g. `stylesModule` if no component sets inline styles).

```
oop-blog-vdom/
├── src/
│   ├── js/
│   │   ├── core/
│   │   │   ├── vdom/          # ← new: the snabbdom clone
│   │   │   │   ├── h.js
│   │   │   │   ├── vnode.js
│   │   │   │   ├── init.js
│   │   │   │   ├── patch.js
│   │   │   │   └── modules/
│   │   │   │       ├── attributes.js
│   │   │   │       ├── class.js
│   │   │   │       ├── style.js
│   │   │   │       ├── props.js
│   │   │   │       └── eventlisteners.js
│   │   │   ├── EventBus.js
│   │   │   ├── Page.js
│   │   │   └── Router.js
│   │   ├── patterns/          # Factory, Decorators, Command, Strategy, Adapter
│   │   ├── services/          # Database.js, ApiProxy.js
│   │   └── app.js
│   ├── css/style.css
│   ├── index.html
│   └── assets/
├── build.mjs
└── dist/
```

## 5. What "parity with ARCHITECTURE.md" does and doesn't mean here

**Same as before:** route-based lazy page construction, `ApiProxy`
caching/invalidation, static/scoped CSS, single mounted tree via
`Router`, same out-of-scope items (no SSR, no real server auth, no real
database — `Database` is still a `localStorage`-backed mock).

**Different, explicitly:** this document does **not** claim the same
paint/interaction-latency profile as `ARCHITECTURE.md`. Introducing a
diff/patch pass is a deliberate departure from that document's rule 1
("no virtual DOM, no diffing"). Treat this as a *second, alternative*
architecture optimized for lower implementation complexity and safer
list/keyed-child updates, not as a drop-in performance-equivalent
replacement. If both non-functional parity *and* implementation
simplicity are required simultaneously, that is a genuine tension between
the two documents and should be resolved explicitly before choosing one.
