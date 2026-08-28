"""
`htmx-3` (see docs/Backends/HTMX-INTEGRATION.md "Stage 3 -- Replace
`wireActions()` wiring loop" / docs/Backends/REFACTOR-INDEX.md row 6):
`wireActions()`'s `querySelectorAll`/`forEach`/per-element-
`addEventListener` wiring loop is deleted, replaced by
`wireActionInterceptor()` -- a single delegated `click` listener
registered once on `document`.

This stage is JS-only: HTML-side `data-ark-on-click="action:..."`/
`data-ark-action-state`/`data-ark-action-args` are unchanged (see
tests/test_html_attrs.py / tests/test_event_modifiers.py for that
coverage, untouched by this stage).

See arklight/backend/js/runtime/dispatch.py's module docstring for why
this lands as a delegated native `click` listener rather than the
`htmx:beforeRequest` interceptor docs/Backends/HTMX-INTEGRATION.md
describes.
"""

from arklight.api import Action, Button, Page, State, Text
from arklight.backend.js.render import JSBackend, SCRIPT_PATH
from arklight.backend.js.runtime.dispatch import ACTION_INTERCEPTOR_JS
from arklight.ir.build import build_website_ir
from arklight.ir.normalize import normalize_ark_ast
from arklight.ir.validate import validate_ark_ast


def _ir(pages):
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    return build_website_ir("site", normalized)


def _plain_ir():
    return _ir({"/": Page(Text("hi"))})


def _stateful_ir():
    return _ir(
        {
            "/": Page(
                State("count", 0),
                Button("+1", on_click=Action.increment("count")),
            )
        }
    )


# ---------------------------------------------------------------------------
# The old wiring loop is gone; the new interceptor exists in its place.
# ---------------------------------------------------------------------------


def test_wire_actions_loop_is_gone():
    js = JSBackend().render(_stateful_ir())[SCRIPT_PATH]
    assert "wireActions" not in js
    assert "querySelectorAll('[data-ark-on-click" not in js


def test_wire_action_interceptor_is_present_and_exported():
    assert "function wireActionInterceptor(store)" in ACTION_INTERCEPTOR_JS
    js = JSBackend().render(_stateful_ir())[SCRIPT_PATH]
    assert "function wireActionInterceptor(store)" in js
    assert js.count("function wireActionInterceptor") == 1


def test_interceptor_is_a_single_delegated_listener_not_a_per_element_loop():
    js = JSBackend().render(_stateful_ir())[SCRIPT_PATH]
    body = js.split("function wireActionInterceptor(store) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    # One addEventListener call, on document -- not a forEach loop over
    # individually-selected elements.
    assert body.count("addEventListener") == 1
    assert 'document.addEventListener("click"' in body
    assert "forEach" not in body
    assert "querySelectorAll" not in body
    # Delegation happens via closest() on the event target instead.
    assert "event.target.closest(" in body
    assert '[data-ark-on-click^="action:"]' in body


def test_no_op_when_store_is_falsy():
    # Same short-circuit wireActions() always had -- no store, no
    # listener registered.
    js = JSBackend().render(_stateful_ir())[SCRIPT_PATH]
    body = js.split("function wireActionInterceptor(store) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    assert body.strip().startswith("if (!store) return;")


def test_only_ships_when_state_is_declared():
    # Same "only ship what's used" discipline as every other v0.0035+
    # runtime piece -- a page with no State(...) gets no interceptor.
    js = JSBackend().render(_plain_ir())[SCRIPT_PATH]
    assert "wireActionInterceptor" not in js
    assert "createState" not in js


# ---------------------------------------------------------------------------
# Dispatch still reads the unchanged HTML-side attributes correctly.
# ---------------------------------------------------------------------------


def test_dispatch_reads_action_state_and_args_off_the_resolved_element():
    js = JSBackend().render(_stateful_ir())[SCRIPT_PATH]
    body = js.split("function wireActionInterceptor(store) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    assert 'el.getAttribute("data-ark-on-click")' in body
    assert 'el.getAttribute("data-ark-action-state")' in body
    assert 'el.getAttribute("data-ark-action-args")' in body
    assert "actions[actionName]" in body


def test_prevent_default_is_unconditional():
    # "prevent" remains honored by construction, same as every prior
    # stage -- event.preventDefault() doesn't depend on any modifier.
    js = JSBackend().render(_stateful_ir())[SCRIPT_PATH]
    body = js.split("function wireActionInterceptor(store) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    assert "event.preventDefault();" in body


# ---------------------------------------------------------------------------
# Guard shape: one try/catch now covers both attribute-read and dispatch,
# since there's no separate per-element wiring phase any more.
# ---------------------------------------------------------------------------


def test_guard_shape_is_one_try_catch_per_click():
    js = JSBackend().render(_stateful_ir())[SCRIPT_PATH]
    body = js.split("function wireActionInterceptor(store) {")[1].split(
        "function highlightActiveNavLink"
    )[0]
    assert body.count("try {") == 1
    assert body.count("catch (err)") == 1
    assert "arkNotify(" in body


# ---------------------------------------------------------------------------
# HTML-side attributes are unaffected -- JS-only stage.
# ---------------------------------------------------------------------------


def test_html_side_action_attributes_unaffected_by_this_stage():
    from arklight.backend.html.render import HTMLBackend

    tree = Page(State("count", 0), Button("+1", on_click=Action.increment("count")))
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert 'data-ark-on-click="action:increment"' in html
    assert 'data-ark-action-state="count"' in html


def test_call_site_updated_in_domcontentloaded_block():
    js = JSBackend().render(_stateful_ir())[SCRIPT_PATH]
    # ARKlight's own DOMContentLoaded registration is the *last*
    # occurrence of this string -- vendored HTMX has its own internal
    # "DOMContentLoaded" listener earlier in the file (see
    # tests/test_js_backend.py's identical HTMX_JS-scoping pattern).
    ready_block = js.rsplit('document.addEventListener("DOMContentLoaded", function () {', 1)[1]
    assert "wireActionInterceptor(store);" in ready_block
    assert "wireActions(store);" not in ready_block
