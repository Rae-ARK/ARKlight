"""
Website IR.

The Website IR is deliberately a *separate* data structure from the ARK
AST, even though in v0.001 they look structurally similar
(`type` / `props` / `children`). The distinction matters going forward:

- ARK AST is "what the user's Python called" -- it's shaped by the
  public API's function-call ergonomics.
- Website IR is "what the website *means*" -- backend-independent
  intent that any backend (HTML today; CSS/JS/Vue/Svelte later) can
  consume without knowing anything about ARKlight's Python API.

Keeping them separate now means later milestones can let the IR diverge
from the ARK AST (e.g. one ARK node expanding into several IR nodes, or
site-wide concerns like navigation being synthesized into the IR) without
disturbing the public API or the validator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from arklight import experimental
from arklight.ast.nodes import ARKNode


@dataclass
class IRNode:
    """A single node in the Website IR."""

    type: str
    props: dict[str, Any] = field(default_factory=dict)
    children: list["IRNode | str"] = field(default_factory=list)


@dataclass
class IRPage:
    route: str
    root: IRNode
    # v0.0035: page-scoped reactive state declared via `State(...)`,
    # extracted from the Page node's children rather than living as a
    # prop on some other node -- state belongs to the page, the same
    # way `title` does. Empty for pages that declare no state.
    state: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebsiteIR:
    """The full compiled site: every route, mapped to its IR tree."""

    site_name: str
    pages: list[IRPage] = field(default_factory=list)
    # v0.042: site-wide custom CSS classes registered via `Site.style(...)`
    # -- name -> {css-property: value}. Structured input only (a plain
    # dict), never a raw CSS string, same boundary the rest of the
    # project holds. Empty for sites that never call `site.style(...)`.
    custom_styles: dict[str, dict[str, str]] = field(default_factory=dict)
    # EXPERIMENTAL (docs/EXPERIMENTAL-APIS.md): (condition, class_name,
    # {prop: value}) triples registered via `site.media_query(...)`.
    # Kept separate from `custom_styles` -- see `Site.media_query`'s
    # docstring for why this isn't folded into the same dict. Empty
    # for sites that never call `site.media_query(...)` (i.e. every
    # site that stays fully within the intrinsic layout model).
    media_queries: list = field(default_factory=list)
    # EXPERIMENTAL (docs/EXPERIMENTAL-APIS.md): every `ExperimentalUsage`
    # recorded during compilation, in call order -- the CLI drains this
    # (deduplicated by feature id) to print the end-of-build summary
    # block via `arklight.experimental.print_summary`.
    experimental_usages: list = field(default_factory=list)
    # CSS backend refactor: `--ark-*` custom property overrides
    # registered via `Site(max_width=..., bg=...)` -- var name (e.g.
    # "--ark-max-width") -> value. Empty for sites that pass neither,
    # in which case `CSSBackend` falls back to its own defaults.
    css_var_overrides: dict[str, str] = field(default_factory=dict)
    # Sitewide default for <html lang="...">. Previously this was a
    # literal "en" baked into the HTML backend with no override path
    # at all -- wrong for every non-English site, and there was no way
    # to fix it short of hand-editing generated HTML after every
    # build. Defaults to "en" (unchanged rendered output for a site
    # that doesn't set `Site(lang=...)`); a per-page `Page(lang=...)`
    # prop, read the same way `title`/`favicon`/`description` already
    # are, overrides this per route.
    lang: str = "en"
    # v0.048 Stage B ("CSS media queries + `<head>` extension" -- see
    # docs/DESIGN-NOTES.md): (condition, generated_class_name,
    # {prop: value}) triples, one per media condition on every node
    # that carried a `responsive_style={...}` prop anywhere on the
    # site. Populated by `build_website_ir`/`_ark_node_to_ir_node`
    # below, which also strips `responsive_style` out of the node's
    # own IR props (it isn't a real HTML attribute) and folds the
    # matching generated class into that node's `class_name` instead.
    # `CSSBackend` compiles this into real `@media (...) { .arkgen-N {
    # ... } }` rules, same shape as `media_queries` above but keyed to
    # a synthesized per-node class instead of an author-chosen one.
    # Empty for sites that never use `responsive_style=`.
    responsive_rules: list = field(default_factory=list)
    # Structural addendum (see docs/DESIGN-NOTES.md "CSS selector
    # algebra + at-rule vocabulary"): straight passthroughs of
    # `Site.style_selector`/`keyframes`/`font_face`/`container_query`/
    # `supports`/`page_rule`/`import_style` registrations. Each keeps
    # the exact shape its `Site` method already validated and
    # normalized -- see `arklight/backend/css/at_rules.py` for what
    # consumes each one. Empty for sites that never call the
    # corresponding method.
    selector_rules: list = field(default_factory=list)
    keyframes: dict = field(default_factory=dict)
    font_faces: list = field(default_factory=list)
    container_queries: list = field(default_factory=list)
    supports_rules: list = field(default_factory=list)
    page_rules: list = field(default_factory=list)
    style_imports: list = field(default_factory=list)
    # htmx-4 (docs/Backends/REFACTOR-INDEX.md row 9): straight
    # passthrough of `Site(app_shell=...)`, same shape as `lang`
    # above. `HTMLBackend` reads this to decide whether to emit
    # `hx-boost="true"` on `<body>` and route the page's state marker
    # through the app-shell-safe shape (see
    # `arklight/backend/html/page_render.py`); the JS backend reads it
    # to decide whether every page needs HTMX loaded, not just ones
    # that already needed it for a behavior/State(...) (see
    # `arklight/backend/js/render.py`'s `needs_htmx`). Defaults to
    # `False`, unchanged output for every existing caller.
    app_shell: bool = False


@dataclass
class _ResponsiveStyleCollector:
    """
    v0.048 Stage B: walks alongside `_ark_node_to_ir_node`, assigning
    each `responsive_style={...}`-carrying node a deterministic,
    site-wide-unique generated class name (`arkgen-1`, `arkgen-2`,
    ...) in build order -- pages in `pages` dict order, depth-first
    within each page -- so two builds of the same source produce
    identical output. Also records one `ExperimentalUsage` per node
    (not per media condition) under the same `css-media-queries`
    feature `Site.media_query(...)` already gates (see
    docs/EXPERIMENTAL-APIS.md): a viewport-keyed `@media` rule is a
    viewport-keyed `@media` rule regardless of which authoring surface
    produced it.
    """

    counter: int = 0
    rules: list[tuple[str, str, dict[str, str]]] = field(default_factory=list)
    experimental_usages: list = field(default_factory=list)

    def collect(
        self,
        node_type: str,
        responsive_style: dict[str, dict[str, Any]],
        *,
        on_warning: Callable[[str], None] | None,
    ) -> str:
        self.counter += 1
        class_name = f"arkgen-{self.counter}"
        for condition, rules in responsive_style.items():
            self.rules.append((condition, class_name, dict(rules)))
        self.experimental_usages.append(
            experimental.emit("css-media-queries", on_warning=on_warning, component=node_type)
        )
        return class_name


def _ark_node_to_ir_node(
    node: ARKNode,
    *,
    collector: _ResponsiveStyleCollector,
    on_warning: Callable[[str], None] | None = None,
) -> IRNode:
    props = dict(node.props)

    # v0.048 Stage B: `responsive_style` is a compile-time-only prop --
    # it never reaches the HTML backend as an attribute (there's no
    # such thing as a `responsive_style="..."` HTML attribute). It's
    # popped here, converted into a generated scoped class folded into
    # `class_name`, and the actual `{condition: {prop: value}}` rules
    # are handed to the collector for `CSSBackend` to compile.
    responsive_style = props.pop("responsive_style", None)
    if responsive_style:
        generated_class = collector.collect(node.type, responsive_style, on_warning=on_warning)
        existing_class = props.get("class_name")
        classes = existing_class.split() if isinstance(existing_class, str) and existing_class else []
        if generated_class not in classes:
            classes.append(generated_class)
        props["class_name"] = " ".join(classes)

    children: list[IRNode | str] = []
    for child in node.children:
        if isinstance(child, ARKNode):
            children.append(_ark_node_to_ir_node(child, collector=collector, on_warning=on_warning))
        else:
            children.append(str(child))
    return IRNode(type=node.type, props=props, children=children)


def _extract_page_state(page: ARKNode) -> tuple[dict[str, Any], list]:
    """
    Split a validated Page node's children into (state, remaining
    children). `State(...)` nodes are declarations, not renderable
    content -- they must never reach the HTML backend as a child.
    """
    state: dict[str, Any] = {}
    remaining: list = []
    for child in page.children:
        if isinstance(child, ARKNode) and child.type == "State":
            state[child.props["name"]] = child.props.get("initial")
        else:
            remaining.append(child)
    return state, remaining


def build_website_ir(
    site_name: str,
    pages: dict[str, ARKNode],
    *,
    custom_styles: dict[str, dict[str, str]] | None = None,
    media_queries: list | None = None,
    experimental_usages: list | None = None,
    css_var_overrides: dict[str, str] | None = None,
    lang: str = "en",
    on_warning: Callable[[str], None] | None = None,
    selector_rules: list | None = None,
    keyframes: dict | None = None,
    font_faces: list | None = None,
    container_queries: list | None = None,
    supports_rules: list | None = None,
    page_rules: list | None = None,
    style_imports: list | None = None,
    app_shell: bool = False,
) -> WebsiteIR:
    """
    Build the Website IR from a normalized + validated ARK AST.

    Callers are expected to have already run `normalize_ark_ast` and
    `validate_ark_ast` on `pages` before calling this. `custom_styles`
    (v0.042), `css_var_overrides` (CSS backend refactor), and `lang`
    are all optional and default to their prior stock values --
    existing callers that only pass `site_name`/`pages` are unaffected.

    `on_warning`, if given, is called once per `responsive_style={...}`
    node encountered (v0.048 Stage B) with the same inline
    "[EXPERIMENTAL FEATURE ACTIVE]" banner text `Site.media_query(...)`
    usages already print -- see `arklight.experimental.emit`. Unlike
    `Site.media_query(...)` (an author-time `Site` method call, so its
    usage is already known before this function runs), a
    `responsive_style` prop is only discovered by walking the tree
    here, so this is this feature's own detection point. Defaults to
    `None` (record the usage, but print nothing) so existing callers
    that don't pass it are unaffected; `arklight.compiler.pipeline`
    passes its stage logger.

    `selector_rules`/`keyframes`/`font_faces`/`container_queries`/
    `supports_rules`/`page_rules`/`style_imports` are the structural
    CSS addendum's registrations (`Site.style_selector`/`keyframes`/
    `font_face`/`container_query`/`supports`/`page_rule`/
    `import_style` -- see docs/DESIGN-NOTES.md), forwarded to the
    matching `WebsiteIR` field unchanged. All default to empty/None so
    existing callers are unaffected.

    `app_shell` (htmx-4, see docs/Backends/REFACTOR-INDEX.md row 9) is
    `Site(app_shell=...)`'s straight passthrough, same shape as
    `lang`. Defaults to `False`, unchanged output for existing callers.
    """
    collector = _ResponsiveStyleCollector()
    ir_pages = []
    for route, page in pages.items():
        state, remaining_children = _extract_page_state(page)
        root_page = ARKNode(type=page.type, props=page.props, children=remaining_children)
        ir_pages.append(
            IRPage(
                route=route,
                root=_ark_node_to_ir_node(root_page, collector=collector, on_warning=on_warning),
                state=state,
            )
        )
    return WebsiteIR(
        site_name=site_name,
        pages=ir_pages,
        custom_styles=dict(custom_styles) if custom_styles else {},
        media_queries=list(media_queries) if media_queries else [],
        experimental_usages=(list(experimental_usages) if experimental_usages else [])
        + collector.experimental_usages,
        css_var_overrides=dict(css_var_overrides) if css_var_overrides else {},
        lang=lang,
        responsive_rules=collector.rules,
        selector_rules=list(selector_rules) if selector_rules else [],
        keyframes=dict(keyframes) if keyframes else {},
        font_faces=list(font_faces) if font_faces else [],
        container_queries=list(container_queries) if container_queries else [],
        supports_rules=list(supports_rules) if supports_rules else [],
        page_rules=list(page_rules) if page_rules else [],
        style_imports=list(style_imports) if style_imports else [],
        app_shell=app_shell,
    )
