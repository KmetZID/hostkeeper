"""Dummy test for stage 1.1."""

from hostkeeper import __version__


def test_version() -> None:
    assert __version__ == "0.1.0"
