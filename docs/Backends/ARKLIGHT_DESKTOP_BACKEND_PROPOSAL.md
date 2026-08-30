# ARKlight Desktop Backend: Native Host Proposal

**Status:** Proposed replacement for the Neutralino.js integration plan  
**Target branch:** `alpha`  
**Target milestone:** `v0.080`  
**Date:** 2026-08-31

## 1. Decision

ARKlight should not make Neutralino.js the canonical desktop backend.

ARKlight should implement a small, purpose-built native desktop host and packager whose only job is to execute an already-built ARKlight static site.

Neutralino.js remains a technically viable third-party option and may remain documented as an experimental/export backend, but it should not define ARKlight's desktop architecture.

The reason is not that Neutralino is incapable of supporting ARKlight. Current Neutralino releases support JavaScript applications, platform WebViews, embedded resources, and single-file executables. Even assuming ARKlight eventually gains full JavaScript support, the problem remains architectural fit: Neutralino is a general desktop application framework, while ARKlight's desktop target is fundamentally a static-artifact deployment target. Neutralino introduces an application runtime, static HTTP serving, WebSocket IPC, a JavaScript client library, and a broad native API model that the first ARKlight desktop target does not need. [Neutralino architecture](https://neutralino.js.org/docs/contributing/architecture/) · [Neutralino CLI](https://neutralino.js.org/docs/cli/neu-cli/) · [Neutralino distribution](https://neutralino.js.org/docs/distribution/overview/)

The proposed pipeline is:

```text
                        ARKlight compiler
                               |
                               v
                    completed static website
                               |
                               v
                         .ark bundle
                               |
                               v
                    embed bundle into native host
                               |
                               v
                     platform desktop executable
                               |
                               v
                  load bundle into process memory
                               |
                               v
                       in-memory asset store
                               |
                               v
                         platform WebView
                               |
                               v
                         rendered ARKlight site
```

The runtime should do everything required to render and run the generated site, and nothing more.

---

## 2. Existing ARKlight direction

The `alpha` branch already separates authoring, compilation, backend rendering, and packaging. ARKlight is a Python-first compiler whose output is ordinary HTML/CSS/JavaScript and static assets. The generated website does not require Python, Node.js, npm, or a server at runtime. [ARKlight `alpha`](https://github.com/Rae-ARK/ARKlight/tree/alpha)

The relevant conceptual boundary is:

```text
Python source
    |
    v
ARKlight compiler
    |
    v
Website IR
    |
    +-----------------------------+
    |             |               |
    v             v               v
  HTML           CSS              JS
 backend       backend          backend
    |             |               |
    +-------------+---------------+
                  |
                  v
            static artifact
```

ARKlight also already has a packaging concept for completed output through the `.ark` bundle format. Packaging belongs after site generation, which makes the desktop target naturally a deployment/package layer rather than another compiler backend. [ARKlight `alpha` docs](https://github.com/Rae-ARK/ARKlight/tree/alpha)

The desktop target therefore should not change the semantics of the web backend. It should consume the same completed artifact that can already be deployed as a static website.

---

## 3. Desktop target semantics

Selecting the desktop target should cause ARKlight to perform the complete build and package sequence automatically.

A user should conceptually be able to write:

```text
arklight build --target desktop
```

or use whatever final CLI spelling ARKlight standardizes for target selection.

The internal sequence is:

```text
1. Parse source
2. Build IR
3. Render HTML/CSS/JS/assets
4. Complete normal post-processing
5. Pack the completed site as an .ark bundle
6. Select the native host for the target platform
7. Embed the .ark bundle into that native host
8. Produce the desktop application artifact
```

There should be no intermediate Neutralino project generated as part of the canonical path.

There should also be no requirement for the user project to contain desktop-framework source files merely because the project is being packaged for desktop.

---

## 4. Native host responsibilities

The native host is intentionally tiny.

### Required responsibilities

The host shall:

1. create the native application/window;
2. initialize the platform WebView;
3. locate and validate the embedded `.ark` bundle;
4. load the bundle into process memory;
5. unpack/decode the bundle into an in-memory asset representation;
6. expose those assets to the WebView through an application-owned resource scheme or equivalent in-process resource handler;
7. load the ARKlight entry document;
8. enforce the desktop navigation policy;
9. release runtime resources and bundle memory when the process exits.

### Explicit non-responsibilities

The host shall not initially provide:

- Node.js;
- npm;
- Python;
- an application HTTP server;
- a WebSocket RPC layer;
- an arbitrary native JavaScript bridge;
- a general-purpose filesystem API;
- a plugin framework;
- a database;
- an embedded browser engine when the platform WebView is sufficient.

This is the core scope rule:

> **The desktop runtime is a launcher and resource provider for an ARKlight artifact, not a second application framework.**

---

## 5. `.ark` bundle is the application payload

When the desktop target is selected, the final site is first packed using the ARKlight `.ark` bundle format.

Conceptually:

```text
build/
├── index.html
├── about.html
├── styles.css
├── arklight.js
└── assets/

        |
        v

     site.ark

        |
        v

+--------------------------------+
| native ARKlight host           |
|                                |
| native code                    |
| platform integration           |
| embedded site.ark              |
+--------------------------------+

        |
        v

   MySite.exe / .app / package
```

The `.ark` bundle is therefore the content payload of the application.

The native executable is the runtime shell around that payload.

This is preferable to copying the generated website into another desktop framework's expected project structure because the ARK bundle remains the canonical representation of the built site.

---

## 6. Embedded-bundle runtime

The installed application should not require the source website to remain as ordinary files on disk.

At process startup:

```text
application starts
      |
      v
locate embedded .ark payload
      |
      v
validate bundle header / integrity information
      |
      v
authenticate/decrypt if the bundle format enables sealing
      |
      v
unpack/decompress into RAM
      |
      v
construct in-memory asset index
      |
      v
initialize WebView
      |
      v
register resource handler
      |
      v
load entry document
```

The default model is **RAM-backed execution of the packaged site**.

The host should not extract the entire website to `%TEMP%`, `/tmp`, or another cache directory just to make the WebView happy.

If a specific platform WebView limitation ever forces temporary materialization for a feature, that should be treated as an explicit platform exception, not the general runtime model.

---

## 7. In-memory asset store

The simplest initial representation is an indexed collection of decoded assets:

```text
AssetStore
├── index.html       -> bytes
├── about.html       -> bytes
├── styles.css       -> bytes
├── arklight.js      -> bytes
└── assets/          -> bytes
```

A descriptor can contain information equivalent to:

```text
path
mime type
compression state
byte range / address
uncompressed size
```

Resource lookup should be indexed rather than implemented as a sequential archive scan for every request.

For example:

```text
ark://site/assets/logo.svg
             |
             v
       normalized path
             |
             v
       asset index lookup
             |
             v
          RAM bytes
             |
             v
          WebView
```

The implementation should optimize for correctness and simplicity first. A contiguous arena, memory-mapped backing, or more elaborate cache can be considered later if profiling demonstrates a real need.

---

## 8. Resource scheme

The WebView should receive an application-owned resource namespace, for example:

```text
ark://site/index.html
ark://site/about.html
ark://site/styles.css
ark://site/arklight.js
ark://site/assets/logo.svg
```

The host owns the resolution of that namespace:

```text
ark://site/<path>
       |
       v
normalize path
       |
       v
lookup asset
       |
       v
return MIME + bytes
```

The exact WebView API will differ per platform, but the logical contract must remain the same.

This avoids adding a localhost server solely to deliver immutable packaged resources.

---

## 9. Routing and navigation

ARKlight's compiler already resolves internal links into generated relative paths. The desktop runtime should preserve those semantics and must not introduce a second route compiler. [ARKlight `alpha`](https://github.com/Rae-ARK/ARKlight/tree/alpha)

The division of responsibility is:

```text
ARKlight compiler
    -> decides what file a route points to

Desktop runtime
    -> resolves the resulting resource request
```

A recommended policy is:

```text
ark://...        -> internal application resource
https://...      -> external navigation policy
http://...       -> external navigation policy
mailto:...       -> platform handler
other supported schemes -> explicit policy
```

The runtime should not expose arbitrary filesystem navigation through the application's resource handler.

---

## 10. JavaScript runtime boundary

The generated ARKlight JavaScript should execute directly inside the platform WebView's JavaScript engine.

```text
ARKlight JS
    |
    v
WebView JS engine
    |
    v
DOM / CSS / events / browser APIs
```

The first desktop release should expose **zero custom native JavaScript APIs**.

This is an intentional design constraint, not an omission.

ARKlight's current programming model already generates constrained JavaScript behavior from its own source model rather than requiring arbitrary application JavaScript to cross into native code. [ARKlight `alpha`](https://github.com/Rae-ARK/ARKlight/tree/alpha)

Native APIs should appear only when a specific ARKlight feature proves that a platform capability is necessary.

When that happens, add a narrowly defined capability rather than a generic RPC function such as:

```text
native.call(name, arguments)
```

The preferred direction is an explicit API surface with individually reviewable capabilities.

---

## 11. Why Neutralino.js is not the canonical backend

Neutralino is technically capable of hosting an ARKlight site. That is not under dispute.

The issue is that Neutralino solves a larger problem than ARKlight's desktop target actually has.

Neutralino documents its framework as a C++ core plus JavaScript client library. Its router processes HTTP and WebSocket messages, it normally serves application resources over HTTP, and native API operations use WebSocket messaging. [Neutralino architecture](https://neutralino.js.org/docs/contributing/architecture/)

Conceptually, the normal Neutralino model is:

```text
application JavaScript
       |
       v
Neutralino client library
       |
       v
WebSocket message
       |
       v
Neutralino core / router
       |
       +------> native API
       |
       v
resource server / WebView
```

The preferred ARKlight model is:

```text
ARK bundle
    |
    v
native host
    |
    v
in-process resource handler
    |
    v
platform WebView
```

That difference is the reason for rejecting Neutralino as the core architecture.

### 11.1 Even assuming full JavaScript support in ARKlight

This proposal does **not** depend on ARKlight remaining limited to generated, constrained JavaScript. Assume the opposite: ARKlight eventually gains full JavaScript support, including arbitrary application JavaScript, modules, asynchronous APIs, browser APIs, and the language/runtime features needed by serious client-side applications.

That still does not make Neutralino the best architectural match.

The reason is that **JavaScript capability and desktop-runtime architecture are separate questions**.

With full ARKlight JavaScript support, the application could look like:

```text
ARKlight source
    |
    v
ARKlight compiler
    |
    +--> HTML
    +--> CSS
    +--> JavaScript
    +--> assets
    |
    v
completed website
    |
    v
.ark bundle
    |
    v
embedded in native ARKlight host
    |
    v
platform WebView JavaScript engine
```

The WebView already supplies the JavaScript engine and browser execution environment. ARKlight does not need another JavaScript application runtime merely because the site contains more JavaScript.

Neutralino's architecture still adds its own framework boundary:

```text
ARKlight application JS
        |
        v
Neutralino client library / framework model
        |
        v
Neutralino router + WebSocket protocol
        |
        v
Neutralino native APIs / resource system
        |
        v
platform WebView / OS
```

By contrast, the proposed ARKlight desktop path is:

```text
ARKlight application JS
        |
        v
platform WebView
        |
        v
ARKlight host resource handler
        |
        v
embedded .ark bundle in process memory
```

Full JavaScript support therefore strengthens the case for a thin native host: the WebView is capable of executing the application without requiring ARKlight to delegate execution to a second desktop framework.

The architectural question becomes:

> **What native facilities must ARKlight expose that a WebView does not already provide?**

Only those facilities should cross the native boundary. If the answer is “none,” the native API surface remains zero. If later the answer is “clipboard,” “notifications,” or another concrete capability, that capability can be added directly to the ARKlight host.

This is fundamentally different from adopting a general-purpose desktop framework first and then deciding which parts of that framework ARKlight happens to use.

### 11.2 Single-file Neutralino builds do not remove the architectural difference

Current Neutralino supports `neu build --embed-resources`, which embeds `resources.neu` into the platform binary and produces a single executable. That feature means Neutralino can achieve a convenient distribution shape. [Neutralino CLI](https://neutralino.js.org/docs/cli/neu-cli/) · [Neutralino distribution](https://neutralino.js.org/docs/distribution/overview/)

ARKlight should also produce a single packaged application where the target platform allows it, but its payload should be an ARKlight `.ark` bundle embedded directly in the ARKlight host.

The desired shape is:

```text
ARKlight:
    native host + embedded site.ark

Neutralino:
    Neutralino runtime + embedded resources.neu
```

Both can be single-file products. Only one is specialized around ARKlight's own artifact model.

### 11.3 Neutralino's native API model is unnecessary for the first target

Neutralino provides a broad native API system and explicit native API allowlists. Its security model exists partly because the framework intentionally exposes native operations through an IPC interface. [Neutralino security](https://neutralino.js.org/docs/contributing/security/) · [Neutralino client/API documentation](https://neutralino.js.org/docs/api/overview/)

ARKlight's initial desktop target can instead have no native page-to-host API at all.

There is no reason to build an authorization system for capabilities that the runtime does not expose.

### 11.4 Neutralino's resource APIs are designed around a general framework resource model

Neutralino exposes resource APIs for listing, reading, and extracting files from its resource bundle. [Neutralino resources API](https://neutralino.js.org/docs/api/resources/)

ARKlight's desktop requirement is narrower: it wants to treat the `.ark` bundle as an immutable application payload and service resources directly from process memory.

The ARKlight host should therefore own an `AssetStore` abstraction rather than adopting a general-purpose desktop resource subsystem.

### 11.5 Neutralino would become an architectural dependency of the desktop target

A Neutralino integration requires ARKlight to understand and maintain:

```text
Neutralino version
Neutralino project structure
Neutralino configuration
Neutralino build tooling
Neutralino resource behavior
Neutralino API behavior
platform-specific Neutralino distribution
third-party licensing/notices
```

The current ARKlight compiler does not need any of that to produce its web artifact.

A custom host reduces the desktop contract to the small set of functionality that ARKlight actually owns.

---

## 12. Security and the limits of “not inspectable”

The runtime should make casual extraction significantly harder, but the project must not claim that a distributed executable is impossible to reverse engineer.

A desktop executable necessarily contains or can derive the information needed to display the site. A sufficiently capable analyst can inspect process memory, instrument the WebView, debug the process, dump decrypted resources, or reverse engineer the host.

Therefore the accurate goal is:

> **Do not leave the packaged website as a normal readable directory on the user's disk, and do not make casual extraction the default path.**

This can be achieved by:

```text
embedded .ark bundle
      |
      v
optional authenticated encryption/sealing
      |
      v
runtime decryption
      |
      v
RAM-only decoded assets
      |
      v
WebView
```

When the process exits:

```text
WebView shutdown
      |
      v
release asset memory
      |
      v
clear sensitive buffers where practical
      |
      v
process termination
```

The operating system reclaims the process address space after termination.

This is a resistance mechanism against casual inspection, not DRM.

If ARKlight's sealing format is cryptographic, the encryption key cannot be treated as a secret that is magically unavailable to the running application. The runtime must be capable of obtaining or deriving whatever key material it needs, so determined reverse engineering remains possible.

---

## 13. Installation and platform packaging

The runtime architecture is platform-neutral, but the installation artifact is not.

Conceptually:

```text
Windows
    MySite.exe / installer

macOS
    MySite.app / installer image or package

Linux
    native package / portable application artifact
```

The installed application must retain only the platform-appropriate native application artifacts and whatever external platform WebView dependency is genuinely required.

ARKlight should not force a cross-platform packaging abstraction where the operating system packaging model differs substantially.

---

## 14. Platform WebView strategy

The native host should prefer the platform WebView instead of shipping a second browser engine.

The initial implementations can target the corresponding system-supported WebView technology for each platform, with the platform-specific code hidden behind a small host interface.

Conceptually:

```text
                ARK Host Core
                     |
          +----------+----------+
          |          |          |
          v          v          v
       Windows      macOS      Linux
       WebView      WebKit     WebView
```

The host core should know about:

```text
window
asset store
resource handler
navigation
lifecycle
```

The platform adapters know how to create the actual WebView and connect the resource handler to the platform API.

---

## 15. Runtime repository layout

A possible source layout is:

```text
ARKlight/
├── arklight/
│   ├── compiler/
│   ├── backends/
│   ├── packaging/
│   └── desktop/
│       ├── build.py
│       ├── bundle.py
│       └── targets.py
│
├── runtime/
│   └── arklight-host/
│       ├── core/
│       │   ├── application
│       │   ├── bundle
│       │   ├── asset_store
│       │   └── navigation
│       └── platform/
│           ├── windows/
│           ├── macos/
│           └── linux/
│
└── tests/
    └── desktop/
```

The exact language and build system are implementation choices. The architectural boundary should not depend on whether the native host is written in C++, Rust, or another suitable systems language.

---

## 16. Desktop build pipeline

The canonical build should be:

```text
             arklight build --target desktop
                         |
                         v
                    compile site
                         |
                         v
                 validate output
                         |
                         v
                    create site.ark
                         |
                         v
                 select host binary
                         |
                         v
                 embed site.ark
                         |
                         v
                 create final app
```

The build system should not generate an intermediate Neutralino project.

A desktop build cache may store reusable native host binaries so the packager does not rebuild the native runtime for every site.

Conceptually:

```text
ARKlight release
      |
      +-- host-windows-x64
      +-- host-linux-x64
      +-- host-macos-arm64
      +-- ...
```

The site-specific step then only embeds the generated `.ark` payload into the appropriate host artifact.

---

## 17. Reproducibility

The desktop target should preserve reproducibility where practical.

Inputs should be explicit:

```text
ARKlight version
host runtime version
platform
bundle contents
bundle format version
packaging metadata
```

The host binary should be versioned independently from the site payload.

A deterministic site should therefore produce the same logical `.ark` payload independent of the target desktop shell.

This separation also makes it possible to test:

```text
site.ark
  -> browser deployment

site.ark
  -> desktop deployment
```

without changing the compiler semantics.

---

## 18. Testing requirements

The desktop backend should be tested at four levels.

### Bundle tests

- valid bundle opens;
- corrupted bundle is rejected;
- missing entrypoint is rejected;
- path traversal is rejected;
- MIME metadata resolves correctly;
- sealed bundles fail cleanly when authentication fails.

### Runtime tests

- application starts;
- `index.html` renders;
- CSS loads;
- generated JavaScript executes;
- internal links resolve;
- assets load from memory;
- external links follow policy;
- application closes cleanly;
- decoded bundle data is released on shutdown.

### Packaging tests

- bundle embeds correctly;
- executable starts with an embedded bundle;
- output does not require the original site directory;
- installation artifact works on a clean target machine subject to the documented WebView prerequisite.

### Regression tests

The normal website build must remain unchanged when no desktop target is selected.

---

## 19. Failure behavior

The runtime should fail closed and explain failures clearly.

Examples:

```text
Invalid embedded ARK bundle
Unsupported bundle version
Integrity verification failed
Missing desktop entrypoint
Unsupported platform WebView
Resource not found
Navigation blocked by application policy
```

No silent fallback to a local filesystem copy should occur merely because an embedded resource lookup failed.

---

## 20. What should not be built yet

The first desktop implementation should deliberately exclude:

```text
native filesystem API
native process spawning
custom IPC protocol
plugins/extensions
application updater
persistent native storage
embedded web server
browser debugging service
arbitrary page JavaScript bridge
```

Those are separate product decisions.

A feature should earn a place in the desktop runtime by demonstrating that the static ARKlight model cannot express it alone.

---

## 21. Relationship to Neutralino

Neutralino should not be deleted from consideration merely because the canonical backend is custom.

It can remain useful as:

- a prototype/reference implementation;
- an experimental backend;
- an export option for users who explicitly want the Neutralino framework;
- a comparison target during native-host development.

The important distinction is:

```text
Canonical ARKlight desktop:
    ARK bundle + ARK native host

Optional third-party backend:
    ARKlight output + Neutralino
```

Neutralino should therefore be treated as an optional integration, not as an architectural dependency of ARKlight itself.

---

## 22. Final architecture

The proposed architecture is:

```text
                              ARKlight
                                  |
                    +-------------+-------------+
                    |                           |
                    v                           v
              normal web target           desktop target
                    |                           |
                    v                           v
             static website                 .ark bundle
                                                |
                                                v
                                        native host packer
                                                |
                                                v
                                      embedded bundle
                                                |
                                                v
                                        desktop executable
                                                |
                                                v
                                         process startup
                                                |
                                                v
                                      bundle -> RAM store
                                                |
                                                v
                                           WebView
                                                |
                                                v
                                         ARKlight site
                                                |
                                      application closes
                                                |
                                                v
                                       release RAM assets
                                                |
                                                v
                                            exit
```

The resulting product can be summarized in one sentence:

> **ARKlight compiles the site, packs the site, embeds the pack into a native host, runs the packaged site from memory through the platform WebView, and exits without turning the site into a second framework application.**

That is a better fit for ARKlight than making Neutralino the center of the architecture because it preserves the compiler's existing separation of concerns and adds the smallest possible runtime needed to turn the existing static artifact into a desktop application.

---

## 23. Sources

- ARKlight `alpha` repository: <https://github.com/Rae-ARK/ARKlight/tree/alpha>
- ARKlight current Neutralino integration document, superseded by this proposal: <https://github.com/Rae-ARK/ARKlight/blob/alpha/docs/Backends/NEUTRALINO-INTEGRATION.md>
- Neutralino architecture: <https://neutralino.js.org/docs/contributing/architecture/>
- Neutralino CLI and embedded-resource builds: <https://neutralino.js.org/docs/cli/neu-cli/>
- Neutralino distribution overview: <https://neutralino.js.org/docs/distribution/overview/>
- Neutralino security: <https://neutralino.js.org/docs/contributing/security/>
- Neutralino resource API: <https://neutralino.js.org/docs/api/resources/>
