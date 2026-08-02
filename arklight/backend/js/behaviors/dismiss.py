"""
`dismiss` behavior fragment. See `toggle.py` for the general shape.
"""

from __future__ import annotations

NAME = "dismiss"

JS_FRAGMENT = """    dismiss: function (el) {
      var selector = el.getAttribute("data-ark-target");
      var className = el.getAttribute("data-ark-toggle-class") || "hidden";
      if (!selector) return;
      document.querySelectorAll(selector).forEach(function (target) {
        target.classList.add(className);
      });
    }"""
