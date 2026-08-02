"""
`copy` behavior fragment. See `toggle.py` for the general shape.
"""

from __future__ import annotations

NAME = "copy"

JS_FRAGMENT = """    copy: function (el) {
      var selector = el.getAttribute("data-ark-target");
      if (!selector) return;
      var target = document.querySelector(selector);
      if (!target || !navigator.clipboard) return;
      var text = target.value !== undefined && target.tagName === "TEXTAREA"
        ? target.value
        : target.textContent;
      navigator.clipboard.writeText(text.trim()).then(function () {
        var original = el.textContent;
        el.textContent = "Copied!";
        setTimeout(function () {
          el.textContent = original;
        }, 1500);
      });
    }"""
