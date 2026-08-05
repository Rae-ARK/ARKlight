from pathlib import Path
from unittest.mock import patch

import pytest

from arklight.cli.main import main, open_in_browser
from arklight.compiler.pipeline import build

SIMPLE_SITE = """
from arklight import *
site = Site()

@site.page("/")
def home():
    return Page(Heading("Hi"))
"""


def write_site(tmp_path: Path) -> Path:
    path = tmp_path / "site.py"
    path.write_text(SIMPLE_SITE)
    return path


def test_open_in_browser_calls_webbrowser_with_file_uri(tmp_path):
    site_path = write_site(tmp_path)
    out_dir = tmp_path / "dist"
    result = build(site_path, out_dir)

    with patch("arklight.cli.main.webbrowser.open") as mock_open:
        opened = open_in_browser(result, out_dir)

    assert opened is True
    mock_open.assert_called_once()
    (called_url,), _ = mock_open.call_args
    assert called_url.startswith("file://")
    assert called_url.endswith("index.html")


def test_open_in_browser_returns_false_when_no_index(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    class FakeResult:
        pass

    with patch("arklight.cli.main.webbrowser.open") as mock_open:
        opened = open_in_browser(FakeResult(), empty_dir)

    assert opened is False
    mock_open.assert_not_called()


def test_open_in_browser_swallows_launch_errors(tmp_path):
    site_path = write_site(tmp_path)
    out_dir = tmp_path / "dist"
    result = build(site_path, out_dir)

    with patch("arklight.cli.main.webbrowser.open", side_effect=RuntimeError("no display")):
        opened = open_in_browser(result, out_dir)

    assert opened is False


def test_cli_build_blocked_without_license_acceptance(tmp_path, monkeypatch):
    site_path = write_site(tmp_path)
    monkeypatch.delenv("ARKLIGHT_ACCEPT_LICENSE", raising=False)
    monkeypatch.setenv("ARKLIGHT_HOME", str(tmp_path / "home"))

    exit_code = main(["build", str(site_path), "-o", str(tmp_path / "dist"), "--no-open"])

    assert exit_code == 1
    assert not (tmp_path / "dist" / "index.html").exists()


def test_cli_build_no_open_does_not_launch_browser(tmp_path, capsys):
    site_path = write_site(tmp_path)
    out_dir = tmp_path / "dist"

    with patch("arklight.cli.main.webbrowser.open") as mock_open:
        exit_code = main(["build", str(site_path), "-o", str(out_dir), "--no-open"])

    assert exit_code == 0
    mock_open.assert_not_called()
    assert (out_dir / "index.html").exists()
    assert (out_dir / "styles.css").exists()


def test_cli_build_open_by_default_launches_browser(tmp_path):
    site_path = write_site(tmp_path)
    out_dir = tmp_path / "dist"

    with patch("arklight.cli.main.webbrowser.open") as mock_open:
        exit_code = main(["build", str(site_path), "-o", str(out_dir)])

    assert exit_code == 0
    mock_open.assert_called_once()


def test_cli_build_default_output_dir_is_ark(tmp_path, capsys, monkeypatch):
    site_path = write_site(tmp_path)
    monkeypatch.chdir(tmp_path)

    with patch("arklight.cli.main.webbrowser.open"):
        exit_code = main(["build", str(site_path), "--no-open"])

    assert exit_code == 0
    assert (tmp_path / "ARK" / "index.html").exists()
    captured = capsys.readouterr()
    assert "-> ARK/" in captured.out


def test_cli_build_failure_returns_nonzero(tmp_path, capsys):
    bad_path = tmp_path / "site.py"
    bad_path.write_text("from arklight import *\nsite = Site()\n")  # no pages

    exit_code = main(["build", str(bad_path), "-o", str(tmp_path / "dist"), "--no-open"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "ARKlight build failed" in captured.err
    assert "Re-run with --debug" in captured.err


def test_cli_build_verbose_prints_pipeline_stages(tmp_path, capsys):
    site_path = write_site(tmp_path)

    exit_code = main(
        ["build", str(site_path), "-o", str(tmp_path / "dist"), "--no-open", "--verbose"]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    # Spot-check a handful of stages rather than the exact full list --
    # this is about the mechanism (stages get narrated at all), not
    # pinning down every wording forever.
    assert "[ARKlight] Discovering site and compiling AST trees..." in captured.out
    assert "[ARKlight] Running validation..." in captured.out
    assert "[ARKlight] Rendering backend 'html'..." in captured.out
    assert "[ARKlight] Build complete ->" in captured.out


def test_cli_build_without_verbose_prints_no_stage_lines(tmp_path, capsys):
    site_path = write_site(tmp_path)

    exit_code = main(["build", str(site_path), "-o", str(tmp_path / "dist"), "--no-open"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "[ARKlight]" not in captured.out


def test_cli_build_debug_prints_full_traceback_on_failure(tmp_path, capsys):
    bad_path = tmp_path / "site.py"
    bad_path.write_text(
        "from arklight import *\n"
        "site = Site()\n"
        "@site.page('/')\n"
        "def home():\n"
        "    return Page(NotARealComponent('oops'))\n"
    )

    exit_code = main(
        ["build", str(bad_path), "-o", str(tmp_path / "dist"), "--no-open", "--debug"]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    # --debug implies --verbose: stage narration still shows up...
    assert "[ARKlight] Discovering site and compiling AST trees..." in captured.out
    # ...and the failure is a full chained Python traceback, not the
    # short one-line message `--debug`-less mode prints.
    assert "Traceback (most recent call last)" in captured.err
    assert "NameError" in captured.err
    assert "site.py" in captured.err


def test_cli_search_exact_match(capsys):
    exit_code = main(["search", "Picture"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("Picture")
    assert "required props" in captured.out
    assert "allows children" in captured.out


def test_cli_search_is_case_insensitive(capsys):
    exit_code = main(["search", "picture"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("Picture")


def test_cli_search_text_only_component_mentions_bind(capsys):
    main(["search", "Heading"])

    captured = capsys.readouterr()
    assert "text only" in captured.out
    assert "Bind" in captured.out


def test_cli_search_required_prop_is_listed(capsys):
    main(["search", "Link"])

    captured = capsys.readouterr()
    assert "href" in captured.out


def test_cli_search_typo_suggests_close_matches(capsys):
    exit_code = main(["search", "Pictur"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "No component named" in captured.out
    assert "Picture" in captured.out


def test_cli_search_unrelated_query_says_nothing_close(capsys):
    main(["search", "zzzznotarealcomponentatall"])

    captured = capsys.readouterr()
    assert "nothing close enough" in captured.out


def test_cli_search_requires_name_unless_serve(capsys):
    exit_code = main(["search"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "required" in captured.err
    assert "--serve" in captured.err


def test_cli_search_name_and_serve_are_mutually_exclusive(capsys):
    # Doesn't actually start the stdio loop -- passing both `name` and
    # `--serve` is rejected before serve_stdio() is ever called, so
    # this can't hang waiting on stdin.
    exit_code = main(["search", "Picture", "--serve"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "mutually exclusive" in captured.err


def test_cli_pwa_icon_flag_adds_icons_to_manifest(tmp_path, capsys):
    import json

    site_path = write_site(tmp_path)
    out_dir = tmp_path / "dist"
    main(["build", str(site_path), "-o", str(out_dir), "--no-open"])
    capsys.readouterr()

    exit_code = main(
        [
            "pwa",
            str(out_dir),
            "--name",
            "My Site",
            "--icon",
            "assets/icon-192.png:192x192",
            "--icon",
            "assets/icon-512.png:512x512:image/png",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "2 icon(s) registered" in captured.out

    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert manifest["icons"] == [
        {"src": "assets/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "assets/icon-512.png", "sizes": "512x512", "type": "image/png"},
    ]


def test_cli_pwa_without_icon_flag_reports_empty_icons(tmp_path, capsys):
    site_path = write_site(tmp_path)
    out_dir = tmp_path / "dist"
    main(["build", str(site_path), "-o", str(out_dir), "--no-open"])
    capsys.readouterr()

    exit_code = main(["pwa", str(out_dir), "--name", "My Site"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "no --icon given" in captured.out


def test_cli_pwa_icon_flag_rejects_bad_sizes(tmp_path, capsys):
    site_path = write_site(tmp_path)
    out_dir = tmp_path / "dist"
    main(["build", str(site_path), "-o", str(out_dir), "--no-open"])
    capsys.readouterr()

    exit_code = main(
        ["pwa", str(out_dir), "--name", "My Site", "--icon", "assets/icon.png:not-a-size"]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "SIZES" in captured.err


def test_cli_pwa_icon_flag_rejects_unknown_extension_without_type(tmp_path, capsys):
    site_path = write_site(tmp_path)
    out_dir = tmp_path / "dist"
    main(["build", str(site_path), "-o", str(out_dir), "--no-open"])
    capsys.readouterr()

    exit_code = main(
        ["pwa", str(out_dir), "--name", "My Site", "--icon", "assets/icon.weird:192x192"]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "couldn't infer a MIME type" in captured.err


def test_cli_no_command_prints_help_and_exits_zero(capsys):
    exit_code = main([])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "usage: arklight" in captured.out
    assert "search" in captured.out
    assert "build" in captured.out


def test_cli_help_flag_lists_every_subcommand(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    for subcommand in ("build", "pack", "unpack", "pwa", "new", "search"):
        assert subcommand in captured.out
