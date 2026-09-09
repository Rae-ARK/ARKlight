"""
Template content for `arklight android scaffold` -- Stage 1 of
docs/Backends/ANDROID-BACKEND-IMPLEMENTATION.md.

Every function here is a pure `(...) -> str` or `(...) -> dict[path,
str]` builder, same "no runtime dependency, no disk I/O" discipline
`arklight.cli.templates` already follows for `arklight new` -- only
`arklight.cli.android` (the CLI-facing module, mirroring `arklight.
cli.scaffold`'s own split) actually writes anything to disk.

Two families of content live here:

- **Vendored, carried over unchanged from `ARKlight-Viewer-for-
  Android-Devices`** (Apache-2.0; see `NOTICE` below) -- `ArkBundle.
  kt`, `ArkSeal.kt`, `MemoryGuard.kt`, and the branded launcher-icon/
  color/theme resources. Only each Kotlin file's `package` line is
  substituted for the destination app's own package ID; everything
  else is byte-for-byte what the Viewer app ships, per
  ANDROID-BACKEND-IMPLEMENTATION.md's Stage-0 file table ("already
  standalone, reusable as-is").
- **New for Application mode** -- `MainActivity.kt` (no bundle picker,
  no menu, no passphrase dialog; one fixed site loaded from `assets/`
  at a stable origin), `ArkApplication.kt`, the manifest, and the
  Gradle/project files, all shaped by this milestone's "Updated
  direction" section rather than lifted from the Viewer repo.

NOTICE: portions of this file are adapted from
https://github.com/Rae-ARK/ARKlight-Viewer-for-Android-Devices,
licensed Apache License 2.0. See that repository's own LICENSE for
the full text; this is not a redistribution of the whole project, only
of the specific files ANDROID-BACKEND-IMPLEMENTATION.md's Stage 0
table marks as carried over unchanged.
"""

from __future__ import annotations

import re
from xml.sax.saxutils import escape as xml_escape

# AGP/Kotlin/AndroidX versions -- kept identical to the Viewer repo's
# own `build.gradle.kts`/`app/build.gradle.kts` (see
# ARKlight-Viewer-for-Android-Devices), since this scaffold's generated
# project targets the exact same toolchain the runtime pieces it
# vendors were already built and tested against.
_AGP_VERSION = "8.5.2"
_KOTLIN_VERSION = "1.9.24"
_COMPILE_SDK = 34
_MIN_SDK = 24
_TARGET_SDK = 34

# Gradle version the CI workflow below installs explicitly. The
# scaffolded project has no `gradlew` wrapper (nothing here templates
# the wrapper's binary jar), so CI can't rely on wrapper-version
# auto-detection the way a wrapper-carrying project would -- it has to
# name a version. Pinned to the oldest Gradle release that supports
# AGP 8.5.2 (Gradle's own compatibility matrix requires >= 8.7 for
# that AGP line), same "match the toolchain the vendored runtime
# pieces were already built against" reasoning `_AGP_VERSION`/
# `_KOTLIN_VERSION` above already follow.
_GRADLE_VERSION = "8.9"

# The stable https origin androidx.webkit's WebViewAssetLoader serves
# local content under -- see docs/Foundational/DESIGN-NOTES.md's "Why
# this needs to exist at all: the file:// problem".
_ASSET_ORIGIN = "https://appassets.androidplatform.net"


def _package_path(package_id: str) -> str:
    return package_id.replace(".", "/")


def _kt_with_package(source: str, package_id: str) -> str:
    """Swap a vendored .kt file's `package com.arklight.viewer` line
    for the destination app's own package ID -- the only edit these
    files need (see module docstring)."""
    first_line, rest = source.split("\n", 1)
    assert first_line.startswith("package "), first_line
    return f"package {package_id}\n{rest}"


def project_files(
    *,
    app_name: str,
    package_id: str,
    version_name: str,
    version_code: int,
    orientation: str,
    edge_to_edge: bool,
    has_custom_icon: bool,
    has_splash: bool,
    has_debug_keystore: bool = False,
    include_release_job: bool = False,
) -> dict[str, str]:
    """
    Return `{relative_path: contents}` for every *generated text* file
    in an Application-mode Android Studio project -- everything except
    the baked-in site itself (`app/src/main/assets/`, copied verbatim
    from the `arklight build` output directory by `arklight.cli.
    android.scaffold_project`, since that content is opaque binary/
    text this module has no business templating), the optional raw
    `icon`/`splash` source images, and the optional `--debug-keystore`
    file (all copied by the same caller, not templated here).

    `has_debug_keystore` controls whether `app/build.gradle.kts` wires
    a `debug` signing config pointing at `app/debug.keystore` -- see
    that function's own docstring for why you'd want one pinned rather
    than letting each machine (a fresh CI runner included) generate
    its own.

    `orientation` is already resolved to its Android manifest value
    (e.g. `"fullSensor"`, not the config file's `"sensor"`) -- see
    `arklight.cli.android._ORIENTATIONS`.

    `include_release_job` controls whether the generated GitHub
    Actions workflow gets a signed release-build job -- see
    `_github_ci_workflow_yml`'s own docstring. Off by default, opted
    into explicitly via `arklight android scaffold --release`, since
    it's a no-op (and a confusing red CI job) without the
    `RELEASE_KEYSTORE_BASE64`/`RELEASE_KEYSTORE_PASSWORD`/
    `RELEASE_KEY_ALIAS`/`RELEASE_KEY_PASSWORD` repo secrets already
    configured.
    """
    package_path = _package_path(package_id)
    java_dir = f"app/src/main/java/{package_path}"

    files: dict[str, str] = {
        "settings.gradle.kts": _settings_gradle_kts(app_name),
        "build.gradle.kts": _root_build_gradle_kts(),
        "gradle.properties": _GRADLE_PROPERTIES,
        "app/proguard-rules.pro": _PROGUARD_RULES,
        "app/build.gradle.kts": _app_build_gradle_kts(
            package_id, version_name, version_code, has_splash, has_debug_keystore
        ),
        "app/src/main/AndroidManifest.xml": _android_manifest_xml(orientation, has_splash),
        f"{java_dir}/MainActivity.kt": _main_activity_kt(package_id, edge_to_edge, has_splash),
        f"{java_dir}/ArkApplication.kt": _kt_with_package(_ARK_APPLICATION_KT, package_id),
        f"{java_dir}/ArkBundle.kt": _kt_with_package(_ARK_BUNDLE_KT, package_id),
        f"{java_dir}/ArkSeal.kt": _kt_with_package(_ARK_SEAL_KT, package_id),
        f"{java_dir}/MemoryGuard.kt": _kt_with_package(_MEMORY_GUARD_KT, package_id),
        "app/src/main/res/values/strings.xml": _strings_xml(app_name),
        "app/src/main/res/values/colors.xml": _COLORS_XML,
        "app/src/main/res/values-night/colors.xml": _COLORS_NIGHT_XML,
        "app/src/main/res/values/themes.xml": _themes_xml(has_splash),
        "app/src/main/res/values-night/themes.xml": _themes_night_xml(has_splash),
        ".github/workflows/android-build.yml": _github_ci_workflow_yml(
            app_name, package_id, include_release_job=include_release_job
        ),
        "README.md": _readme_md(app_name, package_id, has_debug_keystore),
    }

    if has_custom_icon:
        files["app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml"] = _CUSTOM_ADAPTIVE_ICON_XML
        files["app/src/main/res/drawable/ic_launcher_background.xml"] = _ic_launcher_background_xml()
    else:
        files["app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml"] = _DEFAULT_ADAPTIVE_ICON_XML
        files["app/src/main/res/drawable/ic_launcher_background.xml"] = _ic_launcher_background_xml()
        files["app/src/main/res/drawable/ic_launcher_foreground.xml"] = _IC_LAUNCHER_FOREGROUND_XML
        files["app/src/main/res/drawable/ic_launcher_monochrome.xml"] = _IC_LAUNCHER_MONOCHROME_XML

    return files


# ---------------------------------------------------------------------------
# Gradle / project files
# ---------------------------------------------------------------------------


def _settings_gradle_kts(app_name: str) -> str:
    # `rootProject.name` is a display label for Gradle/Android
    # Studio's own project tree, not the app's user-visible name
    # (that's `strings.xml`'s app_name) or its applicationId -- a
    # plain quoted string, escaped for embedded quotes/backslashes.
    escaped = app_name.replace("\\", "\\\\").replace('"', '\\"')
    return f'''\
pluginManagement {{
    repositories {{
        google()
        mavenCentral()
        gradlePluginPortal()
    }}
}}
dependencyResolutionManagement {{
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {{
        google()
        mavenCentral()
    }}
}}

rootProject.name = "{escaped}"
include(":app")
'''


def _root_build_gradle_kts() -> str:
    return f'''\
plugins {{
    id("com.android.application") version "{_AGP_VERSION}" apply false
    id("org.jetbrains.kotlin.android") version "{_KOTLIN_VERSION}" apply false
}}
'''


_GRADLE_PROPERTIES = """\
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
kotlin.code.style=official
"""

_PROGUARD_RULES = """\
# Add project specific ProGuard rules here.
# arklight android scaffold's default project has isMinifyEnabled =
# false, so this file only matters if you turn minification on
# yourself -- see https://developer.android.com/studio/build/shrink-code
"""


def _app_build_gradle_kts(
    package_id: str, version_name: str, version_code: int, has_splash: bool, has_debug_keystore: bool
) -> str:
    splash_dep = (
        '    implementation("androidx.core:core-splashscreen:1.0.1")\n' if has_splash else ""
    )
    debug_signing_config = (
        '        create("debug") {\n'
        '            storeFile = file("debug.keystore")\n'
        '            storePassword = "android"\n'
        '            keyAlias = "androiddebugkey"\n'
        '            keyPassword = "android"\n'
        '        }\n'
        if has_debug_keystore
        else ""
    )
    debug_build_type = (
        '        debug {\n'
        '            signingConfig = signingConfigs.getByName("debug")\n'
        '        }\n'
        if has_debug_keystore
        else ""
    )
    return f'''\
plugins {{
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}}

android {{
    namespace = "{package_id}"
    compileSdk = {_COMPILE_SDK}

    defaultConfig {{
        applicationId = "{package_id}"
        minSdk = {_MIN_SDK}
        targetSdk = {_TARGET_SDK}
        versionCode = {version_code}
        versionName = "{version_name}"
    }}

    // Signing configs. Release: keystore path/passwords are the
    // project owner's own concern, passed through via env vars --
    // ARKlight does not manage keystores/credentials on anyone's
    // behalf (see docs/Backends/ANDROID-BACKEND-IMPLEMENTATION.md,
    // Stage 7). Locally, with these unset, `./gradlew assembleRelease`
    // still works, it just produces an unsigned APK you'd sign
    // yourself. `isNullOrBlank()` (not just a null check) matters here
    // because a CI job driving this the same way would set it from a
    // GitHub Actions secret via an `env:` block -- when that secret
    // isn't configured, the expression evaluating it resolves to an
    // *empty string*, not an unset var, so a plain `!= null` check
    // would still (wrongly) try `file("")` and fail the build instead
    // of falling back to unsigned, same as the local no-env-vars-at-all
    // case does.
    //
    // Debug: with no --debug-keystore given at scaffold time, this
    // deliberately leaves Android Gradle Plugin's own implicit default
    // alone -- it auto-generates and reuses ~/.android/debug.keystore
    // (well-known androiddebugkey/android/android credentials) on
    // whatever machine runs `assembleDebug`. Fine for one dev iterating
    // on one machine, but a fresh CI runner has no such file either, so
    // it generates its *own* debug key on every single run -- a debug
    // APK built by CI won't share a signature with one built on your
    // machine (or with one from a different CI run), so reinstalling
    // one over the other on the same test device fails (`adb install
    // -r` errors out; you'd have to uninstall first). Re-run `arklight
    // android scaffold --debug-keystore <path>` to pin a shared debug
    // key -- it's copied in as app/debug.keystore (checked into git is
    // fine; debug keystores aren't meant to be secret) and every build,
    // this machine or CI, signs with it instead. See README.md.
    val releaseStorePath = System.getenv("RELEASE_KEYSTORE_PATH")
    signingConfigs {{
        if (!releaseStorePath.isNullOrBlank()) {{
            create("release") {{
                storeFile = file(releaseStorePath)
                storePassword = System.getenv("RELEASE_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("RELEASE_KEY_ALIAS")
                keyPassword = System.getenv("RELEASE_KEY_PASSWORD")
            }}
        }}
{debug_signing_config}    }}

    buildTypes {{
{debug_build_type}        release {{
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            if (!releaseStorePath.isNullOrBlank()) {{
                signingConfig = signingConfigs.getByName("release")
            }}
        }}
    }}

    compileOptions {{
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }}

    kotlinOptions {{
        jvmTarget = "17"
    }}

    buildFeatures {{
        viewBinding = false
    }}
}}

dependencies {{
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    // WebViewAssetLoader -- serves app/src/main/assets/ to the WebView
    // over {_ASSET_ORIGIN}/, so ARKlight's Stage 8
    // State(persist=True) -> localStorage stays reliable inside a
    // packaged app (see docs/Foundational/DESIGN-NOTES.md, "v0.0438:
    // Android backend", "Why this needs to exist at all").
    implementation("androidx.webkit:webkit:1.11.0")
{splash_dep}}}
'''


# ---------------------------------------------------------------------------
# CI (Stages 2, 3, and 4 of ANDROID-BACKEND-IMPLEMENTATION.md)
# ---------------------------------------------------------------------------


def _github_ci_workflow_yml(
    app_name: str, package_id: str, *, include_release_job: bool = False
) -> str:
    """
    A GitHub Actions workflow, entirely on GitHub-hosted runners -- so
    a scaffolded project gets automated debug build and install/launch
    verification without a JDK, Android SDK, or a physical/local
    emulator ever needing to exist on the *user's own* machine:

    - **`assemble-debug`** (Stage 2) -- builds a debug APK on every
      push/PR.
    - **`install-launch-smoke-test`** (Stage 3) -- downloads that APK,
      boots a throwaway emulator on the runner itself
      (`reactivecircus/android-emulator-runner`, the standard way to
      get a hardware-accelerated AVD on a GitHub-hosted Linux runner --
      KVM is available there, just not enabled by default, hence the
      udev-rule step ahead of it), installs the APK, starts
      `.MainActivity`, and fails the job if the process isn't still
      alive a few seconds later. Depends on Stage 2's APK, not a local
      one -- same "does this thing actually install and open without
      immediately crashing" question Stage 6 (the local-`adb install`
      equivalent) asks, just answered on a runner-hosted throwaway
      device instead.

    - **`assemble-release`** (Stage 4) -- opt-in, off by default; only
      generated when `include_release_job` is True (wired up to
      `arklight android scaffold --release`). An unsigned release APK
      isn't installable on a stock device, so shipping this job
      pre-wired unconditionally just means it silently produces an
      unsigned artifact for anyone who hasn't set up signing -- hence
      requiring the explicit flag rather than including it always.
      When included, it decodes the `RELEASE_KEYSTORE_BASE64` repo
      secret to a file on the runner and passes it plus
      `RELEASE_KEYSTORE_PASSWORD`/`RELEASE_KEY_ALIAS`/
      `RELEASE_KEY_PASSWORD` through as the same env vars
      `_app_build_gradle_kts`'s `signingConfigs` block already reads
      (`RELEASE_KEYSTORE_PATH` and friends) -- see that function's own
      "Signing configs" comment. Skipped on `pull_request` triggers
      (`if: github.event_name != 'pull_request'`) since a fork PR
      shouldn't be handed a path to a job that expects signing
      secrets, even though such secrets aren't exposed to fork PRs in
      the first place. See the generated README's "Building a release
      APK" section for the equivalent local `gradle assembleRelease`
      command and what the secrets need to contain.

    Uses `gradle` directly (not `./gradlew`) since this scaffold does
    not template the wrapper's binary jar -- `gradle/actions/setup-
    gradle` installs the pinned `_GRADLE_VERSION` itself, so no
    wrapper is needed either locally or here. Relies on the Android
    SDK GitHub's own `ubuntu-latest` runner image ships preinstalled
    (see https://github.com/actions/runner-images) rather than adding
    a third-party `setup-android` action for the debug/release build
    jobs -- one fewer dependency for a file meant to work unmodified
    the moment it's generated. The smoke-test job's emulator comes from
    `reactivecircus/android-emulator-runner`, which manages its own
    system-image install, so nothing extra is needed there either.
    """
    # Used only in the uploaded artifacts' display names -- purely
    # cosmetic, so it's slugified defensively rather than validated
    # the way `package_id`/`app_name` are elsewhere in this module.
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", app_name).strip("-") or "arklight-app"
    release_job = (
        f'''

  assemble-release:
    name: Assemble signed release APK
    runs-on: ubuntu-latest
    # Fork PRs don't get repo secrets anyway; skipped explicitly here
    # rather than relying on that so the job's absence from a PR run
    # is obvious in the Actions UI instead of showing up as a
    # mysterious signing failure.
    if: ${{{{ github.event_name != 'pull_request' }}}}
    steps:
      - name: Check out the project
        uses: actions/checkout@v4

      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: "17"

      - name: Set up Gradle
        uses: gradle/actions/setup-gradle@v4
        with:
          gradle-version: "{_GRADLE_VERSION}"

      - name: Decode release keystore
        env:
          RELEASE_KEYSTORE_BASE64: ${{{{ secrets.RELEASE_KEYSTORE_BASE64 }}}}
        run: |
          if [ -z "$RELEASE_KEYSTORE_BASE64" ]; then
            echo "::error::RELEASE_KEYSTORE_BASE64 repo secret is not set -- see this project's README (\\"Building a release APK\\") for how to generate and add it."
            exit 1
          fi
          echo "$RELEASE_KEYSTORE_BASE64" | base64 --decode > "$RUNNER_TEMP/release.keystore"

      - name: Assemble release APK
        env:
          RELEASE_KEYSTORE_PATH: ${{{{ runner.temp }}}}/release.keystore
          RELEASE_KEYSTORE_PASSWORD: ${{{{ secrets.RELEASE_KEYSTORE_PASSWORD }}}}
          RELEASE_KEY_ALIAS: ${{{{ secrets.RELEASE_KEY_ALIAS }}}}
          RELEASE_KEY_PASSWORD: ${{{{ secrets.RELEASE_KEY_PASSWORD }}}}
        run: gradle assembleRelease --no-daemon

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: {slug}-release-apk
          path: app/build/outputs/apk/release/*.apk
          if-no-files-found: error
'''
        if include_release_job
        else ""
    )
    release_note = (
        "Also includes an opt-in signed release-build job (assemble-release), "
        "generated because --release was passed to `arklight android scaffold`. "
        "It reads its signing key from repo secrets -- see this project's README."
        if include_release_job
        else "No release-build job here -- see this project's README (\"Building "
        "a release APK\") for that, since it needs a keystore only you should "
        "hold, or re-run `arklight android scaffold --release` once you've set "
        "up signing."
    )
    return f'''\
name: Android build

# Builds a debug APK on GitHub-hosted runners on every push/PR, then
# installs and launches it on a throwaway emulator on the same runner
# to confirm it doesn't crash immediately -- see
# ANDROID-BACKEND-IMPLEMENTATION.md, Stages 2 and 3. Requires no JDK,
# Android SDK, or emulator/device on your own machine for either job;
# all of it lives on the runner. {release_note}
on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:

jobs:
  assemble-debug:
    name: Assemble debug APK
    runs-on: ubuntu-latest
    steps:
      - name: Check out the project
        uses: actions/checkout@v4

      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: "17"

      - name: Set up Gradle
        uses: gradle/actions/setup-gradle@v4
        with:
          gradle-version: "{_GRADLE_VERSION}"

      - name: Assemble debug APK
        run: gradle assembleDebug --no-daemon

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: {slug}-debug-apk
          path: app/build/outputs/apk/debug/*.apk
          if-no-files-found: error

  install-launch-smoke-test:
    name: Install + launch on an emulator
    needs: assemble-debug
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - name: Download APK
        uses: actions/download-artifact@v4
        with:
          name: {slug}-debug-apk
          path: apk

      - name: Enable KVM (hardware-accelerated emulator)
        run: |
          echo 'KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"' | sudo tee /etc/udev/rules.d/99-kvm4all.rules
          sudo udevadm control --reload-rules
          sudo udevadm trigger --name-match=kvm

      - name: Install and launch on an emulator
        uses: reactivecircus/android-emulator-runner@v2
        with:
          api-level: {_TARGET_SDK}
          arch: x86_64
          force-avd-creation: false
          emulator-options: -no-window -gpu swiftshader_indirect -noaudio -no-boot-anim -camera-back none
          disable-animations: true
          script: |
            APK="$(find apk -name '*.apk' | head -n 1)"
            adb install -r "$APK"
            adb shell am start -n {package_id}/{package_id}.MainActivity
            sleep 5
            if ! adb shell pidof {package_id}; then
              echo "::error::App process not found a few seconds after launch -- it likely crashed on startup. See logcat below."
              adb logcat -d "*:E"
              exit 1
            fi
            echo "App launched and is still running -- smoke test passed."
{release_job}'''



# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def _android_manifest_xml(orientation: str, has_splash: bool) -> str:
    # Application mode: exactly one launcher activity, no bundle-open
    # intent filters (see ANDROID-BACKEND-IMPLEMENTATION.md's Stage-0
    # file table -- those stay Viewer-mode-only). `.MainActivity`'s
    # theme is the splash launch theme when a splash image was
    # configured (installSplashScreen() in MainActivity then hands
    # off to Theme.ArkApp itself), otherwise Theme.ArkApp directly.
    activity_theme = "@style/Theme.App.Starting" if has_splash else "@style/Theme.ArkApp"
    return f'''\
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <application
        android:name=".ArkApplication"
        android:allowBackup="true"
        android:label="@string/app_name"
        android:icon="@mipmap/ic_launcher"
        android:roundIcon="@mipmap/ic_launcher"
        android:theme="@style/Theme.ArkApp">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:screenOrientation="{orientation}"
            android:theme="{activity_theme}">

            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
'''


# ---------------------------------------------------------------------------
# Kotlin -- new for Application mode
# ---------------------------------------------------------------------------


def _main_activity_kt(package_id: str, edge_to_edge: bool, has_splash: bool) -> str:
    splash_import = (
        "\nimport androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen"
        if has_splash
        else ""
    )
    splash_install = "installSplashScreen()\n        " if has_splash else ""
    edge_to_edge_setup = (
        "WindowCompat.setDecorFitsSystemWindows(window, false)\n        "
        if edge_to_edge
        else ""
    )
    return f'''\
package {package_id}

import android.os.Bundle
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity{splash_import}
import androidx.core.view.WindowCompat
import androidx.webkit.WebViewAssetLoader

/**
 * Application-mode runtime shell, generated by `arklight android
 * scaffold` (see docs/Backends/ANDROID-BACKEND-IMPLEMENTATION.md,
 * Stage 1). Unlike ARKlight-Viewer-for-Android-Devices's own
 * MainActivity, this build has exactly one fixed site baked into
 * `assets/` at generation time -- no bundle picker, no menu, no
 * passphrase prompt. Every visible element that exists only because
 * that app used to be a browser for arbitrary `.ark` bundles is left
 * out here, per this milestone's "if a visible element exists solely
 * because the app used to be a browser for arbitrary bundles, it
 * doesn't belong in application mode" rule.
 *
 * Origin strategy carries over unchanged from the Viewer runtime this
 * evolved from: `androidx.webkit.WebViewAssetLoader` serves this
 * app's `assets/` folder under the same stable
 * `{_ASSET_ORIGIN}` origin a plain `file://`
 * load can't provide, which is what makes ARKlight's
 * `State(persist=True)` -> `localStorage` reliable here.
 *
 * `ArkBundle.kt`/`ArkSeal.kt`/`MemoryGuard.kt` ship alongside this
 * file (vendored unchanged from the Viewer app) but go unused by this
 * default, unpacked-tree code path -- see
 * ANDROID-BACKEND-IMPLEMENTATION.md's "Open questions for Stage 0",
 * "Packed .ark vs. unpacked tree": they're what a future sealed-
 * bundle Application-mode option would call into, without needing to
 * regenerate this project.
 */
class MainActivity : AppCompatActivity() {{

    private lateinit var webView: WebView

    override fun onCreate(savedInstanceState: Bundle?) {{
        {splash_install}super.onCreate(savedInstanceState)
        {edge_to_edge_setup}webView = WebView(this)
        setContentView(webView)

        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true

        val assetLoader = WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(this))
            .build()

        webView.webViewClient = object : WebViewClient() {{
            override fun shouldInterceptRequest(
                view: WebView,
                request: WebResourceRequest
            ): WebResourceResponse? = assetLoader.shouldInterceptRequest(request.url)
        }}

        webView.loadUrl(SITE_URL)
    }}

    @Suppress("DEPRECATION")
    override fun onBackPressed() {{
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }}

    companion object {{
        private const val SITE_URL = "{_ASSET_ORIGIN}/assets/index.html"
    }}
}}
'''


_ARK_APPLICATION_KT = """\
package com.arklight.viewer

import android.app.Application
import com.google.android.material.color.DynamicColors

/**
 * Enables Material You dynamic color (wallpaper-derived theming) on
 * Android 12+ (API 31+) devices, app-wide. Vendored from
 * ARKlight-Viewer-for-Android-Devices's `ArkViewerApplication.kt`,
 * renamed generically since Application mode has no "Viewer" in its
 * name -- see ANDROID-BACKEND-IMPLEMENTATION.md's Stage-0 open
 * question on this class: dynamic color is exactly the kind of thing
 * that "stays in the runtime both modes share" because Android itself
 * (not any Viewer-specific chrome) benefits from it.
 *
 * [DynamicColors.applyToActivitiesIfAvailable] is a no-op below API
 * 31, so this is safe across this app's full minSdk range -- devices
 * that can't do dynamic color just keep the branded fallback palette
 * defined in themes.xml / values-night/themes.xml.
 */
class ArkApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        DynamicColors.applyToActivitiesIfAvailable(this)
    }
}
"""


# ---------------------------------------------------------------------------
# Kotlin -- vendored unchanged (Apache-2.0, see module NOTICE above)
# ---------------------------------------------------------------------------

_ARK_BUNDLE_KT = """\
package com.arklight.viewer

import android.content.Context
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream

/**
 * Mirrors `arklight/packer/bundle.py`'s split point:
 *
 *     [ inlined entry page ][ sealed OR plain ZIP of the build dir ]
 *
 * The archive half starts immediately after the entry page's closing
 * `</html>\\n` -- exactly what ARKlight's HTML backend always emits, so
 * this works identically for sealed and plain bundles without needing
 * to search for the seal magic (plain bundles never have one).
 *
 * Vendored unchanged from ARKlight-Viewer-for-Android-Devices; unused
 * by this Application-mode project's default (unpacked-tree)
 * MainActivity.kt -- see that file's class doc.
 */
object ArkBundle {

    private val HTML_END_MARKER = "</html>\\n".toByteArray(Charsets.UTF_8)

    class FormatError(message: String) : Exception(message)

    data class Split(val entryHtml: String, val archiveBytes: ByteArray)

    fun split(data: ByteArray): Split {
        val idx = indexOf(data, HTML_END_MARKER)
        if (idx == -1) {
            throw FormatError("couldn't find the closing </html> boundary marker")
        }
        val end = idx + HTML_END_MARKER.size
        val entryHtml = String(data, 0, end, Charsets.UTF_8)
        val archiveBytes = data.copyOfRange(end, data.size)
        return Split(entryHtml, archiveBytes)
    }

    /**
     * Writes [entryHtml] to `entryDir/index.html`, clearing whatever
     * was there before -- fixed path, so a "quick view" entry page is
     * served from the same stable origin as the full site via
     * `WebViewAssetLoader`, instead of `loadDataWithBaseURL(null,
     * ...)`'s opaque origin.
     */
    fun writeEntryPage(entryHtml: String, entryDir: File) {
        entryDir.deleteRecursively()
        entryDir.mkdirs()
        File(entryDir, "index.html").writeText(entryHtml, Charsets.UTF_8)
    }

    /**
     * Where an extracted site's files currently live. [Ram] is the
     * preferred backing -- nothing touches disk, and [flush] just
     * drops the reference for GC. [Disk] is the fallback used when
     * [MemoryGuard] says RAM is too tight.
     */
    sealed class SiteBacking {
        data class Ram(val files: Map<String, ByteArray>) : SiteBacking()
        data class Disk(val dir: File) : SiteBacking()
    }

    sealed class ExtractResult {
        data class Success(val backing: SiteBacking) : ExtractResult()
        object NeedsPassphrase : ExtractResult()
        data class Failed(val reason: String) : ExtractResult()
    }

    /**
     * Unseals (if needed) and unzips the archive half, preferring to
     * hold the result entirely in RAM ([SiteBacking.Ram]) and only
     * falling back to writing it under [outDir] ([SiteBacking.Disk])
     * when [MemoryGuard] reports the device doesn't have comfortable
     * headroom for that.
     */
    fun unsealAndExtract(
        archiveBytes: ByteArray,
        outDir: File,
        passphrase: String?,
        context: Context
    ): ExtractResult {
        if (archiveBytes.isEmpty()) {
            return ExtractResult.Failed("no archive half present (entry-page-only bundle)")
        }

        val zipBytes: ByteArray = if (ArkSeal.isSealed(archiveBytes)) {
            try {
                ArkSeal.unseal(archiveBytes, passphrase)
            } catch (e: ArkSeal.NeedsPassphrase) {
                return ExtractResult.NeedsPassphrase
            } catch (e: ArkSeal.SealError) {
                return ExtractResult.Failed(e.message ?: "seal error")
            }
        } else {
            archiveBytes
        }

        // Uncompressed HTML/CSS/JS/JSON typically runs 3-5x the
        // compressed size; budget 6x so a bad guess only ever costs an
        // unnecessary disk write, never a memory squeeze -- the actual
        // safety margin is enforced inside MemoryGuard itself.
        val estimatedUncompressed = zipBytes.size.toLong() * 6

        return if (MemoryGuard.hasRamHeadroom(context, estimatedUncompressed)) {
            extractToMemory(zipBytes)
        } else {
            extractToDisk(zipBytes, outDir)
        }
    }

    /**
     * Releases whichever backing a site is currently using. RAM just
     * drops the reference for GC; disk is deleted outright.
     */
    fun flush(backing: SiteBacking?) {
        if (backing is SiteBacking.Disk) {
            backing.dir.deleteRecursively()
        }
    }

    private fun extractToMemory(zipBytes: ByteArray): ExtractResult {
        val files = mutableMapOf<String, ByteArray>()
        return try {
            ZipInputStream(zipBytes.inputStream()).use { zis ->
                var entry: ZipEntry? = zis.nextEntry
                while (entry != null) {
                    if (!entry.isDirectory) {
                        val name = entry.name
                        if (name.contains("..")) {
                            throw SecurityException("Unsafe zip entry path: $name")
                        }
                        files[name] = zis.readBytes()
                    }
                    zis.closeEntry()
                    entry = zis.nextEntry
                }
            }
            ExtractResult.Success(SiteBacking.Ram(files))
        } catch (e: Exception) {
            ExtractResult.Failed("bad zip once unsealed: ${e.message}")
        }
    }

    private fun extractToDisk(zipBytes: ByteArray, outDir: File): ExtractResult {
        outDir.deleteRecursively()
        outDir.mkdirs()

        return try {
            ZipInputStream(zipBytes.inputStream()).use { zis ->
                var entry: ZipEntry? = zis.nextEntry
                while (entry != null) {
                    val outFile = File(outDir, entry.name)
                    if (!outFile.canonicalPath.startsWith(outDir.canonicalPath + File.separator)) {
                        throw SecurityException("Unsafe zip entry path: ${entry.name}")
                    }
                    if (entry.isDirectory) {
                        outFile.mkdirs()
                    } else {
                        outFile.parentFile?.mkdirs()
                        FileOutputStream(outFile).use { fos -> zis.copyTo(fos) }
                    }
                    zis.closeEntry()
                    entry = zis.nextEntry
                }
            }
            ExtractResult.Success(SiteBacking.Disk(outDir))
        } catch (e: Exception) {
            outDir.deleteRecursively()
            ExtractResult.Failed("bad zip once unsealed: ${e.message}")
        }
    }

    private fun indexOf(data: ByteArray, pattern: ByteArray): Int {
        if (pattern.isEmpty() || data.size < pattern.size) return -1
        outer@ for (i in 0..data.size - pattern.size) {
            for (j in pattern.indices) {
                if (data[i + j] != pattern[j]) continue@outer
            }
            return i
        }
        return -1
    }
}
"""

_ARK_SEAL_KT = """\
package com.arklight.viewer

import java.security.spec.KeySpec
import javax.crypto.Mac
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec

/**
 * Kotlin port of ARKlight's `arklight/packer/seal.py`.
 *
 * Read-only: only `unseal()` is ported. Mirrors the Python
 * implementation field-for-field -- see that file's docstring for the
 * full rationale.
 *
 * Blob layout:
 *   MAGIC(8) || salt(16) || mode(1) || [iterations(4) | key(32)] || tag(32) || ciphertext(...)
 *
 * Vendored unchanged from ARKlight-Viewer-for-Android-Devices; unused
 * by this Application-mode project's default (unpacked-tree)
 * MainActivity.kt -- see that file's class doc.
 */
object ArkSeal {

    private val MAGIC = "ARKSEAL2".toByteArray(Charsets.US_ASCII)
    private val LEGACY_MAGIC = "ARKSEAL1".toByteArray(Charsets.US_ASCII)

    private const val SALT_LEN = 16
    private const val KEY_LEN = 32
    private const val TAG_LEN = 32
    private const val ITER_FIELD_LEN = 4
    private const val LEGACY_ITERATIONS = 200_000

    private const val MODE_PASSPHRASE = 0x00
    private const val MODE_EMBEDDED_KEY = 0x01

    class SealError(message: String) : Exception(message)
    class NeedsPassphrase : Exception("This bundle's archive half was sealed with a passphrase.")

    fun isSealed(blob: ByteArray): Boolean =
        startsWith(blob, MAGIC) || startsWith(blob, LEGACY_MAGIC)

    /** @throws NeedsPassphrase if `passphrase` is null but required. */
    fun unseal(blob: ByteArray, passphrase: String?): ByteArray {
        val legacy: Boolean = when {
            startsWith(blob, MAGIC) -> false
            startsWith(blob, LEGACY_MAGIC) -> true
            else -> throw SealError("Not a sealed ARKlight archive (missing ARKSEAL magic).")
        }

        var offset = MAGIC.size
        require(blob.size >= offset + SALT_LEN + 1) { }
        val salt = blob.copyOfRange(offset, offset + SALT_LEN)
        offset += SALT_LEN

        if (offset >= blob.size) throw SealError("Sealed archive is truncated.")
        val mode = blob[offset].toInt() and 0xFF
        offset += 1

        val key: ByteArray
        when (mode) {
            MODE_EMBEDDED_KEY -> {
                key = blob.copyOfRange(offset, offset + KEY_LEN)
                offset += KEY_LEN
            }
            MODE_PASSPHRASE -> {
                if (passphrase == null) throw NeedsPassphrase()
                val iterations = if (legacy) {
                    LEGACY_ITERATIONS
                } else {
                    val field = blob.copyOfRange(offset, offset + ITER_FIELD_LEN)
                    offset += ITER_FIELD_LEN
                    beUInt32(field)
                }
                key = deriveKey(passphrase, salt, iterations)
            }
            else -> throw SealError("Unrecognized seal mode byte: $mode")
        }

        val tag = blob.copyOfRange(offset, offset + TAG_LEN)
        offset += TAG_LEN
        val ciphertext = blob.copyOfRange(offset, blob.size)

        val expectedTag = hmacSha256(key, salt + ciphertext)
        if (!constantTimeEquals(tag, expectedTag)) {
            throw SealError(
                "Integrity check failed -- wrong passphrase, or the bundle's " +
                    "archive half was corrupted or tampered with."
            )
        }

        return xor(ciphertext, keystream(key, salt, ciphertext.size))
    }

    private fun deriveKey(passphrase: String, salt: ByteArray, iterations: Int): ByteArray {
        val factory = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
        val spec: KeySpec = PBEKeySpec(passphrase.toCharArray(), salt, iterations, KEY_LEN * 8)
        return factory.generateSecret(spec).encoded
    }

    private fun keystream(key: ByteArray, salt: ByteArray, length: Int): ByteArray {
        val out = ByteArray(length)
        var produced = 0
        var counter = 0
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        while (produced < length) {
            mac.reset()
            mac.update(salt)
            mac.update(beBytes(counter))
            val block = mac.doFinal()
            val take = minOf(block.size, length - produced)
            System.arraycopy(block, 0, out, produced, take)
            produced += take
            counter += 1
        }
        return out
    }

    private fun hmacSha256(key: ByteArray, data: ByteArray): ByteArray {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        return mac.doFinal(data)
    }

    private fun xor(a: ByteArray, b: ByteArray): ByteArray {
        val out = ByteArray(a.size)
        for (i in a.indices) out[i] = (a[i].toInt() xor b[i].toInt()).toByte()
        return out
    }

    private fun beBytes(counter: Int): ByteArray = byteArrayOf(
        (counter ushr 24).toByte(),
        (counter ushr 16).toByte(),
        (counter ushr 8).toByte(),
        counter.toByte()
    )

    private fun beUInt32(b: ByteArray): Int =
        ((b[0].toInt() and 0xFF) shl 24) or
            ((b[1].toInt() and 0xFF) shl 16) or
            ((b[2].toInt() and 0xFF) shl 8) or
            (b[3].toInt() and 0xFF)

    private fun constantTimeEquals(a: ByteArray, b: ByteArray): Boolean {
        if (a.size != b.size) return false
        var result = 0
        for (i in a.indices) result = result or (a[i].toInt() xor b[i].toInt())
        return result == 0
    }

    private fun startsWith(data: ByteArray, prefix: ByteArray): Boolean {
        if (data.size < prefix.size) return false
        for (i in prefix.indices) if (data[i] != prefix[i]) return false
        return true
    }
}
"""

_MEMORY_GUARD_KT = """\
package com.arklight.viewer

import android.app.ActivityManager
import android.content.Context

/**
 * Decides whether it's safe to hold an extracted site's files in RAM
 * instead of writing them to disk. Conservative by design: any
 * uncertainty resolves to "no" (disk), since the cost of guessing
 * wrong on RAM is a possible low-memory kill, while the cost of
 * guessing wrong on disk is just a slower, disk-backed WebView load.
 *
 * Vendored unchanged from ARKlight-Viewer-for-Android-Devices; unused
 * by this Application-mode project's default (unpacked-tree)
 * MainActivity.kt -- see that file's class doc.
 */
object MemoryGuard {

    /** Extra headroom kept above the system's own low-memory threshold. */
    private const val SAFETY_MARGIN_BYTES = 32L * 1024 * 1024 // 32MB

    /**
     * True if the device currently has enough free RAM to comfortably
     * absorb [requiredBytes] more resident data without approaching
     * the point where Android would start killing background
     * processes for memory.
     */
    fun hasRamHeadroom(context: Context, requiredBytes: Long): Boolean {
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
            ?: return false

        val info = ActivityManager.MemoryInfo()
        am.getMemoryInfo(info)

        if (info.lowMemory) return false

        val freeAboveThreshold = info.availMem - info.threshold - SAFETY_MARGIN_BYTES
        return freeAboveThreshold > requiredBytes
    }
}
"""


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


def _strings_xml(app_name: str) -> str:
    return f'''\
<resources>
    <string name="app_name">{xml_escape(app_name)}</string>
</resources>
'''


_COLORS_XML = """\
<resources>
    <!-- Brand marks: used only in the launcher icon drawables, not as
         theme color roles; the icon should look the same regardless
         of light/dark/dynamic theme. Vendored from
         ARKlight-Viewer-for-Android-Devices's default branding;
         replace freely once you have your own launcher icon (see
         android.icon in arklight.config.py). -->
    <color name="brand_gradient_start">#5FE0B5</color>
    <color name="brand_gradient_end">#3D6EFF</color>

    <!-- Fallback (non-dynamic) Material 3 color roles; used on
         devices below Android 12, or when the system hasn't handed
         out a wallpaper-derived palette. -->
    <color name="md_theme_primary">#146356</color>
    <color name="md_theme_onPrimary">#FFFFFF</color>
    <color name="md_theme_primaryContainer">#B7F0DD</color>
    <color name="md_theme_onPrimaryContainer">#002016</color>
    <color name="md_theme_secondary">#3D5AFE</color>
    <color name="md_theme_onSecondary">#FFFFFF</color>
    <color name="md_theme_background">#FBFDFA</color>
    <color name="md_theme_onBackground">#191C1A</color>
    <color name="md_theme_surface">#FBFDFA</color>
    <color name="md_theme_onSurface">#191C1A</color>
    <color name="md_theme_surfaceVariant">#DBE5DF</color>
    <color name="md_theme_onSurfaceVariant">#3F4944</color>
    <color name="md_theme_outline">#6F7975</color>

    <!-- Legacy alias kept for the adaptive-icon background reference
         in mipmap-anydpi-v26/ic_launcher.xml; some older launchers
         fall back to a flat background color. -->
    <color name="ic_launcher_background">#0F2A24</color>
</resources>
"""

_COLORS_NIGHT_XML = """\
<resources>
    <!-- Dark-mode mirror of values/colors.xml's Material 3 color
         roles. -->
    <color name="md_theme_primary">#7FD9C3</color>
    <color name="md_theme_onPrimary">#00382C</color>
    <color name="md_theme_primaryContainer">#00513F</color>
    <color name="md_theme_onPrimaryContainer">#B7F0DD</color>
    <color name="md_theme_secondary">#B9C3FF</color>
    <color name="md_theme_onSecondary">#152686</color>
    <color name="md_theme_background">#191C1A</color>
    <color name="md_theme_onBackground">#E1E3DF</color>
    <color name="md_theme_surface">#191C1A</color>
    <color name="md_theme_onSurface">#E1E3DF</color>
    <color name="md_theme_surfaceVariant">#3F4944</color>
    <color name="md_theme_onSurfaceVariant">#BFC9C3</color>
    <color name="md_theme_outline">#89938E</color>
</resources>
"""


def _themes_xml(has_splash: bool) -> str:
    splash_theme = _SPLASH_STARTING_THEME_LIGHT if has_splash else ""
    return f'''\
<resources xmlns:tools="http://schemas.android.com/tools">
    <!--
      Material 3, DayNight-aware, with Material You dynamic color
      wired up via ArkApplication (DynamicColors.
      applyToActivitiesIfAvailable). On Android 12+ this gets
      overridden at runtime with a wallpaper-derived palette;
      everywhere else it falls back to the branded roles below.

      NoActionBar because Application mode's WebView fills the entire
      window (see MainActivity.kt); there is no toolbar/chrome.
    -->
    <style name="Theme.ArkApp" parent="Theme.Material3.DayNight.NoActionBar">
        <item name="colorPrimary">@color/md_theme_primary</item>
        <item name="colorOnPrimary">@color/md_theme_onPrimary</item>
        <item name="colorPrimaryContainer">@color/md_theme_primaryContainer</item>
        <item name="colorOnPrimaryContainer">@color/md_theme_onPrimaryContainer</item>
        <item name="colorSecondary">@color/md_theme_secondary</item>
        <item name="colorOnSecondary">@color/md_theme_onSecondary</item>
        <item name="android:colorBackground">@color/md_theme_background</item>
        <item name="colorOnBackground">@color/md_theme_onBackground</item>
        <item name="colorSurface">@color/md_theme_surface</item>
        <item name="colorOnSurface">@color/md_theme_onSurface</item>
        <item name="colorSurfaceVariant">@color/md_theme_surfaceVariant</item>
        <item name="colorOnSurfaceVariant">@color/md_theme_onSurfaceVariant</item>
        <item name="colorOutline">@color/md_theme_outline</item>

        <item name="android:statusBarColor" tools:targetApi="21">@android:color/transparent</item>
        <item name="android:windowLightStatusBar" tools:targetApi="23">true</item>
        <item name="android:navigationBarColor" tools:targetApi="27">?attr/colorSurface</item>
        <item name="android:windowLightNavigationBar" tools:targetApi="27">true</item>
    </style>
{splash_theme}</resources>
'''


def _themes_night_xml(has_splash: bool) -> str:
    splash_theme = _SPLASH_STARTING_THEME_DARK if has_splash else ""
    return f'''\
<resources xmlns:tools="http://schemas.android.com/tools">
    <!-- Dark-mode mirror of values/themes.xml. -->
    <style name="Theme.ArkApp" parent="Theme.Material3.DayNight.NoActionBar">
        <item name="colorPrimary">@color/md_theme_primary</item>
        <item name="colorOnPrimary">@color/md_theme_onPrimary</item>
        <item name="colorPrimaryContainer">@color/md_theme_primaryContainer</item>
        <item name="colorOnPrimaryContainer">@color/md_theme_onPrimaryContainer</item>
        <item name="colorSecondary">@color/md_theme_secondary</item>
        <item name="colorOnSecondary">@color/md_theme_onSecondary</item>
        <item name="android:colorBackground">@color/md_theme_background</item>
        <item name="colorOnBackground">@color/md_theme_onBackground</item>
        <item name="colorSurface">@color/md_theme_surface</item>
        <item name="colorOnSurface">@color/md_theme_onSurface</item>
        <item name="colorSurfaceVariant">@color/md_theme_surfaceVariant</item>
        <item name="colorOnSurfaceVariant">@color/md_theme_onSurfaceVariant</item>
        <item name="colorOutline">@color/md_theme_outline</item>

        <item name="android:statusBarColor" tools:targetApi="21">@android:color/transparent</item>
        <item name="android:windowLightStatusBar" tools:targetApi="23">false</item>
        <item name="android:navigationBarColor" tools:targetApi="27">?attr/colorSurface</item>
        <item name="android:windowLightNavigationBar" tools:targetApi="27">false</item>
    </style>
{splash_theme}</resources>
'''


# `Theme.App.Starting` -- the manifest-declared launch theme
# `installSplashScreen()` reads (per androidx.core.splashscreen's own
# contract: a `postSplashScreenTheme` pointing back at the app's real
# theme, applied automatically once the splash screen dismisses).
# `windowSplashScreenAnimatedIcon` points at the raw `splash` image
# `arklight.cli.android` copies into `res/drawable/splash_image.*` --
# a static image is a legal (if non-animated) value for that attribute.
_SPLASH_STARTING_THEME_LIGHT = """\
    <style name="Theme.App.Starting" parent="Theme.SplashScreen">
        <item name="windowSplashScreenBackground">@color/md_theme_background</item>
        <item name="windowSplashScreenAnimatedIcon">@drawable/splash_image</item>
        <item name="postSplashScreenTheme">@style/Theme.ArkApp</item>
    </style>
"""

_SPLASH_STARTING_THEME_DARK = """\
    <style name="Theme.App.Starting" parent="Theme.SplashScreen">
        <item name="windowSplashScreenBackground">@color/md_theme_background</item>
        <item name="windowSplashScreenAnimatedIcon">@drawable/splash_image</item>
        <item name="postSplashScreenTheme">@style/Theme.ArkApp</item>
    </style>
"""


def _ic_launcher_background_xml() -> str:
    return """\
<?xml version="1.0" encoding="utf-8"?>
<!-- Adaptive icon background: a deep diagonal teal-to-indigo gradient.
     Vendored from ARKlight-Viewer-for-Android-Devices's default
     branding. -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:aapt="http://schemas.android.com/aapt"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path android:pathData="M0,0h108v108h-108z">
        <aapt:attr name="android:fillColor">
            <gradient
                android:type="linear"
                android:startX="0"
                android:startY="0"
                android:endX="108"
                android:endY="108"
                android:startColor="#0B3A30"
                android:endColor="#0B1E4A" />
        </aapt:attr>
    </path>
</vector>
"""


_IC_LAUNCHER_FOREGROUND_XML = """\
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:aapt="http://schemas.android.com/aapt"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path android:pathData="M54,24 L78,78 L66,78 L61,66 L47,66 L42,78 L30,78 Z M54,42 L47.5,58 L60.5,58 Z">
        <aapt:attr name="android:fillColor">
            <gradient
                android:type="linear"
                android:startX="30"
                android:startY="78"
                android:endX="78"
                android:endY="24"
                android:startColor="@color/brand_gradient_start"
                android:endColor="@color/brand_gradient_end" />
        </aapt:attr>
    </path>
</vector>
"""

_IC_LAUNCHER_MONOCHROME_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<!-- Single-tone mark for Android 13+ themed icons; the system
     recolors this to match the user's wallpaper/theme, so it must be
     flat, not gradient. -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path
        android:fillColor="#FFFFFF"
        android:pathData="M54,24 L78,78 L66,78 L61,66 L47,66 L42,78 L30,78 Z M54,42 L47.5,58 L60.5,58 Z" />
</vector>
"""

_DEFAULT_ADAPTIVE_ICON_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/ic_launcher_background" />
    <foreground android:drawable="@drawable/ic_launcher_foreground" />
    <!-- android:monochrome is API 33+; older parsers ignore unknown
         adaptive-icon children, so this is safe down to minSdk 24. -->
    <monochrome android:drawable="@drawable/ic_launcher_monochrome" />
</adaptive-icon>
"""

# A custom `android.icon` is copied in by `arklight.cli.android` as a
# raw, un-resized bitmap (`res/drawable/ic_launcher_custom.*`) and used
# directly as the adaptive icon's foreground layer. This is a
# deliberately simple v1: proper per-density legacy-icon rasterization
# (mdpi..xxxhdpi PNGs for API < 26, safe-zone-aware cropping) is
# follow-up work, not something this stage silently gets wrong by
# pretending to do -- see this project's own README.md for the note.
_CUSTOM_ADAPTIVE_ICON_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/ic_launcher_background" />
    <foreground android:drawable="@drawable/ic_launcher_custom" />
</adaptive-icon>
"""


def _readme_md(app_name: str, package_id: str, has_debug_keystore: bool) -> str:
    debug_signing_note = (
        "This project has a pinned debug signing key (`app/debug.keystore`, "
        "checked in) -- every build of it, on any machine or CI, produces a "
        "debug APK with the same signature, so you can reinstall an updated "
        "build over an existing test install on the same device without "
        "uninstalling first."
        if has_debug_keystore
        else (
            "This project has **no pinned debug signing key** -- debug builds "
            "fall back to Android Gradle Plugin's own default, which "
            "auto-generates `~/.android/debug.keystore` on whatever machine "
            "runs the build. That's fine for iterating locally on one "
            "machine, but a fresh CI runner has no such file either, so it "
            "generates its own on every run -- a debug APK from CI won't "
            "share a signature with one from your machine (or from a "
            "different CI run), so reinstalling one over the other on the "
            "same test device fails with a signature mismatch; you'd have "
            "to uninstall first. To fix this, generate a shared debug "
            "keystore once:\n\n"
            "```\n"
            "keytool -genkeypair -v -keystore debug.keystore -storepass android "
            "-alias androiddebugkey -keypass android -keyalg RSA -keysize 2048 "
            "-validity 10000 -dname \"CN=Android Debug,O=Android,C=US\"\n"
            "```\n\n"
            "and re-run `arklight android scaffold --debug-keystore "
            "path/to/debug.keystore ...`. Keep using the same "
            "`debug.keystore` file across scaffolds (and check it into git --"
            " debug keystores aren't meant to be secret, that's what makes "
            "this safe) if you want CI-built and locally-built debug APKs to "
            "interoperate."
        )
    )
    debug_keystore_bullet = (
        "- `app/debug.keystore` -- the pinned debug signing key (see "
        '"Debug signing" above). Safe to check into git.\n'
        if has_debug_keystore
        else ""
    )
    return f'''\
# {app_name}

Generated by `arklight android scaffold` -- see
[ANDROID-BACKEND-IMPLEMENTATION.md](
https://github.com/Rae-ARK/ARKlight/blob/alpha/docs/Backends/ANDROID-BACKEND-IMPLEMENTATION.md)
(Stage 1). This is a normal Android Studio / Gradle project, not
something ARKlight expects you to hand-edit blindly -- open it in
Android Studio, or build it from the command line once you have a JDK:

```
./gradlew assembleDebug
```

(`arklight android build` -- Stage 5 of the design doc above -- runs
that same command for you and handles a missing-JDK error gracefully;
not yet implemented as of this scaffold's version.)

## Debug signing

{debug_signing_note}

## Building without a local JDK

This project includes `.github/workflows/android-build.yml` (Stages
2 and 3 of the design doc above) -- push it to GitHub, or open a pull
request against it, and it: builds a debug APK on GitHub's own runners
and attaches it to the workflow run as a downloadable artifact, then
installs and launches that APK on a throwaway emulator on that same
runner to confirm it doesn't crash immediately on startup. Nothing to
configure for either job; no JDK, Android SDK, or emulator/device
needed on your own machine.

**Note:** this workflow only fires on GitHub if `.github/workflows/`
sits at the *root* of the git repository. If you're dropping this
scaffolded project in as a subdirectory of a larger repo (rather than
pushing it as its own repo), move `.github/workflows/android-build.yml`
up to that repo's root, or GitHub will never see it.

There is deliberately no release-build job here -- see "Building a
release APK" below.

## Building a release APK

This scaffold doesn't wire up a CI release job, on purpose: an
unsigned release APK isn't installable on a stock device, and a signed
one needs a keystore only you should generate and hold -- not
something this tool can safely provision for you. When you're ready:

```
gradle assembleRelease
```

runs unsigned by default. To sign it, add a `signingConfigs` block to
`app/build.gradle.kts` pointing at your own keystore (see
https://developer.android.com/studio/publish/app-signing for how to
generate one), or wire the same build into your own CI with your
keystore stored as a repo secret -- this project's earlier scaffold
revisions shipped exactly that as a `RELEASE_KEYSTORE_BASE64`/
`RELEASE_KEYSTORE_PASSWORD`/`RELEASE_KEY_ALIAS`/`RELEASE_KEY_PASSWORD`
secret-driven job, which you're welcome to recreate by hand if you
want it back.

## What's here

- `app/src/main/assets/` -- your `arklight build` output, copied in
  as-is at scaffold time. Re-run `arklight android scaffold` (into a
  fresh `-o` directory, or after clearing this one) after any site
  change; nothing here watches your build directory for edits.
{debug_keystore_bullet}- `app/src/main/java/{package_id.replace(".", "/")}/MainActivity.kt`
  -- the whole app: a `WebView` pointed at the assets above via
  `androidx.webkit.WebViewAssetLoader`, so `fetch()`/`localStorage`
  behave the same way they would if `arklight build`'s output were
  served over plain HTTP, not `file://`.
- `ArkBundle.kt` / `ArkSeal.kt` / `MemoryGuard.kt` -- vendored from
  [ARKlight-Viewer-for-Android-Devices](
  https://github.com/Rae-ARK/ARKlight-Viewer-for-Android-Devices)
  (Apache-2.0). Unused by the default unpacked-tree setup above; kept
  in case you want to swap in a sealed `.ark` bundle by hand later.
- `.github/workflows/android-build.yml` -- builds a debug APK and
  smoke-tests it (install + launch), on GitHub-hosted runners on every
  push/PR (see "Building without a local JDK" above). Only picked up
  by GitHub if it lives at your repo's root -- see the note in that
  section if this project is nested inside a larger repo. Edit or
  delete it freely; it's a normal, hand-editable workflow file, not
  something ARKlight regenerates in place.

## Custom launcher icon

If `arklight.config.py`'s `android.icon` was set, the raw image you
pointed it at was copied in unresized as the adaptive icon's
foreground layer (`res/drawable/ic_launcher_custom.*`) -- this scaffold
does not crop it to the adaptive-icon safe zone or generate legacy
(pre-API-26) mipmap densities. For a production-quality icon, run it
through Android Studio's Image Asset Studio (right-click `res` ->
New -> Image Asset) once, which handles both of those properly.
'''
