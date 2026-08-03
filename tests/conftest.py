import os

import pytest


@pytest.fixture(autouse=True)
def _accept_arklight_license(monkeypatch):
    """
    The CLI's one-time license-acceptance gate (arklight.cli.license_gate)
    prompts interactively on first run. Tests run non-interactively, so
    set the documented CI/scripted-use bypass for every test -- this is
    exactly what a real CI pipeline would do after actually reading
    LICENSE once, not a way of skipping the gate's real behavior (which
    tests/test_license_gate.py exercises directly).
    """
    monkeypatch.setenv("ARKLIGHT_ACCEPT_LICENSE", "1")
