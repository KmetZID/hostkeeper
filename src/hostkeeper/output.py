"""Rendering output terminal (tabel, simbol, warna, dan ringkasan)."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from hostkeeper import messages
from hostkeeper.engine.step import Change, Risk

# Simbol status sesuai SPEC bagian 8
SYM_OK = "[=]"
SYM_CHANGE = "[~]"
SYM_ADD = "[+]"
SYM_FAIL = "[!]"
SYM_SKIP = "[-]"


def is_color_enabled(no_color: bool = False) -> bool:
    """Memeriksa apakah output warna aktif (memperhatikan NO_COLOR dan TTY)."""
    if no_color:
        return False
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


def _change_desc_for_step(
    step_name: str,
    check_current: str,
    changes: list[Change],
    compliant: bool,
) -> tuple[str, str]:
    """Menghasilkan (simbol, deskripsi) untuk baris plan."""
    if compliant:
        return SYM_OK, f"{check_current} (sudah sesuai)"

    if not changes:
        return SYM_OK, f"{check_current} (sudah sesuai)"

    if all(c.action == "install" for c in changes):
        pkgs = ", ".join(c.after or c.target for c in changes if c.after)
        sym = SYM_ADD
        # Cek ada yang sudah terpasang
        installed_note = ""
        if compliant is False and check_current.startswith("belum terpasang"):
            # Ada yang sudah terpasang jika jumlah paket > len(changes)
            pass
        return sym, f"pasang: {pkgs}"

    # set action
    for ch in changes:
        if ch.action == "set" and ch.before is not None and ch.after is not None:
            return SYM_CHANGE, f"{ch.before} -> {ch.after}"

    return SYM_CHANGE, check_current


def print_plan_table(
    plan_items: list[Any],
    no_color: bool = False,
) -> None:
    """Mencetak tabel plan ke stdout.

    plan_items: list[PlanItem] dari engine.planner.
    """
    print(messages.PLAN_TABLE_HEADER)
    for item in plan_items:
        step = item.step
        sym, desc = _change_desc_for_step(
            step_name=step.name,
            check_current=item.check_result.current,
            changes=item.changes,
            compliant=item.check_result.compliant,
        )
        # Tentukan risk string
        risk_str = step.risk.value if item.changes else "-"
        row = format_plan_row(sym, step.name, desc, risk_str)
        print(row)


def print_plan_json(
    version: str,
    profile_path: str,
    plan_items: list[Any],
) -> None:
    """Mencetak output plan dalam format JSON."""
    steps_out: list[dict[str, Any]] = []
    for item in plan_items:
        step = item.step
        status = "ok" if item.check_result.compliant else "change"
        changes_out: list[dict[str, Any]] = []
        for ch in item.changes:
            changes_out.append(
                {
                    "action": ch.action,
                    "target": ch.target,
                    "before": ch.before,
                    "after": ch.after,
                }
            )
        steps_out.append(
            {
                "name": step.name,
                "status": status,
                "risk": step.risk.value,
                "changes": changes_out,
            }
        )

    total_changes = sum(len(item.changes) for item in plan_items)
    total_ok = sum(1 for item in plan_items if item.check_result.compliant)
    total_high_risk = sum(
        1
        for item in plan_items
        if item.changes and step.risk == Risk.HIGH
    )

    output = {
        "version": version,
        "profile": profile_path,
        "steps": steps_out,
        "summary": {
            "changes": total_changes,
            "ok": total_ok,
            "high_risk": total_high_risk,
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=None))


def print_verify_table(
    plan_items: list[Any],
) -> int:
    """Mencetak tabel verify. Mengembalikan jumlah Step drift."""
    drift = 0
    for item in plan_items:
        step = item.step
        chk = item.check_result
        if chk.compliant:
            print(f" {SYM_OK} {step.name:<10} {chk.current}")
        else:
            drift += 1
            expected = ""
            # Cari nilai expected dari changes atau profil
            if item.changes:
                for ch in item.changes:
                    if ch.after:
                        expected = ch.after
                        break
            if expected:
                desc = messages.VERIFY_EXPECT.format(
                    expected=expected, current=chk.current
                )
            else:
                desc = chk.current
            print(f" {SYM_CHANGE} {step.name:<10} {desc}")
    return drift


def print_verify_json(plan_items: list[Any]) -> int:
    """Mencetak verify dalam JSON. Mengembalikan jumlah drift."""
    drift = 0
    steps_out: list[dict[str, Any]] = []
    for item in plan_items:
        step = item.step
        chk = item.check_result
        status = "ok" if chk.compliant else "drift"
        if not chk.compliant:
            drift += 1
        steps_out.append(
            {
                "name": step.name,
                "status": status,
                "current": chk.current,
            }
        )
    output = {"steps": steps_out, "drift": drift}
    print(json.dumps(output, ensure_ascii=False))
    return drift
