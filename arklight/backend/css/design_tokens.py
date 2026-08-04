"""
CSS Backend -- design tokens (`:root` custom properties + `@property`
typing).

CSS backend refactor, Stage 2 (see docs/CSS-BACKEND-REFACTOR.md): the
`:root` block used to be baked directly into BASE_CSS as a constant --
which is exactly why `--ark-max-width` (and, less visibly, `--ark-bg`)
were structurally unreachable from any site-level API. ROOT_VAR_DEFAULTS
is now the single source of truth for both the default value of every
`:root`-declared `--ark-*` variable AND the order it's emitted in;
`render_root_and_property_rules` reads it, merges in whatever a site
passed via `Site(max_width=..., bg=...)`, and generates the
`:root { ... }` block instead of it being hand-written CSS.

Only variables `body` (or another element) reads *directly* belong
here -- variables that already flow through a `var(--x, fallback)` call
at their point of use (`--ark-grid-min`, `--ark-stack-space`, ...) are
already reachable by a site overriding them via a `style=` prop on a
wrapper, per the same reachability rule; adding them to this table is
tracked as a follow-up, not done in this pass.
"""

from __future__ import annotations

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


def render_root_and_property_rules(overrides: dict[str, str]) -> str:
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
