"""
Tests for the JS runtime error-handling hardening pass: a shared
`arkNotify()` on-page notice, plus `try`/`catch` guards around
`initState()`, `wireActionInterceptor()`, `wireBehaviors()`, and their
per-click dispatch, so one malformed attribute or one throwing
behavior/action can't silently take down interactivity for the rest
of the page -- and the person sees a visible notice instead of
nothing at all.

`htmx-3` (see `docs/Backends/HTMX-INTEGRATION.md` "Stage 3") renamed
`wireActions()` to `wireActionInterceptor()` and replaced its
per-element wiring loop with a single delegated `click` listener --
see `arklight/backend/js/runtime/dispatch.py`'s module docstring.
`test_wire_actions_guards_each_element_independently` below is
updated for that shape; see `tests/test_htmx_3.py` for this stage's
own dedicated coverage.

`htmx-5` (see `docs/Backends/HTMX-INTEGRATION.md` "Stage 4 -- Audit
and remove remaining hand-rolled plumbing" / `docs/Backends/
REFACTOR-INDEX.md` row 10) renamed `wireActionInterceptor()` again, to
`wireClickInterceptor()`, and removed `wireBehaviors()`'s successor,
`arkRunBehavior()`, entirely: behavior dispatch now happens inside
`wireClickInterceptor()`'s own `"behavior:"` branch, guarded by its
own `try`/`catch`, rather than through a standalone
`window`-attached wrapper vendored HTMX's `hx-on:click` attribute
processing used to call. The tests below that referenced
`arkRunBehavior`/`wireActionInterceptor` by name are updated
accordingly; `tests/test_htmx_5.py` has this stage's own dedicated
coverage, including of the actual bug this stage fixes:
`hx-on:click`'s attribute-value dispatch was, under the hood,
`new Function("event", attributeValue)` -- an eval-equivalent
operation this project's own "no eval, no new Function" invariant
(see `arklight/backend/js/render.py`'s module docstring) doesn't
permit, vendored dependency or not. `test_runtime_still_has_no_eval_
or_new_function` below, notably, could never have caught that bug --
it only inspects the *JS* file, and the `new Function(...)` call only
ever happened as a side effect of vendored HTMX *processing an HTML
attribute*; the HTML output itself is what needed inspecting, which
`tests/test_html_backend.py` and `tests/test_htmx_5.py` now do.
"""

from arklight.api import Action, Bind, Button, Page, State, Text
from arklight.backend.js.render import JSBackend, SCRIPT_PATH
from arklight.ir.build import build_website_ir
from arklight.ir.normalize import normalize_ark_ast
from arklight.ir.validate import validate_ark_ast


def _ir(pages):
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    return build_website_ir("site", normalized)


def _plain_ir():
    return _ir({"/": Page(Text("hi"))})


def test_no_arknotify_shipped_when_no_interactivity_is_used():
    # Same "only ship what's used" discipline as behaviors/actions --
    # a page with no on_click/State at all doesn't need the notifier.
    js = JSBackend().render(_plain_ir())[SCRIPT_PATH]
    assert "arkNotify" not in js


def test_arknotify_shipped_when_a_behavior_is_used():
    pages = {"/": Page(Button("Show", on_click="toggle", behavior_target="#panel"))}
    js = JSBackend().render(_ir(pages))[SCRIPT_PATH]
    assert "function arkNotify(message)" in js
    # htmx-5: the guard now lives in wireClickInterceptor's behavior
    # branch (see arklight/backend/js/runtime/dispatch.py) -- there is
    # no more standalone arkRunBehavior wrapper.
    assert "wireClickInterceptor" in js
    assert "arkRunBehavior" not in js


def test_arknotify_shipped_when_state_is_used():
    pages = {
        "/": Page(
            State("count", 0),
            Text(Bind("count")),
            Button("+1", on_click=Action.increment("count")),
        )
    }
    js = JSBackend().render(_ir(pages))[SCRIPT_PATH]
    assert "function arkNotify(message)" in js


def test_init_state_is_guarded_against_malformed_json():
    # Previously JSON.parse(raw) in initState() had no guard -- a
    # malformed data-ark-state attribute would throw inside the
    # DOMContentLoaded handler and silently abort wireActionInterceptor()
    # (and anything scheduled after it) for the whole page.
    pages = {
        "/": Page(
            State("count", 0),
            Text(Bind("count")),
            Button("+1", on_click=Action.increment("count")),
        )
    }
    js = JSBackend().render(_ir(pages))[SCRIPT_PATH]
    assert "function initState() {" in js
    init_state_body = js.split("function initState() {")[1].split("function wireClickInterceptor")[0]
    assert "try {" in init_state_body
    assert "catch (err)" in init_state_body
    assert "arkNotify(" in init_state_body


def test_wire_click_interceptor_guards_action_dispatch_independently():
    # htmx-3: the per-element wiring loop is gone -- one malformed
    # data-ark-action-args read on one click must not break the
    # delegated listener for any subsequent click. See
    # tests/test_htmx_3.py for this stage's dedicated coverage.
    # htmx-5: renamed wireActionInterceptor -> wireClickInterceptor;
    # the shipped function now always carries both an action branch
    # and a behavior branch (each with its own try/catch), regardless
    # of which this particular page actually uses -- see
    # tests/test_htmx_5.py.
    pages = {
        "/": Page(
            State("count", 0),
            Button("+1", on_click=Action.increment("count")),
        )
    }
    js = JSBackend().render(_ir(pages))[SCRIPT_PATH]
    wire_body = js.split("function wireClickInterceptor(getStore) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    assert wire_body.count("try {") == 2
    assert wire_body.count("catch (err)") == 2
    assert "arkNotify(" in wire_body


def test_wire_click_interceptor_guards_behavior_dispatch_independently():
    # htmx-1 originally guarded per-behavior dispatch inside a
    # standalone arkRunBehavior() wrapper, called from HTMX's own
    # hx-on:click attribute processing. htmx-5 removed that wrapper --
    # the guard now lives directly in wireClickInterceptor's
    # "behavior:" branch (see arklight/backend/js/runtime/dispatch.py
    # and tests/test_htmx_5.py for why).
    pages = {"/": Page(Button("Show", on_click="toggle", behavior_target="#panel"))}
    js = JSBackend().render(_ir(pages))[SCRIPT_PATH]
    assert "function wireBehaviors() {" not in js
    assert "function arkRunBehavior(name, el) {" not in js
    wire_body = js.split("function wireClickInterceptor(getStore) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    behavior_branch = wire_body.split('raw.indexOf("behavior:") === 0) {')[1]
    assert behavior_branch.count("try {") == 1
    assert behavior_branch.count("catch (err)") == 1
    assert "arkNotify(" in behavior_branch


def test_copy_behavior_handles_clipboard_rejection():
    # navigator.clipboard.writeText(...).then(...) previously had no
    # .catch() -- an unhandled promise rejection on a failure that's
    # common precisely because `arklight build --open` opens sites as
    # file:// URLs by default, where clipboard permissions often fail.
    pages = {"/": Page(Button("Copy", on_click="copy", behavior_target="#snippet"))}
    js = JSBackend().render(_ir(pages))[SCRIPT_PATH]
    assert ".writeText(text.trim()).then(function () {" in js
    assert "}).catch(function () {" in js
    assert "arkNotify(" in js


def test_runtime_still_has_no_eval_or_new_function():
    # The hardening pass must not introduce any string-as-code
    # execution -- arkNotify only ever sets textContent/cssText.
    #
    # This check only ever inspected the JS file, scoped to exclude
    # vendored HTMX's own source -- which is why it could never have
    # caught htmx-5's actual finding (hx-on:click's attribute-value
    # dispatch was, under the hood, new Function("event",
    # attributeValue), reached from an *HTML* attribute this stage
    # removed, not from anything in this JS file). See
    # tests/test_htmx_5.py for the dedicated regression coverage on
    # the HTML side, and arklight/backend/js/runtime/dispatch.py's
    # module docstring for the full finding. This test remains valid
    # for what it actually checks: ARKlight's own authored JS, with
    # vendored HTMX's source excluded, contains no eval-equivalent
    # call -- true before and after htmx-5, since ARKlight's own
    # authored JS never routed through hx-on:click in the first place
    # (only the *compiled HTML attribute* did).
    from arklight.backend.js.htmx import HTMX_JS

    pages = {
        "/": Page(
            State("count", 0),
            Button("+1", on_click=Action.increment("count")),
            Button("Copy", on_click="copy", behavior_target="#snippet"),
        )
    }
    js = JSBackend().render(_ir(pages))[SCRIPT_PATH]
    ark_authored_js = js.replace(HTMX_JS, "")
    assert "eval(" not in ark_authored_js
    assert "new Function(" not in ark_authored_js
