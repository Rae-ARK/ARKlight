# ARKlight Installer

## Overview

The ARKlight Installer installs the current stable release of ARKlight
without requiring the user to understand Python, `pip`, virtual
environments, or package management.

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

### Lightweight

The installer should not bundle:

- The ARKlight source tree
- A C compiler
- Development headers
- Build tools
- A Python compiler
- Unnecessary runtime dependencies

A private Python runtime, when selected, is acquired as a prebuilt
CPython distribution.

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

Presence alone is not sufficient.

The interpreter must satisfy ARKlight's declared Python compatibility
requirements.

The compatibility source of truth is ARKlight's package metadata, not a
separately maintained installer version constant.

If a compatible system Python exists, the installer presents it as an
available option.

If it is missing or incompatible, the system-Python option is disabled.

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

### Windows

The installer provides a conventional Windows installation experience.

Responsibilities include:

* Python detection
* Python compatibility checking
* Runtime selection
* ARKlight installation
* CLI launcher configuration
* Uninstallation

The installer may use a native Windows installer framework such as NSIS
or Inno Setup.

### Linux

Linux distribution should respect existing platform conventions.

Possible outputs include:

* Native distribution packages
* Portable archives
* A bootstrap installer

The exact packaging format is platform-specific.

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
* Require CMake.
* Require CPack at runtime.
* Maintain a separate ARKlight package implementation.
* Bundle development dependencies.
* Modify unrelated Python environments.
* Expose ARKlight's internal compiler architecture to the user.

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
    ├── windows/
    ├── linux/
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

