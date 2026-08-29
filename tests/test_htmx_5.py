"""
`htmx-5` (see `docs/Backends/HTMX-INTEGRATION.md` "Implementation
ladder" Stage 4 / `docs/Backends/REFACTOR-INDEX.md` row 10): audit and
remove remaining hand-rolled plumbing in `arklight.js` that duplicates
HTMX.

The audit's actual finding cuts the other way from what the stage
description implies. `htmx-1`'s mechanism for named behaviors --
`hx-on:click="arkRunBehavior('<name>', this)"` -- routes through
HTMX's own `hx-on:*` attribute-processing internals, which build a
function from the attribute's *string value* with the `Function`
constructor (`new Function("event", attributeValue)`) before calling
it. That's an eval-equivalent operation, gated only by
`htmx.config.allowEval` (`true` by default in the vendored release).
Every named-behavior click on every ARKlight site was, through
`htmx-4`, routing through that path -- directly contradicting this
project's own stated invariant (`arklight/backend/js/render.py`'s
module docstring: "there is no eval, no new Function, no string ever
executed as code"). `arkRunBehavior`'s own body was always a small,
fixed, statically-readable function; the eval-equivalent step was
HTMX's attribute-processing machinery *getting there*, not anything
ARKlight wrote.

This file's tests are grouped to mirror the actual fix:

1. HTML output no longer contains `hx-on:click` for a named behavior
   -- it compiles to `data-ark-on-click="behavior:<name>"` instead,
   matched-pair with the `"action:<name>"` shape `ActionRef` already
   used.
2. The JS runtime's click dispatch (renamed `wireClickInterceptor`)
   handles both shapes through one delegated listener, with no
   `window`-attached `arkBehaviors`/`arkRunBehavior` pair left for
   HTMX's attribute evaluation to reach.
3. A behavior-only page (no `State(...)`) now ships no HTMX at all --
   `hx-on:click` processing was the only reason it ever needed to.
4. Whenever HTMX *does* ship, `htmx.config.allowEval = false` is set
   as defense-in-depth, closing the other vendored-HTMX paths that
   construct a function from a string (`hx-vals`/`hx-vars`,
   bracket-syntax `hx-trigger` filters) -- paths ARKlight's compiler
   never emits into.
5. The actual regression this stage exists to prevent: no
   ARKlight-compiled HTML output, for any behavior/action/state
   combination, ever contains `hx-on:*`, `hx-vals`, or `hx-vars`.

See `tests/test_htmx_3.py`, `tests/test_htmx_4.py`,
`tests/test_html_attrs.py`, `tests/test_html_backend.py`,
`tests/test_js_backend.py`, `tests/test_js_error_handling.py`,
`tests/test_class_binding.py`, `tests/test_event_modifiers.py`,
`tests/test_stateful_js_vocabulary_addendum.py`, and
`tests/test_refactor_0.py` for this stage's updates to prior stages'
own dedicated coverage (mostly the `wireActionInterceptor` ->
`wireClickInterceptor` / `ACTION_INTERCEPTOR_JS` ->
`CLICK_INTERCEPTOR_JS` rename, plus two genuine behavior changes:
`STATE_CORE_JS` no longer bundles the interceptor, and a pure-display
state page no longer ships an unused `actions` object).
"""

from arklight.api import Action, Button, Page, Site, State, Text
from arklight.backend.html.render import HTMLBackend
from arklight.backend.js.htmx import HTMX_JS
from arklight.backend.js.render import JSBackend, SCRIPT_PATH
from arklight.ir.build import build_website_ir
from arklight.ir.normalize import normalize_ark_ast
from arklight.ir.validate import validate_ark_ast


def _ir(pages, *, app_shell=False):
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    return build_website_ir("site", normalized, app_shell=app_shell)


def _plain_ir():
    return _ir({"/": Page(Text("hi"))})


def _behavior_only_ir():
    return _ir({"/": Page(Button("Show", on_click="toggle", behavior_target="#panel"))})


def _stateful_ir():
    pages = {
        "/": Page(
            State("count", 0),
            Button("+1", on_click=Action.increment("count")),
        )
    }
    return _ir(pages)


def _combined_ir():
    pages = {
        "/": Page(
            State("count", 0),
            Button("+1", on_click=Action.increment("count")),
            Button("Copy", on_click="copy", behavior_target="#snippet"),
        )
    }
    return _ir(pages)


# ---------------------------------------------------------------------------
# 1. HTML side: data-ark-on-click="behavior:<name>", not hx-on:click.
# ---------------------------------------------------------------------------


def test_named_behavior_compiles_to_data_ark_on_click_with_behavior_prefix():
    tree = Page(Button("Show", on_click="toggle", behavior_target="#panel"))
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert 'data-ark-on-click="behavior:toggle"' in html
    assert "hx-on:click" not in html
    assert "arkRunBehavior" not in html


def test_every_known_behavior_uses_the_behavior_prefix():
    for name in ("toggle", "scroll-to", "copy", "dismiss"):
        tree = Page(Button("x", on_click=name, behavior_target="#t"))
        html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
        assert f'data-ark-on-click="behavior:{name}"' in html
        assert "hx-on:" not in html


def test_action_ref_prefix_is_unaffected_by_this_stage():
    tree = Page(State("count", 0), Button("+1", on_click=Action.increment("count")))
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert 'data-ark-on-click="action:increment"' in html


def test_behavior_target_and_toggle_class_are_unaffected():
    tree = Page(
        Button(
            "Show",
            on_click="toggle",
            behavior_target="#panel",
            toggle_class="hidden",
        )
    )
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert 'data-ark-target="#panel"' in html
    assert 'data-ark-toggle-class="hidden"' in html


# ---------------------------------------------------------------------------
# 2. JS side: one delegated listener, no window-attached pair.
# ---------------------------------------------------------------------------


def test_click_interceptor_dispatches_both_prefixes():
    js = JSBackend().render(_combined_ir())[SCRIPT_PATH]
    body = js.split("function wireClickInterceptor(getStore) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    assert 'raw.indexOf("action:") === 0' in body
    assert 'raw.indexOf("behavior:") === 0' in body
    assert "actions[actionName]" in body
    assert "behaviors[behaviorName]" in body


def test_no_window_attached_behavior_dispatch_pair():
    js = JSBackend().render(_behavior_only_ir())[SCRIPT_PATH]
    assert "arkBehaviors" not in js
    assert "arkRunBehavior" not in js
    assert "window.arkBehaviors" not in js
    assert "window.arkRunBehavior" not in js
    # The dispatch object still exists, just as a plain local var.
    assert "var behaviors = {" in js
    assert "toggle:" in js


def test_single_delegated_click_listener_for_the_whole_page():
    js = JSBackend().render(_combined_ir())[SCRIPT_PATH]
    own_iife = js.split('(function () {\n  "use strict";', 1)[1]
    assert own_iife.count('addEventListener("click"') == 1


# ---------------------------------------------------------------------------
# 3. A behavior-only page ships no HTMX at all.
# ---------------------------------------------------------------------------


def test_behavior_only_page_ships_no_htmx():
    js = JSBackend().render(_behavior_only_ir())[SCRIPT_PATH]
    assert HTMX_JS not in js
    # The generated header comment mentions htmx-stage names in prose
    # regardless of whether the library itself ships (see
    # arklight/backend/js/render.py's _build_runtime_js) -- so this
    # checks for the vendored library's actual markers, not the bare
    # substring "htmx", which the header's own commentary legitimately
    # contains either way.
    assert "window.htmx" not in js
    assert "htmx.config" not in js
    assert "htmx:afterSettle" not in js


def test_stateful_page_still_ships_htmx():
    js = JSBackend().render(_stateful_ir())[SCRIPT_PATH]
    assert HTMX_JS in js


def test_app_shell_alone_still_ships_htmx_with_no_behaviors_or_state():
    js = JSBackend().render(_ir({"/": Page(Text("hi"))}, app_shell=True))[SCRIPT_PATH]
    assert HTMX_JS in js


# ---------------------------------------------------------------------------
# 4. Defense-in-depth: allowEval disabled whenever HTMX ships.
# ---------------------------------------------------------------------------


def test_allow_eval_disabled_whenever_htmx_ships():
    js = JSBackend().render(_stateful_ir())[SCRIPT_PATH]
    assert "htmx.config.allowEval = false;" in js
    # Set right after HTMX loads, before ARKlight's own IIFE opens.
    htmx_index = js.index(HTMX_JS)
    allow_eval_index = js.index("htmx.config.allowEval = false;")
    own_iife_index = js.index('(function () {\n  "use strict";')
    assert htmx_index < allow_eval_index < own_iife_index


def test_allow_eval_line_absent_when_htmx_does_not_ship():
    js = JSBackend().render(_behavior_only_ir())[SCRIPT_PATH]
    assert "allowEval" not in js


def test_allow_eval_disabled_for_app_shell_alone():
    js = JSBackend().render(_ir({"/": Page(Text("hi"))}, app_shell=True))[SCRIPT_PATH]
    assert "htmx.config.allowEval = false;" in js


# ---------------------------------------------------------------------------
# 5. The actual regression: no compiled HTML ever reaches an
#    eval-equivalent HTMX attribute, for any combination.
# ---------------------------------------------------------------------------


def test_no_eval_reaching_html_attribute_across_behavior_action_and_state():
    tree = Page(
        State("count", 0),
        Text("count"),
        Button("+1", on_click=Action.increment("count")),
        Button("-1", on_click=Action.decrement("count")),
        Button("Reset", on_click=Action.reset("count")),
        Button("Show", on_click="toggle", behavior_target="#panel"),
        Button("Copy", on_click="copy", behavior_target="#snippet"),
        Button("Dismiss", on_click="dismiss", behavior_target="#banner"),
    )
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert "hx-on" not in html
    assert "hx-vals" not in html
    assert "hx-vars" not in html
    assert "arkRunBehavior" not in html
    assert "eval(" not in html
    assert "new Function(" not in html


def test_no_eval_reaching_html_attribute_on_app_shell_site():
    tree = Page(Button("Show", on_click="toggle", behavior_target="#panel"))
    html = HTMLBackend().render(_ir({"/": tree}, app_shell=True))["index.html"]
    assert "hx-on" not in html
    assert "hx-vals" not in html
    assert "hx-vars" not in html
