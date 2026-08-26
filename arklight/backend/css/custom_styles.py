"""
CSS Backend -- custom class rendering (`site.style(...)` registrations).

CSS backend refactor, Stage 3 (see docs/CSS-BACKEND-REFACTOR.md):
`_render_custom_styles` used to live inline in `render.py` alongside
static CSS text and orchestration. It's pure -- a `dict[str, dict[str,
str]]` in, a CSS string out -- with no dependency on the rest of the
backend, so it moves out unchanged into its own module, same pattern as
Stage 2's `design_tokens.py`.

CSS backend, pseudo-class shorthand (docs/CSS-BACKEND-REFACTOR.md
"Stage 2"): a rules key may also be ":<pseudo>:<property>" (e.g.
":hover:background"), validated and split out by
`arklight.api.Site.style()` before it ever reaches `custom_styles` --
`arklight.api.ALLOWED_PSEUDO_CLASSES`/`_CSS_PSEUDO_RULE_RE` is the
single source of truth for what's a valid key, so this module only
groups and renders, it never re-validates.
"""

from __future__ import annotations

import re

# Mirrors `arklight.api._CSS_PSEUDO_RULE_RE` exactly (kept as a
# separate constant, not an import, so this module has no dependency
# on `arklight.api` -- see the module docstring in
# `docs/CSS-BACKEND-REFACTOR.md` on why each backend module stays a
# pure function of its own inputs). `Site.style()` has already
# rejected anything that wouldn't match this, so a non-match here would
# mean a caller went around `Site.style()` -- see `_split_rules` below.
_PSEUDO_KEY_RE = re.compile(r"^:(?P<pseudo>[A-Za-z-]+):(?P<prop>--[A-Za-z0-9-]+|-?[A-Za-z][A-Za-z0-9-]*)$")


def _split_rules(
    rules: dict[str, str],
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """
    Split one class's rules into (base props, {pseudo_name: {prop: value}}).
    `rules` keys are either a plain property or a ":pseudo:property"
    pseudo-class-scoped key -- see the module docstring.
    """
    base: dict[str, str] = {}
    pseudo_groups: dict[str, dict[str, str]] = {}
    for prop, value in rules.items():
        if not prop.startswith(":"):
            base[prop] = value
            continue
        match = _PSEUDO_KEY_RE.match(prop)
        if not match:
            # Site.style() validates every key against this exact
            # pattern before it's ever stored, so reaching this means a
            # caller built `custom_styles` directly instead of going
            # through Site.style() -- fail loudly rather than silently
            # dropping the rule or emitting broken CSS.
            raise ValueError(
                f"custom_styles rule key {prop!r} isn't a valid pseudo-class "
                f"key ':pseudo:property' -- did this bypass Site.style()?"
            )
        pseudo_groups.setdefault(match.group("pseudo"), {})[match.group("prop")] = value
    return base, pseudo_groups


def render_custom_styles(custom_styles: dict[str, dict[str, str]]) -> str:
    """
    Turn `site.style(name, {prop: value})` registrations (v0.042) into
    real `.name { prop: value; ... }` CSS blocks, sorted by class name
    for deterministic output across runs. A pseudo-class-scoped key
    (":hover:background", see module docstring) renders as its own
    `.name:hover { background: value; }` block, right after the base
    block for that class, sorted by pseudo-class name. Empty input ->
    empty string (nothing appended to the stylesheet).
    """
    if not custom_styles:
        return ""

    blocks = [
        "\n/* Custom classes -- registered via `site.style(...)`. */",
    ]
    for class_name in sorted(custom_styles):
        base, pseudo_groups = _split_rules(custom_styles[class_name])

        if base:
            lines = [f".{class_name} {{"]
            for prop in sorted(base):
                lines.append(f"  {prop}: {base[prop]};")
            lines.append("}")
            blocks.append("\n".join(lines))

        for pseudo_name in sorted(pseudo_groups):
            rules = pseudo_groups[pseudo_name]
            lines = [f".{class_name}:{pseudo_name} {{"]
            for prop in sorted(rules):
                lines.append(f"  {prop}: {rules[prop]};")
            lines.append("}")
            blocks.append("\n".join(lines))

    return "\n\n".join(blocks) + "\n"


def render_responsive_styles(responsive_rules: list[tuple[str, str, dict[str, str]]]) -> str:
    """
    v0.048 Stage B ("CSS media queries + `<head>` extension" -- see
    docs/DESIGN-NOTES.md) -- turn `(condition, generated_class,
    {prop: value})` triples (one per media condition on every node
    that carried a `responsive_style={...}` prop, collected by
    `arklight.ir.build._ResponsiveStyleCollector`) into real
    `@media <condition> { .arkgen-N { ... } }` blocks.

    Unlike `render_media_queries` above, `condition` is inserted
    verbatim right after `@media ` rather than auto-wrapped in
    parentheses: `responsive_style`'s keys are documented (see
    `arklight.ir.validate._validate_responsive_style`) as the full
    condition text a site author wants inside `@media <here> { ... }`
    -- e.g. `"(max-width: 600px)"` or a compound condition like
    `"screen and (max-width: 600px)"` -- so this function must not
    assume a single bare feature that always needs its own wrapping
    parens the way `site.media_query(condition, ...)`'s bare-condition
    convention does.

    Property names get the same `_`->`-` conversion the inline
    `style={...}` prop's `_style_dict_to_css` already does (v0.048
    Stage B "extends the existing `style={...}` convention" -- see
    docs/DESIGN-NOTES.md), unlike `render_media_queries`/
    `render_custom_styles` above, which expect literal CSS property
    names already, since those are registered through `Site.style()`/
    `Site.media_query()` rather than authored as a Python-kwarg-shaped
    dict on a node. Kept in registration (site-build) order, same
    reasoning as `render_media_queries` -- a later block winning the
    cascade for the same generated class is meaningful here too, since
    a single node's `responsive_style` may register more than one
    condition against its own class. Empty input -> empty string.
    """
    if not responsive_rules:
        return ""

    blocks = [
        "\n/* v0.048 Stage B: @media blocks -- generated from nodes' "
        "`responsive_style={...}` props. See docs/DESIGN-NOTES.md "
        '("v0.048: CSS media queries + `<head>` extension") and '
        "docs/EXPERIMENTAL-APIS.md (gated under `css-media-queries`, "
        "same as `site.media_query(...)`). */",
    ]
    for condition, class_name, rules in responsive_rules:
        lines = [f"@media {condition} {{", f"  .{class_name} {{"]
        for prop in sorted(rules):
            css_prop = prop.replace("_", "-")
            lines.append(f"    {css_prop}: {rules[prop]};")
        lines.append("  }")
        lines.append("}")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks) + "\n"


def render_media_queries(media_queries: list[tuple[str, str, dict[str, str]]]) -> str:
    """
    EXPERIMENTAL (see `docs/EXPERIMENTAL-APIS.md`) -- turn
    `site.media_query(condition, class_name, rules)` registrations
    into real `@media (condition) { .class_name { ... } }` blocks,
    kept in registration order (unlike `render_custom_styles`, which
    sorts by class name -- media queries commonly rely on later blocks
    winning the cascade for the same class, so preserving call order
    matters here). Empty input -> empty string.
    """
    if not media_queries:
        return ""

    blocks = [
        "\n/* Experimental: @media blocks -- registered via "
        "`site.media_query(...)`. See docs/EXPERIMENTAL-APIS.md. */",
    ]
    for condition, class_name, rules in media_queries:
        lines = [f"@media ({condition}) {{", f"  .{class_name} {{"]
        for prop in sorted(rules):
            lines.append(f"    {prop}: {rules[prop]};")
        lines.append("  }")
        lines.append("}")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks) + "\n"
