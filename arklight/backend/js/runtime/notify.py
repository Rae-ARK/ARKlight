"""
`arkNotify`: a self-contained, inline-styled on-page notice for
runtime edge cases the fixed behavior/action vocabulary didn't
anticipate. Deliberately inline-styled rather than class-based so it
still renders correctly if the page's own stylesheet is implicated in
the failure, and wrapped in its own try/catch so a notification
failure can never itself become a second, worse error.

Split out of `arklight/backend/js/render.py`'s old `_NOTIFY_JS`
constant (`refactor-0`). Pure move, no JS output change.
"""

from __future__ import annotations

NOTIFY_JS = """  function arkNotify(message) {
    // Self-contained on-page notice for runtime edge cases the fixed
    // behavior/action vocabulary didn't anticipate -- deliberately
    // inline-styled (not a `.stack`/`.card`/etc. class) so it renders
    // correctly even on a page whose stylesheet this failure might
    // itself be related to, and wrapped in its own try/catch so a
    // notification failure can never become a second, worse error.
    try {
      var el = document.getElementById("ark-notify");
      if (!el) {
        el = document.createElement("div");
        el.id = "ark-notify";
        el.setAttribute("role", "alert");
        el.style.cssText =
          "position:fixed;bottom:1rem;right:1rem;left:auto;max-width:22rem;" +
          "background:#111827;color:#f9fafb;padding:0.75rem 1rem;" +
          "border-radius:0.5rem;font:14px/1.4 system-ui,sans-serif;" +
          "box-shadow:0 4px 12px rgba(0,0,0,.35);z-index:2147483647;";
        document.body.appendChild(el);
      }
      el.textContent = message;
      el.style.display = "block";
      clearTimeout(el._arkNotifyTimer);
      el._arkNotifyTimer = setTimeout(function () {
        el.style.display = "none";
      }, 6000);
    } catch (notifyErr) {
      /* notification is best-effort; never let it throw */
    }
  }"""
