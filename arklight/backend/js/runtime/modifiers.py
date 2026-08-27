"""
`arkApplyModifiers`: reads an element's `data-ark-modifiers` attribute
once (`prevent,debounce:300`, etc. -- see
`arklight.ir.schema.MODIFIER_REGISTRY`) and wraps a zero-arg callback
so the caller decides *if*/*when* it actually runs, instead of
duplicating debounce/throttle/once/stop into every action fragment.

Split out of `arklight/backend/js/render.py`'s old `_STATE_CORE_JS`
(`refactor-0`). Pure move, no JS output change.
"""

from __future__ import annotations

APPLY_MODIFIERS_JS = """  function arkApplyModifiers(el, run) {
    // Stage 3 ("Reactive-core vdom staging"): one small wrapper, read
    // once per element from data-ark-modifiers="prevent,debounce:300"
    // (see ActionRef.modifiers / MODIFIER_REGISTRY), instead of
    // duplicating debounce/throttle/once/stop into every action
    // fragment. `run` is a zero-arg callback (the actual state
    // mutation); this returns a click handler that decides *if*/*when*
    // to call it. "prevent" is deliberately a no-op here: wireActions'
    // click listener already unconditionally calls
    // event.preventDefault() before this runs (existing, pre-Stage-3
    // behavior this stage doesn't change), so an explicit .with_modifiers("prevent")
    // is honored by construction rather than by a second call.
    var raw = el.getAttribute("data-ark-modifiers");
    if (!raw) return function () { run(); };

    var stop = false, once = false, debounceMs = 0, throttleMs = 0;
    raw.split(",").forEach(function (token) {
      var bits = token.split(":");
      var name = bits[0];
      if (name === "stop") stop = true;
      else if (name === "once") once = true;
      else if (name === "debounce") debounceMs = parseInt(bits[1], 10) || 0;
      else if (name === "throttle") throttleMs = parseInt(bits[1], 10) || 0;
    });

    var dispatch = run;
    if (debounceMs) {
      dispatch = (function (fn, ms) {
        var timer;
        return function () {
          clearTimeout(timer);
          timer = setTimeout(fn, ms);
        };
      })(dispatch, debounceMs);
    } else if (throttleMs) {
      dispatch = (function (fn, ms) {
        var last = 0;
        return function () {
          var now = Date.now();
          if (now - last >= ms) {
            last = now;
            fn();
          }
        };
      })(dispatch, throttleMs);
    }
    if (once) {
      dispatch = (function (fn) {
        var called = false;
        return function () {
          if (called) return;
          called = true;
          fn();
        };
      })(dispatch);
    }

    return function (event) {
      if (stop) event.stopPropagation();
      dispatch();
    };
  }

"""
