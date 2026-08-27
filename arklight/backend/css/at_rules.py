"""
CSS Backend -- at-rule + selector-rule rendering (structural addendum,
see docs/DESIGN-NOTES.md "CSS selector algebra + at-rule vocabulary").

Same discipline as `custom_styles.py`'s `render_*` functions: each
function here is pure -- structured data in, a CSS string out -- with
no re-validation of its own. Everything it's handed has already been
validated at the `arklight.api.Site.*` call site (selector strings
through `arklight.backend.css.selectors.parse_selector_list`, property/
value pairs through the same `_validate_css_syntax` every other
`Site.style*` method uses), so a malformed input reaching this module
would mean a caller went around the public API -- same posture
`custom_styles._split_rules` already takes for a bad pseudo-class key.
"""

from __future__ import annotations


def _render_declarations(rules: dict[str, str], indent: str = "  ") -> list[str]:
    return [f"{indent}{prop}: {rules[prop]};" for prop in sorted(rules)]


def render_selector_rules(selector_rules: list[tuple[str, dict[str, str]]]) -> str:
    """
    Turn `(canonical_selector_text, {prop: value})` pairs -- registered
    via `Site.style_selector(...)` -- into real CSS blocks. `selector`
    is already the canonical text `arklight.backend.css.selectors
    .render_selector_list` produced from a validated AST, so this
    module never re-parses or re-validates it; it only writes it out
    as a literal selector. Kept in registration order (not sorted,
    unlike `render_custom_styles`): a combinator/attribute/pseudo-
    element selector routinely targets the same element as a plain
    class rule elsewhere in the sheet, and author call order is the
    only signal available for which one should win the cascade.
    """
    if not selector_rules:
        return ""

    blocks = [
        "\n/* Structural CSS selectors -- registered via "
        "`site.style_selector(...)`. See docs/DESIGN-NOTES.md "
        '("CSS selector algebra + at-rule vocabulary"). */',
    ]
    for selector, rules in selector_rules:
        lines = [f"{selector} {{", *_render_declarations(rules), "}"]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def render_keyframes(keyframes: dict[str, dict[str, dict[str, str]]]) -> str:
    """
    Turn `name -> {stop: {prop: value}}` registrations -- from
    `Site.keyframes(name, frames)` -- into `@keyframes name { ... }`
    blocks, sorted by animation name for deterministic output. Each
    stop (`"0%"`/`"50%"`/`"100%"`/`"from"`/`"to"`) is emitted in the
    order `Site.keyframes` stored it (already sorted there -- see its
    docstring for why stop order is normalized at the call site rather
    than here).
    """
    if not keyframes:
        return ""

    blocks = [
        "\n/* @keyframes -- registered via `site.keyframes(...)`. */",
    ]
    for name in sorted(keyframes):
        lines = [f"@keyframes {name} {{"]
        for stop, rules in keyframes[name].items():
            lines.append(f"  {stop} {{")
            lines.extend(f"  {line}" for line in _render_declarations(rules))
            lines.append("  }")
        lines.append("}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def render_font_faces(font_faces: list[dict[str, str]]) -> str:
    """
    Turn `Site.font_face(...)` registrations into `@font-face { ... }`
    blocks, one per call, in registration order (later calls can
    legitimately add another `@font-face` for the same family at a
    different weight/style -- order doesn't matter for correctness,
    but preserving it keeps output stable and matches the "author
    order" convention `render_selector_rules`/`render_media_queries`
    already use). Each entry is a flat `{descriptor: value}` dict
    already fully assembled by `Site.font_face` (including `src`,
    pre-joined into one valid `src` value).
    """
    if not font_faces:
        return ""

    blocks = [
        "\n/* @font-face -- registered via `site.font_face(...)`. */",
    ]
    for descriptors in font_faces:
        lines = ["@font-face {", *_render_declarations(descriptors), "}"]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def render_container_queries(container_queries: list[tuple[str, str, str, dict[str, str]]]) -> str:
    """
    Turn `(name_or_None, condition, selector, {prop: value})` tuples --
    from `Site.container_query(...)` -- into `@container name?
    (condition) { selector { ... } }` blocks. `selector` is already
    canonical text (see `render_selector_rules`). Kept in registration
    order, same reasoning as `render_media_queries`.
    """
    if not container_queries:
        return ""

    blocks = [
        "\n/* @container -- registered via `site.container_query(...)`. */",
    ]
    for name, condition, selector, rules in container_queries:
        prefix = f"@container {name} " if name else "@container "
        lines = [
            f"{prefix}({condition}) {{",
            f"  {selector} {{",
            *(f"  {line}" for line in _render_declarations(rules)),
            "  }",
            "}",
        ]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def render_supports_rules(supports_rules: list[tuple[str, str, dict[str, str]]]) -> str:
    """
    Turn `(condition, selector, {prop: value})` tuples -- from
    `Site.supports(...)` -- into `@supports (condition) { selector {
    ... } }` blocks. Kept in registration order, same reasoning as
    `render_media_queries`.
    """
    if not supports_rules:
        return ""

    blocks = [
        "\n/* @supports -- registered via `site.supports(...)`. */",
    ]
    for condition, selector, rules in supports_rules:
        lines = [
            f"@supports ({condition}) {{",
            f"  {selector} {{",
            *(f"  {line}" for line in _render_declarations(rules)),
            "  }",
            "}",
        ]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def render_page_rules(page_rules: list[tuple[str | None, dict[str, str]]]) -> str:
    """
    Turn `(pseudo_or_None, {prop: value})` tuples -- from
    `Site.page_rule(...)` -- into `@page` / `@page :pseudo { ... }`
    blocks, in registration order.
    """
    if not page_rules:
        return ""

    blocks = [
        "\n/* @page -- registered via `site.page_rule(...)`. */",
    ]
    for pseudo, rules in page_rules:
        selector = f"@page :{pseudo}" if pseudo else "@page"
        lines = [f"{selector} {{", *_render_declarations(rules), "}"]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def render_imports(imports: list[str]) -> str:
    """
    Turn `Site.import_style(url)` registrations into `@import
    url("...");` statements, in registration order. Per the CSS spec,
    `@import` statements must precede every other rule in the
    stylesheet (aside from `@charset`), so `CSSBackend.render` places
    this block first -- see `arklight/backend/css/render.py`.
    """
    if not imports:
        return ""

    lines = [
        "/* @import -- registered via `site.import_style(...)`. Must "
        "stay first in the stylesheet -- see this function's docstring. */",
    ]
    lines.extend(f'@import url("{url}");' for url in imports)
    return "\n".join(lines) + "\n\n"
