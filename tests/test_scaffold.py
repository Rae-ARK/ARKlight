from pathlib import Path
from unittest.mock import patch

import pytest

from arklight.cli.main import main
from arklight.cli.scaffold import ScaffoldError, new_project
from arklight.compiler.pipeline import build


def test_new_simple_writes_expected_files(tmp_path):
    result = new_project("my_site", template="simple", dest_dir=tmp_path)

    assert result.project_dir == tmp_path / "my_site"
    assert result.template == "simple"
    assert (tmp_path / "my_site" / "site.py").exists()
    assert (tmp_path / "my_site" / "README.md").exists()


def test_new_production_writes_expected_files(tmp_path):
    result = new_project("my_site", template="production", dest_dir=tmp_path)

    project = result.project_dir
    for rel in [
        "site.py",
        "README.md",
        "components/__init__.py",
        "components/nav.py",
        "pages/__init__.py",
        "pages/home.py",
        "pages/about.py",
        "content/__init__.py",
        "content/site_content.py",
        "assets/.gitkeep",
    ]:
        assert (project / rel).exists(), rel


def test_new_default_template_is_simple(tmp_path):
    result = new_project("my_site", dest_dir=tmp_path)
    assert result.template == "simple"


def test_new_unknown_template_raises(tmp_path):
    with pytest.raises(ScaffoldError, match="Unknown template"):
        new_project("my_site", template="bogus", dest_dir=tmp_path)


def test_new_empty_name_raises(tmp_path):
    with pytest.raises(ScaffoldError, match="must not be empty"):
        new_project("", dest_dir=tmp_path)


def test_new_name_with_path_separator_raises(tmp_path):
    with pytest.raises(ScaffoldError, match="path separator"):
        new_project("nested/name", dest_dir=tmp_path)


def test_new_refuses_existing_nonempty_dir(tmp_path):
    target = tmp_path / "my_site"
    target.mkdir()
    (target / "existing.txt").write_text("hi")

    with pytest.raises(ScaffoldError, match="already exists and is not empty"):
        new_project("my_site", dest_dir=tmp_path)


def test_new_allows_existing_empty_dir(tmp_path):
    target = tmp_path / "my_site"
    target.mkdir()

    result = new_project("my_site", dest_dir=tmp_path)
    assert (result.project_dir / "site.py").exists()


@pytest.mark.parametrize("template", ["simple", "production"])
def test_scaffolded_project_builds_successfully(tmp_path, template):
    """The real end-to-end guarantee: whatever `arklight new` writes,
    `arklight build` must be able to compile without any manual edits
    -- this is the "zero-thinking path" the templates promise."""
    result = new_project("my_site", template=template, dest_dir=tmp_path)

    out_dir = tmp_path / "dist"
    build_result = build(result.project_dir / "site.py", out_dir)

    assert (out_dir / "index.html").exists()
    assert (out_dir / "about.html").exists()
    assert build_result.written_paths


def test_cli_new_scaffolds_and_reports_files(tmp_path, capsys):
    exit_code = main(["new", "my_site", "--dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "my_site" / "site.py").exists()
    captured = capsys.readouterr()
    assert "scaffolded a 'simple' project" in captured.out


def test_cli_new_with_production_template(tmp_path, capsys):
    exit_code = main(["new", "my_site", "--template", "production", "--dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "my_site" / "pages" / "home.py").exists()


def test_cli_new_invalid_template_is_rejected_by_argparse(tmp_path):
    with pytest.raises(SystemExit):
        main(["new", "my_site", "--template", "bogus", "--dir", str(tmp_path)])


def test_cli_new_failure_returns_nonzero(tmp_path, capsys):
    target = tmp_path / "my_site"
    target.mkdir()
    (target / "existing.txt").write_text("hi")

    exit_code = main(["new", "my_site", "--dir", str(tmp_path)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "ARKlight new failed" in captured.err


def test_cli_new_default_dir_is_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    exit_code = main(["new", "my_site"])

    assert exit_code == 0
    assert (tmp_path / "my_site" / "site.py").exists()
