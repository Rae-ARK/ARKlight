"""
Validation stage.

Once the ARK AST is normalized, ARKlight checks it against a small
schema of known node types before it's allowed to become Website IR.
This is the main guardrail that keeps ARKlight "beginner friendly": bad
trees fail loudly and specifically, at build time, in Python -- never
silently in the browser.

Checks performed:

1. The node `type` is a recognized built-in (arklight.ir.schema.SCHEMA).
2. Required props for that type are present (e.g. `Link` needs `href`,
   `Image` needs `src`).
3. Node types that require plain-text-only children (e.g. `Text`,
   `Button`) don't contain nested component nodes -- except `Bind(...)`,
   which is a value reference, not a component (see below).
4. `on_click`, if present, is either a known behavior name (paired with
   a `behavior_target` selector -- arklight.ir.schema.KNOWN_BEHAVIORS)
   or an `Action.*(...)` reference (arklight.ir.schema.ACTION_REGISTRY)
   whose `state` targets a `State(...)` declared on the same page.
5. `State(...)` may only appear as a direct child of `Page(...)` --
   state belongs to the page, not to an arbitrary nested component --
   and every `Bind(...)` anywhere on the page must name a `State(...)`
   actually declared there.
6. The tree's root is a `Page` node.
7. Recurses into every child.
8. `bind_class`, if present, is a `Bind.when(...)` reference
   (arklight.ast.nodes.ClassBindSpec) whose `state` targets a
   `State(...)` declared on the same page (Stage 2 of "Reactive-core
   vdom staging" -- see docs/DESIGN-NOTES.md).
9. An `Action.*(...)`'s `.modifiers` (from `.with_modifiers(...)`,
   `.debounce(...)`, `.throttle(...)`) are each a known token from
   `arklight.ir.schema.MODIFIER_REGISTRY` -- `prevent`/`stop`/`once`
   bare, `debounce`/`throttle` as `"<name>:<ms>"` with a positive
   integer `ms` (Stage 3 of "Reactive-core vdom staging" -- see
   docs/DESIGN-NOTES.md).
10. `responsive_style`, if present, is a non-empty `dict[str,
    dict[str, str]]` -- each key a non-empty media-condition string
    (e.g. `"(max-width: 600px)"`), each value a non-empty dict of
    non-empty CSS property name -> string/number value (v0.048 Stage
    B, "CSS media queries + `<head>` extension" -- see
    docs/DESIGN-NOTES.md). Structured input only, same discipline as
    `site.style(...)`/`site.media_query(...)` -- never a raw CSS
    string.
11. `meta`/`links` on `Page(...)`, if present, are structurally
    well-formed (v0.048 Stage A, "CSS media queries + `<head>`
    extension" -- see docs/DESIGN-NOTES.md): `meta` a non-empty
    `dict[str, str]` of name -> content pairs; `links` a non-empty
    `list[dict[str, str]]` of attribute -> value pairs, each carrying
    a `rel`. Structured input only, same "no raw HTML-injection escape
    hatch" discipline every other extension point in the project
    holds.
12. `shell_persistent`, if `True` on a node, requires that same node
    to also carry a non-empty `id` (htmx-4, see
    docs/Backends/REFACTOR-INDEX.md row 9): `hx-preserve` -- the HTML
    backend's target for this prop, see `arklight/backend/html/attrs.py`
    -- only works if htmx can find the *same* element in both the old
    and the newly-fetched DOM to keep, and the only thing it matches
    on is a stable `id`. A node with no `id` would compile to a
    `hx-preserve="true"` attribute htmx silently can't use, so this
    fails loudly at build time instead.
13. `Computed(...)` (`vdom-4`, see docs/Backends/REFACTOR-INDEX.md row
    12) may only appear as a direct child of `Page(...)`, same as
    `State(...)`; needs a non-empty string `name`, not already used by
    a `State(...)`/other `Computed(...)` on the same page; needs a
    non-empty `deps` tuple, every entry of which resolves to a
    `State(...)`/other `Computed(...)` declared on the same page; its
    `derive` must be a `Derive.*(...)` reference
    (`arklight.ast.nodes.DerivationRef`) whose `kind` is known
    (`arklight.ir.schema.DERIVATION_REGISTRY`), whose `names` count
    satisfies that kind's arity and is a subset of the declared
    `deps`, whose `args` carry exactly that kind's closed set of extra
    keys (`join`'s `sep`, `format`'s `template`/`names_map`,
    `compare`'s `op`, itself checked against
    `arklight.ir.schema.COMPARE_OPS`), and which does not, directly or
    transitively through other `Computed(...)` deps, depend on itself.
    `Bind(...)`/`bind_class=` may reference a `Computed(...)`'s `name`
    exactly like a `State(...)`'s; `Action.*(...)` may not -- a
    `Computed(...)` has no independent value of its own to mutate.
"""

from __future__ import annotations

from arklight.ast.nodes import ActionRef, ARKNode, ClassBindSpec, DerivationRef
from arklight.ir.schema import (
    ACTION_REGISTRY,
    COMPARE_OPS,
    DERIVATION_REGISTRY,
    KNOWN_BEHAVIORS,
    MODIFIER_REGISTRY,
    SCHEMA,
)


class ValidationError(Exception):
    """Raised when an ARK AST tree fails validation."""


def _validate_bind(node: ARKNode, *, path: str, page_state: frozenset[str]) -> None:
    name = node.props.get("name")
    if not isinstance(name, str) or not name:
        raise ValidationError(f"Bind(...) at {path} needs a non-empty string name.")
    if name not in page_state:
        known = ", ".join(sorted(page_state)) or "(none declared)"
        raise ValidationError(
            f"Bind({name!r}) at {path} references state that isn't declared "
            f"on this page. State/Computed declared on this page: {known}."
        )


def _validate_modifiers(action: ActionRef, *, path: str) -> None:
    """Stage 3 ("Reactive-core vdom staging"): check each token in
    `action.modifiers` against `MODIFIER_REGISTRY` -- a bare name
    (`prevent`/`stop`/`once`) must take no parameter, and a
    `"<name>:<value>"` token (`debounce:300`/`throttle:300`) must both
    name a param-taking modifier and carry a positive integer value."""
    for token in action.modifiers:
        name, sep, param = token.partition(":")
        spec = MODIFIER_REGISTRY.get(name)
        if spec is None:
            known = ", ".join(sorted(MODIFIER_REGISTRY))
            raise ValidationError(
                f"on_click at {path} uses unknown modifier {name!r} (from "
                f"{token!r}). Known modifiers are: {known}."
            )
        if spec.has_param:
            if not sep:
                raise ValidationError(
                    f"on_click at {path} uses modifier {name!r} without a "
                    f"millisecond value -- use .{name}(<ms>), e.g. .{name}(300)."
                )
            if not param.isdigit() or int(param) <= 0:
                raise ValidationError(
                    f"on_click at {path} uses modifier {token!r} with an "
                    f"invalid value -- {name!r} needs a positive integer "
                    f"millisecond count."
                )
        elif sep:
            raise ValidationError(
                f"on_click at {path} uses modifier {token!r}, but {name!r} "
                f"doesn't take a value -- use .with_modifiers({name!r}) "
                f"instead."
            )


def _validate_action(action: ActionRef, *, path: str, mutable_state: frozenset[str]) -> None:
    if action.action not in ACTION_REGISTRY:
        known = ", ".join(sorted(ACTION_REGISTRY))
        raise ValidationError(
            f"on_click at {path} uses unknown action {action.action!r}. "
            f"Known actions are: {known}."
        )
    if action.state not in mutable_state:
        known = ", ".join(sorted(mutable_state)) or "(none declared)"
        raise ValidationError(
            f"on_click at {path} ({action.action!r}) targets state "
            f"{action.state!r}, which isn't declared on this page as "
            f"State(...) (a Computed(...) name can't be an Action.*(...) "
            f"target -- it has no independent value of its own to mutate). "
            f"State declared on this page: {known}."
        )
    _validate_modifiers(action, path=path)


def _validate_class_bind(node: ARKNode, *, path: str, page_state: frozenset[str]) -> None:
    bind_class = node.props.get("bind_class")
    if bind_class is None:
        return
    if not isinstance(bind_class, ClassBindSpec):
        raise ValidationError(
            f"{node.type!r} at {path} has bind_class={bind_class!r}, which isn't "
            f"a Bind.when(...) reference."
        )
    if not bind_class.class_name:
        raise ValidationError(f"Bind.when(...) at {path} needs a non-empty class_name.")
    if bind_class.state not in page_state:
        known = ", ".join(sorted(page_state)) or "(none declared)"
        raise ValidationError(
            f"bind_class at {path} (Bind.when({bind_class.state!r}, ...)) "
            f"targets state {bind_class.state!r}, which isn't declared on this "
            f"page. State declared on this page: {known}."
        )


def _validate_responsive_style(node: ARKNode, *, path: str) -> None:
    """
    v0.048 Stage B: `responsive_style={"(max-width: 600px)": {"display":
    "none"}}` -- a per-node prop any component may carry, extending the
    existing `style={...}` convention with a viewport-keyed variant
    (see docs/DESIGN-NOTES.md, "v0.048: CSS media queries + `<head>`
    extension"). Validated eagerly and structurally, matching
    `Site.style()`/`Site.media_query()`'s discipline, since this
    compiles straight into the generated stylesheet rather than a
    per-page inline attribute -- a malformed entry here would otherwise
    surface as silently broken CSS instead of a clear build-time error.
    """
    responsive_style = node.props.get("responsive_style")
    if responsive_style is None:
        return
    if not isinstance(responsive_style, dict) or not responsive_style:
        raise ValidationError(
            f"{node.type!r} at {path} has responsive_style={responsive_style!r}, "
            f"which must be a non-empty dict of "
            f'{{media_condition: {{css_property: value}}}}, e.g. '
            f'{{"(max-width: 600px)": {{"display": "none"}}}}.'
        )
    for condition, rules in responsive_style.items():
        if not isinstance(condition, str) or not condition.strip():
            raise ValidationError(
                f"{node.type!r} at {path} has a responsive_style entry with an "
                f"invalid media condition key -- expected a non-empty string "
                f"like \"(max-width: 600px)\", got {condition!r}."
            )
        if not isinstance(rules, dict) or not rules:
            raise ValidationError(
                f"{node.type!r} at {path} responsive_style[{condition!r}] must "
                f"be a non-empty dict of {{css_property: value}}, got {rules!r}."
            )
        for prop, value in rules.items():
            if not isinstance(prop, str) or not prop.strip():
                raise ValidationError(
                    f"{node.type!r} at {path} responsive_style[{condition!r}] "
                    f"has a non-empty string CSS property name required, got "
                    f"{prop!r}."
                )
            if value is None or isinstance(value, bool) or not isinstance(value, (str, int, float)):
                raise ValidationError(
                    f"{node.type!r} at {path} "
                    f"responsive_style[{condition!r}][{prop!r}] needs a string "
                    f"(or plain number) CSS value, got {value!r}."
                )


def _validate_page_head_extensions(node: ARKNode, *, path: str) -> None:
    """
    v0.048 Stage A: `meta`/`links` on `Page(...)` -- structured `<head>`
    extension points, matching the discipline `responsive_style` (Stage
    B, above) and `Site.style(...)` already use: no raw HTML-injection
    escape hatch, validated eagerly and structurally so a malformed
    entry fails loudly at build time instead of silently producing
    broken `<head>` output. Only meaningful on `Page(...)` -- the HTML
    backend only ever reads these two props off `page.root`, matching
    `favicon`/`description`/`og_*`'s existing page-only convention (see
    `arklight/backend/html/render.py`'s `_render_head_meta`).
    """
    meta = node.props.get("meta")
    if meta is not None:
        if not isinstance(meta, dict) or not meta:
            raise ValidationError(
                f"Page(...) at {path} has meta={meta!r}, which must be a "
                f"non-empty dict of {{name: content}}, e.g. "
                f'{{"theme-color": "#0f0f0f"}}.'
            )
        for name, content in meta.items():
            if not isinstance(name, str) or not name.strip():
                raise ValidationError(
                    f"Page(...) at {path} has a meta entry with an invalid "
                    f"name key -- expected a non-empty string, got {name!r}."
                )
            if not isinstance(content, str):
                raise ValidationError(
                    f"Page(...) at {path} meta[{name!r}] needs a string "
                    f"content value, got {content!r}."
                )

    links = node.props.get("links")
    if links is not None:
        if not isinstance(links, list) or not links:
            raise ValidationError(
                f"Page(...) at {path} has links={links!r}, which must be a "
                f"non-empty list of {{attribute: value}} dicts, e.g. "
                f'[{{"rel": "preconnect", "href": "https://fonts.gstatic.com"}}].'
            )
        for i, link in enumerate(links):
            if not isinstance(link, dict) or not link:
                raise ValidationError(
                    f"Page(...) at {path} links[{i}] must be a non-empty "
                    f"dict of {{attribute: value}}, got {link!r}."
                )
            for attr, value in link.items():
                if not isinstance(attr, str) or not attr.strip():
                    raise ValidationError(
                        f"Page(...) at {path} links[{i}] has a non-string "
                        f"or empty attribute name key, got {attr!r}."
                    )
                if not isinstance(value, str):
                    raise ValidationError(
                        f"Page(...) at {path} links[{i}][{attr!r}] needs a "
                        f"string value, got {value!r}."
                    )
            if "rel" not in link:
                raise ValidationError(
                    f'Page(...) at {path} links[{i}] is missing a "rel" '
                    f"attribute -- every <link> needs one, got {link!r}."
                )


def _validate_shell_persistent(node: ARKNode, *, path: str) -> None:
    """
    htmx-4 (docs/Backends/REFACTOR-INDEX.md row 9): `shell_persistent`
    is inert (not just unused, but never even checked) on a site that
    never sets `Site(app_shell=True)` -- this validates the prop's own
    shape regardless, the same "fail loudly at build time, not
    silently in the browser" discipline `_validate_responsive_style`/
    `_validate_page_head_extensions` already hold for props that are
    only meaningful in combination with something else.
    """
    shell_persistent = node.props.get("shell_persistent")
    if not shell_persistent:
        return
    node_id = node.props.get("id")
    if not isinstance(node_id, str) or not node_id.strip():
        raise ValidationError(
            f"{node.type!r} at {path} has shell_persistent=True but no "
            f"(non-empty) id -- htmx's hx-preserve, which this prop "
            f"compiles to, can only keep an element across a boosted "
            f"navigation by matching a stable id between the old and "
            f"newly-fetched page. Add id=\"...\" to this node."
        )


def _validate_behavior_props(node: ARKNode, *, path: str, mutable_state: frozenset[str]) -> None:
    on_click = node.props.get("on_click")
    if on_click is None:
        return

    if isinstance(on_click, ActionRef):
        _validate_action(on_click, path=path, mutable_state=mutable_state)
        return

    if on_click not in KNOWN_BEHAVIORS:
        known = ", ".join(sorted(KNOWN_BEHAVIORS))
        raise ValidationError(
            f"{node.type!r} at {path} has on_click={on_click!r}, which isn't a "
            f"recognized behavior or Action.*(...) reference. Known behaviors "
            f"are: {known}."
        )
    if "behavior_target" not in node.props:
        raise ValidationError(
            f"{node.type!r} at {path} has on_click={on_click!r} but no "
            f"`behavior_target` prop (a CSS selector for the element(s) it "
            f"should act on)."
        )


def _validate_state_declaration(node: ARKNode, *, path: str, parent_is_page: bool) -> None:
    if not parent_is_page:
        raise ValidationError(
            f"State(...) at {path} may only be declared as a direct child of "
            f"Page(...) -- state belongs to the page, not to a nested "
            f"component. Move it up to the top level of Page(...)."
        )
    name = node.props.get("name")
    if not isinstance(name, str) or not name:
        raise ValidationError(f"State(...) at {path} needs a non-empty string name.")


def _validate_derive_ref(
    derive: DerivationRef, *, path: str, deps: tuple[str, ...]
) -> None:
    """
    `vdom-4`: structural checks for a `Computed(...)`'s `derive=`
    value, mirroring `_validate_action`'s discipline for `ActionRef`.
    Checked once `deps` itself is known to be a non-empty tuple of
    strings (`_validate_computed_declaration` checks that first), so
    `deps` here is trusted shape, just not yet cross-checked against
    the page's declared state -- that cross-check
    (`_collect_page_reactive_names`) happens after every page's
    `State(...)`/`Computed(...)` names are known, to allow a
    `Computed(...)` to depend on another `Computed(...)` declared
    later in `Page(...)`'s children.
    """
    if not isinstance(derive, DerivationRef):
        raise ValidationError(
            f"Computed(...) at {path} has derive={derive!r}, which isn't a "
            f"Derive.*(...) reference."
        )
    spec = DERIVATION_REGISTRY.get(derive.kind)
    if spec is None:
        known = ", ".join(sorted(DERIVATION_REGISTRY))
        raise ValidationError(
            f"Computed(...) at {path} uses unknown derivation {derive.kind!r}. "
            f"Known derivations are: {known}."
        )
    count = len(derive.names)
    if count < spec.min_names or (spec.max_names is not None and count > spec.max_names):
        arity = (
            f"exactly {spec.min_names}"
            if spec.max_names == spec.min_names
            else f"at least {spec.min_names}"
            if spec.max_names is None
            else f"between {spec.min_names} and {spec.max_names}"
        )
        raise ValidationError(
            f"Computed(...) at {path} uses Derive.{derive.kind}(...) with "
            f"{count} name(s) ({derive.names!r}), but Derive.{derive.kind}(...) "
            f"needs {arity}."
        )
    missing_from_deps = [name for name in derive.names if name not in deps]
    if missing_from_deps:
        raise ValidationError(
            f"Computed(...) at {path} uses Derive.{derive.kind}(...) reading "
            f"{missing_from_deps!r}, which isn't in this Computed(...)'s own "
            f"deps={deps!r}. Every name Derive.*(...) reads must also be "
            f"listed in deps."
        )
    unknown_args = set(derive.args) - set(spec.extra_args)
    if unknown_args:
        raise ValidationError(
            f"Computed(...) at {path} passes unexpected argument(s) "
            f"{sorted(unknown_args)!r} to Derive.{derive.kind}(...). Known "
            f"arguments for Derive.{derive.kind}(...) are: {spec.extra_args!r}."
        )
    missing_args = [name for name in spec.extra_args if name not in derive.args]
    if missing_args:
        raise ValidationError(
            f"Computed(...) at {path} is missing required argument(s) "
            f"{missing_args!r} for Derive.{derive.kind}(...)."
        )
    if derive.kind == "compare":
        op = derive.args.get("op")
        if op not in COMPARE_OPS:
            known = ", ".join(sorted(COMPARE_OPS))
            raise ValidationError(
                f"Computed(...) at {path} uses Derive.compare(...) with "
                f"unknown op {op!r}. Known ops are: {known}."
            )


def _validate_computed_declaration(node: ARKNode, *, path: str, parent_is_page: bool) -> None:
    if not parent_is_page:
        raise ValidationError(
            f"Computed(...) at {path} may only be declared as a direct child "
            f"of Page(...) -- like State(...), it belongs to the page, not "
            f"to a nested component. Move it up to the top level of "
            f"Page(...)."
        )
    name = node.props.get("name")
    if not isinstance(name, str) or not name:
        raise ValidationError(f"Computed(...) at {path} needs a non-empty string name.")
    deps = node.props.get("deps")
    if not isinstance(deps, tuple) or not deps or not all(isinstance(d, str) and d for d in deps):
        raise ValidationError(
            f"Computed({name!r}) at {path} needs a non-empty deps=(...) tuple "
            f"of non-empty state/computed names, got {deps!r}."
        )
    _validate_derive_ref(node.props.get("derive"), path=path, deps=deps)


def validate_node(
    node: ARKNode,
    *,
    path: str = "root",
    page_state: frozenset[str] = frozenset(),
    mutable_state: frozenset[str] = frozenset(),
    parent_is_page: bool = False,
) -> None:
    """
    `page_state` is the *bindable* set -- every `State(...)`/
    `Computed(...)` name declared on the page -- used for `Bind(...)`/
    `bind_class=` validation. `mutable_state` is the narrower `vdom-4`
    restriction of that set to `State(...)` names only, used for
    `Action.*(...)` validation: a `Computed(...)` name is readable
    (bindable) but never a valid mutation target.
    """
    if node.type == "Bind":
        _validate_bind(node, path=path, page_state=page_state)
        return

    if node.type == "State":
        _validate_state_declaration(node, path=path, parent_is_page=parent_is_page)
        return

    if node.type == "Computed":
        _validate_computed_declaration(node, path=path, parent_is_page=parent_is_page)
        return

    spec = SCHEMA.get(node.type)
    if spec is None:
        known = ", ".join(sorted(SCHEMA))
        raise ValidationError(
            f"Unknown component type {node.type!r} at {path}. "
            f"Known component types are: {known}."
        )

    for prop_name in spec.required_props:
        if prop_name not in node.props:
            raise ValidationError(
                f"{node.type!r} at {path} is missing required prop {prop_name!r}."
            )

    _validate_behavior_props(node, path=path, mutable_state=mutable_state)
    _validate_class_bind(node, path=path, page_state=page_state)
    _validate_responsive_style(node, path=path)
    _validate_shell_persistent(node, path=path)
    if node.type == "Page":
        _validate_page_head_extensions(node, path=path)

    if not spec.allow_children and node.children:
        raise ValidationError(f"{node.type!r} at {path} must not have children.")

    if spec.text_only_children:
        for i, child in enumerate(node.children):
            if isinstance(child, ARKNode):
                if child.type == "Bind":
                    _validate_bind(child, path=f"{path}/children[{i}]", page_state=page_state)
                    continue
                raise ValidationError(
                    f"{node.type!r} at {path} can only contain text (or "
                    f"Bind(...)), but found a nested {child.type!r} component "
                    f"at {path}/children[{i}]. Move the {child.type!r} outside "
                    f"of {node.type!r}."
                )
            if not isinstance(child, str):
                raise ValidationError(
                    f"{node.type!r} at {path} expected a string child, got "
                    f"{type(child).__name__!r}."
                )
        return

    for i, child in enumerate(node.children):
        if isinstance(child, ARKNode):
            validate_node(
                child,
                path=f"{path}/{child.type}[{i}]",
                page_state=page_state,
                mutable_state=mutable_state,
                parent_is_page=(node.type == "Page"),
            )
        elif not isinstance(child, str):
            raise ValidationError(
                f"{node.type!r} at {path} has an unexpected child of type "
                f"{type(child).__name__!r} at position {i}."
            )


def _find_computed_cycle(computed_deps: dict[str, tuple[str, ...]]) -> list[str] | None:
    """
    DFS cycle detection over the `Computed(...) -> Computed(...)` edges
    of a page's dependency graph (edges to a `State(...)` name are
    leaves -- state has no further deps to walk). Returns the cycle as
    a list of names (first repeated last) if one exists, else `None`.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {name: WHITE for name in computed_deps}
    stack: list[str] = []

    def visit(name: str) -> list[str] | None:
        color[name] = GRAY
        stack.append(name)
        for dep in computed_deps[name]:
            if dep not in computed_deps:
                continue  # a State(...) dependency -- not part of this graph
            if color[dep] == GRAY:
                cycle_start = stack.index(dep)
                return stack[cycle_start:] + [dep]
            if color[dep] == WHITE:
                found = visit(dep)
                if found is not None:
                    return found
        stack.pop()
        color[name] = BLACK
        return None

    for name in computed_deps:
        if color[name] == WHITE:
            found = visit(name)
            if found is not None:
                return found
    return None


def _collect_page_reactive_names(page: ARKNode, route: str) -> tuple[frozenset[str], frozenset[str]]:
    """
    Walk `page`'s direct children once, gathering every `State(...)`/
    `Computed(...)` declaration. Returns `(bindable, mutable_state)`:
    `bindable` is every name `Bind(...)`/`bind_class=` may reference
    (`State(...)` + `Computed(...)`); `mutable_state` is the narrower
    `State(...)`-only set `Action.*(...)` may target (`vdom-4` --
    see this module's docstring, point 13).

    Also performs the cross-declaration checks that can only happen
    once every name on the page is known: a `Computed(...)`'s `deps`
    must each resolve to a `State(...)`/other `Computed(...)`
    declared on this same page (forward references allowed -- a
    `Computed(...)` may depend on one declared later in `Page(...)`'s
    children), and the resulting dependency graph must not contain a
    cycle.
    """
    state_names: set[str] = set()
    computed_specs: dict[str, tuple[tuple[str, ...], ARKNode]] = {}

    for child in page.children:
        if not isinstance(child, ARKNode):
            continue
        if child.type == "State":
            name = child.props.get("name")
            if not isinstance(name, str) or not name:
                raise ValidationError(
                    f"State(...) on page {route!r} needs a non-empty string name."
                )
            if name in state_names or name in computed_specs:
                raise ValidationError(
                    f"State {name!r} is declared more than once on page {route!r}."
                )
            state_names.add(name)
        elif child.type == "Computed":
            name = child.props.get("name")
            if not isinstance(name, str) or not name:
                raise ValidationError(
                    f"Computed(...) on page {route!r} needs a non-empty string name."
                )
            if name in state_names or name in computed_specs:
                raise ValidationError(
                    f"State/Computed {name!r} is declared more than once on "
                    f"page {route!r}."
                )
            deps = child.props.get("deps")
            if not isinstance(deps, tuple):
                deps = ()
            computed_specs[name] = (deps, child)

    known = frozenset(state_names) | frozenset(computed_specs)

    for name, (deps, child) in computed_specs.items():
        unknown_deps = [d for d in deps if d not in known]
        if unknown_deps:
            raise ValidationError(
                f"Computed({name!r}) on page {route!r} depends on "
                f"{unknown_deps!r}, which isn't declared on this page. "
                f"State/Computed declared on this page: "
                f"{', '.join(sorted(known)) or '(none declared)'}."
            )

    cycle = _find_computed_cycle({name: deps for name, (deps, _child) in computed_specs.items()})
    if cycle is not None:
        raise ValidationError(
            f"Computed(...) dependency cycle on page {route!r}: "
            f"{' -> '.join(cycle)}."
        )

    return known, frozenset(state_names)


def validate_page(route: str, page: ARKNode) -> None:
    if page.type != "Page":
        raise ValidationError(
            f"Page function for route {route!r} must return Page(...) as its "
            f"root node, got {page.type!r} instead."
        )
    page_state, mutable_state = _collect_page_reactive_names(page, route)
    validate_node(
        page,
        path=f"page:{route}",
        page_state=page_state,
        mutable_state=mutable_state,
        parent_is_page=False,
    )


def validate_ark_ast(pages: dict[str, ARKNode]) -> None:
    """Validate every page. Raises ValidationError on the first problem found."""
    for route, page in pages.items():
        validate_page(route, page)
