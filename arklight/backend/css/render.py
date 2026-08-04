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

This module is the orchestrator (see docs/CSS-BACKEND-REFACTOR.md,
Stage 4): `CSSBackend.render` is now pure composition of three sibling
modules -- `base_stylesheet.py` (static default CSS text),
`design_tokens.py` (`:root`/`@property` generation), and
`custom_styles.py` (custom-class rendering) -- with no generation logic
of its own left in this file.
"""

from __future__ import annotations

from arklight.backend.base import Backend
from arklight.backend.css.base_stylesheet import BASE_CSS_BODY, BASE_CSS_HEADER
from arklight.backend.css.custom_styles import render_custom_styles
from arklight.backend.css.design_tokens import render_root_and_property_rules
from arklight.ir.build import WebsiteIR

# Where the HTML backend expects to find the generated stylesheet,
# relative to the output directory root. Shared as a constant so both
# backends agree on the filename without importing each other's
# rendering internals.
STYLESHEET_PATH = "styles.css"


class CSSBackend(Backend):
    name = "css"

    def render(self, ir: WebsiteIR) -> dict[str, str]:
        # v0.002 ships a single, site-wide stylesheet. Cascade order
        # matters: base rules, then `:root`/`@property` design tokens
        # (`ir.css_var_overrides`, from `Site(max_width=..., bg=...)`),
        # then the fixed tag/utility rules, then v0.042 custom classes
        # (`ir.custom_styles`, from `site.style(...)`) last so they can
        # override any of the above.
        css = (
            BASE_CSS_HEADER
            + "\n"
            + render_root_and_property_rules(ir.css_var_overrides)
            + "\n\n"
            + BASE_CSS_BODY
            + render_custom_styles(ir.custom_styles)
        )
        return {STYLESHEET_PATH: css}
