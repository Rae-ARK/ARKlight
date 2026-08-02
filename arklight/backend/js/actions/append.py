"""
`append` action fragment. See `set.py` for the general shape.

v0.0035 vocabulary addendum II: the first action that assumes a
list-valued `State(...)` rather than a scalar one. Deliberately
minimal -- it appends one value and re-uses the existing reactive core
unchanged. `renderBindings` (`arklight/backend/js/render.py`) sets
`el.textContent = store.get(key)`; for an array that's JS's own
`Array.prototype.toString()` (comma-joined elements), which is enough
for a simple tag list / count display without any new rendering
machinery. Per-item templating (e.g. one `<li>` per item) is real,
separate design work left for a future version.
"""

from __future__ import annotations

NAME = "append"

JS_FRAGMENT = """    append: function (store, key, args) {
      var list = store.get(key) || [];
      store.set(key, list.concat([args.value]));
    }"""
