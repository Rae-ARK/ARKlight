"""
CSS Backend.

v0.002 milestone. ARKlight ships one global stylesheet by default so a
freshly-generated site looks intentional out of the box, with zero CSS
written by the user -- matching "beginner friendly" and "Flask-like
simplicity". It targets the same tag mapping the HTML backend uses
(h1-h6, p, button, a, div, ul/li), plus a couple of small utility
classes (`.nav`, `.page`) that the built-in components can opt into via
the `class_name` prop.

Per-node customization doesn't require touching this file: any
component can carry a `style={...}` dict prop (rendered as an inline
`style` attribute by the HTML backend) or a `class_name="..."` prop
(rendered as `class`) to layer custom rules or override these defaults.

This module is the orchestrator (see docs/CSS-BACKEND-REFACTOR.md):
`CSSBackend.render` composes output from focused, single-responsibility
sibling modules rather than doing the generation itself --
`base_stylesheet.py` (static default CSS text) and `design_tokens.py`
(`:root`/`@property` generation) today, with custom-class rendering
below staged to move out the same way in the next refactor stage.
"""

from __future__ import annotations

from arklight.backend.base import Backend
from arklight.backend.css.base_stylesheet import BASE_CSS_BODY, BASE_CSS_HEADER
from arklight.backend.css.design_tokens import render_root_and_property_rules
from arklight.ir.build import WebsiteIR

# Where the HTML backend expects to find the generated stylesheet,
# relative to the output directory root. Shared as a constant so both
# backends agree on the filename without importing each other's
# rendering internals.
STYLESHEET_PATH = "styles.css"


def _render_custom_styles(custom_styles: dict[str, dict[str, str]]) -> str:
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


class CSSBackend(Backend):
    name = "css"

    def render(self, ir: WebsiteIR) -> dict[str, str]:
        # v0.002 ships a single, site-wide stylesheet; v0.042 appends
        # any custom classes a site registered via `site.style(...)`
        # (see `ir.custom_styles`, threaded from `Site.custom_styles`
        # through `build_website_ir`) after the fixed base stylesheet,
        # so custom classes can override base rules by cascade order.
        #
        # CSS backend refactor: `:root` (+ its `@property` typing) is no
        # longer part of the static BASE_CSS constant -- it's generated
        # here from ROOT_VAR_DEFAULTS merged with `ir.css_var_overrides`
        # (threaded from `Site(max_width=..., bg=...)`), so those two
        # variables are finally reachable from site code instead of
        # baked in. Everything else in BASE_CSS_BODY is unchanged.
        root_and_properties = render_root_and_property_rules(ir.css_var_overrides)
        css = (
            BASE_CSS_HEADER
            + "\n"
            + root_and_properties
            + "\n\n"
            + BASE_CSS_BODY
            + _render_custom_styles(ir.custom_styles)
        )
        return {STYLESHEET_PATH: css}
