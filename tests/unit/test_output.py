from __future__ import annotations

import pytest

from hostkeeper.engine.step import Risk
from hostkeeper.output import (
    SYM_ADD,
    SYM_CHANGE,
    SYM_FAIL,
    SYM_OK,
    SYM_SKIP,
    format_plan_row,
    format_plan_summary,
)


def test_symbols() -> None:
    assert SYM_OK == "[=]"
    assert SYM_CHANGE == "[~]"
    assert SYM_ADD == "[+]"
    assert SYM_FAIL == "[!]"
    assert SYM_SKIP == "[-]"


def test_format_plan_row() -> None:
    row = format_plan_row(
        status=SYM_CHANGE,
        step_name="hostname",
        change_desc="web-old -> web-01",
        risk=Risk.LOW,
    )
    assert "[~]" in row
    assert "hostname" in row
    assert "web-old -> web-01" in row
    assert "rendah" in row


def test_format_plan_summary() -> None:
    summary1 = format_plan_summary(changes=2, ok=1, high_risk=0)
    assert "2 perubahan" in summary1
    assert "1 sudah sesuai" in summary1
    assert "0 berisiko tinggi" in summary1

    summary0 = format_plan_summary(changes=0, ok=3, high_risk=0)
    assert "0 perubahan" in summary0
    assert "Server sudah sesuai profil" in summary0


def test_is_color_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from hostkeeper.output import is_color_enabled

    monkeypatch.setenv("NO_COLOR", "1")
    assert is_color_enabled() is False

    monkeypatch.delenv("NO_COLOR", raising=False)
    # in non-interactive/pytest, sys.stdout.isatty() is usually False
    assert isinstance(is_color_enabled(), bool)
