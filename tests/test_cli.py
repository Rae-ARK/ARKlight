from pathlib import Path
from unittest.mock import patch

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


def test_cli_build_failure_returns_nonzero(tmp_path, capsys):
    bad_path = tmp_path / "site.py"
    bad_path.write_text("from arklight import *\nsite = Site()\n")  # no pages

    exit_code = main(["build", str(bad_path), "-o", str(tmp_path / "dist"), "--no-open"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "ARKlight build failed" in captured.err
