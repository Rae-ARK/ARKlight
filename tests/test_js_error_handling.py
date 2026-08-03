"""
Tests for the JS runtime error-handling hardening pass: a shared
`arkNotify()` on-page notice, plus `try`/`catch` guards around
`initState()`, `wireActions()`, `wireBehaviors()`, and their per-click
dispatch, so one malformed attribute or one throwing behavior/action
can't silently take down interactivity for the rest of the page --
and the person sees a visible notice instead of nothing at all.
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
    assert "wireBehaviors" in js


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
    # DOMContentLoaded handler and silently abort wireActions() (and
    # anything scheduled after it) for the whole page.
    pages = {
        "/": Page(
            State("count", 0),
            Text(Bind("count")),
            Button("+1", on_click=Action.increment("count")),
        )
    }
    js = JSBackend().render(_ir(pages))[SCRIPT_PATH]
    assert "function initState() {" in js
    init_state_body = js.split("function initState() {")[1].split("function wireActions")[0]
    assert "try {" in init_state_body
    assert "catch (err)" in init_state_body
    assert "arkNotify(" in init_state_body


def test_wire_actions_guards_each_element_independently():
    # One malformed data-ark-action-args on one element must not abort
    # the forEach loop for every other element.
    pages = {
        "/": Page(
            State("count", 0),
            Button("+1", on_click=Action.increment("count")),
        )
    }
    js = JSBackend().render(_ir(pages))[SCRIPT_PATH]
    wire_actions_body = js.split("function wireActions(store) {")[1].split("function highlightActiveNavLink")[0]
    # Guard around the per-element setup (attribute reads + JSON.parse).
    assert wire_actions_body.count("try {") == 2  # per-element setup + click dispatch
    assert wire_actions_body.count("catch (err)") == 2
    assert "arkNotify(" in wire_actions_body


def test_wire_behaviors_guards_each_element_independently():
    pages = {"/": Page(Button("Show", on_click="toggle", behavior_target="#panel"))}
    js = JSBackend().render(_ir(pages))[SCRIPT_PATH]
    wire_behaviors_body = js.split("function wireBehaviors() {")[1].split("function initState")[0] \
        if "function initState" in js else js.split("function wireBehaviors() {")[1].split("document.addEventListener")[0]
    assert wire_behaviors_body.count("try {") == 2  # per-element setup + click dispatch
    assert wire_behaviors_body.count("catch (err)") == 2
    assert "arkNotify(" in wire_behaviors_body


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
    pages = {
        "/": Page(
            State("count", 0),
            Button("+1", on_click=Action.increment("count")),
            Button("Copy", on_click="copy", behavior_target="#snippet"),
        )
    }
    js = JSBackend().render(_ir(pages))[SCRIPT_PATH]
    assert "eval(" not in js
    assert "new Function(" not in js
