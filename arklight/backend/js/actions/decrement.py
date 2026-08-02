"""
`decrement` action fragment. See `set.py` for the general shape.

v0.0035 vocabulary addendum: `increment` shipped without its natural
counterpart -- almost every counter demo needs both a `+1` and a `-1`
button, and routing `-1` through `Action.increment(name, delta=-1)`
works but is a footgun-by-omission (nothing stops a typo of the sign,
and it's not the "obvious way" to decrement). `decrement` is exactly
`increment` with the delta subtracted instead of added, kept as a
separate fragment (not `increment` with a negated default) so it's
symmetric and discoverable in the registry/dispatch table by name.
"""

from __future__ import annotations

NAME = "decrement"

JS_FRAGMENT = """    decrement: function (store, key, args) {
      var delta = args && args.delta !== undefined ? args.delta : 1;
      store.set(key, (store.get(key) || 0) - delta);
    }"""
