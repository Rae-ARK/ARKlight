# ARKlight Desktop Interface and Neutralino.js Integration

## Overview

ARKlight supports optional desktop application builds through an external Neutralino.js backend.

The architectural boundary is:

```text
ARKlight
  -> generates HTML/CSS/JS
  -> optionally packages the generated website
  -> desktop application
````

ARKlight remains responsible for website generation. Neutralino.js remains a separate third-party desktop backend.

Normal website builds must not require Neutralino.js or desktop tooling.

## Desktop Interface

The primary CLI entry point is:

```text
arklight desktop
```

Optional backends:

```text
arklight desktop --native
arklight desktop --github-actions
arklight desktop --github-ci
arklight desktop --export
arklight licenses
```

Recommended behavior:

```text
arklight build
  -> website only

arklight desktop
  -> local/native desktop build

arklight desktop --github-actions
  -> generates a reproducible GitHub Actions workflow

arklight desktop --export
  -> exports the generated desktop project

arklight licenses
  -> displays applicable third-party licenses and notices
```

The desktop interface should abstract desktop backends so future implementations can support alternatives such as Tauri or Electron without adding their dependencies to the core compiler.

## Architecture

```text
                         ARKlight
                            |
                 +----------+----------+
                 |                     |
                 v                     v
          Website Builder       Desktop Builder
                 |                     |
                 v                     v
             HTML/CSS/JS       Neutralino Backend
                                       |
                              +--------+--------+
                              |        |        |
                              v        v        v
                            Linux   Windows   macOS
```

The normal website path is:

```text
Python + ARKlight
  -> website
```

The optional desktop path is:

```text
Python + ARKlight + Neutralino.js
  -> desktop application
```

## Dependency Model

ARKlight core should remain dependency-light.

```text
arklight build
  -> Python
  -> ARKlight
  -> HTML/CSS/assets
  -> no Neutralino.js

arklight desktop
  -> ARKlight output
  -> Neutralino.js
  -> platform-specific build requirements
```

Neutralino.js should be treated as an external optional dependency rather than copied unnecessarily into the ARKlight source tree.

The core compiler must not depend on Neutralino.js.

## Native Backend

A native build should:

1. Validate the ARKlight project.
2. Build the website.
3. Select the desktop backend.
4. Check for the required pinned Neutralino.js version.
5. Obtain missing Neutralino components.
6. Verify downloaded artifacts.
7. Create a temporary desktop build directory.
8. Copy the generated website into the Neutralino project.
9. Generate the required Neutralino configuration.
10. Invoke the Neutralino build tooling.
11. Place resulting artifacts in `dist/desktop/`.

Conceptually:

```text
arklight desktop
  -> arklight build
  -> generated website
  -> Neutralino project
  -> native build
  -> dist/desktop/
```

The local command should target the current host platform by default. Cross-platform builds should not be assumed.

ARKlight should detect missing system toolchains and explain how to install them rather than silently installing arbitrary system packages or requiring elevated privileges.

## GitHub Actions Backend

The GitHub Actions backend should generate a workflow rather than perform the desktop build locally.

Example:

```text
arklight desktop --github-actions
```

Generated output:

```text
.github/
└── workflows/
    └── arklight-desktop.yml
```

The workflow should:

1. Check out the repository.
2. Establish the required ARKlight environment.
3. Obtain the pinned Neutralino.js version.
4. Build the website.
5. Create the Neutralino project.
6. Build desktop artifacts.
7. Upload the resulting artifacts.

The workflow must establish its own dependencies and must not rely on local caches, installed compilers, npm packages, previous artifacts, or other developer-machine state.

A matrix build may target Linux, Windows, and macOS.

## Project Layout

Neutralino-generated files should not pollute the user's source tree unless an explicit export is requested.

Recommended structure:

```text
project/
├── arklight.py
├── assets/
├── ...
└── dist/
    ├── website/
    └── desktop/
```

Temporary/generated desktop tooling may use:

```text
.arklight/
├── cache/
│   └── neutralino/
└── build/
    └── desktop/
```

An exported desktop project may be produced with:

```text
arklight desktop --export
```

and placed under:

```text
dist/desktop-project/
```

Generated files should clearly identify themselves and distinguish user-owned source, ARKlight-generated files, and Neutralino-generated files.

## Dependency Cache and Versioning

Downloaded Neutralino.js components should be cached, for example:

```text
~/.cache/arklight/neutralino/
```

The build process should:

```text
Check cache
  -> cached: verify and use
  -> missing: download
  -> verify
  -> build
```

ARKlight must pin a known Neutralino.js version rather than silently using the latest release.

The supported version should be defined by the ARKlight release and intentionally updated in future releases.

## Integrity and Security

Third-party build artifacts should be verified before execution where a trustworthy integrity mechanism is available.

The dependency manager should:

* Use HTTPS.
* Pin dependency versions.
* Verify downloaded artifacts.
* Avoid arbitrary shell execution where possible.
* Avoid blindly executing downloaded scripts.
* Avoid requiring root privileges.
* Clearly identify third-party software.
* Keep third-party components separate from ARKlight source.

ARKlight should not blindly execute an unverified downloaded executable when a reliable checksum or equivalent integrity mechanism is available.

## Offline Behavior

If required Neutralino.js components are already cached, desktop builds should work offline.

If they are unavailable, the desktop command should clearly report that internet access is required for the initial installation.

The normal website build must remain independent of network access and desktop dependencies.

## Neutralino Project and Runtime

ARKlight should generate the Neutralino project structure required by the currently supported Neutralino.js tooling and place the generated website inside it.

Conceptually:

```text
desktop-project/
├── index.html
├── styles.css
├── assets/
└── neutralino/
    ├── neutralino.config.json
    └── ...
```

ARKlight should not reimplement Neutralino APIs.

A website remains valid as a normal browser website. Desktop-specific functionality may use Neutralino APIs when available.

Conceptually:

```text
Browser
  -> normal web APIs

Neutralino
  -> normal web APIs
  -> Neutralino APIs
```

Desktop-specific functionality should provide sensible browser fallbacks where practical.

A static ARKlight website must remain usable without JavaScript solely because it is packaged as a desktop application.

## Licensing and Third-Party Notices

ARKlight and Neutralino.js retain separate licensing and copyright boundaries.

The build system must distinguish:

```text
ARKlight source
  -> ARKlight license

Neutralino.js
  -> Neutralino license and copyright

User website
  -> user's license and copyright

Other dependencies
  -> their respective notices
```

ARKlight must preserve applicable third-party copyright and license notices when distributing software containing those components.

The exact obligations must be determined from the actual versions and distributions used. License details, checksums, and notice text must not be invented or hard-coded without verification.

A desktop distribution should include the notices required by applicable licenses.

The runtime distinction remains explicit even when multiple components are JavaScript:

```text
arklight.js
  -> ARKlight licensing terms

Neutralino runtime/API code
  -> applicable Neutralino licensing terms
```

## License Interface

ARKlight should identify the specific third-party software used by a build rather than providing a vague global license-acceptance mechanism.

For example:

```text
This build uses:
  Neutralino.js
  License: <actual license>
```

The CLI should distinguish between displaying license information and requiring affirmative legal acceptance. These are not automatically equivalent.

Automated builds must not hang waiting for interactive prompts.

If a dependency genuinely requires affirmative acceptance that cannot legally be automated, the build should fail clearly rather than silently treating execution as consent.

A mechanism such as:

```text
arklight licenses
```

should display applicable licenses for optional components.

## Generated Desktop Artifacts

The generated desktop application may contain code from multiple copyright holders. ARKlight must not replace third-party notices with ARKlight notices.

Generated artifacts should preserve applicable attribution and license information.

The desktop project should keep user source, ARKlight-generated files, Neutralino-generated files, and third-party components identifiable.

## Backend Interface

Desktop builders should use an internal backend abstraction.

Conceptually:

```text
DesktopBackend
  -> check_dependencies()
  -> install_dependencies()
  -> build()
  -> export()
  -> licenses()

NeutralinoBackend
  -> implements DesktopBackend
```

Future implementations may include:

```text
TauriBackend
ElectronBackend
CustomBackend
```

The core ARKlight compiler should not depend on the implementation details of individual desktop backends.

A possible structure is:

```text
arklight/
├── __init__.py
├── cli.py
├── compiler/
├── runtime/
├── desktop/
│   ├── __init__.py
│   ├── base.py
│   ├── neutralino.py
│   ├── dependencies.py
│   ├── licenses.py
│   └── github_actions.py
└── ...
```

## User Experience

The intended interface is:

```text
Website:
  arklight build
  -> website

Local desktop:
  arklight desktop
  -> website
  -> Neutralino.js
  -> native application

CI desktop:
  arklight desktop --github-actions
  -> workflow
  -> GitHub Actions
  -> Neutralino.js
  -> native artifacts
```

Users should not need to understand the internal desktop architecture to perform normal builds.

## Failure Handling

Errors should identify the actionable cause.

Desktop build failures should report, where applicable:

* Failed step.
* Missing dependency.
* Required version.
* Target platform.
* Relevant command.
* Location of logs or generated files.

Example:

```text
Desktop build failed.

Missing dependency:
  <dependency>

Required for:
  <platform>

Install or enable the required desktop toolchain and try again.
```

## Implementation Priority

### Phase 1: Native Backend

Implement:

```text
arklight desktop --native
```

with:

* Pinned Neutralino.js version.
* Dependency detection.
* Dependency cache.
* Integrity verification.
* Generated Neutralino project.
* Local build.
* Clear errors.

### Phase 2: GitHub Actions

Implement:

```text
arklight desktop --github-actions
```

with a reproducible workflow that performs the desktop build remotely.

### Phase 3: Export

Implement:

```text
arklight desktop --export
```

for users who need to inspect or modify the generated desktop project.

### Phase 4: Licensing

Implement:

```text
arklight licenses
```

and improve third-party attribution and notice generation.

### Phase 5: Additional Backends

Consider additional backends such as:

```text
arklight desktop --tauri
arklight desktop --electron
```

only when there is a concrete use case.

## Design Principles

1. ARKlight generates the website.
2. Neutralino.js is an optional external desktop backend.
3. `arklight build` must never require Neutralino.js.
4. Desktop tooling must remain isolated from the core compiler.
5. Desktop dependencies should be acquired only when desktop functionality is requested.
6. Dependencies should be version-pinned and verified where practical.
7. Local builds should use the host platform by default.
8. GitHub Actions should provide an optional reproducible remote build path.
9. Third-party code, licenses, copyrights, and notices must remain identifiable.
10. System-level dependencies must not be installed silently or with unnecessary elevated privileges.
11. The desktop interface should permit future backend implementations without redesigning the website compiler.

## Final Architecture

```text
                         ARKlight
                            |
              +-------------+-------------+
              |                           |
              v                           v
       Website Builder             Desktop Interface
              |                           |
              v                           v
         HTML/CSS/JS              Desktop Backend
                                          |
                                  +-------+-------+
                                  |               |
                                  v               v
                            Native Backend   GitHub Actions
                                  |               |
                                  v               v
                            Neutralino.js     CI runners
                                  |               |
                           +------+------+        |
                           |      |      |        |
                           v      v      v        v
                         Linux  Windows macOS  Artifacts
```

ARKlight remains a lightweight, web-first website compiler. The desktop interface provides an optional bridge from generated web projects to native applications while keeping Neutralino.js and future desktop frameworks separate from the core ARKlight architecture.

```
