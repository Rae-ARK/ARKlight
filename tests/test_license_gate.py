import io

from arklight.cli.license_gate import ensure_license_accepted


def test_env_var_bypasses_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("ARKLIGHT_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ARKLIGHT_ACCEPT_LICENSE", "1")

    accepted = ensure_license_accepted(stream_in=io.StringIO(""), stream_out=io.StringIO())

    assert accepted is True


def test_marker_file_bypasses_prompt_on_subsequent_runs(monkeypatch, tmp_path):
    monkeypatch.delenv("ARKLIGHT_ACCEPT_LICENSE", raising=False)
    monkeypatch.setenv("ARKLIGHT_HOME", str(tmp_path / "home"))
    marker_dir = tmp_path / "home"
    marker_dir.mkdir()
    (marker_dir / "license-accepted").write_text("accepted 2026-01-01T00:00:00+00:00\n")

    accepted = ensure_license_accepted(stream_in=io.StringIO(""), stream_out=io.StringIO())

    assert accepted is True


def test_non_interactive_without_env_var_refuses_without_hanging(monkeypatch, tmp_path):
    monkeypatch.delenv("ARKLIGHT_ACCEPT_LICENSE", raising=False)
    monkeypatch.setenv("ARKLIGHT_HOME", str(tmp_path / "home"))

    fake_stdin = io.StringIO("")  # StringIO.isatty() is always False

    accepted = ensure_license_accepted(stream_in=fake_stdin, stream_out=io.StringIO())

    assert accepted is False


class _FakeTTY(io.StringIO):
    def isatty(self) -> bool:  # noqa: D102
        return True


def test_interactive_agree_writes_marker_and_accepts(monkeypatch, tmp_path):
    monkeypatch.delenv("ARKLIGHT_ACCEPT_LICENSE", raising=False)
    monkeypatch.setenv("ARKLIGHT_HOME", str(tmp_path / "home"))

    accepted = ensure_license_accepted(stream_in=_FakeTTY("agree\n"), stream_out=io.StringIO())

    assert accepted is True
    assert (tmp_path / "home" / "license-accepted").exists()


def test_interactive_decline_does_not_write_marker(monkeypatch, tmp_path):
    monkeypatch.delenv("ARKLIGHT_ACCEPT_LICENSE", raising=False)
    monkeypatch.setenv("ARKLIGHT_HOME", str(tmp_path / "home"))

    accepted = ensure_license_accepted(stream_in=_FakeTTY("nope\n"), stream_out=io.StringIO())

    assert accepted is False
    assert not (tmp_path / "home" / "license-accepted").exists()


def test_interactive_agree_is_case_insensitive(monkeypatch, tmp_path):
    monkeypatch.delenv("ARKLIGHT_ACCEPT_LICENSE", raising=False)
    monkeypatch.setenv("ARKLIGHT_HOME", str(tmp_path / "home"))

    accepted = ensure_license_accepted(stream_in=_FakeTTY("AGREE\n"), stream_out=io.StringIO())

    assert accepted is True
