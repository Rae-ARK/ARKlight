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
