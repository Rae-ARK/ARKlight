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
`base_stylesheet.py` (static default CSS text) today, with
`:root`/`@property` generation and custom-class rendering below staged
to move out the same way in the following refactor stages.
"""

from __future__ import annotations

from arklight.backend.base import Backend
from arklight.backend.css.base_stylesheet import BASE_CSS_BODY, BASE_CSS_HEADER
from arklight.ir.build import WebsiteIR

# Where the HTML backend expects to find the generated stylesheet,
# relative to the output directory root. Shared as a constant so both
# backends agree on the filename without importing each other's
# rendering internals.
STYLESHEET_PATH = "styles.css"

# CSS backend refactor: the `:root` block used to be baked directly into
# BASE_CSS as a constant -- which is exactly why `--ark-max-width`
# (and, less visibly, `--ark-bg`) were structurally unreachable from any
# site-level API (see docs/CONTAINER-WIDTH-BUG.md and
# `Site.css_var_overrides` in arklight/api.py). This table is now the
# single source of truth for both the default value of every
# `:root`-declared `--ark-*` variable AND the order it's emitted in;
# `_render_root_and_property_rules` below reads it, merges in whatever
# a site passed via `Site(max_width=..., bg=...)`, and generates the
# `:root { ... }` block instead of it being hand-written CSS.
#
# Only variables `body` (or another element) reads *directly* belong
# here -- variables that already flow through a `var(--x, fallback)`
# call at their point of use (`--ark-grid-min`, `--ark-stack-space`,
# ...) are already reachable by a site overriding them via a `style=`
# prop on a wrapper, per the same reachability rule; adding them to
# this table is tracked as a follow-up, not done in this pass.
ROOT_VAR_DEFAULTS: dict[str, str] = {
    "--ark-bg": "#ffffff",
    "--ark-text": "#1a1a2e",
    "--ark-muted": "#5b5b76",
    "--ark-accent": "#4f46e5",
    "--ark-accent-hover": "#4338ca",
    "--ark-border": "#e5e5f0",
    # The one-line fix for the container-width bug: `min()` combines a
    # fluid bound (page never touches the viewport edge) with an
    # absolute cap (~1200px, wide enough for multi-column layouts,
    # narrow enough to stay readable) -- the same "intrinsic" idiom
    # (clamp/min/minmax) the rest of BASE_CSS already leans on for
    # .switcher/.grid/.fluid-heading, instead of a fixed 720px column.
    "--ark-max-width": "min(100% - 3rem, 75rem)",
}

# `@property` gives the browser (and a site author debugging output) a
# real type to check a `--ark-*` value against, instead of every custom
# property being an untyped string substitution where a typo
# (`--ark-max-width: 75re;`) fails silently. `syntax` values are CSS
# <syntax-string>s -- kept as a small table next to ROOT_VAR_DEFAULTS
# rather than hand-written per-variable, since it's mechanical to get
# right once and easy to get subtly wrong by hand each time.
ROOT_VAR_SYNTAX: dict[str, str] = {
    "--ark-bg": '"<color>"',
    "--ark-text": '"<color>"',
    "--ark-muted": '"<color>"',
    "--ark-accent": '"<color>"',
    "--ark-accent-hover": '"<color>"',
    "--ark-border": '"<color>"',
    "--ark-max-width": '"<length-percentage>"',
}


def _render_root_and_property_rules(overrides: dict[str, str]) -> str:
    """
    Generate the `:root { --ark-*: ...; }` block plus one `@property`
    block per variable, merging `overrides` (from `Site(max_width=...,
    bg=...)`, i.e. `ir.css_var_overrides`) over ROOT_VAR_DEFAULTS.

    `@property`'s `initial-value` is always the *default*, not whatever
    override is active -- per spec it's the fallback used before any
    value (including the `:root` declaration itself) is assigned, not a
    mirror of the current value, and it must be a value the declared
    `syntax` can parse on its own.
    """
    root_lines = [":root {"]
    for var_name, default in ROOT_VAR_DEFAULTS.items():
        value = overrides.get(var_name, default)
        root_lines.append(f"  {var_name}: {value};")
    root_lines.append("}")

    property_blocks = []
    for var_name, default in ROOT_VAR_DEFAULTS.items():
        syntax = ROOT_VAR_SYNTAX[var_name]
        property_blocks.append(
            f"@property {var_name} {{\n"
            f"  syntax: {syntax};\n"
            f"  inherits: true;\n"
            f"  initial-value: {default};\n"
            f"}}"
        )

    return "\n".join(root_lines) + "\n\n" + "\n\n".join(property_blocks)


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
        root_and_properties = _render_root_and_property_rules(ir.css_var_overrides)
        css = (
            BASE_CSS_HEADER
            + "\n"
            + root_and_properties
            + "\n\n"
            + BASE_CSS_BODY
            + _render_custom_styles(ir.custom_styles)
        )
        return {STYLESHEET_PATH: css}
