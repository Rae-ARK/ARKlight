"""
`scroll-to` behavior fragment. See `toggle.py` for the general shape.
"""

from __future__ import annotations

NAME = "scroll-to"

JS_FRAGMENT = """    "scroll-to": function (el) {
      var selector = el.getAttribute("data-ark-target");
      if (!selector) return;
      var target = document.querySelector(selector);
      if (target && target.scrollIntoView) {
        target.scrollIntoView({ behavior: "smooth" });
      }
    }"""
