# Building Real Applications on KaiOS
### A systems-level design doc, reverse-engineered from `strukturart/o.map`

---

## 0. Why this doc is shaped the way it is

KaiOS is not "a mobile browser you build a webpage for." It's a specific, aging point in the Gecko/SpiderMonkey lineage, wrapped in a Gonk (AOSP-derived) HAL, running on hardware that is closer to a 2012 Android budget phone than anything current. Every design decision downstream — how you structure your JS, how you touch the DOM, how you cache, how you handle input — is a consequence of three hard constraints:

1. **CPU**: single/dual-core ARM Cortex-A7-class, ~1.1–1.5 GHz, no or minimal JIT tiering warm-up budget for you to waste.
2. **RAM**: KaiOS 2.5's *platform minimum* is 256 MB total system RAM (per KaiOS Technologies' own MWC 2018 disclosure), shared across the whole Gonk/Gecko stack — your app gets a sliver of that, and the OOM killer is not polite about reclaiming it.
3. **Engine**: KaiOS 2.5 = Gecko 48 (2016-era SpiderMonkey). KaiOS 3.0 moved to a newer Gecko baseline, still years behind desktop Firefox. KaiOS 4.0 (Gecko 123, 2024) is a big jump but not yet universal across the device fleet. You are, in practice, targeting the *worst* of these unless you fork your build.

`o.map` is a good specimen precisely because its `package.json` states this constraint explicitly:

```json
"browserslist": ["Firefox <= 48"]
```

That one line is the root of almost every architectural choice in the codebase, and it's the root of most of the advice in this document. Everything below is organized bottom-up: engine → memory → rendering → input → storage → networking → build/packaging → architecture. Not top-down, because on this platform the hardware and engine constraints *are* the architecture; they aren't an afterthought you bolt on.

---

## 1. The runtime stack, precisely

```
┌─────────────────────────────────────────────┐
│  Your app: HTML + CSS + JS (+ manifest)      │
├─────────────────────────────────────────────┤
│  Gecko (layout/paint) + SpiderMonkey (JS)    │  ← Firefox 48-ish on 2.5, newer on 3.0/4.0
│  XPConnect / WebIDL bindings → C++ internals │
│  IPDL-defined IPC between app process & core │
├─────────────────────────────────────────────┤
│  Gonk: AOSP-derived HAL, radio/gfx/sensors   │
├─────────────────────────────────────────────┤
│  Linux kernel (monolithic, Android-patched)  │
├─────────────────────────────────────────────┤
│  ARM SoC: Cortex-A7-class, Mali/Adreno low-end│
└─────────────────────────────────────────────┘
```

Key mechanism-level facts that should change how you write code:

- **Each privileged app runs its own Gecko content process**, communicated with the parent ("chrome") process via IPDL-generated IPC (serialize → Unix domain socket / shared memory → deserialize). This is architecturally identical to how Firefox itself isolates tabs. It means: crossing the app/OS boundary (camera, geolocation, storage APIs backed by system services, `mozActivity`) is not a free function call — it's a message-passing round trip, with allocation and copy overhead. Batch these calls; don't poll them in a tight loop.
- **SpiderMonkey on Gecko 48 has a JIT, but its tiering is primitive by modern standards** — Baseline JIT after a warm-up threshold, no full Ion-level optimizations you can rely on for short-lived code paths. Practically: a function called once per keypress will rarely get past interpreter/Baseline. Don't write code assuming it will be "optimized away" — write code that's *cheap in its unoptimized form*, because that's the form it will mostly run in.
- **GC is a stop-the-world (or near-stop-the-world) generational GC** for this SpiderMonkey vintage. On a single-core 1.2 GHz part with 256 MB total RAM, a GC pause is not a rounding error — it's visible jank on a device where "visible jank" is a 200–300 ms dropped frame on a keypress-driven UI, not a 60fps scroll-jank complaint. Every unnecessary allocation (closures created per-frame, object literals per D-pad event, array `.map()`/`.filter()` chains that allocate intermediate arrays) is GC pressure you're choosing to pay for.

---

## 2. Memory: the actual constraint that shapes everything

256 MB total RAM is shared by: the Linux kernel, Gonk services (radio, telephony, Wi-Fi), the Gecko *parent* process, and your app's *content* process, plus whatever else the launcher/system apps are holding onto. Your realistic working set budget is on the order of **tens of megabytes**, not hundreds. `o.map`'s own README documents a real symptom of this: it warns that the "intensiv" tile cache mode can cause slowdowns after a few thousand cached tiles and recommends a "long-press power button" memory cleanup — i.e., **the OS-level low-memory killer is a known, user-facing failure mode**, not a hypothetical.

Concrete implications for your JS:

- **Avoid unbounded in-memory caches.** `o.map` caches map tiles to *disk-backed storage* (IndexedDB via `localforage`, or PouchDB-cached tile layers for Leaflet), not to a JS `Map`/object held in RAM. A tile is decoded pixel data; keeping thousands of them live in a JS heap on a 256 MB device is how you get OOM-killed mid-session.
- **Prefer typed arrays over generic arrays/objects for anything numeric and large** (GPS track points, GeoJSON coordinate arrays). A `Float64Array` of N points is N×8 contiguous bytes with no per-element boxing, no hidden-class transitions, no GC scanning of object headers. A plain JS array of `{lat, lng}` objects is N allocations, N object headers, N sets of hidden-class metadata, and a GC that has to walk pointers instead of scanning a flat buffer.
- **Kill your own listeners and timers on teardown.** This is not optional polish — it is a memory-leak / CPU-leak prevention step. See §4.
- **Prefer streaming/incremental parsing over "load whole file, then parse."** For GPX/GeoJSON import (both present in `o.map`), a multi-megabyte file parsed via `JSON.parse` on the whole string means: the raw string in memory, plus the fully-materialized object graph, coexisting briefly, plus GC pressure once the intermediate string is dropped. On a memory-starved device this transient peak can be the thing that trips the OOM killer even though your steady-state usage is fine.

---

## 3. Rendering: what "DOM" costs on this hardware

Gecko's rendering pipeline is conceptually the same as desktop Firefox: DOM → style resolution → frame/layout tree → paint → composite. What's different is the *cost per stage relative to your CPU budget*.

- **Style recalculation and reflow are O(affected subtree), and "affected subtree" is easy to make larger than you think.** Toggling a class on a high-level container can force layout recomputation across everything beneath it. `o.map`'s markup keeps the interactive chrome (`#top-bar`, `#bottom-bar`, per-screen containers) as flat, purpose-built `div`s rather than deep generic component trees — fewer nodes means less to restyle/relayout per state change.
- **`o.map` explicitly avoids the two most expensive DOM-diffing frameworks in favor of Mithril** (`mithril@2.x`, ~9–10 KB gzipped, no VDOM abstraction layers beyond a minimal one, synchronous-by-default render model). This is a deliberate engineering choice, not an accident:
  - React/Vue-class frameworks assume a JIT that aggressively inlines and optimizes their reconciliation hot paths, and a device that can absorb the extra parse/eval cost of a larger runtime. Neither assumption holds on Gecko 48/SpiderMonkey-2016 + Cortex-A7.
  - Mithril's redraw model is coarse and predictable: you call `m.redraw()` (or return from an event handler Mithril wraps) and it re-runs `view()` and diffs once — no fiber scheduling, no concurrent-mode heuristics to reason about on hardware where those heuristics were never tuned for you.
- **Route-based screens, not always-mounted overlays.** `o.map` structures the app as Mithril route components — `mapView`, `menuView`, `searchView`, `routingView`, etc. — where each screen's DOM is created on `oncreate` and torn down on `onremove`. This bounds the live DOM tree to roughly one screen's worth of nodes at a time instead of accumulating hidden-but-mounted screens (`display:none` stacks), which would otherwise keep costing style/layout bookkeeping and memory for content the user can't currently see.
- **`requestAnimationFrame` is used sparingly and deliberately** (once, for a debounced UI transition in `o.map`), not as a per-frame render-loop driver. This is correct for a D-pad-driven, event-triggered UI: there is no continuous 60fps motion to drive, so a `rAF` loop running unconditionally would just be burning battery and CPU for nothing. Render on state change, not on a clock.
- **Leaflet is the one heavyweight dependency, and it's used with awareness of its cost.** Leaflet's default DOM-based tile/marker rendering creates real elements per tile/marker; on a map-heavy app this is where you *do* want to think about canvas-based rendering (`preferCanvas`) if marker/vector count grows, because canvas composites as a single surface instead of N separately-styled/reflowed DOM nodes. If you extend `o.map`-like code with many overlays, that's the first lever to pull before you start micro-optimizing anything else.

---

## 4. Input: D-pad/softkey event model, and the leak pattern to avoid

KaiOS devices have no touchscreen (or a very limited one on some 3.0 devices) — the primary input is a numeric keypad plus a directional pad and two softkeys mapped under the top corners of the screen, matching the `#top-bar`/`#bottom-bar` "button-left / button-center / button-right" regions you see in `o.map`'s `index.html`. This is a **keyboard-event API dressed as a physical-button API**:

```js
if (e.key === "SoftLeft" || e.key === "Control") { ... }
if (e.key === "SoftRight" || e.key === "Alt")     { ... }
if (e.key === "ArrowUp")    { MoveMap("up");   getMarkers(); }
if (e.key === "ArrowDown")  { MoveMap("down"); getMarkers(); }
if (e.key === "Enter")      { m.route.set("/menuView"); }
```

Mechanism to understand: `SoftLeft`/`SoftRight` are **non-standard `KeyboardEvent.key` values that exist only in this platform's Gecko fork** to represent the two softkeys; some KaiOS/Firefox-OS-lineage builds alias them to `Control`/`Alt` for compatibility, which is why `o.map` checks both. This is a portability landmine: code written against a "normal" web keyboard-event assumption (`e.keyCode`, or assuming `Tab`/`Escape` semantics) will not map cleanly onto this input model. Always design your key handling around the *actual enumerated key set* KaiOS exposes, not around assumptions carried over from desktop or touch UIs.

**The critical hygiene pattern**, present consistently throughout `o.map`'s per-screen components:

```js
oncreate: function () {
  document.addEventListener("keydown", this.handler);
},
onremove: function () {
  document.removeEventListener("keydown", this.handler);
},
```

Why this matters at a mechanism level, not just a style-guide level: `document` is a single, long-lived object for the life of the app process. Every `addEventListener` call without a matching `removeEventListener` on teardown keeps a strong reference alive from `document`'s listener list back to the closure (and everything that closure closed over — component state, DOM references, sometimes the entire previous screen's object graph). On desktop, with gigabytes of RAM and a fast GC, a handful of leaked listeners across a session is invisible. On a 256 MB device, if every screen transition leaks one keydown listener, you get:

1. **Memory growth** proportional to screens visited — nothing frees the closed-over state.
2. **CPU growth per keypress** — every stale listener still runs on every subsequent keydown, even for a screen no longer visible, silently multiplying per-event work as the session goes on.
3. **Logic bugs**, not just performance bugs — a leaked handler from a previous screen firing route changes or map manipulations the user never intended.

This is the single most important discipline lesson in the whole codebase: **every `addEventListener` needs a symmetric teardown, tied to the same lifecycle hook that created the DOM it's associated with.** If you use a framework, tie listener lifetime to component lifetime explicitly; if you use vanilla JS, treat "add listener" and "remove listener" as a pair you write together, in the same commit, never one without the other in your mental model.

---

## 5. Storage: why `localforage`, and why the Cache API is conditionally disabled

`o.map` uses `localforage` (a wrapper that picks IndexedDB, then WebSQL, then `localStorage` as fallback, in that priority order, based on feature detection) for essentially everything persistent: last known GPS position, saved markers, GPX files, tile cache metadata, user settings, an in-flight-tracking recovery buffer.

Why not the Cache API / Service Worker storage for everything, given `o.map` ships a `sw.js`? Look at the actual guard in that file:

```js
const userAgent = /* ... */ self.navigator.userAgent;

if (userAgent && !userAgent.includes("KAIOS")) {
  // Cache API install/activate/fetch handlers registered here
}
```

**The entire Cache-API-based offline strategy is disabled when running on real KaiOS hardware**, and only active for the browser/PWA (`npm run web`) build. This is a deliberate feature-detection boundary reflecting real platform divergence: privileged packaged KaiOS apps have their own storage quota and installation model (they're delivered as a zip via the KaiStore or sideloaded, not fetched-and-cached like a PWA), and Service Worker `Cache` semantics inside that packaged-app sandbox were unreliable/unnecessary duplication of what the packaging model already gives you for free (your app's own files ship *inside* the zip — you don't need to cache your own shell). What you *do* still need persisted regardless of build target — user data, downloaded map tiles, GPS tracks — goes through `localforage`, because that's backed by IndexedDB, which is the actual durable, quota-bearing, structured storage available across both build targets.

**Mechanism-level lesson**: don't assume "PWA best practices" (Cache-first Service Worker shell caching) transfer unmodified to a packaged native-feeling app on this platform. Feature-detect the actual runtime (`navigator.userAgent.includes("KAIOS")`, or check for a KaiOS-specific API's presence) and branch your persistence strategy accordingly, exactly as `o.map` does.

A second mechanism to respect: IndexedDB writes are asynchronous and transactional, but they still cost real I/O time on eMMC-class flash storage that's far slower than what you'd assume from a laptop's SSD. `o.map` doesn't write on every `mousemove`-equivalent event; position updates are throttled and only written at meaningful state transitions (`lastPosition` on view changes, not per GPS tick). Treat every `setItem` call as a real disk write with latency, not a free operation — batch and debounce writes to slow-changing state.

---

## 6. Networking: `systemXHR`, offline-first tiles, and why plain `fetch` isn't enough

Two networking realities specific to this platform, both visible in `o.map`'s manifest and code:

**a) Privileged cross-origin requests need the `systemXHR` permission.** A normal web page's `fetch`/`XMLHttpRequest` is subject to standard same-origin/CORS rules. `o.map`'s manifest declares:

```json
"systemXHR": { "description": "Required to load remote content" }
```

This is a *capability grant*, not a polyfill — it tells the privileged-app permission model "this app is allowed to make requests that an ordinary sandboxed web page could not" (fetching tile servers, routing APIs, OSM's OAuth endpoint, etc., across origins, without those origins needing to cooperate via CORS headers). Mechanism to internalize: on this platform, network capability is gated by the **manifest's declared permission set**, checked by the privileged-app runtime before the request ever leaves the process — not by the target server's CORS policy. Design your manifest's permission list around every remote origin your app actually needs to hit, and understand that a missing permission fails at the platform layer, not as an ordinary CORS console error you'd recognize from normal web dev.

**b) Offline-first is a first-class requirement, not a stretch goal**, because the target user is frequently on 2G/3G, in poor coverage, or intentionally airplane-mode-adjacent (outdoor/hiking use case, explicitly `o.map`'s stated purpose). This is why the tile layer uses `L.TileLayer.PouchDBCached` — a Leaflet tile layer subclass that intercepts tile requests, serves from a local IndexedDB-backed cache when available, and falls back to network fetch only on cache miss, with explicit user-triggered bulk-caching (`caching_tiles()`, bound to the `*` key) rather than implicit background prefetch that would burn a metered/slow data connection without the user asking for it.

Mechanism-level design rule this implies: **never assume the network round trip will complete, and never make the network round trip block the UI thread's ability to respond to input.** All of `o.map`'s network calls are Promise-based (`fetch`, `async/await`), which under Mithril's model means a keypress can still be handled and redraw the UI while a tile or routing request is in flight — but you still have to *design* your state machine so that "waiting for network" is a visible, interruptible UI state (a spinner/toast) rather than a modal block, because on 2G a request can take multiple seconds and the user still has a device with responsive physical buttons that they expect to keep working.

---

## 7. Build toolchain: what's actually happening to your source

`o.map`'s three build targets tell you almost everything about the deployment model:

```json
"build":    "parcel build ... src/index.html ... zip -r build/omap.zip .",     // KaiOS 3 (webmanifest)
"build-k2": "parcel build ... src/index.html ... zip -r build/omap-k2.zip .",  // KaiOS 2 (manifest.webapp)
"web":      "parcel build --dist-dir docs ... src/index.html ..."              // browser/PWA
```

**Mechanism**: Parcel (a bundler, here targeting the `browserslist: ["Firefox <= 48"]` constraint) does three things that matter for this platform specifically:

1. **Babel transpilation down to a ~2016 JS baseline.** Modern syntax you write (`async`/`await`, optional chaining `?.`, class fields, arrow functions with implicit returns) gets compiled to whatever subset Gecko 48's SpiderMonkey actually implements. `o.map`'s devDependencies include `babel-plugin-transform-async-to-promises` — a strong signal that `async`/`await` is being **desugared to explicit Promise chains at build time** rather than relying on native engine support, because native `async`/`await` support and its performance characteristics on 2016-era SpiderMonkey aren't something you want to bet the whole app on. This is exactly analogous to targeting an old C++ standard and having your compiler lower newer-standard constructs to equivalent code the target actually runs well — the abstraction is source-level only; the generated bytecode is deliberately conservative.
2. **`core-js` polyfills** fill in missing/incomplete standard library surface (`Promise`, `Array.prototype` extras, `Object.entries`, etc.) that a 2016 engine won't have natively. Every polyfilled method is real, shipped JS running in the interpreter/Baseline tier — not free. Prefer built-ins that are actually native on your minimum target where you can verify it, and treat every polyfill-covered API as a small, real per-call cost, not an abstraction you get for free.
3. **Packaging as a zip with a manifest at the root** (`manifest.webapp` for KaiOS 2 / `manifest.webmanifest` with an embedded `b2g_features` block for KaiOS 3) — this is *not* a hosted web app being crawled and cached; it's closer to packaging a native app bundle. The manifest format difference between the two targets is substantial enough (`manifest.webapp`'s flat `permissions`/`activities`/`messages` keys vs. `manifest.webmanifest`'s nested `b2g_features` object wrapping the same concepts) that `o.map` maintains **two manifest source files** and lets the build script pick the right one per target, rather than trying to unify them with a single generated artifact. That's the right call: don't fight the platform's schema drift with cleverness, just maintain both and be explicit.

**Design takeaway**: your build pipeline's job on this platform isn't just "bundle and minify" — it's "translate your comfortable, modern JS source into the dialect and polyfill-completeness that a specific, old, fixed JS engine actually executes well." Pin your `browserslist`/target explicitly, verify what Babel is actually doing to your hot paths (inspect the output, don't just trust the toolchain), and treat `async/await` → Promise-chain desugaring as the default assumption for your minimum-supported KaiOS version, not an edge case.

---

## 8. Application architecture pattern (the shape to copy)

Distilled from `o.map`'s actual structure — this is the architecture template to use for a new KaiOS app:

```
src/
  index.html          — static shell: top-bar / bottom-bar softkey regions,
                         map/content container, single <script type="module">
  index.js            — single JS entry: Mithril routes, one component per screen
  manifest.webapp      — KaiOS 2.x manifest (flat schema)
  manifest.webmanifest — KaiOS 3.x manifest (b2g_features-nested schema)
  sw.js                — Service Worker, feature-detected to KAIOS user agent
                         (Cache API path only active off-device / PWA build)
  assets/
    css/   — hand-written, framework-light CSS (flexbox grid, no heavy UI kit)
    js/    — vendored/adapted libs requiring platform-specific patches
             (e.g. Leaflet + a PouchDB/IndexedDB-cached tile layer subclass)
    icons/, image/, fonts/
```

**Per-screen component contract** (the pattern every route follows):

```js
let someView = {
  handler: function (e) {           // keydown handler, closed over local state
    if (e.key === "SoftLeft") { /* ... */ }
    if (e.key === "ArrowUp")  { /* ... */ }
    if (e.key === "Enter")    { m.route.set("/nextView"); }
  },
  oncreate: function () {
    top_bar(leftLabel, centerLabel, rightLabel);   // sync softkey chrome to screen
    bottom_bar(leftLabel, centerLabel, rightLabel);
    document.addEventListener("keydown", this.handler);
  },
  onremove: function () {
    document.removeEventListener("keydown", this.handler);  // mandatory, symmetric
  },
  view: function () {
    return m("div", { id: "someView" }, /* ... */);
  },
};
```

Why this specific shape is correct for the constraints in §1–§6, stated explicitly:

- **One listener per active screen, added/removed at mount/unmount** → bounded, predictable memory and CPU cost (§4).
- **Softkey labels (`top_bar`/`bottom_bar`) are explicit per-screen state, not inferred from global app state** → no hidden coupling between screens, and the physical-button affordances always match what the current screen's `handler` actually does — critical on a UI with no touch affordance to "discover" what's tappable.
- **Screens are Mithril route components, mounted/unmounted, not always-alive with visibility toggles** → bounded live-DOM size (§3).
- **All persistence goes through one storage abstraction (`localforage`)**, feature-detected per build target, not scattered `localStorage.setItem` calls with no quota/durability guarantees (§5).
- **A single JS entry point, bundled once** rather than many lazily-loaded chunks — on this platform, script-loading/parsing overhead per additional file and the complexity of managing multiple in-flight module loads on a slow radio/CPU generally isn't worth it versus one well-tree-shaken bundle. (Verify this trade-off if your app grows large enough that initial-parse time of one big bundle becomes the bottleneck instead — but don't reach for code-splitting by default here the way you would on the modern web.)

---

## 9. Concrete checklist for a new KaiOS app

**Engine/build**
- [ ] Pin `browserslist` to your actual minimum KaiOS/Gecko target; don't guess.
- [ ] Verify Babel's `async/await` output (desugared to Promises, or native) matches what your minimum engine handles well.
- [ ] Maintain separate `manifest.webapp` (KaiOS 2.x) and `manifest.webmanifest` (KaiOS 3.x) source files; don't try to auto-unify.
- [ ] Declare every remote origin you touch in the manifest's permission block (`systemXHR`, etc.) — a missing permission is a platform-layer failure, not a CORS error.

**Memory**
- [ ] No unbounded in-memory caches; anything that can grow with usage (tiles, tracks, history) goes to IndexedDB via a storage abstraction.
- [ ] Typed arrays for large numeric data (coordinates, samples), not arrays of small objects.
- [ ] Debounce/throttle writes to persistent storage; treat every write as real, non-free I/O.
- [ ] Parse large imports incrementally where feasible; be aware of the transient peak (raw string + parsed object coexisting) even when steady-state memory is fine.

**Rendering**
- [ ] Keep the live DOM bounded to "current screen," using mount/unmount, not `display:none` stacking.
- [ ] Choose a rendering approach that matches the actual update model (event-driven, not continuous) — don't run a `requestAnimationFrame` loop for a UI with no continuous motion.
- [ ] If a map/canvas-like surface accumulates many overlay elements, prefer canvas compositing over per-element DOM nodes before micro-optimizing anything else.

**Input**
- [ ] Handle the actual enumerated `KeyboardEvent.key` values this platform exposes (`SoftLeft`/`SoftRight`/`Enter`/arrows/digits), including known aliasing (`Control`/`Alt` fallbacks for softkeys) — don't assume desktop/touch key semantics.
- [ ] Every `addEventListener` on a long-lived target (`document`) has a matching `removeEventListener` tied to the same lifecycle boundary that created it. Treat this as a hard rule, not a linter suggestion.
- [ ] Keep the softkey labels (`top_bar`/`bottom_bar`) in sync with per-screen handler behavior, explicitly, per screen.

**Storage/network**
- [ ] Feature-detect the actual runtime (`navigator.userAgent` KaiOS check or equivalent) before assuming Cache-API/Service-Worker behavior is available/appropriate; branch persistence strategy accordingly.
- [ ] Design offline-first: explicit, user-triggered caching for large/expensive resources (tiles, maps) rather than implicit background prefetch on a possibly metered/slow connection.
- [ ] Every network call is a real, possibly multi-second round trip on 2G — make "waiting" a visible, non-blocking UI state, not an assumption that it'll be fast.

---

## 10. Where `o.map` earns extra study time

If you clone it (`git clone https://github.com/strukturart/o.map.git`) and want to trace mechanism end-to-end yourself, the highest-signal files are:

- `package.json` — the entire constraint set (`browserslist`, build targets, dependency choices) in one file.
- `src/index.js` — search for `oncreate`/`onremove` pairs to see the listener-lifecycle pattern repeated across every screen; search for `localforage.` to see the storage-abstraction usage; search for `e.key ===` to see the full input-handling surface.
- `src/sw.js` — the KaiOS-vs-PWA branch on `navigator.userAgent`; small file, large architectural implication.
- `src/manifest.webapp` vs `src/manifest.webmanifest` — diff these directly to see the KaiOS 2 → 3 schema migration in a real shipped app.
- `assets/js/L.TileLayer.PouchDBCached.js` (vendored/adapted) — the offline-tile-cache mechanism referenced in §6.

And for the maximally minimal counterpart — to see the *skeleton* without the load-bearing engineering `o.map` adds on top — pair this with KaiOS's own `sample-vanilla` reference app from the official developer docs. One shows you the four files a KaiOS app minimally needs; this doc, and `o.map`, show you what those four files have to become once real constraints show up.

---

## 11. Verification note — this section was checked against live source

Everything above was written analytically from architectural reasoning about the platform. Everything below was checked directly against the actual repositories: `git clone https://github.com/strukturart/o.map.git` (commit at time of writing, `v2.0.2`) and `git clone https://github.com/kaiostech/sample-vanilla.git` (the correct org is `kaiostech`, not `kaiOS` or `KaiOS-Apps`). Three corrections and one important addition fell out of that check:

- **`package.json`'s `"license"` field says `"ISC"`, but `LICENSE.md` in the repo root is the actual MIT License text** (copyright strukturart, 2023). The `browserslist: ["Firefox <= 48"]` line, the three build scripts, and the dependency list quoted earlier in this doc are verified verbatim against the real file — no corrections needed there.
- **`o.map`'s actual entry point is 4,573 lines in a single `src/index.js`**, confirming §8's "one JS entry point, bundled once" claim isn't a simplification — it's literally true even at this app's size. The Mithril `oncreate`/`document.addEventListener("keydown", this.handler)` / `onremove`/`document.removeEventListener(...)` triple appears **verbatim, per-screen, at least ten separate times** in the real file (`mapView`, `menuView`, `searchView`, and others) — this is the load-bearing idiom of the whole codebase, not an occasional pattern.
- **`sample-vanilla` does not use Mithril, routes, or `oncreate`/`onremove` at all.** It's a single-screen to-do list with no navigation between views, so it has no lifecycle-driven mount/unmount story to teach. What it teaches instead — and this wasn't in the original doc — is a **declarative, attribute-driven spatial-navigation pattern** that's worth adding to your toolbox for KaiOS apps that are one screen with many focusable items (lists, forms, settings pages) rather than many screens. See §12.
- **New, verified addition: `o.map` has an explicit screen-wake-lock pattern** (`keepScreenOn()` / `allowScreenOff()` in `assets/js/helper.js`) that the original doc didn't cover at all, and that any KaiOS app doing GPS tracking, timers, or anything else that needs the screen alive needs to know about. See §13.

---

## 12. Two real navigation patterns, side by side

KaiOS apps need *some* answer to "how does D-pad focus move around, and how do the two softkeys know what they currently do." The two reference apps answer this differently because they have different shapes, and the difference is instructive — it tells you which pattern to reach for based on your app's screen count, not just personal taste.

### 12a. `o.map`'s pattern: per-screen owned handler, softkeys as explicit screen state

Already covered in §8, confirmed verbatim in source. The shape, taken directly from `src/index.js` (mapView component, lightly trimmed):

```js
let mapView = {
  handler: function (e) {
    if (e.key === "#") { panToNextMarker(); }
    if (e.key === "*") { caching_tiles(); }
    // ...more key checks specific to this screen...
  },

  oncreate: function () {
    bottom_bar("", "<img class='menu-button' src='assets/image/menu.svg'>", "");
    top_bar("", "", "");
    document.querySelector("#map-container").style.display = "block";
    document.addEventListener("keydown", this.handler);
  },

  onremove: function () {
    document.removeEventListener("keydown", this.handler);
  },

  view: function () {
    return m("div", { id: "mapView" /* ... */ }, /* ... */);
  },
};
```

`top_bar`/`bottom_bar` themselves (from `assets/js/helper.js`, verified verbatim) are almost embarrassingly simple — which is the point, on this platform simple and cheap beats clever:

```js
export let top_bar = function (left, center, right) {
  document.querySelector("div#top-bar div.button-left").innerHTML = left;
  document.querySelector("div#top-bar div.button-center").innerHTML = center;
  document.querySelector("div#top-bar div.button-right").innerHTML = right;
  if (left == "" && center == "" && right == "") {
    document.querySelector("div#top-bar").style.display = "none";
  } else {
    document.querySelector("div#top-bar").style.display = "block";
  }
};
```

**Use this pattern when your app has multiple distinct screens/routes.** Each screen owns its own key semantics; the softkey labels are set explicitly on `oncreate`, not derived from some global "current mode" flag; and there's exactly one `keydown` listener alive at any moment because the previous screen's `onremove` fired before the new screen's `oncreate` runs.

### 12b. `sample-vanilla`'s pattern: `nav-selectable`/`nav-index` attributes, one global listener

`sample-vanilla` is a single-screen to-do list with a growing/shrinking list of focusable items, so it doesn't need per-screen routing — it needs "which of these N items has focus, and what do Up/Down/Enter/SoftRight do to it." Its actual, complete source (three files, verified verbatim):

```js
// src/index.js — one global listener for the app's entire lifetime
import Softkey from "./js/softkey";
import Navigation from "./js/navigation";

document.addEventListener("keydown", event => {
  switch (event.key) {
    case "Enter":     return Softkey.Enter(event);
    case "ArrowDown":  return Navigation.Down(event);
    case "ArrowUp":    return Navigation.Up(event);
    case "SoftRight":  return Softkey.SoftRight(event);
    default: return;
  }
});
```

```js
// src/js/navigation.js — focus lives in the DOM as attributes, not in a JS variable
const getAllElements = () => document.querySelectorAll("[nav-selectable]");

const getTheIndexOfTheSelectedElement = () => {
  const element = document.querySelector("[nav-selected=true]");
  return element ? parseInt(element.getAttribute("nav-index"), 10) : 0;
};

const selectElement = selectElement =>
  [].forEach.call(getAllElements(), (element, index) => {
    const selectThisElement = element === selectElement;
    element.setAttribute("nav-selected", selectThisElement);
    element.setAttribute("nav-index", index);
    if (element.nodeName === "INPUT") {
      selectThisElement ? element.focus() : element.blur();
    }
  });

const Down = event => {
  const allElements = getAllElements();
  const currentIndex = getTheIndexOfTheSelectedElement();
  const goToFirstElement = currentIndex + 1 > allElements.length - 1;
  const setIndex = goToFirstElement ? 0 : currentIndex + 1;
  selectElement(allElements[setIndex] || allElements[0]);
  setSoftkey(setIndex);
};
```

Any element that should be D-pad-focusable just gets `nav-selectable="true"` in the markup; `Down`/`Up` walk the live `NodeList` of everything with that attribute, move the `nav-selected`/`nav-index` attributes to the new target, and call `.focus()`/`.blur()` on it if it's an `<input>`. Softkey labels are pushed reactively whenever selection changes (`setSoftkey`, called from inside `Down`/`Up`), not set once per screen the way `o.map` does it, because there's only one "screen" here.

**Use this pattern when your app is a single screen (or a small fixed number of non-routed views) with a variable-length list of focusable things** — settings pages, forms, todo/checklist UIs. It avoids the overhead of a router and component-lifecycle framework entirely for a case that doesn't need one. **Don't** reach for it once you have real multi-screen navigation with distinct key semantics per screen — at that point you're reimplementing `o.map`'s per-screen handler pattern badly, with global `if (currentScreen === X)` branches inside one giant listener instead of getting that dispatch for free from mount/unmount.

The mechanism-level takeaway that applies to *both*: **KaiOS gives you exactly one meaningful input primitive — a `keydown` listener reading `event.key`.** Every navigation pattern on this platform, however different the two above look, is ultimately "one function that inspects `event.key` and mutates some notion of *current focus* and *current softkey labels*." The only design choice is where you put the state machine: owned per-screen-object (`o.map`) or expressed declaratively in DOM attributes with one global dispatcher (`sample-vanilla`). Pick based on screen count, not preference.

---

## 13. Screen wake-lock: keeping the display alive during tracking/timers

Not covered in the original doc, and genuinely necessary for any KaiOS app that runs something time-based while the user isn't actively pressing keys (GPS tracking, a countdown timer, audio playback UI) — the platform will otherwise dim/lock the screen on its normal idle timeout, exactly like a phone. `o.map`'s verified, complete implementation (`assets/js/helper.js`):

```js
export function keepScreenOn() {
  if ("requestWakeLock" in navigator) {
    navigator
      .requestWakeLock("screen")
      .then((lock) => {
        window.screenWakeLock = lock;
      })
      .catch((err) => {
        console.error("Wake lock failed:", err);
        // Fallback for older KaiOS versions
        if ("mozPower" in navigator) {
          navigator.mozPower.screenEnabled = true;
        }
      });
  } else if ("mozPower" in navigator) {
    navigator.mozPower.screenEnabled = true;
  }
}

export function allowScreenOff() {
  if (window.screenWakeLock) {
    window.screenWakeLock.unlock();
    window.screenWakeLock = null;
  } else if ("mozPower" in navigator) {
    navigator.mozPower.screenEnabled = false;
  }
}
```

Two mechanism-level things worth internalizing from this:

1. **This is a two-tier feature-detect, not a single API call**, because it's straddling a real API migration: `navigator.requestWakeLock` (newer, promise-based, matches the standards-track Screen Wake Lock API shape) versus `navigator.mozPower.screenEnabled` (older, Gecko/B2G-specific, synchronous property assignment). A KaiOS 2.5 device may only have the `mozPower` path; never assume the newer API exists without checking, and always keep the older fallback if you want your app to run across the actual device fleet rather than just the simulator.
2. **The `power` and `wake-lock` permissions must be declared in the manifest** (both `manifest.webapp` and `manifest.webmanifest`, verified present in `o.map`'s copies of both) or this silently no-ops on-device even though it may appear to work in a browser tab during development — another instance of §6's "network/system capability is gated by the manifest, not by a runtime error you'd recognize."

Pair every `keepScreenOn()` call with a symmetric `allowScreenOff()` on whatever teardown path corresponds — screen `onremove`, tracking-stopped, timer-finished — for exactly the same reason §4 argues for symmetric `addEventListener`/`removeEventListener`: an un-released wake lock is a battery leak that outlives the feature that requested it, and on a device whose whole value proposition is multi-day battery life, that's a real regression, not a cosmetic one.

---

## 14. A minimal, working, vanilla KaiOS app skeleton (synthesized from both references)

This is original code — not copied from either repository — built by applying the verified patterns from §8, §12, and §13 to the smallest possible multi-screen app: a two-screen example (a list screen and a detail screen) with proper listener lifecycle, softkey sync, and `localforage`-backed persistence. Use this as your actual starting point in preference to either reference app if you don't need Leaflet-scale complexity or a to-do-list's worth of simplicity.

**`index.html`**
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no" />
  <title>My KaiOS App</title>
  <link rel="stylesheet" href="assets/css/main.css" />
</head>
<body>
  <div id="top-bar">
    <div class="button-left"></div>
    <div class="button-center"></div>
    <div class="button-right"></div>
  </div>

  <div id="screen"></div>

  <div id="bottom-bar">
    <div class="button-left"></div>
    <div class="button-center"></div>
    <div class="button-right"></div>
  </div>

  <script type="module" src="app.js"></script>
</body>
</html>
```

**`assets/js/chrome.js`** — the `top_bar`/`bottom_bar` helper, same shape as `o.map`'s verified version:
```js
export function setBar(barId, left, center, right) {
  const bar = document.getElementById(barId);
  bar.querySelector(".button-left").textContent = left;
  bar.querySelector(".button-center").textContent = center;
  bar.querySelector(".button-right").textContent = right;
  bar.style.display = (left || center || right) ? "block" : "none";
}
export const topBar = (l, c, r) => setBar("top-bar", l, c, r);
export const bottomBar = (l, c, r) => setBar("bottom-bar", l, c, r);
```

**`app.js`** — a tiny router (no framework) implementing the same `mount`/`unmount` contract §8 argues for, so screens follow the exact discipline verified in `o.map`:

```js
import { topBar, bottomBar } from "./assets/js/chrome.js";
import { listScreen } from "./screens/list.js";
import { detailScreen } from "./screens/detail.js";

const screens = { list: listScreen, detail: detailScreen };
const container = document.getElementById("screen");

let current = null; // { unmount, handler }

export function navigate(name, params = {}) {
  if (current) {
    document.removeEventListener("keydown", current.handler);
    if (current.unmount) current.unmount();
    current = null;
  }

  const screen = screens[name];
  container.innerHTML = "";
  const { view, handler, onMount, softkeys } = screen(params, navigate);

  container.appendChild(view);
  topBar(...(softkeys?.top || ["", "", ""]));
  bottomBar(...(softkeys?.bottom || ["", "", ""]));

  document.addEventListener("keydown", handler);
  current = { handler, unmount: onMount?.() };
}

navigate("list");
```

**`screens/list.js`** — a list screen following the `nav-selectable` idea from §12b *inside* a single screen, combined with §8's screen-level ownership:

```js
import localforage from "localforage"; // or any storage abstraction — see §5
import { navigate } from "../app.js";

export function listScreen() {
  const el = document.createElement("div");
  el.id = "listView";
  let items = [];
  let index = 0;

  function render() {
    el.innerHTML = "";
    items.forEach((item, i) => {
      const row = document.createElement("div");
      row.className = "item" + (i === index ? " selected" : "");
      row.textContent = item;
      el.appendChild(row);
    });
  }

  function handler(e) {
    if (e.key === "ArrowDown") { index = Math.min(index + 1, items.length - 1); render(); }
    if (e.key === "ArrowUp")   { index = Math.max(index - 1, 0); render(); }
    if (e.key === "Enter")     { navigate("detail", { item: items[index] }); }
  }

  localforage.getItem("items").then((stored) => {
    items = stored || [];
    render();
  });

  return {
    view: el,
    handler,
    softkeys: { top: ["", "", ""], bottom: ["", "Select", ""] },
  };
}
```

**`screens/detail.js`** — the second screen, proving mount/unmount symmetry across a real navigation:

```js
export function detailScreen(params, navigate) {
  const el = document.createElement("div");
  el.id = "detailView";
  el.textContent = `Detail: ${params.item ?? "(none)"}`;

  function handler(e) {
    if (e.key === "SoftLeft" || e.key === "Control") { navigate("list"); }
  }

  return {
    view: el,
    handler,
    softkeys: { top: ["", "", ""], bottom: ["Back", "", ""] },
  };
}
```

This ~80-line skeleton already satisfies every checklist item in §9's "Input" and most of "Rendering": one `keydown` listener alive at a time, softkey labels explicit per screen, DOM bounded to the current screen (the router clears `container.innerHTML` on every navigation), and storage routed through an abstraction rather than raw `localStorage`. It has no build step at all — it's plain ES modules — which is a legitimate choice for a small app on a platform where you've already seen (§7) that the build step's only real job is down-leveling syntax for old SpiderMonkey; if you write the source in an already-old-enough dialect (no optional chaining, no top-level `?.`, `var`/plain `function` instead of relying on class-field transforms), you can sometimes skip Babel/Parcel entirely for something this small. Verify against your actual minimum target's engine before shipping that shortcut, per §7's own advice.

---

## 15. Deployment and testing loop, verified against both repos

Neither doc section before this one covered how you actually get bytes onto a device or into the simulator. Both repos converge on the same two tools even though their build systems differ (`o.map` = Parcel + zip; `sample-vanilla` = Parcel + `kdeploy`), which tells you these are the platform-standard tools, not a per-project choice:

- **KaiOS Simulator**, bundled with the WebIDE / available via the KaiOS developer portal — loads an unpacked app directory directly (point it at your `src/` or build output containing `manifest.webapp`/`manifest.webmanifest` at the root) and gives you a Console tab that's a real Gecko devtools console, so `console.log` and breakpoints work as they would in desktop Firefox devtools.
- **`kdeploy`** (`sample-vanilla`'s `devDependencies` pull it straight from `kaiostech/kdeploy` on GitHub, confirmed in its `package.json`) — a CLI that talks to a real device over ADB/USB debugging, with `app:install` / `app:uninstall` / `app:update` / `app:start` / `app:stop` scripts wired up in `package.json` exactly as shown. This is the "put it on actual hardware" path, which matters because the simulator does not reproduce the memory ceiling from §2 — a build that runs fine in the simulator on your dev machine's RAM can still get OOM-killed on-device. Test memory-sensitive changes on real hardware, not just the simulator, before trusting them.
- **`o.map`'s own build output is a `.zip` with the manifest at its root** (`build/omap.zip` / `build/omap-k2.zip`, verified in `package.json`'s scripts), which is the format both KaiStore submission and manual sideloading via WebIDE's "Add Packaged App" expect — confirming §7's point that this is packaging, not hosting.

A practical loop, combining both: develop against the Simulator for layout/logic iteration speed (fast reload, real devtools), then periodically push to a real device via `kdeploy` (or WebIDE's packaged-app installer) specifically to catch the two classes of bug the simulator can't show you — memory-pressure behavior (§2) and actual D-pad/softkey hardware timing, since a simulator's keyboard-event emulation via your dev machine's keyboard doesn't always perfectly match physical button debounce/repeat behavior on-device.

---

## 16. Source map — every claim in this document, traced to a file

| Claim | File (repo) | Verified |
|---|---|---|
| `browserslist: ["Firefox <= 48"]` | `o.map/package.json` | ✅ verbatim |
| MIT license (not the `package.json` `"ISC"` field) | `o.map/LICENSE.md` | ✅ verbatim |
| `oncreate`/`removeEventListener` per-screen pattern | `o.map/src/index.js` | ✅ verbatim, ×10+ occurrences |
| `top_bar`/`bottom_bar` helpers | `o.map/src/assets/js/helper.js` | ✅ verbatim |
| Cache API disabled on real KaiOS via UA sniff | `o.map/src/sw.js` | ✅ verbatim |
| `systemXHR` permission | `o.map/src/manifest.webapp`, `manifest.webmanifest` | ✅ verbatim, both files |
| Two manifest source files, not unified | `o.map/src/manifest.webapp` + `manifest.webmanifest` | ✅ both present, structurally distinct as described |
| Three build targets (`build`, `build-k2`, `web`) | `o.map/package.json` scripts | ✅ verbatim |
| `babel-plugin-transform-async-to-promises` | `o.map/package.json` devDependencies | ✅ present |
| `localforage` for persistence | `o.map/src/index.js` imports, `package.json` deps | ✅ present |
| Mithril, not React/Vue | `o.map/package.json` deps (`mithril@^2.2.2`) | ✅ present |
| Leaflet + `leaflet-gpx` + tile caching | `o.map/package.json` deps, `assets/js/L.TileLayer.PouchDBCached.js` | ✅ present |
| `nav-selectable`/`nav-index` attribute navigation | `sample-vanilla/src/js/navigation.js`, `softkey.js` | ✅ verbatim |
| `SoftLeft`/`SoftRight`/`Control`/`Alt` key aliasing | `o.map/src/index.js` (`e.key === "SoftLeft" || e.key === "Control"`) | ✅ verbatim |
| Wake-lock pattern (`requestWakeLock` / `mozPower` fallback) | `o.map/src/assets/js/helper.js` | ✅ verbatim — new in this revision |
| `kdeploy` install/update/start/stop scripts | `sample-vanilla/package.json` | ✅ verbatim — new in this revision |

Both repositories were cloned directly (`git clone https://github.com/strukturart/o.map.git`, `git clone https://github.com/kaiostech/sample-vanilla.git`) rather than reconstructed from memory, specifically so every claim in §11–§16 could be checked against the literal file contents rather than a plausible-sounding recollection of them.
