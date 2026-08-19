from __future__ import annotations

import pytest

from arklight.config import ConfigError, find_config, load_config, section


def test_find_config_returns_none_when_absent(tmp_path):
    assert find_config(tmp_path) is None


def test_load_config_returns_empty_dict_when_absent(tmp_path):
    assert load_config(tmp_path) == {}


def test_load_config_reads_config_dict(tmp_path):
    (tmp_path / "arklight.config.py").write_text(
        'CONFIG = {"live_streaming": {"port": 9000}}\n', encoding="utf-8"
    )
    config = load_config(tmp_path)
    assert config == {"live_streaming": {"port": 9000}}


def test_load_config_raises_on_syntax_error(tmp_path):
    (tmp_path / "arklight.config.py").write_text("CONFIG = {\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_load_config_raises_when_config_missing(tmp_path):
    (tmp_path / "arklight.config.py").write_text("X = 1\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_load_config_raises_when_config_not_a_dict(tmp_path):
    (tmp_path / "arklight.config.py").write_text("CONFIG = [1, 2]\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_section_returns_defaults_when_absent():
    assert section({}, "live_streaming", {"port": 8347}) == {"port": 8347}


def test_section_merges_project_values_over_defaults():
    config = {"live_streaming": {"port": 9000}}
    merged = section(config, "live_streaming", {"host": "127.0.0.1", "port": 8347})
    assert merged == {"host": "127.0.0.1", "port": 9000}


def test_section_raises_when_section_not_a_dict():
    with pytest.raises(ConfigError):
        section({"live_streaming": "nope"}, "live_streaming", {})
