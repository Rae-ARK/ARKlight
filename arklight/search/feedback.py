"""
Stage 8 -- compile-time error feedback loop.

Fills a real, currently-thrown-away signal: `arklight/ir/validate.py`'s
`validate_node()` already raises a structured `ValidationError`
whenever `node.type` isn't in `SCHEMA` --

    Unknown component type {node.type!r} at {path}. Known component
    types are: {known}.

-- today that string just gets caught by `compile_site_file`'s error
handler, wrapped as a `CompileError`, and otherwise discarded. Every
one of those is a real, in-the-wild typo a real person typed against
this real project -- exactly the kind of grounded signal the rest of
this pipeline (Stage 3's usage graph, Stage 4's usage stats) already
prefers over anything synthetic.

**Bug fixed here:** in ordinary use, that `ValidationError` path is
essentially unreachable. Every component (`Heading`, `Image`, ...) is
a real Python function/name -- misspelling one (`Headingg(...)`)
fails as a plain Python `NameError` *inside* `Site.build_ark_ast()`,
before an `ARKNode` is ever constructed, so `node.type` can only ever
hold a string from ARKlight's own fixed, correctly-spelled vocabulary.
`compile_site_file` catches that `NameError` several stages earlier
than the `ValidationError` this module was built to listen for, so
`record_validation_feedback` below never actually fired from a normal
typo. `parse_undefined_component_name`/`record_name_error_feedback`
cover that real path; `parse_unknown_component_type`/
`record_validation_feedback` are kept for the rarer case an
already-built `ARKNode` reaches `validate_node()` with an unknown
`.type` directly (e.g. IR constructed by a lower-level caller that
skips the documented component functions entirely).

This module never changes what `validate.py`/Python itself raises or
when (it's read-only over message text `compile_site_file` already
has), and never changes whether/how a build succeeds or fails -- it
only ever records a background fact *after* a real error, for Stage
2/5's `known_typo` signal and typo short-circuit to use on future
searches. See `arklight.compiler.pipeline` for the (best-effort,
failure-swallowing) call sites.
"""

from __future__ import annotations

import ast
import re

from arklight.search.engine import SearchEngine

# Matches the start of the exact `ValidationError` text
# `validate_node()` raises for an unknown component type (see
# `arklight/ir/validate.py`). Anchored to the start only, and doesn't
# try to match the rest of the message (path, known-types list) --
# any other `ValidationError` (missing required prop, bad on_click,
# ...) simply won't match this prefix, which is the only thing that
# matters for "was this specifically an unknown-component-type error".
_UNKNOWN_TYPE_RE = re.compile(r"^Unknown component type (?P<type_repr>'(?:[^'\\]|\\.)*') at ")

# Matches Python's own `NameError` message for a bare undefined name
# (`name 'Headingg' is not defined`) -- what a misspelled component
# call actually raises, since every component is a real Python
# function/name rather than a string `validate_node()` checks against
# `SCHEMA`. Deliberately narrow: only a bare identifier, no dotted
# attribute access (`foo.bar` typos raise `AttributeError`, not
# `NameError`, and aren't a component-name typo in the same sense) and
# no free variable named after a component either raises this in the
# same shape, so this stays a reasonable (not perfect) heuristic --
# same "best effort, never trusted blindly" posture the rest of this
# module already has.
_NAME_ERROR_RE = re.compile(r"^name '(?P<name>[A-Za-z_][A-Za-z0-9_]*)' is not defined$")


def parse_unknown_component_type(message: str) -> str | None:
    """
    If `message` is (the start of) `validate_node()`'s unknown-
    component-type `ValidationError` text, return the typo'd type name
    it names. Otherwise `None` -- either some other, unrelated
    `ValidationError`, or a message this parser doesn't recognize.

    The name is recovered with `ast.literal_eval` on the matched
    `repr()` text rather than by slicing quote characters off by hand,
    so a type name containing a quote or backslash (however unlikely
    in practice) round-trips correctly instead of corrupting the
    extracted typo.
    """
    match = _UNKNOWN_TYPE_RE.match(message)
    if match is None:
        return None
    try:
        value = ast.literal_eval(match.group("type_repr"))
    except (ValueError, SyntaxError):
        return None
    return value if isinstance(value, str) else None


def parse_undefined_component_name(message: str) -> str | None:
    """
    If `message` is a Python `NameError` string of the shape `name
    'X' is not defined`, return `X`. Otherwise `None`.

    This is the message a misspelled component call (`Headingg(...)`
    instead of `Heading(...)`) actually raises in ordinary use -- see
    the module docstring's "bug fixed here" note for why the
    `ValidationError` parser above doesn't see it.
    """
    match = _NAME_ERROR_RE.match(message)
    if match is None:
        return None
    return match.group("name")


def record_validation_feedback(message: str, engine: SearchEngine) -> None:
    """
    Given the text of a `ValidationError` `compile_site_file` just
    caught, record a Stage 8 confusion if (and only if) it was
    specifically an unknown-component-type error.

    `resolved` is `engine`'s own current top-ranked suggestion for the
    typo'd name at this moment (`engine.search(typo, limit=1)`) -- if
    ranking has no candidate at all to offer, nothing is recorded; no
    guess is better than a recorded bad one. This mirrors
    `record_acceptance`'s "just update counters" learning story: no
    assumption is made about whether the person that hit this error
    actually used the suggestion afterward, since this hook has no way
    to observe that.

    Any failure while searching/recording (e.g. the on-disk usage-
    stats store being unwritable) is the caller's responsibility to
    swallow -- see `arklight.compiler.pipeline`'s call site, which
    treats this function as strictly best-effort and never lets it
    affect whether/how a build succeeds or fails.
    """
    typo = parse_unknown_component_type(message)
    if typo is None:
        return

    results = engine.search(typo, limit=1)
    if not results:
        return

    engine.record_confusion(typo, results[0].name)


def record_name_error_feedback(message: str, engine: SearchEngine) -> None:
    """
    Given the text of a `NameError` `compile_site_file` just caught
    while calling a site's page functions, record a Stage 8 confusion
    if (and only if) the message matches the "name 'X' is not
    defined" shape a misspelled component call raises.

    This is the actual live path for "someone typo'd a component
    name" in ordinary use -- see the module docstring's "bug fixed
    here" note. Same recording rule and same best-effort contract as
    `record_validation_feedback` above: no candidate, no record; any
    failure is the caller's responsibility to swallow.
    """
    typo = parse_undefined_component_name(message)
    if typo is None:
        return

    results = engine.search(typo, limit=1)
    if not results:
        return

    engine.record_confusion(typo, results[0].name)

