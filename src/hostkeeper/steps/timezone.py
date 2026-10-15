"""Step untuk konfigurasi timezone sistem."""

from __future__ import annotations

from typing import ClassVar

from hostkeeper import messages
from hostkeeper.engine.step import Change, CheckResult, Risk, Step


class TimezoneStep(Step):
    """Mengonfigurasi zona waktu pada sistem Debian/Ubuntu."""

    name: ClassVar[str] = "timezone"
    risk: ClassVar[Risk] = Risk.LOW
    requires: ClassVar[tuple[str, ...]] = ()
    reversible: ClassVar[bool] = True

    def enabled(self) -> bool:
        """Aktif jika profil mendefinisikan timezone."""
        return self.profile.timezone is not None

    def check(self) -> CheckResult:
        """Membaca timezone saat ini secara murni (read-only)."""
        res = self.runner.run(
            ["timedatectl", "show", "-p", "Timezone", "--value"],
            mutates=False,
        )
        current = res.stdout.strip()
        target = self.profile.timezone or ""
        compliant = current == target
        detail = messages.STEP_COMPLIANT if compliant else ""
        return CheckResult(compliant=compliant, current=current, detail=detail)

    def plan(self) -> list[Change]:
        """Menghasilkan perubahan jika timezone berbeda dari profil."""
        chk = self.check()
        if chk.compliant or self.profile.timezone is None:
            return []
        return [
            Change(
                step=self.name,
                action="set",
                target="timezone",
                before=chk.current,
                after=self.profile.timezone,
            )
        ]

    def apply(self, changes: list[Change]) -> None:
        """Menerapkan timezone baru lewat timedatectl."""
        if self.profile.timezone is None:
            return
        res = self.runner.run(
            ["timedatectl", "set-timezone", self.profile.timezone],
            mutates=True,
        )
        if not res.ok:
            raise RuntimeError(f"timedatectl set-timezone gagal: {res.stderr.strip()}")

    def verify(self) -> CheckResult:
        """Memverifikasi timezone dengan memeriksa ulang kondisi sistem."""
        return self.check()

    def undo(self, changes: list[Change]) -> None:
        """Mengembalikan timezone lama yang tercatat pada changes."""
        for change in changes:
            if change.target == "timezone" and change.before:
                self.runner.run(
                    ["timedatectl", "set-timezone", change.before],
                    mutates=True,
                )
