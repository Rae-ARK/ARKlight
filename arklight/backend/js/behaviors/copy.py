"""
`copy` behavior fragment. See `toggle.py` for the general shape.
"""

from __future__ import annotations

NAME = "copy"

JS_FRAGMENT = """    copy: function (el) {
      var selector = el.getAttribute("data-ark-target");
      if (!selector) return;
      var target = document.querySelector(selector);
      if (!target || !navigator.clipboard) {
        arkNotify("Copy isn't available in this browser or context.");
        return;
      }
      var text = target.value !== undefined && target.tagName === "TEXTAREA"
        ? target.value
        : target.textContent;
      navigator.clipboard.writeText(text.trim()).then(function () {
        var original = el.textContent;
        el.textContent = "Copied!";
        setTimeout(function () {
          el.textContent = original;
        }, 1500);
      }).catch(function () {
        arkNotify("Couldn't copy to clipboard -- try selecting and copying the text manually.");
      });
    }"""
