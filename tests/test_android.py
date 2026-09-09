from pathlib import Path

import pytest

from arklight.cli.android import AndroidError, scaffold_project
from arklight.cli.main import main
from arklight.compiler.pipeline import build

SIMPLE_SITE = """
from arklight import *
site = Site()

@site.page("/")
def home():
    return Page(Heading("Hi"), Text("Hello from ARKlight."))

@site.page("/about")
def about():
    return Page(Heading("About"))
"""

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def write_site(tmp_path: Path) -> Path:
    path = tmp_path / "site.py"
    path.write_text(SIMPLE_SITE)
    return path


def build_dir(tmp_path: Path) -> Path:
    site_path = write_site(tmp_path)
    out_dir = tmp_path / "ARK"
    build(site_path, out_dir)
    return out_dir


def write_config(tmp_path: Path, android_section: str) -> None:
    (tmp_path / "arklight.config.py").write_text(
        f"CONFIG = {{\n    \"android\": {android_section},\n}}\n"
    )


# --------------------------------------------------------------------
# Defaults (no arklight.config.py at all)
# --------------------------------------------------------------------


def test_scaffold_with_no_config_uses_defaults(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"

    result = scaffold_project(out_dir, output_dir=project_dir)

    assert result.project_dir == project_dir
    assert result.app_name == "ARKlight App"
    assert result.package_id == "com.arklight.app"

    java_dir = project_dir / "app/src/main/java/com/arklight/app"
    assert (java_dir / "MainActivity.kt").exists()
    assert (java_dir / "ArkApplication.kt").exists()
    assert (java_dir / "ArkBundle.kt").exists()
    assert (java_dir / "ArkSeal.kt").exists()
    assert (java_dir / "MemoryGuard.kt").exists()
    assert (project_dir / "app/src/main/AndroidManifest.xml").exists()
    assert (project_dir / "settings.gradle.kts").exists()
    assert (project_dir / "app/build.gradle.kts").exists()


def test_scaffold_default_manifest_has_portrait_orientation(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"

    scaffold_project(out_dir, output_dir=project_dir)

    manifest = (project_dir / "app/src/main/AndroidManifest.xml").read_text()
    assert 'android:screenOrientation="portrait"' in manifest


def test_scaffold_copies_build_dir_into_assets(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"

    scaffold_project(out_dir, output_dir=project_dir)

    assets_dir = project_dir / "app/src/main/assets"
    assert (assets_dir / "index.html").read_text() == (out_dir / "index.html").read_text()
    assert (assets_dir / "about.html").exists()
    assert (assets_dir / "styles.css").exists()
    assert (assets_dir / "arklight.js").exists()


def test_scaffold_no_icon_no_splash_omits_custom_drawables(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"

    scaffold_project(out_dir, output_dir=project_dir)

    drawable_dir = project_dir / "app/src/main/res/drawable"
    assert not any(drawable_dir.glob("ic_launcher_custom.*"))
    assert not any(drawable_dir.glob("splash_image.*"))
    # Default (non-custom) adaptive icon layers still get written.
    assert (drawable_dir / "ic_launcher_foreground.xml").exists()
    assert (drawable_dir / "ic_launcher_monochrome.xml").exists()


# --------------------------------------------------------------------
# CI (Stages 2-4: GitHub Actions workflow)
# --------------------------------------------------------------------


def test_scaffold_generates_github_actions_workflow(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"

    scaffold_project(out_dir, output_dir=project_dir)

    workflow = project_dir / ".github/workflows/android-build.yml"
    assert workflow.exists()
    contents = workflow.read_text()
    assert "actions/checkout@v4" in contents
    assert "actions/setup-java@v4" in contents
    assert 'java-version: "17"' in contents
    assert "gradle/actions/setup-gradle@v4" in contents
    assert "gradle assembleDebug" in contents
    assert "actions/upload-artifact@v4" in contents
    # No `./gradlew` -- this scaffold doesn't template the wrapper's
    # binary jar, so CI (like a local build) has to use a `gradle`
    # installed by the setup-gradle action instead.
    assert "gradlew" not in contents


def test_scaffold_github_actions_workflow_slugifies_app_name_for_artifact(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"
    write_config(tmp_path, '{"app_name": "My Cool App!"}')

    scaffold_project(out_dir, output_dir=project_dir)

    contents = (project_dir / ".github/workflows/android-build.yml").read_text()
    assert "name: My-Cool-App-debug-apk" in contents


def test_scaffold_github_actions_workflow_includes_install_launch_smoke_test(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"

    scaffold_project(out_dir, output_dir=project_dir)

    contents = (project_dir / ".github/workflows/android-build.yml").read_text()
    assert "install-launch-smoke-test" in contents
    assert "needs: assemble-debug" in contents
    assert "actions/download-artifact@v4" in contents
    assert "reactivecircus/android-emulator-runner@v2" in contents
    assert "adb install" in contents
    assert "am start -n com.arklight.app/com.arklight.app.MainActivity" in contents
    assert "adb shell pidof com.arklight.app" in contents


def test_scaffold_github_actions_workflow_smoke_test_uses_configured_package_id(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"
    write_config(tmp_path, '{"package_id": "com.example.cool"}')

    scaffold_project(out_dir, output_dir=project_dir)

    contents = (project_dir / ".github/workflows/android-build.yml").read_text()
    assert "am start -n com.example.cool/com.example.cool.MainActivity" in contents
    assert "adb shell pidof com.example.cool" in contents


def test_scaffold_github_actions_workflow_has_no_release_job(tmp_path):
    # Release builds need a keystore this tool has no business
    # provisioning -- deliberately not included; see the generated
    # README's "Building a release APK" section instead.
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"

    scaffold_project(out_dir, output_dir=project_dir)

    contents = (project_dir / ".github/workflows/android-build.yml").read_text()
    assert "assemble-release" not in contents
    assert "assembleRelease" not in contents
    assert "RELEASE_KEYSTORE" not in contents


def test_readme_documents_manual_release_build(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"

    scaffold_project(out_dir, output_dir=project_dir)

    contents = (project_dir / "README.md").read_text()
    assert "Building a release APK" in contents
    assert "gradle assembleRelease" in contents


def test_scaffold_result_has_no_enclosing_git_root_when_project_dir_is_standalone(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"

    result = scaffold_project(out_dir, output_dir=project_dir)

    assert result.enclosing_git_root is None


def test_scaffold_result_flags_enclosing_git_root(tmp_path):
    # Scaffolding into a subdirectory of a repo the caller already has
    # checked out -- `.github/workflows/` won't be discovered by GitHub
    # unless it's moved up to the repo root, so this should be surfaced.
    (tmp_path / ".git").mkdir()
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android"

    result = scaffold_project(out_dir, output_dir=project_dir)

    assert result.enclosing_git_root == tmp_path.resolve()


def test_scaffold_result_no_warning_when_git_init_happens_after_scaffolding(tmp_path):
    # The realistic "project_dir is its own repo root" flow: scaffold
    # first (output_dir has to be empty/absent, so it can't already
    # contain a `.git` at scaffold time -- see the non-empty-output_dir
    # check above), `git init` after. Detection runs at scaffold time,
    # before that `.git` exists, and should stay quiet either way since
    # there's no *enclosing* repo above `project_dir` here.
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"

    result = scaffold_project(out_dir, output_dir=project_dir)

    assert result.enclosing_git_root is None


def test_cli_warns_when_project_dir_nested_in_existing_repo(tmp_path, capsys):
    (tmp_path / ".git").mkdir()
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android"

    exit_code = main(["android", "scaffold", str(out_dir), "-o", str(project_dir)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "NOTE:" in out
    assert str(project_dir / ".github/workflows/android-build.yml") in out
    assert str(tmp_path.resolve() / ".github/workflows/android-build.yml") in out


def test_app_build_gradle_falls_back_to_unsigned_when_keystore_path_blank(tmp_path):
    # RELEASE_KEYSTORE_PATH coming from an unset GitHub Actions secret
    # resolves to an *empty string*, not an absent env var -- the
    # signing-config check has to treat that the same as "no signing
    # configured" rather than trying (and failing) to open `file("")`.
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"

    scaffold_project(out_dir, output_dir=project_dir)

    contents = (project_dir / "app/build.gradle.kts").read_text()
    assert "releaseStorePath.isNullOrBlank()" in contents
    assert "releaseStorePath != null" not in contents


# --------------------------------------------------------------------
# Config-driven identity
# --------------------------------------------------------------------


def test_scaffold_reads_app_identity_from_config(tmp_path):
    out_dir = build_dir(tmp_path)
    write_config(
        tmp_path,
        '{"app_name": "ARKfolio", "package_id": "com.example.arkfolio", '
        '"version_name": "1.2.0", "version_code": 7}',
    )
    project_dir = tmp_path / "android-project"

    result = scaffold_project(out_dir, output_dir=project_dir)

    assert result.app_name == "ARKfolio"
    assert result.package_id == "com.example.arkfolio"

    java_dir = project_dir / "app/src/main/java/com/example/arkfolio"
    assert (java_dir / "MainActivity.kt").exists()
    main_activity = (java_dir / "MainActivity.kt").read_text()
    assert main_activity.startswith("package com.example.arkfolio")

    strings_xml = (project_dir / "app/src/main/res/values/strings.xml").read_text()
    assert "ARKfolio" in strings_xml

    build_gradle = (project_dir / "app/build.gradle.kts").read_text()
    assert 'versionName = "1.2.0"' in build_gradle
    assert "versionCode = 7" in build_gradle


def test_scaffold_sensor_orientation_maps_to_fullsensor(tmp_path):
    out_dir = build_dir(tmp_path)
    write_config(tmp_path, '{"orientation": "sensor"}')
    project_dir = tmp_path / "android-project"

    scaffold_project(out_dir, output_dir=project_dir)

    manifest = (project_dir / "app/src/main/AndroidManifest.xml").read_text()
    assert 'android:screenOrientation="fullSensor"' in manifest


def test_scaffold_landscape_orientation_passes_through(tmp_path):
    out_dir = build_dir(tmp_path)
    write_config(tmp_path, '{"orientation": "landscape"}')
    project_dir = tmp_path / "android-project"

    scaffold_project(out_dir, output_dir=project_dir)

    manifest = (project_dir / "app/src/main/AndroidManifest.xml").read_text()
    assert 'android:screenOrientation="landscape"' in manifest


def test_scaffold_edge_to_edge_wires_window_compat(tmp_path):
    out_dir = build_dir(tmp_path)
    write_config(tmp_path, '{"edge_to_edge": True}')
    project_dir = tmp_path / "android-project"

    scaffold_project(out_dir, output_dir=project_dir)

    main_activity = (
        project_dir / "app/src/main/java/com/arklight/app/MainActivity.kt"
    ).read_text()
    assert "WindowCompat.setDecorFitsSystemWindows(window, false)" in main_activity


# --------------------------------------------------------------------
# Icon / splash
# --------------------------------------------------------------------


def test_scaffold_copies_custom_icon(tmp_path):
    out_dir = build_dir(tmp_path)
    (out_dir / "icon.png").write_bytes(_PNG_BYTES)
    write_config(tmp_path, '{"icon": "icon.png"}')
    project_dir = tmp_path / "android-project"

    scaffold_project(out_dir, output_dir=project_dir)

    custom_icon = project_dir / "app/src/main/res/drawable/ic_launcher_custom.png"
    assert custom_icon.read_bytes() == _PNG_BYTES

    adaptive_icon_xml = (
        project_dir / "app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml"
    ).read_text()
    assert "ic_launcher_custom" in adaptive_icon_xml


def test_scaffold_copies_splash_image(tmp_path):
    out_dir = build_dir(tmp_path)
    (out_dir / "splash.png").write_bytes(_PNG_BYTES)
    write_config(tmp_path, '{"splash": "splash.png"}')
    project_dir = tmp_path / "android-project"

    scaffold_project(out_dir, output_dir=project_dir)

    splash_image = project_dir / "app/src/main/res/drawable/splash_image.png"
    assert splash_image.read_bytes() == _PNG_BYTES

    themes_xml = (project_dir / "app/src/main/res/values/themes.xml").read_text()
    assert "Theme.App.Starting" in themes_xml

    manifest = (project_dir / "app/src/main/AndroidManifest.xml").read_text()
    assert 'android:theme="@style/Theme.App.Starting"' in manifest

    build_gradle = (project_dir / "app/build.gradle.kts").read_text()
    assert "androidx.core:core-splashscreen" in build_gradle


def test_scaffold_icon_path_must_stay_inside_build_dir(tmp_path):
    out_dir = build_dir(tmp_path)
    write_config(tmp_path, '{"icon": "../outside.png"}')
    project_dir = tmp_path / "android-project"

    with pytest.raises(AndroidError, match="must stay inside the build directory"):
        scaffold_project(out_dir, output_dir=project_dir)


def test_scaffold_missing_icon_raises(tmp_path):
    out_dir = build_dir(tmp_path)
    write_config(tmp_path, '{"icon": "nope.png"}')
    project_dir = tmp_path / "android-project"

    with pytest.raises(AndroidError, match="not found"):
        scaffold_project(out_dir, output_dir=project_dir)


def test_scaffold_unsupported_icon_extension_raises(tmp_path):
    out_dir = build_dir(tmp_path)
    (out_dir / "icon.css").write_text("body {}")
    write_config(tmp_path, '{"icon": "icon.css"}')
    project_dir = tmp_path / "android-project"

    with pytest.raises(AndroidError, match="unsupported extension"):
        scaffold_project(out_dir, output_dir=project_dir)


# --------------------------------------------------------------------
# Validation errors
# --------------------------------------------------------------------


def test_scaffold_missing_build_dir_raises(tmp_path):
    with pytest.raises(AndroidError, match="Build directory not found"):
        scaffold_project(tmp_path / "nope", output_dir=tmp_path / "android-project")


def test_scaffold_build_dir_without_index_html_raises(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(AndroidError, match="no index.html"):
        scaffold_project(empty, output_dir=tmp_path / "android-project")


def test_scaffold_refuses_nonempty_output_dir(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"
    project_dir.mkdir()
    (project_dir / "existing.txt").write_text("hi")

    with pytest.raises(AndroidError, match="already exists and is not empty"):
        scaffold_project(out_dir, output_dir=project_dir)


def test_scaffold_allows_existing_empty_output_dir(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"
    project_dir.mkdir()

    result = scaffold_project(out_dir, output_dir=project_dir)
    assert (result.project_dir / "settings.gradle.kts").exists()


def test_scaffold_invalid_package_id_raises(tmp_path):
    out_dir = build_dir(tmp_path)
    write_config(tmp_path, '{"package_id": "not-a-package-id"}')

    with pytest.raises(AndroidError, match="Invalid android.package_id"):
        scaffold_project(out_dir, output_dir=tmp_path / "android-project")


def test_scaffold_single_segment_package_id_raises(tmp_path):
    out_dir = build_dir(tmp_path)
    write_config(tmp_path, '{"package_id": "myapp"}')

    with pytest.raises(AndroidError, match="Invalid android.package_id"):
        scaffold_project(out_dir, output_dir=tmp_path / "android-project")


def test_scaffold_non_int_version_code_raises(tmp_path):
    out_dir = build_dir(tmp_path)
    write_config(tmp_path, '{"version_code": "7"}')

    with pytest.raises(AndroidError, match="version_code must be an int"):
        scaffold_project(out_dir, output_dir=tmp_path / "android-project")


def test_scaffold_bool_version_code_raises(tmp_path):
    # bool is a subclass of int in Python -- must be explicitly rejected.
    out_dir = build_dir(tmp_path)
    write_config(tmp_path, '{"version_code": True}')

    with pytest.raises(AndroidError, match="version_code must be an int"):
        scaffold_project(out_dir, output_dir=tmp_path / "android-project")


def test_scaffold_unknown_orientation_raises(tmp_path):
    out_dir = build_dir(tmp_path)
    write_config(tmp_path, '{"orientation": "upside-down"}')

    with pytest.raises(AndroidError, match="Unknown android.orientation"):
        scaffold_project(out_dir, output_dir=tmp_path / "android-project")


def test_scaffold_malformed_config_raises_android_error(tmp_path):
    out_dir = build_dir(tmp_path)
    (tmp_path / "arklight.config.py").write_text("this is not valid python (((")

    with pytest.raises(AndroidError):
        scaffold_project(out_dir, output_dir=tmp_path / "android-project")


# --------------------------------------------------------------------
# CLI wiring
# --------------------------------------------------------------------


def test_cli_android_scaffold_reports_success(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out_dir = build_dir(tmp_path)

    exit_code = main(["android", "scaffold", str(out_dir), "-o", "android-project"])

    assert exit_code == 0
    assert (tmp_path / "android-project" / "settings.gradle.kts").exists()
    captured = capsys.readouterr()
    assert "scaffolded an Android project" in captured.out
    assert "com.arklight.app" in captured.out


def test_cli_android_scaffold_failure_returns_nonzero(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)

    exit_code = main(["android", "scaffold", "does-not-exist", "-o", "android-project"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "ARKlight android scaffold failed" in captured.err


def test_cli_android_without_subcommand_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        main(["android"])


def test_cli_android_scaffold_requires_output_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out_dir = build_dir(tmp_path)
    with pytest.raises(SystemExit):
        main(["android", "scaffold", str(out_dir)])


def _write_debug_keystore(tmp_path: Path) -> Path:
    # A real keystore isn't needed for these tests -- scaffold_project
    # only ever copies the file byte-for-byte, it never opens it with
    # `keytool` or Gradle -- so a placeholder file with the right name
    # is enough to exercise the copy-in/template-wiring behavior.
    path = tmp_path / "my-debug.keystore"
    path.write_bytes(b"not a real keystore, just needs to exist")
    return path


def test_scaffold_without_debug_keystore_flag_has_no_debug_signing_config(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"

    result = scaffold_project(out_dir, output_dir=project_dir)

    assert result.has_debug_keystore is False
    assert not (project_dir / "app/debug.keystore").exists()
    contents = (project_dir / "app/build.gradle.kts").read_text()
    assert 'create("debug")' not in contents
    assert "signingConfig = signingConfigs.getByName(\"debug\")" not in contents


def test_scaffold_with_debug_keystore_flag_copies_and_wires_it_up(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"
    keystore = _write_debug_keystore(tmp_path)

    result = scaffold_project(out_dir, output_dir=project_dir, debug_keystore=keystore)

    assert result.has_debug_keystore is True
    dest = project_dir / "app/debug.keystore"
    assert dest.is_file()
    assert dest.read_bytes() == keystore.read_bytes()

    contents = (project_dir / "app/build.gradle.kts").read_text()
    assert 'create("debug")' in contents
    assert 'storeFile = file("debug.keystore")' in contents
    assert 'storePassword = "android"' in contents
    assert 'keyAlias = "androiddebugkey"' in contents
    assert 'keyPassword = "android"' in contents
    assert 'signingConfig = signingConfigs.getByName("debug")' in contents


def test_scaffold_debug_keystore_missing_file_raises(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"

    with pytest.raises(AndroidError, match="not found"):
        scaffold_project(out_dir, output_dir=project_dir, debug_keystore=tmp_path / "nope.keystore")


def test_readme_documents_debug_signing_warning_by_default(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"

    scaffold_project(out_dir, output_dir=project_dir)

    contents = (project_dir / "README.md").read_text()
    assert "no pinned debug signing key" in contents
    assert "keytool -genkeypair" in contents


def test_readme_documents_debug_signing_when_pinned(tmp_path):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"
    keystore = _write_debug_keystore(tmp_path)

    scaffold_project(out_dir, output_dir=project_dir, debug_keystore=keystore)

    contents = (project_dir / "README.md").read_text()
    assert "pinned debug signing key" in contents
    assert "app/debug.keystore" in contents


def test_cli_warns_about_debug_keystore_by_default(tmp_path, capsys):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"

    exit_code = main(["android", "scaffold", str(out_dir), "-o", str(project_dir)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "WARNING: no --debug-keystore given" in out


def test_cli_no_debug_keystore_warning_when_flag_given(tmp_path, capsys):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"
    keystore = _write_debug_keystore(tmp_path)

    exit_code = main(
        ["android", "scaffold", str(out_dir), "-o", str(project_dir), "--debug-keystore", str(keystore)]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "WARNING: no --debug-keystore given" not in out
    assert "Debug builds are signed with your pinned app/debug.keystore" in out


def test_cli_debug_keystore_missing_file_reports_android_error(tmp_path, capsys):
    out_dir = build_dir(tmp_path)
    project_dir = tmp_path / "android-project"

    exit_code = main(
        [
            "android",
            "scaffold",
            str(out_dir),
            "-o",
            str(project_dir),
            "--debug-keystore",
            str(tmp_path / "nope.keystore"),
        ]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "ARKlight android scaffold failed" in captured.err
