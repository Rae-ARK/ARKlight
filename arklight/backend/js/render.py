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
(`arklight.ir.schema.MODIFIER_REGISTRY`) to an `ActionRef`, compiled to
`data-ark-modifiers="prevent,debounce:300"`. One small wrapper,
`arkApplyModifiers`, reads that attribute once per element and decides
*if*/*when* the underlying action actually runs -- not duplicated into
every `ACTION_FRAGMENTS` entry. Shipped as part of the state runtime
core (alongside `renderClassBindings`) whenever a page declares
`State(...)`, the same "ship per-feature, not per-element-usage"
granularity that core already uses, rather than a separate detection
pass over whether any given site's `ActionRef`s actually carry
modifiers. `prevent` is honored by construction: `wireActions`'s click
listener already unconditionally calls `event.preventDefault()`
(unchanged, pre-Stage-3 behavior), so there is nothing left for the
modifier itself to additionally do. Named behaviors (`on_click=
"toggle"`, etc.) have no modifier-attaching API yet -- deliberately
left for a future addendum rather than speculatively wired up now.
"""

from __future__ import annotations

from arklight.ast.nodes import ActionRef
from arklight.backend.base import Backend
from arklight.backend.js.actions import ACTION_FRAGMENTS
from arklight.backend.js.behaviors import BEHAVIOR_FRAGMENTS
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
    if not used_behaviors:
        return None
    fragments = [
        BEHAVIOR_FRAGMENTS[name] for name in sorted(used_behaviors) if name in BEHAVIOR_FRAGMENTS
    ]
    if not fragments:
        return None
    entries = ",\n".join(fragments)
    return (
        "  var behaviors = {\n" + entries + "\n  };\n\n"
        "  function wireBehaviors() {\n"
        '    document.querySelectorAll("[data-ark-on-click]").forEach(function (el) {\n'
        "      try {\n"
        '        var name = el.getAttribute("data-ark-on-click");\n'
        "        var behavior = behaviors[name];\n"
        "        if (!behavior) return;\n"
        '        el.addEventListener("click", function (event) {\n'
        "          event.preventDefault();\n"
        "          try {\n"
        "            behavior(el);\n"
        "          } catch (err) {\n"
        '            arkNotify("Something went wrong running this action -- an unsupported or unexpected case was hit.");\n'
        "          }\n"
        "        });\n"
        "      } catch (err) {\n"
        "        // One malformed element must not abort wiring for\n"
        "        // every other behavior-tagged element on the page.\n"
        '        arkNotify("One of this page\'s interactive elements couldn\'t be set up.");\n'
        "      }\n"
        "    });\n"
        "  }"
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

    parts: list[str] = [
        "// Generated by ARKlight -- v0.0035 runtime + Stage 1-3 of the",
        "// reactive-core vdom staging (vdom core, class binding, event",
        "// modifiers). Implements only the named behaviors and",
        "// Action.*(...) references this site actually uses -- see",
        "// arklight.ir.schema.BEHAVIOR_REGISTRY / ACTION_REGISTRY /",
        "// MODIFIER_REGISTRY. No other JavaScript runs on this site.",
        "// Pages with state also carry a vendored snabbdom core (init + h,",
        "// no optional modules) -- see arklight/backend/js/vdom.py.",
        "(function () {",
        '  "use strict";',
        "",
    ]

    behaviors_block = _behaviors_block(used_behaviors)
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

    ready_calls = []
    if behaviors_block:
        ready_calls.append("    wireBehaviors();")
    ready_calls.append("    highlightActiveNavLink();")
    if has_state:
        ready_calls.append("    var store = initState();")
        ready_calls.append("    if (store) { renderBindings(store); renderClassBindings(store); }")
        ready_calls.append("    wireActions(store);")

    parts.append('  document.addEventListener("DOMContentLoaded", function () {')
    parts.extend(ready_calls)
    parts.append("  });")
    parts.append("})();")
    parts.append("")

    return "\n".join(parts)


class JSBackend(Backend):
    name = "js"

    def render(self, ir: WebsiteIR) -> dict[str, str]:
        return {SCRIPT_PATH: _build_runtime_js(ir)}
