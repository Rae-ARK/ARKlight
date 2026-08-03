"""
Vendored vdom core -- Stage 1 of the staged JS-runtime expansion.

Source: snabbdom (https://github.com/snabbdom/snabbdom), MIT licensed,
version 3.6.4, `build/{vnode,is,htmldomapi,h,init}.js`. Only the four
*core* files are vendored -- `init` (the diff/patch algorithm), `h`
(hyperscript vnode constructor), `vnode` (the plain vnode factory),
and `htmldomapi` (the real-DOM adapter `init` patches against). None
of snabbdom's optional *modules* (`attributes`, `class`, `dataset`,
`eventlisteners`, `props`, `style`) are included -- this is
deliberately the "bare" core, matching the ask: a real, unmodified
diff/patch algorithm, not a full framework. `is.js`'s two one-line
helpers are inlined directly rather than kept as a fifth file.

This is Stage 1 of the reactive-core expansion: it swaps the
`renderBindings` re-render pass (which previously did a raw
`el.textContent = ...` on every subscriber notification) for a real
vdom patch, so a future stage (list rendering, conditional show/hide,
attribute/class binding, etc.) has a diffing engine to build on rather
than re-inventing one. It does not itself add any new page-facing
Python API -- `State`/`Bind` behave exactly as before; only the
mechanism underneath changed.

The vendored code below is adapted only mechanically (ES module
`import`/`export` statements stripped and replaced with plain
variables inside one closure, so it can be inlined into the single
IIFE `arklight.js` already ships as) -- the diff/patch logic itself is
untouched snabbdom.
"""

from __future__ import annotations

SNABBDOM_CORE_JS = """  // ---- vendored: snabbdom 3.6.4 core (MIT) -- vnode + h + init + htmlDomApi.
  // Only the bare diff/patch core is vendored, none of snabbdom's
  // optional modules (attributes/class/style/props/eventlisteners).
  var snabbdom = (function () {
    function vnode(sel, data, children, text, elm) {
      var key = data === undefined ? undefined : data.key;
      return { sel: sel, data: data, children: children, text: text, elm: elm, key: key };
    }

    var isArray = Array.isArray;
    function isPrimitive(s) {
      return (
        typeof s === "string" ||
        typeof s === "number" ||
        s instanceof String ||
        s instanceof Number
      );
    }

    function h(sel, b, c) {
      var data = {};
      var children, text, i;
      if (c !== undefined) {
        if (b !== null) data = b;
        if (isArray(c)) children = c;
        else if (isPrimitive(c)) text = c.toString();
        else if (c && c.sel) children = [c];
      } else if (b !== undefined && b !== null) {
        if (isArray(b)) children = b;
        else if (isPrimitive(b)) text = b.toString();
        else if (b && b.sel) children = [b];
        else data = b;
      }
      if (children !== undefined) {
        for (i = 0; i < children.length; ++i) {
          if (isPrimitive(children[i])) {
            children[i] = vnode(undefined, undefined, undefined, children[i], undefined);
          }
        }
      }
      return vnode(sel, data, children, text, undefined);
    }

    var htmlDomApi = {
      createElement: function (tag) { return document.createElement(tag); },
      createElementNS: function (ns, tag) { return document.createElementNS(ns, tag); },
      createTextNode: function (text) { return document.createTextNode(text); },
      createComment: function (text) { return document.createComment(text); },
      insertBefore: function (parent, node, ref) { parent.insertBefore(node, ref); },
      removeChild: function (node, child) { node.removeChild(child); },
      appendChild: function (node, child) { node.appendChild(child); },
      parentNode: function (node) { return node.parentNode; },
      nextSibling: function (node) { return node.nextSibling; },
      tagName: function (elm) { return elm.tagName; },
      setTextContent: function (node, text) { node.textContent = text; },
      getTextContent: function (node) { return node.textContent; },
      isElement: function (node) { return node.nodeType === 1; },
      isText: function (node) { return node.nodeType === 3; },
      isComment: function (node) { return node.nodeType === 8; },
      isDocumentFragment: function (node) { return node.nodeType === 11; }
    };

    var emptyNode = vnode("", {}, [], undefined, undefined);

    function sameVnode(v1, v2) {
      var isSameKey = v1.key === v2.key;
      var isSameIs = (v1.data && v1.data.is) === (v2.data && v2.data.is);
      var isSameSel = v1.sel === v2.sel;
      return isSameSel && isSameKey && isSameIs;
    }

    function init(modules, domApi) {
      var cbs = { create: [], update: [], remove: [], destroy: [], pre: [], post: [] };
      var api = domApi !== undefined ? domApi : htmlDomApi;
      var hookNames = ["create", "update", "remove", "destroy", "pre", "post"];
      for (var hi = 0; hi < hookNames.length; hi++) {
        for (var mi = 0; mi < modules.length; mi++) {
          var currentHook = modules[mi][hookNames[hi]];
          if (currentHook !== undefined) cbs[hookNames[hi]].push(currentHook);
        }
      }

      function emptyNodeAt(elm) {
        var id = elm.id ? "#" + elm.id : "";
        var classes = elm.getAttribute("class");
        var c = classes ? "." + classes.split(" ").join(".") : "";
        return vnode(api.tagName(elm).toLowerCase() + id + c, {}, [], undefined, elm);
      }

      function createRmCb(childElm, listeners) {
        return function rmCb() {
          if (--listeners === 0) {
            var parent = api.parentNode(childElm);
            if (parent !== null) api.removeChild(parent, childElm);
          }
        };
      }

      function createElm(vnode, insertedVnodeQueue) {
        var i, data = vnode.data;
        var hook = data && data.hook;
        if (hook && hook.init) hook.init(vnode);
        var children = vnode.children;
        var sel = vnode.sel;
        if (sel === "!") {
          if (vnode.text === undefined) vnode.text = "";
          vnode.elm = api.createComment(vnode.text);
        } else if (sel === "") {
          vnode.elm = api.createTextNode(vnode.text);
        } else if (sel !== undefined) {
          var hashIdx = sel.indexOf("#");
          var dotIdx = sel.indexOf(".", hashIdx);
          var hash = hashIdx > 0 ? hashIdx : sel.length;
          var dot = dotIdx > 0 ? dotIdx : sel.length;
          var tag = hashIdx !== -1 || dotIdx !== -1 ? sel.slice(0, Math.min(hash, dot)) : sel;
          var elm = (vnode.elm = api.createElement(tag));
          if (hash < dot) elm.setAttribute("id", sel.slice(hash + 1, dot));
          if (dotIdx > 0) elm.setAttribute("class", sel.slice(dot + 1).replace(/\\./g, " "));
          for (i = 0; i < cbs.create.length; ++i) cbs.create[i](emptyNode, vnode);
          if (isPrimitive(vnode.text) && (!isArray(children) || children.length === 0)) {
            api.appendChild(elm, api.createTextNode(vnode.text));
          }
          if (isArray(children)) {
            for (i = 0; i < children.length; ++i) {
              var ch = children[i];
              if (ch != null) api.appendChild(elm, createElm(ch, insertedVnodeQueue));
            }
          }
          if (hook !== undefined) {
            if (hook.create) hook.create(emptyNode, vnode);
            if (hook.insert) insertedVnodeQueue.push(vnode);
          }
        } else {
          vnode.elm = api.createTextNode(vnode.text);
        }
        return vnode.elm;
      }

      function addVnodes(parentElm, before, vnodes, startIdx, endIdx, insertedVnodeQueue) {
        for (; startIdx <= endIdx; ++startIdx) {
          var ch = vnodes[startIdx];
          if (ch != null) api.insertBefore(parentElm, createElm(ch, insertedVnodeQueue), before);
        }
      }

      function invokeDestroyHook(vnode) {
        var data = vnode.data;
        if (data !== undefined) {
          if (data.hook && data.hook.destroy) data.hook.destroy(vnode);
          for (var i = 0; i < cbs.destroy.length; ++i) cbs.destroy[i](vnode);
          if (vnode.children !== undefined) {
            for (var j = 0; j < vnode.children.length; ++j) {
              var child = vnode.children[j];
              if (child != null && typeof child !== "string") invokeDestroyHook(child);
            }
          }
        }
      }

      function removeVnodes(parentElm, vnodes, startIdx, endIdx) {
        for (; startIdx <= endIdx; ++startIdx) {
          var listeners, ch = vnodes[startIdx];
          if (ch != null) {
            if (ch.sel !== undefined) {
              invokeDestroyHook(ch);
              listeners = cbs.remove.length + 1;
              var rm = createRmCb(ch.elm, listeners);
              for (var i = 0; i < cbs.remove.length; ++i) cbs.remove[i](ch, rm);
              var removeHook = ch.data && ch.data.hook && ch.data.hook.remove;
              if (removeHook) removeHook(ch, rm);
              else rm();
            } else if (ch.children) {
              invokeDestroyHook(ch);
              removeVnodes(parentElm, ch.children, 0, ch.children.length - 1);
            } else {
              api.removeChild(parentElm, ch.elm);
            }
          }
        }
      }

      function createKeyToOldIdx(children, beginIdx, endIdx) {
        var map = {};
        for (var i = beginIdx; i <= endIdx; ++i) {
          var key = children[i] && children[i].key;
          if (key !== undefined) map[key] = i;
        }
        return map;
      }

      function updateChildren(parentElm, oldCh, newCh, insertedVnodeQueue) {
        var oldStartIdx = 0, newStartIdx = 0;
        var oldEndIdx = oldCh.length - 1;
        var oldStartVnode = oldCh[0];
        var oldEndVnode = oldCh[oldEndIdx];
        var newEndIdx = newCh.length - 1;
        var newStartVnode = newCh[0];
        var newEndVnode = newCh[newEndIdx];
        var oldKeyToIdx, idxInOld, elmToMove, before;
        while (oldStartIdx <= oldEndIdx && newStartIdx <= newEndIdx) {
          if (oldStartVnode == null) { oldStartVnode = oldCh[++oldStartIdx]; }
          else if (oldEndVnode == null) { oldEndVnode = oldCh[--oldEndIdx]; }
          else if (newStartVnode == null) { newStartVnode = newCh[++newStartIdx]; }
          else if (newEndVnode == null) { newEndVnode = newCh[--newEndIdx]; }
          else if (sameVnode(oldStartVnode, newStartVnode)) {
            patchVnode(oldStartVnode, newStartVnode, insertedVnodeQueue);
            oldStartVnode = oldCh[++oldStartIdx];
            newStartVnode = newCh[++newStartIdx];
          } else if (sameVnode(oldEndVnode, newEndVnode)) {
            patchVnode(oldEndVnode, newEndVnode, insertedVnodeQueue);
            oldEndVnode = oldCh[--oldEndIdx];
            newEndVnode = newCh[--newEndIdx];
          } else if (sameVnode(oldStartVnode, newEndVnode)) {
            patchVnode(oldStartVnode, newEndVnode, insertedVnodeQueue);
            api.insertBefore(parentElm, oldStartVnode.elm, api.nextSibling(oldEndVnode.elm));
            oldStartVnode = oldCh[++oldStartIdx];
            newEndVnode = newCh[--newEndIdx];
          } else if (sameVnode(oldEndVnode, newStartVnode)) {
            patchVnode(oldEndVnode, newStartVnode, insertedVnodeQueue);
            api.insertBefore(parentElm, oldEndVnode.elm, oldStartVnode.elm);
            oldEndVnode = oldCh[--oldEndIdx];
            newStartVnode = newCh[++newStartIdx];
          } else {
            if (oldKeyToIdx === undefined) oldKeyToIdx = createKeyToOldIdx(oldCh, oldStartIdx, oldEndIdx);
            idxInOld = oldKeyToIdx[newStartVnode.key];
            if (idxInOld === undefined) {
              api.insertBefore(parentElm, createElm(newStartVnode, insertedVnodeQueue), oldStartVnode.elm);
              newStartVnode = newCh[++newStartIdx];
            } else {
              elmToMove = oldCh[idxInOld];
              if (elmToMove.sel !== newStartVnode.sel) {
                api.insertBefore(parentElm, createElm(newStartVnode, insertedVnodeQueue), oldStartVnode.elm);
              } else {
                patchVnode(elmToMove, newStartVnode, insertedVnodeQueue);
                oldCh[idxInOld] = undefined;
                api.insertBefore(parentElm, elmToMove.elm, oldStartVnode.elm);
              }
              newStartVnode = newCh[++newStartIdx];
            }
          }
        }
        if (newStartIdx <= newEndIdx) {
          before = newCh[newEndIdx + 1] == null ? null : newCh[newEndIdx + 1].elm;
          addVnodes(parentElm, before, newCh, newStartIdx, newEndIdx, insertedVnodeQueue);
        }
        if (oldStartIdx <= oldEndIdx) removeVnodes(parentElm, oldCh, oldStartIdx, oldEndIdx);
      }

      function patchVnode(oldVnode, vnode, insertedVnodeQueue) {
        var hook = vnode.data && vnode.data.hook;
        if (hook && hook.prepatch) hook.prepatch(oldVnode, vnode);
        var elm = (vnode.elm = oldVnode.elm);
        if (oldVnode === vnode) return;
        if (vnode.data !== undefined || (vnode.text !== undefined && vnode.text !== oldVnode.text)) {
          if (vnode.data === undefined) vnode.data = {};
          if (oldVnode.data === undefined) oldVnode.data = {};
          for (var i = 0; i < cbs.update.length; ++i) cbs.update[i](oldVnode, vnode);
          if (vnode.data.hook && vnode.data.hook.update) vnode.data.hook.update(oldVnode, vnode);
        }
        var oldCh = oldVnode.children;
        var ch = vnode.children;
        if (vnode.text === undefined) {
          if (oldCh !== undefined && ch !== undefined) {
            if (oldCh !== ch) updateChildren(elm, oldCh, ch, insertedVnodeQueue);
          } else if (ch !== undefined) {
            if (oldVnode.text !== undefined) api.setTextContent(elm, "");
            addVnodes(elm, null, ch, 0, ch.length - 1, insertedVnodeQueue);
          } else if (oldCh !== undefined) {
            removeVnodes(elm, oldCh, 0, oldCh.length - 1);
          } else if (oldVnode.text !== undefined) {
            api.setTextContent(elm, "");
          }
        } else if (oldVnode.text !== vnode.text) {
          if (oldCh !== undefined) removeVnodes(elm, oldCh, 0, oldCh.length - 1);
          api.setTextContent(elm, vnode.text);
        }
        if (hook && hook.postpatch) hook.postpatch(oldVnode, vnode);
      }

      return function patch(oldVnode, vnode) {
        var i, elm, parent;
        var insertedVnodeQueue = [];
        for (i = 0; i < cbs.pre.length; ++i) cbs.pre[i]();
        if (api.isElement(oldVnode)) oldVnode = emptyNodeAt(oldVnode);
        if (sameVnode(oldVnode, vnode)) {
          patchVnode(oldVnode, vnode, insertedVnodeQueue);
        } else {
          elm = oldVnode.elm;
          parent = api.parentNode(elm);
          createElm(vnode, insertedVnodeQueue);
          if (parent !== null) {
            api.insertBefore(parent, vnode.elm, api.nextSibling(elm));
            removeVnodes(parent, [oldVnode], 0, 0);
          }
        }
        for (i = 0; i < insertedVnodeQueue.length; ++i) {
          insertedVnodeQueue[i].data.hook.insert(insertedVnodeQueue[i]);
        }
        for (i = 0; i < cbs.post.length; ++i) cbs.post[i]();
        return vnode;
      };
    }

    return { h: h, init: init, vnode: vnode, htmlDomApi: htmlDomApi };
  })();

  var arkPatch = snabbdom.init([]);

  function arkSelectorFor(el) {
    var sel = el.tagName.toLowerCase();
    if (el.id) sel += "#" + el.id;
    var cls = el.getAttribute("class");
    if (cls) sel += "." + cls.trim().split(/\\s+/).join(".");
    return sel;
  }"""
