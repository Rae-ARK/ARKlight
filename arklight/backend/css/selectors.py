"""
CSS Backend -- selector grammar (structural addendum, see
docs/DESIGN-NOTES.md "CSS selector algebra + at-rule vocabulary").

`arklight.api.Site.style(name, rules)` only ever emits one flat
`.name { ... }` block -- deliberately, since a bare pseudo-class
shorthand (":hover:background") is the only "selector-shaped" thing it
accepts. That's a real structural ceiling: it can't express pseudo-
elements, parameterized pseudo-classes (`:not()`, `:has()`, `:is()`,
`:where()`, `:nth-child()`), attribute selectors, combinators
(`.a > .b`), grouped selectors (`h1, h2`), or a bare tag override
(`blockquote { ... }` without touching every node).

This module closes that gap the same way the rest of ARKlight closes
gaps: not with a raw-CSS-string escape hatch, but with a small,
explicit grammar that only accepts selector *shapes* it knows about.
`parse_selector_list` either returns a validated AST or raises
`CSSSyntaxError` -- there is no code path where an unrecognized
fragment of the input string reaches the generated stylesheet
unexamined. `render_selector_list` turns that AST back into canonical
CSS text, so what gets written is always exactly what was validated,
never the caller's original (unvalidated) string.

Grammar (informally):

    selector_list    := complex_selector ("," complex_selector)*
    complex_selector  := compound_selector (combinator compound_selector)*
    combinator        := ">" | "+" | "~" | " " (descendant)
    compound_selector := simple_selector+
    simple_selector    := tag | class | attr | pseudo_class | pseudo_element
    tag                := one of KNOWN_HTML_TAGS, only as the first
                           simple selector in a compound
    class              := "." identifier
    attr               := "[" identifier (operator quoted_string)? "]"
    pseudo_class        := ":" identifier
                          | ":" functional_name "(" nth_or_selector_list ")"
    pseudo_element      := "::" identifier (one of PSEUDO_ELEMENTS)

`:has(...)` is the one functional pseudo-class allowed a *relative*
selector list (its arguments may start with a bare combinator, e.g.
`:has(> .icon)`) -- `:not()`/`:is()`/`:where()` require an ordinary
selector list, matching the real CSS spec's own asymmetry here.
"""

from __future__ import annotations

import re

# Duplicated from `arklight.backend.html.render.TAG_MAP`'s values
# rather than imported: the HTML backend already imports from
# `arklight.backend.css.render` (for `STYLESHEET_PATH`), so importing
# the other direction here would create a cycle. Same "small constant,
# copied not imported, so each backend module stays a pure function of
# its own inputs" reasoning `custom_styles.py`'s `_PSEUDO_KEY_RE`
# already documents for its own duplicated regex. Keep this in sync
# with `TAG_MAP`'s values by hand if a new built-in component is added.
KNOWN_HTML_TAGS = frozenset(
    {
        "html", "head", "body", "div", "h1", "h2", "h3", "h4", "h5", "h6", "p",
        "button", "a", "img", "ul", "li",
        "header", "footer", "main", "nav", "section", "article", "aside",
        "figure", "figcaption", "details", "summary",
        "strong", "em", "small", "mark", "code", "cite", "abbr", "sub", "sup",
        "span", "time", "hr", "br", "pre", "blockquote",
        "form", "input", "textarea", "select", "option", "optgroup", "label",
        "fieldset", "legend",
        "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
        "video", "audio", "source",
        "ol", "dl", "dt", "dd",
        "picture", "progress", "meter", "datalist", "output", "dialog",
        "kbd", "samp", "var", "data", "ins", "del", "q", "dfn", "address",
        "wbr", "bdi", "bdo", "ruby", "rt", "rp",
        "colgroup", "col", "track", "map", "area", "iframe", "noscript",
    }
)

# Pseudo-elements: a fixed, curated set, same discipline as
# `arklight.api.ALLOWED_PSEUDO_CLASSES` -- these become a literal
# `::name` suffix on a compound selector with no further validation
# downstream, so an open-ended name would reopen the "no arbitrary
# CSS/selector strings" boundary. Extend this set (not the regex) if a
# new pseudo-element is needed later.
PSEUDO_ELEMENTS = frozenset(
    {"before", "after", "placeholder", "selection", "marker", "first-line", "first-letter"}
)

# Functional pseudo-classes whose argument is itself a selector list.
# `has` additionally allows its selector list to start with a bare
# combinator (a "relative selector"), matching the real CSS grammar --
# see `_parse_complex_selector`'s `allow_leading_combinator`.
SELECTOR_LIST_PSEUDO_CLASSES = frozenset({"not", "is", "where", "has"})
_RELATIVE_SELECTOR_PSEUDO_CLASSES = frozenset({"has"})

# Functional pseudo-classes whose argument is an An+B micro-syntax
# expression (or the `odd`/`even` keywords).
NTH_PSEUDO_CLASSES = frozenset(
    {"nth-child", "nth-last-child", "nth-of-type", "nth-last-of-type"}
)

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
_ANB_RE = re.compile(
    r"^\s*(odd|even|[+-]?\d+|[+-]?\d*n(\s*[+-]\s*\d+)?)\s*$", re.IGNORECASE
)
_ATTR_OPERATORS = ("^=", "$=", "*=", "~=", "|=", "=")
_COMBINATOR_CHARS = frozenset(">+~")


class CSSSelectorSyntaxError(ValueError):
    """
    Raised by `parse_selector_list` (and, downstream, by
    `arklight.api.Site.style_selector`/`container_query`/`supports`)
    when a selector string isn't valid for the grammar this module
    accepts. Subclasses `ValueError` for the same reason
    `arklight.api.CSSSyntaxError` does -- existing `except ValueError`
    call sites keep working -- while still being catchable on its own.
    """


# ---------------------------------------------------------------------------
# AST
# ---------------------------------------------------------------------------
# Kept as plain tuples (not dataclasses) -- these are small, short-lived,
# and only ever produced by the parser and consumed by the renderer
# directly below it, so a heavier class hierarchy would add ceremony
# without adding safety.
#
# SimpleSelector    = ("tag", name) | ("class", name)
#                    | ("attr", name, operator_or_None, value_or_None)
#                    | ("pseudo-class", name)
#                    | ("pseudo-class-func", name, args) -- args is
#                      either a SelectorList (for SELECTOR_LIST_PSEUDO_CLASSES)
#                      or a str (the An+B text, for NTH_PSEUDO_CLASSES)
#                    | ("pseudo-element", name)
# CompoundSelector  = list[SimpleSelector]
# ComplexSelector   = list[(combinator_or_None, CompoundSelector)]
#                      -- first entry's combinator is always None
# SelectorList      = list[ComplexSelector]


def parse_selector_list(text: str, *, allow_leading_combinator: bool = False):
    """
    Parse `text` as a comma-separated selector list. Raises
    `CSSSelectorSyntaxError` on anything outside the grammar described
    in this module's docstring; returns the validated AST otherwise.

    `allow_leading_combinator` is only ever `True` when parsing a
    `:has(...)` argument list (a "relative selector list") -- see
    `_parse_functional_pseudo_args`.
    """
    if not isinstance(text, str) or not text.strip():
        raise CSSSelectorSyntaxError(
            f"expected a non-empty selector string, got {text!r}."
        )
    parts = _split_top_level(text, ",")
    if any(not part.strip() for part in parts):
        raise CSSSelectorSyntaxError(
            f"selector {text!r} has an empty item in a comma-separated list."
        )
    return [
        _parse_complex_selector(part.strip(), allow_leading_combinator=allow_leading_combinator)
        for part in parts
    ]


def render_selector_list(selector_list) -> str:
    """Canonical CSS text for a `parse_selector_list(...)` result."""
    return ", ".join(_render_complex_selector(complex_sel) for complex_sel in selector_list)


# ---------------------------------------------------------------------------
# Splitting helpers -- depth-aware so commas/combinators *inside* a
# functional pseudo-class's parentheses or an attribute selector's
# brackets don't get mistaken for top-level structure.
# ---------------------------------------------------------------------------


def _split_top_level(text: str, sep: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def _parse_complex_selector(text: str, *, allow_leading_combinator: bool = False):
    # Tokenize into an alternating [compound, combinator, compound, ...]
    # sequence by scanning left to right at bracket/paren depth 0. A
    # run of whitespace at depth 0 is a descendant combinator *unless*
    # it's immediately adjacent to an explicit ">"/"+"/"~", in which
    # case the explicit combinator wins and surrounding whitespace is
    # just formatting.
    tokens: list[str] = []
    depth = 0
    current: list[str] = []

    def flush():
        piece = "".join(current).strip()
        if piece:
            tokens.append(piece)
        current.clear()

    i = 0
    while i < len(text):
        ch = text[i]
        if ch in "([":
            depth += 1
            current.append(ch)
        elif ch in ")]":
            depth -= 1
            current.append(ch)
        elif depth == 0 and ch in _COMBINATOR_CHARS:
            flush()
            tokens.append(ch)
        elif depth == 0 and ch.isspace():
            # Only meaningful if it separates two compounds and isn't
            # just padding around an explicit combinator -- collapse
            # runs, and let an explicit combinator token absorb any
            # whitespace before/after it (handled by flush() calls).
            flush()
            tokens.append(" ")
        else:
            current.append(ch)
        i += 1
    flush()

    # Collapse runs of whitespace-tokens into one, then drop any
    # whitespace token adjacent (either side) to an explicit combinator
    # token -- it's redundant formatting, e.g. "a > b" tokenizes to
    # ["a", " ", ">", " ", "b"] and should collapse to ["a", ">", "b"].
    merged: list[str] = []
    for tok in tokens:
        if tok == " " and merged and merged[-1] == " ":
            continue
        merged.append(tok)

    collapsed: list[str] = []
    for idx, tok in enumerate(merged):
        if tok == " ":
            prev = collapsed[-1] if collapsed else None
            nxt = merged[idx + 1] if idx + 1 < len(merged) else None
            if prev in _COMBINATOR_CHARS or nxt in _COMBINATOR_CHARS:
                continue
        collapsed.append(tok)
    while collapsed and collapsed[-1] == " ":
        collapsed.pop()
    while collapsed and collapsed[0] == " ":
        collapsed.pop(0)

    if not collapsed:
        raise CSSSelectorSyntaxError(f"selector {text!r} is empty.")

    parsed: list[tuple[str | None, list]] = []
    idx = 0
    pending_combinator: str | None = None

    if collapsed[0] in _COMBINATOR_CHARS:
        if not allow_leading_combinator:
            raise CSSSelectorSyntaxError(
                f"selector {text!r} starts with a combinator "
                f"({collapsed[0]!r}) -- only :has(...) accepts a "
                f"relative (combinator-first) selector."
            )
        pending_combinator = collapsed[0]
        idx = 1

    expect_compound = True
    while idx < len(collapsed):
        tok = collapsed[idx]
        if expect_compound:
            if tok in _COMBINATOR_CHARS or tok == " ":
                raise CSSSelectorSyntaxError(
                    f"selector {text!r} has two combinators with no "
                    f"selector between them."
                )
            compound = _parse_compound_selector(tok)
            parsed.append((pending_combinator, compound))
            pending_combinator = None
            expect_compound = False
        else:
            if tok == " ":
                pending_combinator = " "
            elif tok in _COMBINATOR_CHARS:
                pending_combinator = tok
            else:
                raise CSSSelectorSyntaxError(
                    f"selector {text!r} has two selectors with no "
                    f"combinator between them."
                )
            expect_compound = True
        idx += 1

    if expect_compound:
        raise CSSSelectorSyntaxError(
            f"selector {text!r} ends with a dangling combinator."
        )

    return parsed


def _parse_compound_selector(text: str) -> list:
    simple_selectors: list = []
    i = 0
    n = len(text)
    saw_non_tag = False

    while i < n:
        ch = text[i]
        if ch == ".":
            m = _IDENT_RE.match(text, i + 1)
            if not m:
                raise CSSSelectorSyntaxError(f"selector {text!r} has a malformed class selector.")
            simple_selectors.append(("class", m.group(0)))
            i = m.end()
            saw_non_tag = True
        elif ch == "[":
            end = text.find("]", i)
            if end == -1:
                raise CSSSelectorSyntaxError(f"selector {text!r} has an unterminated attribute selector.")
            simple_selectors.append(_parse_attr_selector(text[i : end + 1], text))
            i = end + 1
            saw_non_tag = True
        elif text.startswith("::", i):
            m = _IDENT_RE.match(text, i + 2)
            if not m:
                raise CSSSelectorSyntaxError(f"selector {text!r} has a malformed pseudo-element.")
            name = m.group(0)
            if name not in PSEUDO_ELEMENTS:
                raise CSSSelectorSyntaxError(
                    f"selector {text!r} uses unsupported pseudo-element "
                    f"'::{name}'. Supported: {', '.join(sorted(PSEUDO_ELEMENTS))}."
                )
            simple_selectors.append(("pseudo-element", name))
            i = m.end()
            saw_non_tag = True
        elif ch == ":":
            m = _IDENT_RE.match(text, i + 1)
            if not m:
                raise CSSSelectorSyntaxError(f"selector {text!r} has a malformed pseudo-class.")
            name = m.group(0)
            i = m.end()
            if i < n and text[i] == "(":
                end = _matching_paren(text, i)
                args_text = text[i + 1 : end]
                simple_selectors.append(_parse_functional_pseudo(name, args_text, text))
                i = end + 1
            else:
                from arklight.api import ALLOWED_PSEUDO_CLASSES  # local import: avoid a module-load cycle

                if name in NTH_PSEUDO_CLASSES or name in SELECTOR_LIST_PSEUDO_CLASSES:
                    raise CSSSelectorSyntaxError(
                        f"selector {text!r} uses pseudo-class ':{name}' "
                        f"without the required '(...)' argument."
                    )
                if name not in ALLOWED_PSEUDO_CLASSES:
                    raise CSSSelectorSyntaxError(
                        f"selector {text!r} uses unsupported pseudo-class "
                        f"':{name}'. Supported (no-argument): "
                        f"{', '.join(sorted(ALLOWED_PSEUDO_CLASSES))}."
                    )
                simple_selectors.append(("pseudo-class", name))
            saw_non_tag = True
        else:
            m = _IDENT_RE.match(text, i)
            if not m:
                raise CSSSelectorSyntaxError(f"selector {text!r} has an unrecognized character {ch!r}.")
            if saw_non_tag or simple_selectors:
                raise CSSSelectorSyntaxError(
                    f"selector {text!r} has a tag name in the middle of a "
                    f"compound selector -- a tag selector may only be the "
                    f"first simple selector (e.g. 'a.button', not '.button a')."
                )
            name = m.group(0)
            if name not in KNOWN_HTML_TAGS:
                raise CSSSelectorSyntaxError(
                    f"selector {text!r} uses unrecognized tag '{name}' -- "
                    f"only real HTML tags ARKlight's HTML backend emits are "
                    f"allowed as a bare tag selector."
                )
            simple_selectors.append(("tag", name))
            i = m.end()

    if not simple_selectors:
        raise CSSSelectorSyntaxError(f"selector {text!r} has an empty compound selector.")
    return simple_selectors


def _matching_paren(text: str, open_idx: int) -> int:
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    raise CSSSelectorSyntaxError(f"selector {text!r} has an unterminated '('.")


def _parse_functional_pseudo(name: str, args_text: str, full_text: str):
    if name in NTH_PSEUDO_CLASSES:
        arg = args_text.strip()
        if not _ANB_RE.match(arg):
            raise CSSSelectorSyntaxError(
                f"selector {full_text!r} has an invalid ':{name}(...)' "
                f"argument {args_text!r} -- expected 'odd', 'even', an "
                f"integer, or An+B syntax like '2n+1'."
            )
        return ("pseudo-class-func", name, arg.lower())
    if name in SELECTOR_LIST_PSEUDO_CLASSES:
        nested = parse_selector_list(
            args_text, allow_leading_combinator=name in _RELATIVE_SELECTOR_PSEUDO_CLASSES
        )
        return ("pseudo-class-func", name, nested)
    raise CSSSelectorSyntaxError(
        f"selector {full_text!r} uses unsupported functional pseudo-class "
        f"':{name}(...)'. Supported: "
        f"{', '.join(sorted(SELECTOR_LIST_PSEUDO_CLASSES | NTH_PSEUDO_CLASSES))}."
    )


def _parse_attr_selector(bracket_text: str, full_text: str):
    # bracket_text includes the surrounding "[" "]".
    inner = bracket_text[1:-1].strip()
    if not inner:
        raise CSSSelectorSyntaxError(f"selector {full_text!r} has an empty '[]' attribute selector.")

    name_match = _IDENT_RE.match(inner)
    if not name_match:
        raise CSSSelectorSyntaxError(f"selector {full_text!r} has a malformed attribute name in {bracket_text!r}.")
    name = name_match.group(0)
    rest = inner[name_match.end():].strip()

    if not rest:
        return ("attr", name, None, None)

    operator = None
    for candidate in _ATTR_OPERATORS:
        if rest.startswith(candidate):
            operator = candidate
            rest = rest[len(candidate):].strip()
            break
    if operator is None:
        raise CSSSelectorSyntaxError(
            f"selector {full_text!r} has an invalid attribute operator in "
            f"{bracket_text!r} -- expected one of "
            f"{', '.join(_ATTR_OPERATORS)}."
        )

    if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in ("'", '"'):
        value = rest[1:-1]
        if any(ch in value for ch in ("{", "}", ";", "\n", rest[0])):
            raise CSSSelectorSyntaxError(
                f"selector {full_text!r} has an attribute value in "
                f"{bracket_text!r} that isn't safe to emit -- quotes, "
                f"braces, semicolons, and newlines aren't allowed inside "
                f"an attribute value."
            )
    else:
        raise CSSSelectorSyntaxError(
            f"selector {full_text!r} has an attribute value in "
            f"{bracket_text!r} that isn't quoted -- wrap it in single or "
            f"double quotes, e.g. '[type=\"email\"]'."
        )

    return ("attr", name, operator, value)


# ---------------------------------------------------------------------------
# Rendering -- turns the validated AST back into canonical CSS text.
# ---------------------------------------------------------------------------


def _render_complex_selector(complex_selector) -> str:
    pieces: list[str] = []
    for combinator, compound in complex_selector:
        rendered_compound = _render_compound_selector(compound)
        if not pieces:
            if combinator is None:
                pieces.append(rendered_compound)
            else:
                # Leading combinator -- only reachable for a `:has(...)`
                # relative selector list, e.g. ":has(> .icon)".
                pieces.append(f"{combinator} {rendered_compound}")
        elif combinator == " ":
            pieces.append(f" {rendered_compound}")
        else:
            pieces.append(f" {combinator} {rendered_compound}")
    return "".join(pieces)


def _render_compound_selector(compound) -> str:
    out = []
    for simple in compound:
        kind = simple[0]
        if kind == "tag":
            out.append(simple[1])
        elif kind == "class":
            out.append(f".{simple[1]}")
        elif kind == "pseudo-class":
            out.append(f":{simple[1]}")
        elif kind == "pseudo-element":
            out.append(f"::{simple[1]}")
        elif kind == "attr":
            _, name, operator, value = simple
            if operator is None:
                out.append(f"[{name}]")
            else:
                out.append(f'[{name}{operator}"{value}"]')
        elif kind == "pseudo-class-func":
            _, name, args = simple
            if isinstance(args, str):
                out.append(f":{name}({args})")
            else:
                out.append(f":{name}({render_selector_list(args)})")
        else:  # pragma: no cover -- exhaustive over the AST this module builds
            raise AssertionError(f"unknown simple selector kind {kind!r}")
    return "".join(out)
