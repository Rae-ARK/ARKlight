# ARKlight Installer

## Overview

The ARKlight Installer installs the current stable release of ARKlight
without requiring the user to understand Python, `pip`, virtual
environments, or package management.

It is a desktop GUI application — a single wizard the user opens, runs,
and closes when it's done. Nothing stays running in the background
afterward.

The installer is a distribution layer, not part of the ARKlight compiler
or runtime.

Its responsibility is simple:

1. Find a compatible Python installation.
2. Let the user choose whether to use it.
3. If no suitable Python is available, offer a private CPython runtime.
4. Install the current stable ARKlight release from PyPI.
5. Create the platform-specific launch configuration.
6. Leave the user with a working `arklight` command.

The installer does not compile ARKlight.

---

## Design Goals

### Simple for users

A user should be able to:

> Download ARKlight → Install → `arklight build`

No Python knowledge should be required.

### Deliberately designed

The installer is a real interface, not a bare form. Typography, spacing,
theming (light/dark), and motion on state changes are part of what
ships — not something bolted on afterward. An unstyled wizard is not an
acceptable version of this tool.

### Lightweight

The installer should not bundle:

- The ARKlight source tree
- A C compiler
- Development headers
- Build tools
- A Python compiler
- Unnecessary runtime dependencies

A private Python runtime, when selected, is acquired as a prebuilt
CPython distribution — downloaded at install time, not shipped inside
the installer binary.

### Current by default

The installer does not pin an ARKlight release.

It installs the current stable package available from PyPI:

```text
pip install arklight
````

Users who require a historical version can install one explicitly using
Python and `pip`.

### Separate distribution from development

The installer must not become coupled to ARKlight's internal compiler
implementation.

ARKlight can change internally without requiring the installer itself
to be redesigned.

---

## Application Lifecycle

The installer has no background presence. There is no service, no tray
icon, and nothing registered to launch automatically. It runs only when
the user opens it, and exits fully when the task is done.

On launch, it checks whether ARKlight is already installed and branches
accordingly:

```text
                    Launch
                       │
                       ▼
              Is ARKlight installed?
                       │
          ┌────────────┴────────────┐
          │                         │
         No                        Yes
          │                         │
          ▼                         ▼
     Install flow          Update / Repair / Uninstall
```

This is the same binary handling the whole lifecycle — there is nothing
running between one launch and the next to keep that state fresh.

**Repair is not just "reinstall."** Its first job is validating that
the existing install still points at something real. For a system-Python
install, that means confirming the interpreter the virtual environment
was built against still exists at that path — a global Python
uninstall or upgrade after the fact is exactly what breaks this
silently, surfacing later as an obscure path error instead of anything
that explains itself. If that interpreter is gone, Repair doesn't just
report the break: it offers to pivot the install onto the private
standalone CPython runtime, the same one the private-runtime path
already knows how to acquire, so the user ends up with a working
`arklight` again without needing to understand why it broke or track
down a matching Python themselves.

Uninstalling is the one step with any platform-specific handling: on
most platforms the installer can remove itself as its final action, but
Windows cannot delete a program while it's still running, so uninstall
there ends by handing off to a small helper that finishes the cleanup
after the installer has closed. This only happens on the uninstall path
— installing, updating, and repairing never touch it.

---

## Dependencies & Connectivity

Nothing the installer needs — the private CPython runtime, ARKlight
itself, any supporting packages — is bundled into the installer binary.
All of it is fetched at install time, the same way `pip install
arklight` or a private CPython download would be run manually. This is
what keeps the installer small.

That means an internet connection is required to install, update, or
repair. Before making any change to the system, the installer checks
that it can actually reach what it needs. If it can't:

- Nothing is installed, partially or otherwise. No half-created virtual
  environment, no partially unpacked runtime left behind to clean up.
- The user is told clearly, in the wizard itself, that a connection is
  required because the runtime and package are downloaded rather than
  shipped with the installer — with the option to retry once
  connectivity is back.

---

## Installation Model

```text
                ARKlight Installer
                        │
                        ▼
               Detect CPython
                        │
              ┌─────────┴─────────┐
              │                   │
       Compatible Python     Missing or
           available          incompatible
              │                   │
              ▼                   ▼
       Use system Python    Install private
              │               CPython
              │                   │
              └─────────┬─────────┘
                        ▼
                 Install ARKlight
                        │
                        ▼
                   Ready to use
```

---

## Python Selection

The installer checks for an installed CPython interpreter.

If a system Python is found, the installer presents it as an available
option. If none is found, the system-Python option is unavailable and
the private runtime becomes the path forward.

The installer does not maintain its own Python version compatibility
matrix. It has one install step — the current stable ARKlight release —
and lets that release's own package metadata be the thing that fails
loudly if an interpreter genuinely can't run it, rather than trying to
predict that in the installer ahead of time.

---

## System Python

When the user selects the system Python:

```text
System CPython
      │
      ▼
Create isolated environment
      │
      ▼
Install ARKlight from PyPI
```

A virtual environment is used in this mode because the interpreter is
shared with other software.

The installer must not modify unrelated system Python packages.

**Risk inherent to this mode:** the virtual environment depends on the
system interpreter continuing to exist at the path it was created
against. If the user later deletes or upgrades their global Python
installation, the environment's internal links point at nothing, and
`arklight` starts failing with an interpreter-path error that means
nothing to someone who never chose to think about virtual environments
in the first place. This isn't a bug to fix in the venv logic — it's a
structural consequence of building on top of something outside the
installer's control. See Application Lifecycle for how Repair detects
and resolves this.

---

## Private Python

When the user selects the private runtime:

```text
Installer
    │
    ▼
Acquire compatible prebuilt CPython
    │
    ▼
Install into ARKlight's private runtime location
    │
    ▼
Install ARKlight directly into that interpreter
```

No virtual environment is required.

The private interpreter is already isolated because it exists solely for
ARKlight.

The installer does not compile CPython.

The private runtime is acquired as a prebuilt platform-specific
distribution.

---

## ARKlight Installation

ARKlight is installed through its normal Python package distribution.

The installer does not copy ARKlight's source tree manually.

Conceptually:

```text
pip install arklight
```

The installer always targets the current stable PyPI release unless the
user explicitly performs a developer installation outside the installer.

---

## Version Policy

The installer is intentionally version-agnostic.

It does not contain:

```text
ARKLIGHT_VERSION = "..."
```

The installer instead follows the stable PyPI release.

For example:

```text
Installer
    ↓
pip install arklight
    ↓
latest stable PyPI release
```

Publishing a new stable ARKlight release does not require rebuilding the
installer solely because the version changed.

Historical versions remain available to developers through normal Python
package tooling.

---

## Platform Support

The installer is a single codebase, built once and compiled per
platform, so Windows, Linux, and macOS all get the same wizard rather
than three separate implementations. Platform differences show up only
in how the result is packaged for that OS's native install experience —
one packaging configuration, multiple installable formats (Windows,
Linux, and macOS package formats), produced from the same build.

### Windows

Responsibilities include:

* Python detection
* Runtime selection
* ARKlight installation
* CLI launcher configuration
* Update, repair, and uninstallation

### Linux

Linux distribution respects existing platform conventions, producing
native distribution packages appropriate to the target system.

The underlying ARKlight installation model remains the same.

### macOS

macOS support is planned after the initial Windows and Linux targets.

The installation model remains:

```text
compatible system Python
        OR
private CPython
        ↓
ARKlight from PyPI
```

---

## What the Installer Does Not Do

The installer does not:

* Compile Python.
* Compile ARKlight.
* Compile carklight.
* Require a C compiler.
* Maintain a separate ARKlight package implementation.
* Bundle development dependencies.
* Modify unrelated Python environments.
* Expose ARKlight's internal compiler architecture to the user.
* Run in the background between launches.

---

## Relationship to carklight

carklight is a separate native compiler project.

The installer architecture should not assume that ARKlight will always be
implemented entirely in Python.

The eventual relationship may be:

```text
ARKlight
    │
    ├── Python implementation
    │
    └── carklight native implementation
              │
              ▼
       Native distribution
```

The installer should remain concerned with acquiring and configuring the
user-facing ARKlight distribution rather than understanding the compiler
implementation underneath it.

---

## Development

Installer development lives alongside ARKlight during the experimental
stage.

The installer is kept separate from the `arklight/` Python package because
it is distribution infrastructure rather than runtime functionality.

Suggested layout:

```text
ARKlight/
├── arklight/
├── tests/
├── docs/
├── pyproject.toml
└── installer/
    ├── gui/
    ├── linux/
    ├── windows/
    ├── macos/
    └── README.md
```

The installer may initially be developed on a dedicated branch before
being merged into the main development line.

---

## Release Principle

ARKlight releases and installer releases are related but independent.

A compiler change does not require installer changes.

A new ARKlight release does not require installer source changes.

The installer should change only when its installation behavior changes.

The intended result is:

```text
ARKlight development
        ↓
      PyPI
        ↓
  existing installer
        ↓
 current stable ARKlight
```

The installer is infrastructure around ARKlight, not another version of
ARKlight itself.
