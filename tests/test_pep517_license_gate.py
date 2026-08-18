import pytest

from arklight import _pep517_backend as backend


def test_env_var_accepts(monkeypatch):
    monkeypatch.setenv(backend.ENV_VAR, "1")
    assert backend._accepted(config_settings=None) is True


def test_env_var_case_and_word_forms(monkeypatch):
    monkeypatch.setenv(backend.ENV_VAR, "YES")
    assert backend._accepted(config_settings=None) is True


def test_no_env_var_no_config_setting_not_accepted(monkeypatch):
    monkeypatch.delenv(backend.ENV_VAR, raising=False)
    assert backend._accepted(config_settings=None) is False
    assert backend._accepted(config_settings={}) is False


def test_config_setting_accepts(monkeypatch):
    monkeypatch.delenv(backend.ENV_VAR, raising=False)
    settings = {backend.CONFIG_SETTING_KEY: "1"}
    assert backend._accepted(config_settings=settings) is True


def test_config_setting_list_value_accepts(monkeypatch):
    # pip may pass repeated --config-settings flags through as a list.
    monkeypatch.delenv(backend.ENV_VAR, raising=False)
    settings = {backend.CONFIG_SETTING_KEY: ["0", "1"]}
    assert backend._accepted(config_settings=settings) is True


def test_config_setting_falsy_does_not_accept(monkeypatch):
    monkeypatch.delenv(backend.ENV_VAR, raising=False)
    settings = {backend.CONFIG_SETTING_KEY: "0"}
    assert backend._accepted(config_settings=settings) is False


def test_require_acceptance_raises_systemexit_when_not_accepted(monkeypatch, capsys):
    monkeypatch.delenv(backend.ENV_VAR, raising=False)
    with pytest.raises(SystemExit):
        backend._require_acceptance(config_settings=None)
    assert "ARKlight is licensed under the GNU GPLv3" in capsys.readouterr().err


def test_require_acceptance_passes_silently_when_accepted(monkeypatch):
    monkeypatch.setenv(backend.ENV_VAR, "1")
    backend._require_acceptance(config_settings=None)  # should not raise


def test_build_wheel_blocked_without_acceptance(monkeypatch, tmp_path):
    monkeypatch.delenv(backend.ENV_VAR, raising=False)
    with pytest.raises(SystemExit):
        backend.build_wheel(str(tmp_path))


def test_build_sdist_blocked_without_acceptance(monkeypatch, tmp_path):
    monkeypatch.delenv(backend.ENV_VAR, raising=False)
    with pytest.raises(SystemExit):
        backend.build_sdist(str(tmp_path))


def test_build_editable_blocked_without_acceptance(monkeypatch, tmp_path):
    monkeypatch.delenv(backend.ENV_VAR, raising=False)
    with pytest.raises(SystemExit):
        backend.build_editable(str(tmp_path))


def test_build_wheel_delegates_to_setuptools_when_accepted(monkeypatch, tmp_path):
    monkeypatch.setenv(backend.ENV_VAR, "1")
    calls = []
    monkeypatch.setattr(
        backend._orig,
        "build_wheel",
        lambda wheel_directory, config_settings=None, metadata_directory=None: calls.append(
            (wheel_directory, config_settings, metadata_directory)
        )
        or "fake-wheel-name",
    )
    result = backend.build_wheel(str(tmp_path))
    assert result == "fake-wheel-name"
    assert calls == [(str(tmp_path), None, None)]


def test_non_build_hooks_forwarded_unchanged():
    # These should be the exact same objects as setuptools' own hooks --
    # no gating, no wrapping.
    assert backend.get_requires_for_build_wheel is backend._orig.get_requires_for_build_wheel
    assert backend.get_requires_for_build_sdist is backend._orig.get_requires_for_build_sdist
    assert (
        backend.prepare_metadata_for_build_wheel
        is backend._orig.prepare_metadata_for_build_wheel
    )
