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
"""

from __future__ import annotations

from arklight.ast.nodes import ActionRef
from arklight.backend.base import Backend
from arklight.backend.js.actions import ACTION_FRAGMENTS
from arklight.backend.js.behaviors import BEHAVIOR_FRAGMENTS
from arklight.ir.build import IRNode, WebsiteIR

# Where the HTML backend expects to find the generated runtime,
# relative to the output directory root.
SCRIPT_PATH = "arklight.js"

_NOTIFY_JS = """  function arkNotify(message) {
    // Self-contained on-page notice for runtime edge cases the fixed
    // behavior/action vocabulary didn't anticipate -- deliberately
    // inline-styled (not a `.stack`/`.card`/etc. class) so it renders
    // correctly even on a page whose stylesheet this failure might
    // itself be related to, and wrapped in its own try/catch so a
    // notification failure can never become a second, worse error.
    try {
      var el = document.getElementById("ark-notify");
      if (!el) {
        el = document.createElement("div");
        el.id = "ark-notify";
        el.setAttribute("role", "alert");
        el.style.cssText =
          "position:fixed;bottom:1rem;right:1rem;left:auto;max-width:22rem;" +
          "background:#111827;color:#f9fafb;padding:0.75rem 1rem;" +
          "border-radius:0.5rem;font:14px/1.4 system-ui,sans-serif;" +
          "box-shadow:0 4px 12px rgba(0,0,0,.35);z-index:2147483647;";
        document.body.appendChild(el);
      }
      el.textContent = message;
      el.style.display = "block";
      clearTimeout(el._arkNotifyTimer);
      el._arkNotifyTimer = setTimeout(function () {
        el.style.display = "none";
      }, 6000);
    } catch (notifyErr) {
      /* notification is best-effort; never let it throw */
    }
  }"""

_NAV_HIGHLIGHT_JS = """  function highlightActiveNavLink() {
    document.querySelectorAll(".nav a").forEach(function (link) {
      var here = location.href.replace(/#.*$/, "");
      var there = link.href.replace(/#.*$/, "");
      if (there === here) {
        link.classList.add("is-active");
      }
    });
  }"""

_STATE_CORE_JS = """  function createState(initial) {
    var state = Object.assign({}, initial);
    var listeners = [];
    return {
      get: function (key) { return state[key]; },
      set: function (key, value) {
        state[key] = value;
        listeners.forEach(function (fn) { fn(); });
      },
      reset: function (key) {
        state[key] = initial[key];
        listeners.forEach(function (fn) { fn(); });
      },
      subscribe: function (fn) { listeners.push(fn); }
    };
  }

  function renderBindings(store) {
    document.querySelectorAll("[data-ark-bind]").forEach(function (el) {
      var key = el.getAttribute("data-ark-bind");
      el.textContent = store.get(key);
    });
  }

  function initState() {
    var raw = document.body.getAttribute("data-ark-state");
    if (!raw) return null;
    try {
      var store = createState(JSON.parse(raw));
      store.subscribe(function () { renderBindings(store); });
      return store;
    } catch (err) {
      arkNotify("This page's saved state couldn't be loaded -- interactive features on this page may not work.");
      return null;
    }
  }

  function wireActions(store) {
    if (!store) return;
    document.querySelectorAll('[data-ark-on-click^="action:"]').forEach(function (el) {
      try {
        var actionName = el.getAttribute("data-ark-on-click").slice("action:".length);
        var stateKey = el.getAttribute("data-ark-action-state");
        var argsRaw = el.getAttribute("data-ark-action-args");
        var args = argsRaw ? JSON.parse(argsRaw) : {};
        var action = actions[actionName];
        if (!action) return;
        el.addEventListener("click", function (event) {
          event.preventDefault();
          try {
            action(store, stateKey, args);
          } catch (err) {
            arkNotify("Something went wrong updating this page -- an unsupported or unexpected case was hit.");
          }
        });
      } catch (err) {
        // One malformed element (e.g. bad data-ark-action-args JSON)
        // must not abort wiring for every other element in this loop.
        arkNotify("One of this page's interactive elements couldn't be set up.");
      }
    });
  }"""


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
        "// Generated by ARKlight -- v0.0035 runtime.",
        "// Implements only the named behaviors and Action.*(...) references",
        "// this site actually uses -- see arklight.ir.schema.BEHAVIOR_REGISTRY",
        "// and ACTION_REGISTRY. No other JavaScript runs on this site.",
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
        ready_calls.append("    if (store) { renderBindings(store); }")
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
