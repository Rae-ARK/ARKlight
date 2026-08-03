"""
Backend Interface.

A "backend" turns Website IR into output files. v0.001 ships exactly
one backend (HTML). Future milestones add CSS, JavaScript, Vue, and
Svelte backends -- all of them implement this same tiny contract, so
the compiler pipeline never needs to know which backend it's talking to.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from arklight.ir.build import WebsiteIR


class Backend(ABC):
    """Base class every ARKlight backend implements."""

    name: str = "base"

    @abstractmethod
    def render(self, ir: WebsiteIR) -> dict[str, str]:
        """
        Render the given Website IR to output.

        Returns a dict mapping *relative output file path* -> *file
        contents*. The compiler pipeline is responsible for actually
        writing these to disk; a backend never touches the filesystem
        itself, which keeps backends trivially testable.
        """
        raise NotImplementedError

    def postprocess(self, output_files: dict[str, str]) -> dict[str, str]:
        """
        Optional second pass over the *combined* output of every
        backend's `render()`, run in `backends=[...]` order after all
        `render()` calls finish (see `arklight.compiler.pipeline.build`).

        Default is a no-op identity so existing backends (HTMLBackend,
        CSSBackend, JSBackend) need no changes and behave exactly as
        before. A new backend can override this to add or transform
        files that depend on what other backends already produced --
        e.g. injecting analytics/OG tags computed from data the HTML
        backend already rendered -- without editing that backend's
        source. This is the "add a backend" extension point; prefer it
        over modifying an existing backend's `render()` unless the
        capability is intrinsic to that backend's own output (e.g. a
        new *_head_ tag HTMLBackend already knows how to build from
        Page props -- see `_render_head_meta` in
        `arklight.backend.html.render`).
        """
        return output_files
