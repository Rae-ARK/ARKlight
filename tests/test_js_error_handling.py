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
    # htmx-1: wireBehaviors() is gone -- arkRunBehavior is the guard
    # now (see arklight/backend/js/render.py's module docstring).
    assert "arkRunBehavior" in js


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
    init_state_body = js.split("function initState() {")[1].split("function wireActionInterceptor")[0]
    assert "try {" in init_state_body
    assert "catch (err)" in init_state_body
    assert "arkNotify(" in init_state_body


def test_wire_action_interceptor_guards_dispatch_independently():
    # htmx-3: the per-element wiring loop is gone -- one malformed
    # data-ark-action-args read on one click must not break the
    # delegated listener for any subsequent click. See
    # tests/test_htmx_3.py for this stage's dedicated coverage.
    pages = {
        "/": Page(
            State("count", 0),
            Button("+1", on_click=Action.increment("count")),
        )
    }
    js = JSBackend().render(_ir(pages))[SCRIPT_PATH]
    wire_body = js.split("function wireActionInterceptor(getStore) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    assert wire_body.count("try {") == 1
    assert wire_body.count("catch (err)") == 1
    assert "arkNotify(" in wire_body


def test_wire_behaviors_guards_each_element_independently():
    # htmx-1: there is no more wireBehaviors() wiring pass -- HTMX's
    # own hx-on:click processing does the wiring, and per-call
    # guarding now happens inside arkRunBehavior instead of a
    # querySelectorAll/forEach loop. This test now checks that
    # smaller, per-call guard directly.
    pages = {"/": Page(Button("Show", on_click="toggle", behavior_target="#panel"))}
    js = JSBackend().render(_ir(pages))[SCRIPT_PATH]
    assert "function wireBehaviors() {" not in js
    assert "function arkRunBehavior(name, el) {" in js
    run_behavior_body = js.split("function arkRunBehavior(name, el) {")[1].split(
        "window.arkRunBehavior"
    )[0]
    assert run_behavior_body.count("try {") == 1
    assert run_behavior_body.count("catch (err)") == 1
    assert "arkNotify(" in run_behavior_body


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
    # htmx-1: this page ships vendored HTMX, a general-purpose
    # third-party library that (like most such libraries) has its own
    # internal eval/new Function uses unrelated to this guarantee --
    # see test_js_backend.py's identical scoping adjustment.
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
