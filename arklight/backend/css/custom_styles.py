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
