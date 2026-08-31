"""
Experimental / legacy API registry -- see `docs/EXPERIMENTAL-APIS.md`.

ARKlight's default surface is intrinsic-layout-only (see
`docs/DESIGN-NOTES.md`): nothing in it is keyed to a viewport width,
device class, or browser engine. A feature that steps outside that
model isn't refused outright, but it isn't silent either -- it has to
be registered here, and every use prints a warning, both inline (at
the moment it's detected) and as an end-of-run summary. This module
owns the *content* of those warnings; callers (the compiler pipeline,
`arklight/pwa.py`, the CLI) own *when* to call `emit()`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ExperimentalFeature:
    id: str
    # One-line reason shown on the compact, inline "unlocked an
    # experimental API" banner (the `-> Note:` line).
    inline_note: str
    # Full paragraph, pre-wrapped to short lines, for the end-of-run
    # summary block ("⚠ Experimental API enabled").
    detail_lines: list[str]
    # Trailing "Legacy API detected" note -- why it's still here /
    # what to prefer instead.
    legacy_note: str


FEATURES: dict[str, ExperimentalFeature] = {
    "css-media-queries": ExperimentalFeature(
        id="css-media-queries",
        inline_note="Media queries target viewport characteristics rather than intrinsic layout.",
        detail_lines=[
            "Media queries target viewport characteristics rather than",
            "intrinsic layout.",
            "Device-specific breakpoints reduce portability and may behave",
            "differently across Android devices, tablets, foldables and",
            "desktop browsers.",
            "Prefer intrinsic layouts (.grid, .switcher, .cluster,",
            "minmax(), auto-fit, clamp()) whenever possible.",
        ],
        legacy_note=(
            "Viewport-keyed rules (whether from site.media_query(...) or a "
            "node's responsive_style={...} prop) step outside ARKlight's "
            "intrinsic layout model and are retained as an explicit escape "
            "hatch, not the default path. New projects should prefer "
            ".switcher, .grid, .cluster, .sidebar, or other intrinsic "
            "layout primitives wherever the design can be expressed that way."
        ),
    ),
    "experimental-install-pwa": ExperimentalFeature(
        id="experimental-install-pwa",
        inline_note="Runtime stability relies entirely on native browser engine support.",
        detail_lines=[
            "The install button depends on the `beforeinstallprompt` event,",
            "which is not part of any web standard and is not implemented",
            "by every browser engine (notably absent or partial on several",
            "non-Chromium browsers, and inconsistent across Android OEM",
            "WebView builds).",
            "Where unsupported, the button silently has nothing to do --",
            "always provide a normal way to use the site alongside it.",
        ],
        legacy_note=(
            "Native install prompts are not standardized across browsers -- "
            "behavior (and availability) varies by engine and platform. "
            "Treat this as a progressive enhancement, not the only way to "
            "install or use the site."
        ),
    ),
    "css-import": ExperimentalFeature(
        id="css-import",
        inline_note="The imported file's contents can't be validated by ARKlight.",
        detail_lines=[
            "@import pulls in a stylesheet from a URL at request time --",
            "the imported file's contents can't be validated by ARKlight,",
            "unlike every other rule this project generates.",
            "It also blocks the CSS Object Model until it resolves, which",
            "can delay first paint, and its availability/behavior depends",
            "on the visiting network and browser having access to that URL.",
            "Prefer Page(links=[{'rel': 'stylesheet', 'href': ...}]) for an",
            "external stylesheet where possible -- it doesn't block the CSSOM",
            "the way @import does.",
        ],
        legacy_note=(
            "An @import URL is opaque to ARKlight -- its contents are fetched "
            "and applied by the browser at request time, so nothing about "
            "them is checked the way every other generated rule is. Retained "
            "as an explicit escape hatch for the rare case a stylesheet truly "
            "isn't reachable via Page(links=[...]), not the default path."
        ),
    ),
    "raw-postprocess": ExperimentalFeature(
        id="raw-postprocess",
        inline_note="Runs your own code directly over the final output files, completely unchecked by ARKlight.",
        detail_lines=[
            "This is an advanced experimental feature. It hands your",
            "function the *entire* dict of generated output files --",
            "every path, every byte -- after every backend has already",
            "rendered and postprocessed them, and whatever your function",
            "returns is written to disk exactly as-is.",
            "Nothing about it is validated, normalized, or checked against",
            "ARKlight's layout model, HTML/CSS/JS correctness, or anything",
            "else the rest of the pipeline guarantees -- it is the single",
            "widest surface exposed to user code in the whole project.",
            "Used carelessly, it can give you a million different ways to",
            "shoot yourself in the foot: a typo can silently corrupt every",
            "page, strip a <script> tag, or ship broken CSS with no error",
            "at build time. Use it wisely, and proceed with caution.",
        ],
        legacy_note=(
            "Not a legacy API in the historical sense -- a raw, unchecked "
            "escape hatch for the rare transformation that genuinely can't "
            "be expressed any other way (e.g. a one-off script-based build "
            "step). If the transformation is reusable or depends on what "
            "another backend produced, prefer a real Backend subclass "
            "overriding postprocess() (see arklight.backend.base.Backend) "
            "instead -- it gets the same second pass with none of the "
            "unchecked-arbitrary-code risk."
        ),
    ),
}


@dataclass
class ExperimentalUsage:
    """One recorded use of an experimental feature, enough to render
    both the inline banner and (deduplicated) the end-of-run block."""

    feature_id: str
    component: str | None = None


def format_inline_banner(usage: ExperimentalUsage) -> str:
    """The compact, interleaved-with-stage-log banner, printed the
    moment a feature is detected -- see `docs/EXPERIMENTAL-APIS.md`
    "CLI contract"."""
    feature = FEATURES[usage.feature_id]
    if usage.component:
        header = (
            f"\u26a0\ufe0f  [EXPERIMENTAL FEATURE ACTIVE]: Component "
            f"{usage.component!r} unlocked an experimental API."
        )
    else:
        header = f"\u26a0\ufe0f  [EXPERIMENTAL FEATURE ACTIVE]: {feature.id} unlocked an experimental API."
    return "\n".join(
        [
            header,
            f"   -> Feature: {feature.id}",
            f"   -> Note: {feature.inline_note}",
        ]
    )


def format_summary_block(feature_id: str) -> str:
    """The full end-of-run block for one *distinct* feature -- callers
    are responsible for deduplicating by `feature_id` first (one block
    per feature actually used, not once per occurrence)."""
    feature = FEATURES[feature_id]
    lines = ["\u26a0 Experimental API enabled", f"    Feature : {feature.id}"]
    lines.extend(f"    {line}" for line in feature.detail_lines)
    lines.append(f"Legacy API detected: {feature.id}")
    lines.append(feature.legacy_note)
    return "\n".join(lines)


def emit(
    feature_id: str,
    *,
    on_warning: Callable[[str], None] | None = None,
    component: str | None = None,
) -> ExperimentalUsage:
    """
    Record + (if `on_warning` given) immediately print the inline
    banner for one use of `feature_id`. Returns the `ExperimentalUsage`
    so the caller can collect it for the end-of-run summary (see
    `format_summary_block`). Raises `KeyError` if `feature_id` isn't
    registered in `FEATURES` -- fail loudly rather than silently
    skipping the warning for a typo'd id.
    """
    if feature_id not in FEATURES:
        raise KeyError(
            f"{feature_id!r} isn't a registered experimental feature -- "
            f"add it to arklight.experimental.FEATURES first (see "
            f"docs/EXPERIMENTAL-APIS.md)."
        )
    usage = ExperimentalUsage(feature_id=feature_id, component=component)
    if on_warning is not None:
        on_warning(format_inline_banner(usage))
    return usage


def print_summary(usages: list[ExperimentalUsage], *, file=None) -> None:
    """Print one deduplicated end-of-run block per distinct feature
    id in `usages`, in first-seen order. No-op for an empty list."""
    import sys

    out = file or sys.stdout
    seen: set[str] = set()
    for usage in usages:
        if usage.feature_id in seen:
            continue
        seen.add(usage.feature_id)
        print(format_summary_block(usage.feature_id), file=out)
