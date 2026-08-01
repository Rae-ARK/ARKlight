from arklight.api import Page, Text
from arklight.backend.js.render import JSBackend, SCRIPT_PATH
from arklight.ir.build import build_website_ir
from arklight.ir.normalize import normalize_ark_ast
from arklight.ir.validate import validate_ark_ast


def _ir():
    pages = {"/": Page(Text("hi"))}
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    return build_website_ir("site", normalized)


def test_js_backend_returns_script_path():
    output = JSBackend().render(_ir())
    assert set(output.keys()) == {SCRIPT_PATH}


def test_js_runtime_implements_known_behaviors():
    js = JSBackend().render(_ir())[SCRIPT_PATH]
    assert "toggle:" in js
    assert '"scroll-to":' in js
    assert "data-ark-on-click" in js
    assert "data-ark-target" in js
    assert "data-ark-toggle-class" in js


def test_js_runtime_highlights_active_nav_link():
    js = JSBackend().render(_ir())[SCRIPT_PATH]
    assert "highlightActiveNavLink" in js
    assert "is-active" in js


def test_js_runtime_has_no_eval_or_new_function():
    # Sanity check that the shipped runtime doesn't execute arbitrary
    # strings -- it only dispatches to the fixed `behaviors` object.
    js = JSBackend().render(_ir())[SCRIPT_PATH]
    assert "eval(" not in js
    assert "new Function(" not in js


def test_js_runtime_implements_copy_and_dismiss():
    js = JSBackend().render(_ir())[SCRIPT_PATH]
    assert "copy:" in js
    assert "dismiss:" in js
    assert "navigator.clipboard" in js


def test_js_runtime_still_has_no_eval_or_new_function_after_extension():
    js = JSBackend().render(_ir())[SCRIPT_PATH]
    assert "eval(" not in js
    assert "new Function(" not in js
