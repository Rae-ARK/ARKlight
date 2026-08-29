"""
JS Backend.

v0.003 milestone (extended in v0.003, then again in v0.0035). ARKlight
does not compile Python to JavaScript, and components do not accept
arbitrary JS strings -- both would break "the browser never executes
Python" in spirit and "one obvious way" in practice (every site
inventing its own inline-JS dialect). Instead, following the same model
as Alpine.js/htmx (describe behavior with HTML attributes; a small
shipped runtime does the rest, no build step), ARKlight ships one
static `arklight.js` implementing a fixed, documented vocabulary:

- `toggle`     -- toggles a CSS class on `target` element(s). Which
                  class is controlled by `toggle_class` (default
                  "is-open"). This is enough for menus, accordions,
                  and disclosure widgets without writing any JS.
- `scroll-to`  -- smooth-scrolls `target` into view.
- `copy`       -- copies `target`'s text content to the clipboard, and
                  briefly swaps the clicked element's own text to
                  confirm it worked (a "Copy" button next to a code
                  snippet or a share link).
- `dismiss`    -- adds `toggle_class` (default "hidden") to `target`
                  element(s) and leaves it there -- a one-way hide, for
                  closing a banner/alert/cookie-notice permanently
                  rather than toggling it back and forth.

A component opts in with `on_click="toggle"` (or `"scroll-to"`,
`"copy"`, `"dismiss"`) plus a `behavior_target="<css selector>"` prop --
validated against `arklight.ir.schema.KNOWN_BEHAVIORS` at the
Validation stage, so a typo in a behavior name is caught at build time,
not silently ignored in the browser.

v0.0035 adds a second, closed vocabulary on top of the above: reactive
page state. A page that declares `State("count", 0)` gets a small
reactive core (a `createState` store, a `data-ark-bind` re-render pass,
and an action dispatcher) plus only the `Action.*` fragments
(`arklight/backend/js/actions/`) that page's `on_click=` values
actually reference. Pages with no `State(...)` get none of this --
same "only ship what's used" discipline v0.0035 also brought to the
named-behavior runtime below. See docs/DESIGN-NOTES.md ("v0.0035:
stateful JS -- capability, not vocabulary") for the full design.

Every behavior/action fragment here is a small, statically-readable JS
function -- there is no `eval`, no `new Function`, no string ever
executed as code. The registries (`arklight.ir.schema.BEHAVIOR_REGISTRY`
/ `ACTION_REGISTRY`) are what's open to new *data*; the runtime itself
never becomes a general-purpose interpreter.

The runtime also auto-highlights the current page's nav link (any `<a>`
inside `.nav` whose resolved URL matches the current page) with an
`is-active` class -- zero wiring required, since every site with a
`nav()` gets this for free.

Stage 1 (staged reactive-core expansion, see
`arklight/backend/js/vdom.py`): pages with state now re-render their
`data-ark-bind` elements through a vendored snabbdom core (`init` +
`h`, no optional modules) instead of a raw `el.textContent = ...`
assignment. Behavior is unchanged from the outside -- this only swaps
the re-render mechanism for a real diff/patch algorithm, so later
stages (list rendering, conditional show/hide, attribute binding) have
a diffing engine to build on instead of each hand-rolling one.

Stage 2 adds reactive class binding: `bind_class=Bind.when("active",
"is-active")` toggles a class as `active`'s truthiness changes,
compiled to `data-ark-bind-class="<class>"` +
`data-ark-bind-class-state="<key>"`. This one deliberately does *not*
go through the vdom core -- the bare vendored core has no class
module, and re-deriving an element's vdom selector to add/remove a
class would make `patch()` treat it as a different vnode and remount
the element (dropping any already-wired listeners) -- so it's a
direct, one-line `classList.toggle` instead, run in its own pass
(`renderClassBindings`) alongside `renderBindings`.

Stage 3 adds event modifiers: `Action.set("saved", True).debounce(300)`
/ `Action.remove("items", 0).with_modifiers("prevent", "stop", "once")`
attach `prevent`/`stop`/`once`/`debounce:<ms>`/`throttle:<ms>` tokens
(`arklight.ir.schema.MODIFIER_REGISTRY`) to an `ActionRef`. At Stage 3
these compiled to `data-ark-modifiers="prevent,debounce:300"`, read by
one small shipped wrapper, `arkApplyModifiers`, that decided
*if*/*when* the underlying action actually ran. `htmx-2` (below)
replaced that attribute and wrapper with `hx-trigger` compiled at
build time. `prevent` is, and always was, honored by construction:
`wireActions`'s click listener unconditionally calls
`event.preventDefault()` regardless of any modifier, so there was
never a second effect for that particular token to add. Named
behaviors (`on_click="toggle"`, etc.) have no modifier-attaching API
yet -- deliberately left for a future addendum rather than
speculatively wired up now.

`htmx-1` (see `docs/Backends/HTMX-INTEGRATION.md` "Stage 1 --
Behaviors" / `docs/Backends/REFACTOR-INDEX.md` row 4) replaces the
named-behavior wiring pass with HTMX. `wireBehaviors()` and its
`_behaviors_block` are gone -- there is no more `DOMContentLoaded`
query/`addEventListener` loop over `[data-ark-on-click]` elements,
because `arklight/backend/html/attrs.py` now compiles a string
`on_click` straight to `hx-on:click="arkRunBehavior('<name>', this)"`
and HTMX's own attribute-processing pass (which runs on page load and
on any DOM HTMX subsequently swaps in, not just once at
`DOMContentLoaded`) does the wiring instead. What stays on the
ARKlight side is only what HTMX has no equivalent for: the closed
`behaviors` dispatch object itself (still just the four
`BEHAVIOR_FRAGMENTS` entries this site's IR actually references, same
"only ship what's used" discipline as before) and a one-line
`arkRunBehavior(name, el)` wrapper that looks a name up in it and
guards the call in `try`/`catch` -- the same guarantee
`wireBehaviors()`'s per-element `try`/`catch` used to give, just
scoped per-*call* instead of per-*wiring-pass* now that there is no
wiring pass to wrap. Both are attached to `window` because HTMX
evaluates `hx-on:click`'s value in the browser's normal (non-strict,
non-module) global scope, not inside this file's own IIFE closure --
see `arklight/backend/js/htmx.py`'s module docstring for why the two
scripts don't otherwise need to share scope.

Vendored HTMX itself (`arklight/backend/js/htmx.py`, upstream 2.0.10,
Zero-Clause BSD) ships whenever a page uses a named behavior *or*
declares state -- see `_build_runtime_js`'s `needs_htmx`. State-only
pages don't yet emit any `hx-*` attribute (that's `htmx-2`/`htmx-3`
territory: modifiers and `Action.*` dispatch still go through
`data-ark-modifiers`/`wireActions()` unchanged by this stage), but
`docs/Backends/REFACTOR-INDEX.md` row 4 scopes HTMX's inclusion to
"behaviors or state" rather than "behaviors only" so that landing
`htmx-2`/`htmx-3` later doesn't also have to touch this
already-shipped condition.

`htmx-2` (see `docs/Backends/HTMX-INTEGRATION.md` "Stage 2 --
Modifiers" / `docs/Backends/REFACTOR-INDEX.md` row 5) removes
`arkApplyModifiers` entirely -- `arklight/backend/html/attrs.py` now
compiles an `ActionRef`'s modifier tokens into an `hx-trigger`
attribute at build time instead of the `data-ark-modifiers` attribute
this runtime used to parse, so there is no attribute left for a
runtime parser to read. `wireActions` (`runtime/dispatch.py`) no
longer wraps its dispatch through that function -- it calls the action
directly on every click, same as before Stage 3 existed. This is a
deliberate, documented, temporary gap: `hx-trigger` is compiled into
the page's markup by this stage, but nothing reads it as a *trigger*
yet, so `debounce`/`throttle`/`once`/`stop` have no runtime effect
until `htmx-3` (row 6) replaces `wireActions`'s hand-rolled loop with
an `htmx:beforeRequest` interceptor that HTMX's own trigger processing
actually feeds. `prevent` is unaffected either way, per Stage 3's note
above.

`htmx-3` (see `docs/Backends/HTMX-INTEGRATION.md` "Stage 3 -- Replace
`wireActions()` wiring loop" / `docs/Backends/REFACTOR-INDEX.md` row 6)
deletes `wireActions`'s `querySelectorAll('[data-ark-on-click^=
"action:"]')`/`forEach`/per-element-`addEventListener` loop entirely.
In its place, `runtime/dispatch.py`'s `ACTION_INTERCEPTOR_JS` registers
one delegated `click` listener on `document` (`wireActionInterceptor`)
that resolves the clicked element via `Element.closest()` -- a single
registration instead of a per-element wiring pass, matching the "audit
and remove hand-rolled plumbing" spirit `htmx-2` left for this stage.
See `runtime/dispatch.py`'s module docstring for why this is a
delegated native `click` listener rather than the literal
`htmx:beforeRequest` interceptor `HTMX-INTEGRATION.md` describes: that
event is only dispatched by HTMX's own request path, which requires a
request-verb attribute (`hx-get`/`hx-post`/etc) that `Action.*(...)`
buttons -- being client-local, not server requests -- deliberately
never carry, so wiring only through it would silently drop every
unmodified action button's click handling. `data-ark-on-click="action:
..."`/`data-ark-action-state`/`data-ark-action-args` are unchanged --
`REFACTOR-INDEX.md` row 6 scopes this stage to the JS backend only.
`initState()`/`renderBindings()`/`renderClassBindings()` are
untouched; only the `DOMContentLoaded` call site's `wireActions(store)`
becomes `wireActionInterceptor(store)` below.

`htmx-4` (see `docs/Backends/JS-BACKEND-REFACTOR-PLAN.md` "The
app-illusion problem, stated precisely" / `docs/Backends/
REFACTOR-INDEX.md` row 9) is app-shell navigation:
`Site(app_shell=True)` (see `arklight/backend/html/page_render.py`)
emits `hx-boost="true"` on `<body>`, so same-origin link clicks become
an in-place AJAX swap instead of a full document reload -- the fix for
packaging backends (Android/KaiOS/Desktop) wrapping ARKlight's
otherwise real multi-page output in a shell whose whole purpose is to
*not* look like a browser. This stage's audit surfaced two gaps a
boosted swap opens that the runtime as it stood through `htmx-3`
didn't handle:

1. **`needs_htmx` below now also ships HTMX for `ir.app_shell` alone**
   -- previously gated on "a named behavior or `State(...)` is used
   *anywhere on the site*" (see the `htmx-1` paragraph above), which
   left a real gap: `arklight.js` is one shared file across every page
   (`SCRIPT_PATH`), but a plain nav-only page in an `app_shell` site
   with no behaviors or state used *anywhere* would previously have
   shipped without HTMX loaded at all -- `hx-boost` requires HTMX's
   own click-interception to do anything, so clicking away from such a
   page would have silently fallen back to a real document navigation.
2. **`DOMContentLoaded` only ever fires once per real document
   load; a boosted swap doesn't refire it.** Nothing before this
   stage re-ran nav-link highlighting or (re-)hydrated a page's
   `State(...)` after navigating to a *different* page via a boosted
   link -- `highlightActiveNavLink()`/`initState()`/`renderBindings()`/
   `renderClassBindings()` all ran exactly once, at the very first
   page load, and never again. `arkInitPage()` below is the same init
   logic, just named and made re-callable: wired to `DOMContentLoaded`
   unconditionally (unchanged initial-load behavior) and, only for
   `app_shell` sites, to htmx's own `"htmx:afterSettle"` event too --
   the standard hook for "new content just settled into the DOM."
   `wireActionInterceptor` is registered exactly once regardless (see
   `runtime/dispatch.py`'s module docstring for why re-registering it
   on every boosted swap would be a bug, and how the getter-based
   signature avoids it).

Also see `arklight/backend/html/page_render.py`'s `_render_page`
docstring for a third gap this stage fixes on the HTML side: why a
state page's `data-ark-state` blob moves off `<body>` (whose own
attributes a boosted swap never updates) when `app_shell=True`.
"""

from __future__ import annotations

from arklight.ast.nodes import ActionRef
from arklight.backend.base import Backend
from arklight.backend.js.actions import ACTION_FRAGMENTS
from arklight.backend.js.behaviors import BEHAVIOR_FRAGMENTS
from arklight.backend.js.htmx import HTMX_JS
from arklight.backend.js.runtime import NAV_HIGHLIGHT_JS as _NAV_HIGHLIGHT_JS
from arklight.backend.js.runtime import NOTIFY_JS as _NOTIFY_JS
from arklight.backend.js.runtime import STATE_CORE_JS as _STATE_CORE_JS
from arklight.backend.js.vdom import SNABBDOM_CORE_JS
from arklight.ir.build import IRNode, WebsiteIR

# Where the HTML backend expects to find the generated runtime,
# relative to the output directory root.
SCRIPT_PATH = "arklight.js"

# _NOTIFY_JS / _NAV_HIGHLIGHT_JS / _STATE_CORE_JS used to be defined
# inline here as triple-quoted string constants. `refactor-0` (see
# docs/Backends/REFACTOR-INDEX.md) split them into
# arklight/backend/js/runtime/{state,bindings,modifiers,dispatch,nav,
# notify}.py, mirroring the actions/ and behaviors/ per-file pattern.
# The values imported above are byte-for-byte identical to the old
# inline constants -- pure refactor, no generated JS output change.


def _walk(node: IRNode):
    yield node
    for child in node.children:
        if isinstance(child, IRNode):
            yield from _walk(child)


def _collect_usage(ir: WebsiteIR) -> tuple[set[str], set[str], bool]:
    """
    Inspect the site's IR for what the runtime actually needs to ship:
    which named behaviors are referenced, which actions are referenced,
    and whether any page declares state at all.
    """
    used_behaviors: set[str] = set()
    used_actions: set[str] = set()
    has_state = any(page.state for page in ir.pages)

    for page in ir.pages:
        for node in _walk(page.root):
            on_click = node.props.get("on_click")
            if isinstance(on_click, str):
                used_behaviors.add(on_click)
            elif isinstance(on_click, ActionRef):
                used_actions.add(on_click.action)

    return used_behaviors, used_actions, has_state


def _behaviors_block(used_behaviors: set[str]) -> str | None:
    # htmx-1: no more wiring loop here -- HTMX's own hx-on:click
    # processing is the wiring pass now (see arklight/backend/html/
    # attrs.py and this file's module docstring). What's left is just
    # the closed dispatch object (`arkBehaviors`, still only the
    # fragments this site's IR actually references) and a one-line
    # lookup-and-call wrapper (`arkRunBehavior`) that HTMX's
    # hx-on:click="arkRunBehavior('<name>', this)" attribute value
    # calls directly. Both attach to `window` because HTMX evaluates
    # that attribute's value in normal global scope, not inside this
    # file's own IIFE.
    if not used_behaviors:
        return None
    fragments = [
        BEHAVIOR_FRAGMENTS[name] for name in sorted(used_behaviors) if name in BEHAVIOR_FRAGMENTS
    ]
    if not fragments:
        return None
    entries = ",\n".join(fragments)
    return (
        "  var arkBehaviors = {\n" + entries + "\n  };\n"
        "  window.arkBehaviors = arkBehaviors;\n\n"
        "  function arkRunBehavior(name, el) {\n"
        "    var behavior = arkBehaviors[name];\n"
        "    if (!behavior) return;\n"
        "    try {\n"
        "      behavior(el);\n"
        "    } catch (err) {\n"
        '      arkNotify("Something went wrong running this action -- an unsupported or unexpected case was hit.");\n'
        "    }\n"
        "  }\n"
        "  window.arkRunBehavior = arkRunBehavior;"
    )


def _actions_block(used_actions: set[str]) -> str:
    fragments = [
        ACTION_FRAGMENTS[name] for name in sorted(used_actions) if name in ACTION_FRAGMENTS
    ]
    entries = ",\n".join(fragments)
    actions_obj = "  var actions = {\n" + entries + "\n  };\n\n" if fragments else "  var actions = {};\n\n"
    return actions_obj + _STATE_CORE_JS


def _build_runtime_js(ir: WebsiteIR) -> str:
    used_behaviors, used_actions, has_state = _collect_usage(ir)

    behaviors_block = _behaviors_block(used_behaviors)

    # htmx-1 (docs/Backends/REFACTOR-INDEX.md row 4): vendored HTMX
    # ships whenever a page uses a named behavior or declares state --
    # see arklight/backend/js/htmx.py's module docstring for why the
    # "or state" half of this condition is scoped ahead of what this
    # stage alone strictly needs. htmx-4 (row 9) adds a third
    # condition: `ir.app_shell` alone, independent of behaviors/state
    # -- see this module's docstring, htmx-4 paragraph, point 1, for
    # why a plain nav-only page in an app_shell site still needs HTMX
    # loaded (hx-boost does nothing without it).
    needs_htmx = bool(behaviors_block) or has_state or ir.app_shell

    parts: list[str] = [
        "// Generated by ARKlight -- v0.0035 runtime + Stage 1-2 of the",
        "// reactive-core vdom staging (vdom core, class binding), plus",
        "// htmx-1 (named behaviors wire through vendored HTMX's",
        "// hx-on:click instead of a hand-rolled wiring pass), htmx-2",
        "// (Action.* event modifiers compile to hx-trigger instead of a",
        "// shipped modifier-parsing runtime function), htmx-3",
        "// (Action.* dispatch wires through a single delegated click",
        "// listener instead of a per-element wiring pass), and htmx-4",
        "// (Site(app_shell=True) boosts navigation via hx-boost; page",
        "// init re-runs after a boosted swap, not just at first load).",
        "// Implements only the named behaviors and Action.*(...)",
        "// references this site actually uses -- see",
        "// arklight.ir.schema.BEHAVIOR_REGISTRY / ACTION_REGISTRY /",
        "// MODIFIER_REGISTRY. No other JavaScript runs on this site.",
        "// Pages with state also carry a vendored snabbdom core",
        "// (init + h, no optional modules) -- see",
        "// arklight/backend/js/vdom.py.",
    ]

    if needs_htmx:
        parts.append("")
        parts.append(HTMX_JS)

    parts.append("")
    parts.append("(function () {")
    parts.append('  "use strict";')
    parts.append("")

    needs_notify = bool(behaviors_block) or has_state
    if needs_notify:
        parts.append(_NOTIFY_JS)
        parts.append("")

    if behaviors_block:
        parts.append(behaviors_block)
        parts.append("")

    if has_state:
        parts.append(SNABBDOM_CORE_JS)
        parts.append("")
        parts.append(_actions_block(used_actions))
        parts.append("")

    parts.append(_NAV_HIGHLIGHT_JS)
    parts.append("")

    # htmx-4: DOMContentLoaded only ever fires once per real document
    # load, but a boosted navigation (app_shell's hx-boost) swaps
    # <body>'s content in place with no new DOMContentLoaded event --
    # so nothing would otherwise re-run for the page just swapped in.
    # arkInitPage() is the same init logic prior stages ran directly
    # inside the DOMContentLoaded handler, just named and made
    # re-callable, so it can also run after a boosted swap settles.
    if has_state:
        parts.append("  var arkStore = null;")
        parts.append("")

    init_body = ["    highlightActiveNavLink();"]
    if has_state:
        init_body.append("    arkStore = initState();")
        init_body.append(
            "    if (arkStore) { renderBindings(arkStore); renderClassBindings(arkStore); }"
        )

    parts.append("  function arkInitPage() {")
    parts.extend(init_body)
    parts.append("  }")
    parts.append("")

    ready_calls = ["    arkInitPage();"]
    if has_state:
        # Registered exactly once, here -- never from inside
        # arkInitPage() itself, and never again on a later boosted
        # swap. document is never replaced by hx-boost, so a second
        # registration would stack a second listener closing over a
        # now-stale store, double-firing every click. The getter
        # closure (see runtime/dispatch.py) always reads whatever
        # arkStore currently holds, so one registration is enough for
        # the lifetime of the page, boosted navigation or not.
        ready_calls.append("    wireActionInterceptor(function () { return arkStore; });")

    parts.append('  document.addEventListener("DOMContentLoaded", function () {')
    parts.extend(ready_calls)
    parts.append("  });")

    if ir.app_shell:
        # "htmx:afterSettle" is htmx's own post-swap-and-settle
        # lifecycle event -- the app-shell equivalent of
        # DOMContentLoaded for content a boosted navigation just
        # brought in. Only registered for app_shell sites: on a plain
        # site hx-boost is never active, so this event never fires and
        # the extra listener would be dead weight.
        parts.append("")
        parts.append('  document.body.addEventListener("htmx:afterSettle", arkInitPage);')

    parts.append("})();")
    parts.append("")

    return "\n".join(parts)


class JSBackend(Backend):
    name = "js"

    def render(self, ir: WebsiteIR) -> dict[str, str]:
        return {SCRIPT_PATH: _build_runtime_js(ir)}
