"""Rendering output terminal (tabel, simbol, warna, dan ringkasan)."""

from __future__ import annotations

import os
import sys

from hostkeeper import messages
from hostkeeper.engine.step import Risk

# Simbol status sesuai SPEC bagian 8
SYM_OK = "[=]"
SYM_CHANGE = "[~]"
SYM_ADD = "[+]"
SYM_FAIL = "[!]"
SYM_SKIP = "[-]"


def is_color_enabled() -> bool:
    """Memeriksa apakah output warna aktif (memperhatikan NO_COLOR dan TTY)."""
    if "NO_COLOR" in os.environ and os.environ["NO_COLOR"]:
        return False
    return sys.stdout.isatty()


def format_plan_row(
    status: str,
    step_name: str,
    change_desc: str,
    risk: Risk | str,
) -> str:
    """Format satu baris tabel plan."""
    risk_str = risk.value if isinstance(risk, Risk) else str(risk)
    return f" {status:<7} {step_name:<10} {change_desc:<43} {risk_str}"


def format_plan_summary(changes: int, ok: int, high_risk: int) -> str:
    """Format teks ringkasan plan."""
    if changes == 0:
        return messages.PLAN_SUMMARY_ALL_OK
    return messages.PLAN_SUMMARY.format(
        changes=changes,
        ok=ok,
        high_risk=high_risk,
    )
