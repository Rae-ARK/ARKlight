"""
`highlightActiveNavLink`: adds `is-active` to any `.nav a` whose
resolved URL matches the current page. Runs unconditionally (every
site with a `nav()` gets this for free), independent of whether the
page declares `State(...)`.

Split out of `arklight/backend/js/render.py`'s old
`_NAV_HIGHLIGHT_JS` constant (`refactor-0`). Pure move, no JS output
change.
"""

from __future__ import annotations

NAV_HIGHLIGHT_JS = """  function highlightActiveNavLink() {
    document.querySelectorAll(".nav a").forEach(function (link) {
      var here = location.href.replace(/#.*$/, "");
      var there = link.href.replace(/#.*$/, "");
      if (there === here) {
        link.classList.add("is-active");
      }
    });
  }"""
