# Windows Phone Backend

## Purpose

Provide an experimental backend for packaging ARKlight's generated
HTML/CSS/JS output as a Windows Phone application targeting the
Windows 10 Mobile / UWP platform.

This backend is optional and is not part of ARKlight's default supported
platform matrix.

## Architecture

ARKlight source
        |
        v
   Compiler / IR
        |
        v
  HTML + CSS + JS
        |
        v
 Windows Phone Backend
        |
        v
 UWP application package
        |
        v
 Windows 10 Mobile

The backend must consume the generated web artifact rather than adding
Windows Mobile-specific behavior to the core compiler.

## Packaging

Generate a minimal UWP project containing:

- Application manifest targeting `Windows.Mobile`
- Local ARKlight build output
- UWP WebView-based application shell
- Required assets and package metadata
- Build/package configuration appropriate to the selected Windows 10
  Mobile SDK

The generated application must operate from local packaged content and
must not require a remote web server.

Microsoft documents `Windows.Mobile` as a UWP target device family:
https://learn.microsoft.com/en-us/uwp/schemas/appxpackage/uapmanifestschema/element-targetdevicefamily

Microsoft documents UWP WebView support for hosting local HTML content:
https://learn.microsoft.com/en-us/uwp/api/windows.ui.xaml.controls.webview

## Toolchain

Target the legacy Windows 10 Mobile/UWP toolchain required by the
selected backend version.

Microsoft provides archived Windows 10 SDK releases and Microsoft
Emulator for Windows 10 Mobile, including SDK/emulator combinations for
Windows 10 Mobile versions 1507 through 1709:

https://learn.microsoft.com/en-us/windows/apps/windows-sdk/downloads-archive

The archived SDKs and emulators are unsupported legacy software.
Development must therefore pin the required SDK/emulator versions rather
than depending on the current Windows SDK.

## Emulator-first development

Physical Windows Phone hardware is not required for initial backend
development.

The backend must support:

1. Generating the UWP project.
2. Building the application with the pinned legacy SDK.
3. Deploying to the Microsoft Windows 10 Mobile Emulator.
4. Running generated ARKlight output inside the emulator.
5. Testing navigation, local assets, JavaScript, state, viewport behavior,
   and application lifecycle behavior.

Physical-device validation is recommended before declaring a release
usable on actual Windows 10 Mobile hardware.

## Scope

The backend provides packaging and platform integration only.

It must not:

- Add Windows Phone-specific APIs to ARKlight's core API.
- Require Windows Phone tooling for normal `arklight build`.
- Change the default static-site output.
- Introduce a server requirement.
- Become a dependency of other ARKlight backends.
- Promise modern Windows support.

## Status

**Experimental / legacy platform.**

The backend exists as an optional escape hatch for users who need to
target Windows 10 Mobile or wish to experiment with the platform.

The primary validation environment is the Microsoft Windows 10 Mobile
Emulator. Hardware compatibility remains subject to physical-device
testing.

## References

- Windows SDK archive and Windows 10 Mobile Emulator:
  https://learn.microsoft.com/en-us/windows/apps/windows-sdk/downloads-archive
- UWP target device families:
  https://learn.microsoft.com/en-us/uwp/schemas/appxpackage/uapmanifestschema/element-targetdevicefamily
- UWP WebView:
  https://learn.microsoft.com/en-us/uwp/api/windows.ui.xaml.controls.webview
