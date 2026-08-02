"""
`toggle` behavior fragment.

See `arklight.ir.schema.BEHAVIOR_REGISTRY` for the spec (this behavior
reads an optional `toggle_class` prop, default "is-open") and
`docs/DESIGN-NOTES.md` ("v0.0035: stateful JS -- capability, not
vocabulary") for why behaviors live as one small fragment per file
instead of one hand-maintained runtime string.
"""

from __future__ import annotations

NAME = "toggle"

JS_FRAGMENT = """    toggle: function (el) {
      var selector = el.getAttribute("data-ark-target");
      var className = el.getAttribute("data-ark-toggle-class") || "is-open";
      if (!selector) return;
      document.querySelectorAll(selector).forEach(function (target) {
        target.classList.toggle(className);
      });
    }"""
