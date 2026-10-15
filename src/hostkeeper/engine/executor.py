"""Executor: menjalankan apply dengan kebijakan fail-fast dan undo mundur."""

from __future__ import annotations

import datetime
import hashlib
import secrets
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Callable

from hostkeeper import messages
from hostkeeper.engine.audit import AuditWriter
from hostkeeper.engine.journal import JournalWriter
from hostkeeper.engine.step import Change, Step


def make_run_id() -> str:
    """Menghasilkan run_id format '20260114T093000Z-ab12'."""
    now = datetime.datetime.now(datetime.timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    suffix = secrets.token_hex(2)  # 4 karakter hex
    return f"{ts}-{suffix}"


def sha256_file(path: Path) -> str:
    """Menghitung SHA-256 dari file profil."""
    try:
        data = path.read_bytes()
        return hashlib.sha256(data).hexdigest()
    except OSError:
        return ""


@dataclass
class StepResult:
    """Hasil eksekusi satu Step oleh Executor."""

    step_name: str
    changes: list[Change]
    applied: bool = False
    verified: bool = False
    skipped: bool = False
    failed: bool = False
    error: str = ""
    undone: bool = False


@dataclass
class ExecutionReport:
    """Laporan keseluruhan hasil apply."""

    run_id: str
    results: list[StepResult] = field(default_factory=list)
    journal_path: Path | None = None
    aborted: bool = False

    @property
    def n_applied(self) -> int:
        return sum(1 for r in self.results if r.applied and r.verified)

    @property
    def n_failed(self) -> int:
        return sum(1 for r in self.results if r.failed)


class Executor:
    """Menjalankan apply dengan kebijakan fail-fast, undo mundur hanya reversible.

    Kebijakan (SPEC 4.4):
    1. Lock diambil di luar (di cli.py).
    2. Buat run_id.
    3. Untuk tiap Step: tampilkan plan, minta konfirmasi (kecuali --yes).
    4. Per Step yang punya perubahan: apply() -> verify().
    5. Jika apply/verify gagal: fail-fast, undo mundur hanya reversible.
    6. Tulis journal dan audit.
    """

    def __init__(
        self,
        steps_with_changes: list[tuple[Step, list[Change]]],
        run_id: str,
        profile_path: Path,
        audit: AuditWriter,
        journal: JournalWriter,
        out: IO[str] | None = None,
        dry_run: bool = False,
        yes: bool = False,
        confirm_fn: Callable[[str], str] | None = None,
    ) -> None:
        self.steps_with_changes = steps_with_changes
        self.run_id = run_id
        self.profile_path = profile_path
        self.audit = audit
        self.journal = journal
        self.out = out or sys.stdout
        self.dry_run = dry_run
        self.yes = yes
        self.confirm_fn = confirm_fn or input

    def _print(self, msg: str) -> None:
        print(msg, file=self.out)

    def run(self) -> ExecutionReport:
        """Menjalankan apply. Mengembalikan ExecutionReport."""
        report = ExecutionReport(run_id=self.run_id)

        # Hitung total perubahan
        total_changes = sum(len(ch) for _, ch in self.steps_with_changes)

        if total_changes == 0:
            return report

        # Minta konfirmasi jika tidak --yes dan tidak dry-run
        if not self.yes and not self.dry_run:
            prompt = messages.APPLY_CONFIRM_PROMPT.format(changes=total_changes)
            try:
                answer = self.confirm_fn(prompt)
            except (EOFError, KeyboardInterrupt):
                self._print(messages.APPLY_ABORT)
                report.aborted = True
                return report
            if answer.strip().lower() != "y":
                self._print(messages.APPLY_ABORT)
                report.aborted = True
                return report

        # Jalankan tiap Step
        applied_reversible: list[tuple[Step, list[Change]]] = []
        idx = 0

        for step, changes in self.steps_with_changes:
            idx += 1
            if not changes:
                sr = StepResult(step_name=step.name, changes=[], skipped=True)
                report.results.append(sr)
                self.journal.record_step(
                    name=step.name,
                    status="skipped",
                    reversible=step.reversible,
                    changes=[],
                )
                continue

            sr = StepResult(step_name=step.name, changes=changes)
            desc = self._describe_changes(changes)

            if self.dry_run:
                self._print(
                    messages.APPLY_DRY_RUN.format(cmd=f"{step.name}: {desc}")
                )
                sr.skipped = True
                report.results.append(sr)
                continue

            # Apply
            apply_ok = True
            apply_err = ""
            try:
                step.apply(changes)
                sr.applied = True
            except Exception as exc:
                apply_ok = False
                apply_err = str(exc)

            if not apply_ok:
                sr.failed = True
                sr.error = apply_err
                self._print(f" [!] {step.name:<10} {desc}")
                self._print(f"  ERROR: {sr.error}")
                self.audit.log_step_failed(step.name, sr.error)
                report.results.append(sr)
                self.journal.record_step(
                    name=step.name,
                    status="failed",
                    reversible=step.reversible,
                    changes=changes,
                )
                self._handle_failure(
                    failed_step=step,
                    applied_reversible=applied_reversible,
                    report=report,
                    remaining=self.steps_with_changes[idx:],
                )
                return report

            # Verify
            verify_ok = True
            verify_err = ""
            try:
                verify_res = step.verify()
                verify_ok = verify_res.compliant
                if not verify_ok:
                    verify_err = verify_res.current
            except Exception as exc:
                verify_ok = False
                verify_err = str(exc)

            if not verify_ok:
                sr.failed = True
                sr.error = verify_err
                self._print(f" [!] {step.name:<10} verify gagal: {sr.error}")
                self.audit.log_step_failed(step.name, f"verify: {sr.error}")
                report.results.append(sr)
                self.journal.record_step(
                    name=step.name,
                    status="failed",
                    reversible=step.reversible,
                    changes=changes,
                )
                self._handle_failure(
                    failed_step=step,
                    applied_reversible=applied_reversible,
                    report=report,
                    remaining=self.steps_with_changes[idx:],
                )
                return report

            sr.verified = True
            self._print(f" [~] {step.name:<10} {desc} OK (verify lolos)")
            self.audit.log_step_applied(step.name, len(changes))
            self.audit.log_step_verified(step.name)
            self.journal.record_step(
                name=step.name,
                status="applied",
                reversible=step.reversible,
                changes=changes,
            )

            if step.reversible:
                applied_reversible.append((step, changes))

            report.results.append(sr)

        # Sukses: tulis journal
        journal_path = self.journal.write()
        report.journal_path = journal_path
        self._print(
            "\n"
            + messages.APPLY_DONE.format(
                applied=report.n_applied,
                failed=report.n_failed,
            )
        )
        self._print(messages.APPLY_JOURNAL.format(path=journal_path))
        self.audit.log_run_end("ok")

        return report

    def _describe_changes(self, changes: list[Change]) -> str:
        """Merangkum deskripsi perubahan untuk tampilan."""
        if not changes:
            return "(sudah sesuai)"
        if all(c.action == "install" for c in changes):
            pkgs = ", ".join(c.after or c.target for c in changes)
            return f"pasang: {pkgs}"
        parts: list[str] = []
        for ch in changes:
            if ch.action == "set" and ch.before is not None and ch.after is not None:
                parts.append(f"{ch.before} -> {ch.after}")
            elif ch.after is not None:
                parts.append(ch.after)
            else:
                parts.append(ch.target)
        return ", ".join(parts)

    def _handle_failure(
        self,
        failed_step: Step,
        applied_reversible: list[tuple[Step, list[Change]]],
        report: ExecutionReport,
        remaining: list[tuple[Step, list[Change]]],
    ) -> None:
        """Menangani kegagalan: undo mundur dan tandai sisa Step sebagai skipped."""
        # Undo mundur hanya yang reversible
        undone_names: list[str] = []
        for step, changes in reversed(applied_reversible):
            try:
                step.undo(changes)
                undone_names.append(step.name)
                self.audit.log_undo(step.name)
                for r in report.results:
                    if r.step_name == step.name:
                        r.undone = True
            except Exception:
                pass

        # Cetak ringkasan kegagalan
        if undone_names:
            undone_str = ", ".join(
                f"{n} dikembalikan" for n in undone_names
            )
            self._print(
                messages.APPLY_FAIL_SUMMARY.format(
                    step=failed_step.name,
                    undone=undone_str,
                )
            )
        else:
            self._print(
                messages.APPLY_FAIL_SUMMARY.format(
                    step=failed_step.name,
                    undone="(tidak ada)",
                )
            )

        if not failed_step.reversible:
            self._print(messages.PACKAGES_CANNOT_UNDO)

        # Sisa Step ditandai skipped
        for step, _ in remaining:
            self._print(f" [-] (tidak ada Step tersisa)")
            report.results.append(
                StepResult(step_name=step.name, changes=[], skipped=True)
            )

        self.journal.write()
        self.audit.log_run_end("fail")
