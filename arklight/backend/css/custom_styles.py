"""
CSS Backend -- custom class rendering (`site.style(...)` registrations).

CSS backend refactor, Stage 3 (see docs/CSS-BACKEND-REFACTOR.md):
`_render_custom_styles` used to live inline in `render.py` alongside
static CSS text and orchestration. It's pure -- a `dict[str, dict[str,
str]]` in, a CSS string out -- with no dependency on the rest of the
backend, so it moves out unchanged into its own module, same pattern as
Stage 2's `design_tokens.py`.
"""

from __future__ import annotations


def render_custom_styles(custom_styles: dict[str, dict[str, str]]) -> str:
    """
    Turn `site.style(name, {prop: value})` registrations (v0.042) into
    real `.name { prop: value; ... }` CSS blocks, sorted by class name
    for deterministic output across runs. Empty input -> empty string
    (nothing appended to the stylesheet).
    """
    if not custom_styles:
        return ""

    blocks = [
        "\n/* Custom classes -- registered via `site.style(...)`. */",
    ]
    for class_name in sorted(custom_styles):
        rules = custom_styles[class_name]
        lines = [f".{class_name} {{"]
        for prop in sorted(rules):
            lines.append(f"  {prop}: {rules[prop]};")
        lines.append("}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"
