# ARKlight's Philosophy

- **"The browser never executes Python."** (`arklight/__init__.py`) —
  output is plain HTML/CSS/vanilla JS; the compiler is the only thing
  that runs Python.
- **"No eval, no new Function, no string ever executed as code."**
  (`arklight/backend/js/render.py`, `runtime/dispatch.py`, `attrs.py`) —
  the shipped runtime never turns a string into executable code, even
  via a vendored dependency's optional feature.
- **"Fail loudly at build time, not silently in the browser."**
  (`ir/validate.py`, `config.py`, `experimental.py`) — anything wrong
  with a site should raise a `ValidationError` in Python during
  `arklight build`, never manifest as silent broken behavior after
  deployment.
- **"Only ship what's used."** (`js/htmx.py`, `js/render.py`, `attrs.py`)
  — the compiler emits the minimum HTML/CSS/JS a given site's IR
  actually needs; nothing bundled unconditionally.
- **Compiled markup should be honest about what it does** — the project
  repeatedly frames "inspectable, predictable" output as the point of
  compiling to plain HTML at all (`README.md`'s opening description).

# Other Folders

`docs/Foundational` - has the important docs.

-  *ARCHITECTURE.md* 

- *CONFIGURABILITY.md* 

- *DEPLOYMENT-CLU.md* 

- *DESIGN-NOTES.md* 

- *EXPERIMENTAL-APIS.md*

`docs/Backends` - has the Backend Related details.

*this file is not completed yet...*