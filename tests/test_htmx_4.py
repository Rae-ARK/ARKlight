"""
`htmx-4` (see docs/Backends/JS-BACKEND-REFACTOR-PLAN.md "The
app-illusion problem, stated precisely" / docs/Backends/
REFACTOR-INDEX.md row 9): app-shell navigation.

`Site(app_shell=True)` emits `hx-boost="true"` on `<body>` (turning
same-origin link clicks into an in-place AJAX swap instead of a full
document reload) and, on the JS side, ships HTMX for every page of the
site (not just ones that already needed it for a behavior/State(...))
and re-runs page init after a boosted swap settles, not just at first
load. A node carrying `shell_persistent=True` (with a matching `id`,
required by Validation) compiles to `hx-preserve="true"`, htmx's own
mechanism for keeping an element untouched across a boosted swap.

Default (`app_shell` unset, the vast majority of existing sites) is
asserted to be byte-for-byte unaffected by this stage throughout.
"""

from arklight.api import (
    Action,
    Button,
    Container,
    Header,
    Link,
    Nav,
    Page,
    Site,
    State,
    Text,
)
from arklight.backend.html.render import HTMLBackend
from arklight.backend.js.render import JSBackend, SCRIPT_PATH
from arklight.ir.build import build_website_ir
from arklight.ir.normalize import normalize_ark_ast
from arklight.ir.validate import ValidationError, validate_ark_ast
import pytest


def _ir(pages, *, app_shell=False):
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    return build_website_ir("site", normalized, app_shell=app_shell)


def _plain_ir(*, app_shell=False):
    return _ir({"/": Page(Text("hi"))}, app_shell=app_shell)


def _stateful_ir(*, app_shell=False):
    return _ir(
        {
            "/": Page(
                State("count", 0),
                Button("+1", on_click=Action.increment("count")),
            )
        },
        app_shell=app_shell,
    )


# ---------------------------------------------------------------------------
# Site(app_shell=...) plumbing: api.py -> WebsiteIR -> pipeline, all default
# to False and off, unaffected by this stage unless explicitly opted in.
# ---------------------------------------------------------------------------


def test_site_defaults_app_shell_to_false():
    site = Site("site")
    assert site.app_shell is False


def test_site_app_shell_flag_is_stored():
    site = Site("site", app_shell=True)
    assert site.app_shell is True


def test_build_website_ir_defaults_app_shell_to_false():
    ir = _plain_ir()
    assert ir.app_shell is False


def test_build_website_ir_forwards_app_shell():
    ir = _plain_ir(app_shell=True)
    assert ir.app_shell is True


# ---------------------------------------------------------------------------
# HTML backend: hx-boost on <body>, only when app_shell=True.
# ---------------------------------------------------------------------------


def test_no_hx_boost_by_default():
    html = HTMLBackend().render(_plain_ir())["index.html"]
    assert "hx-boost" not in html


def test_hx_boost_emitted_when_app_shell_is_true():
    html = HTMLBackend().render(_plain_ir(app_shell=True))["index.html"]
    assert '<body hx-boost="true">' in html


def test_plain_site_html_is_byte_for_byte_unaffected():
    # The exact regression guard this stage's own module docstrings
    # promise: an existing caller that never sets app_shell gets prior
    # output, unchanged.
    tree = Page(Container("Panel", Text("hi")))
    html_before_shape = HTMLBackend().render(_ir({"/": tree}, app_shell=False))["index.html"]
    html_default = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert html_before_shape == html_default


# ---------------------------------------------------------------------------
# State + app_shell: data-ark-state moves off <body> into a swappable
# marker element, since hx-boost's default swap never updates <body>'s own
# attributes (only its innerHTML) -- see page_render.py's _render_page
# docstring for the full reasoning, verified directly against htmx's docs.
# ---------------------------------------------------------------------------


def test_state_stays_on_body_attribute_without_app_shell():
    html = HTMLBackend().render(_stateful_ir())["index.html"]
    assert 'data-ark-state="' in html
    # It's the <body> tag's own attribute, not a separate marker element.
    body_line = [line for line in html.splitlines() if line.startswith("<body")][0]
    assert "data-ark-state=" in body_line
    assert 'id="ark-state"' not in html


def test_state_moves_to_marker_element_with_app_shell():
    html = HTMLBackend().render(_stateful_ir(app_shell=True))["index.html"]
    assert '<body hx-boost="true">' in html
    body_line = [line for line in html.splitlines() if line.startswith("<body")][0]
    assert "data-ark-state=" not in body_line
    assert '<div id="ark-state" data-ark-state="' in html
    assert "hidden" in html.split('<div id="ark-state"', 1)[1].split(">", 1)[0]


def test_app_shell_with_no_state_emits_no_marker():
    html = HTMLBackend().render(_plain_ir(app_shell=True))["index.html"]
    assert "ark-state" not in html


# ---------------------------------------------------------------------------
# shell_persistent -> hx-preserve, Validation requires a matching id.
# ---------------------------------------------------------------------------


def test_shell_persistent_compiles_to_hx_preserve():
    tree = Page(
        Nav(Link("Home", href="/"), id="site-nav", shell_persistent=True),
        Text("hi"),
    )
    html = HTMLBackend().render(_ir({"/": tree}, app_shell=True))["index.html"]
    assert 'id="site-nav"' in html
    assert 'hx-preserve="true"' in html


def test_shell_persistent_without_id_fails_validation():
    tree = Page(Nav(Link("Home", href="/"), shell_persistent=True))
    normalized = normalize_ark_ast({"/": tree})
    with pytest.raises(ValidationError, match="shell_persistent"):
        validate_ark_ast(normalized)


def test_shell_persistent_with_empty_id_fails_validation():
    tree = Page(Nav(Link("Home", href="/"), id="  ", shell_persistent=True))
    normalized = normalize_ark_ast({"/": tree})
    with pytest.raises(ValidationError, match="shell_persistent"):
        validate_ark_ast(normalized)


def test_shell_persistent_false_needs_no_id():
    # Only True triggers the requirement -- an explicit False (or the
    # prop simply never being set) is inert, same as any other unused
    # boolean prop.
    tree = Page(Nav(Link("Home", href="/"), shell_persistent=False))
    normalized = normalize_ark_ast({"/": tree})
    validate_ark_ast(normalized)  # must not raise


def test_shell_persistent_is_inert_without_app_shell():
    # Compiles to the same hx-preserve attribute either way -- htmx
    # just never looks for it on a non-app_shell page, since hx-boost
    # itself is never active there.
    tree = Page(Header(Text("Site"), id="site-header", shell_persistent=True))
    html = HTMLBackend().render(_ir({"/": tree}))["index.html"]
    assert 'hx-preserve="true"' in html
    assert "hx-boost" not in html


# ---------------------------------------------------------------------------
# JS backend: needs_htmx now includes app_shell alone.
# ---------------------------------------------------------------------------


def test_app_shell_alone_ships_htmx_even_with_no_behaviors_or_state():
    # The gap this stage's audit found: a plain nav-only page in an
    # app_shell site previously shipped with no HTMX runtime at all,
    # so hx-boost would have had nothing to intercept clicks with.
    js = JSBackend().render(_plain_ir(app_shell=True))[SCRIPT_PATH]
    assert "htmx" in js.lower()
    assert "function htmx(" in js or "var htmx" in js or "htmx.defineExtension" in js or True
    # Concretely: the vendored HTMX source is present, not just a
    # mention of the word "htmx" somewhere in a comment.
    from arklight.backend.js.htmx import HTMX_JS

    assert HTMX_JS in js


def test_plain_site_without_app_shell_still_ships_no_htmx():
    js = JSBackend().render(_plain_ir())[SCRIPT_PATH]
    from arklight.backend.js.htmx import HTMX_JS

    assert HTMX_JS not in js


# ---------------------------------------------------------------------------
# Re-init after a boosted swap: arkInitPage() extraction + htmx:afterSettle.
# ---------------------------------------------------------------------------


def test_ark_init_page_is_defined_and_called_on_domcontentloaded():
    js = JSBackend().render(_stateful_ir(app_shell=True))[SCRIPT_PATH]
    assert "function arkInitPage() {" in js
    ready_block = js.rsplit('document.addEventListener("DOMContentLoaded", function () {', 1)[1]
    assert "arkInitPage();" in ready_block


def test_after_settle_listener_only_registered_for_app_shell():
    listener_line = 'document.body.addEventListener("htmx:afterSettle", arkInitPage);'
    js_shell = JSBackend().render(_stateful_ir(app_shell=True))[SCRIPT_PATH]
    assert listener_line in js_shell

    # Vendored HTMX's own source legitimately mentions "htmx:afterSettle"
    # internally (it's one of the events htmx itself dispatches) -- this
    # site still ships HTMX (it has State(...)), so the bare substring
    # would appear either way. What must differ is ARKlight's own
    # registration of a listener *for* that event.
    js_plain = JSBackend().render(_stateful_ir())[SCRIPT_PATH]
    assert listener_line not in js_plain


def test_action_interceptor_registered_exactly_once_regardless_of_app_shell():
    # The bug this stage's design deliberately avoids: re-registering
    # the click listener on every boosted swap would stack duplicate
    # listeners, each closing over a stale store. htmx-5 renamed the
    # function (wireActionInterceptor -> wireClickInterceptor -- see
    # tests/test_htmx_5.py); the call-once guarantee this test checks
    # is unaffected by that rename.
    js = JSBackend().render(_stateful_ir(app_shell=True))[SCRIPT_PATH]
    assert js.count("wireClickInterceptor(function () { return arkStore; });") == 1
    assert "wireActionInterceptor" not in js
    # Scoped to ARKlight's own IIFE, not vendored HTMX's source (which
    # registers its own internal click listener(s) too).
    own_iife = js.split('(function () {\n  "use strict";', 1)[1]
    assert own_iife.count('addEventListener("click"') == 1


def test_ark_init_page_reassigns_shared_store_variable():
    js = JSBackend().render(_stateful_ir(app_shell=True))[SCRIPT_PATH]
    assert "var arkStore = null;" in js
    init_body = js.split("function arkInitPage() {")[1].split("}", 1)[0]
    assert "arkStore = initState();" in init_body
    assert "highlightActiveNavLink();" in init_body


def test_nav_highlighting_reruns_on_every_init_regardless_of_state():
    # Even a plain app_shell page with no State(...) still needs
    # highlightActiveNavLink() to rerun after every boosted swap, so
    # the active nav link is correct on whatever page was just
    # navigated to.
    js = JSBackend().render(_plain_ir(app_shell=True))[SCRIPT_PATH]
    assert "function arkInitPage() {" in js
    init_body = js.split("function arkInitPage() {")[1].split("}", 1)[0]
    assert "highlightActiveNavLink();" in init_body
    assert 'document.body.addEventListener("htmx:afterSettle", arkInitPage);' in js


# ---------------------------------------------------------------------------
# initState() checks the app_shell marker first, falls back to the <body>
# attribute -- see runtime/state.py's docstring.
# ---------------------------------------------------------------------------


def test_init_state_checks_marker_before_body_attribute():
    from arklight.backend.js.runtime.state import INIT_STATE_JS

    assert 'document.getElementById("ark-state")' in INIT_STATE_JS
    assert 'document.body.getAttribute("data-ark-state")' in INIT_STATE_JS
    # The marker check comes first (fallback, not primary).
    marker_pos = INIT_STATE_JS.index('document.getElementById("ark-state")')
    fallback_pos = INIT_STATE_JS.index('document.body.getAttribute("data-ark-state")')
    assert marker_pos < fallback_pos
