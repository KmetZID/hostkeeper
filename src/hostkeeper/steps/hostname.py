"""Step untuk konfigurasi hostname sistem."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from hostkeeper import messages
from hostkeeper.engine.step import Change, CheckResult, Risk, Step


class HostnameStep(Step):
    """Mengonfigurasi static hostname pada sistem Debian/Ubuntu."""

    name: ClassVar[str] = "hostname"
    risk: ClassVar[Risk] = Risk.LOW
    requires: ClassVar[tuple[str, ...]] = ()
    reversible: ClassVar[bool] = True

    def enabled(self) -> bool:
        """Aktif jika profil mendefinisikan hostname."""
        return self.profile.hostname is not None

    def check(self) -> CheckResult:
        """Membaca hostname statis saat ini secara murni (read-only)."""
        res = self.runner.run(["hostnamectl", "--static"], mutates=False)
        current = res.stdout.strip()
        target = self.profile.hostname or ""
        compliant = current == target
        detail = messages.STEP_COMPLIANT if compliant else ""
        return CheckResult(compliant=compliant, current=current, detail=detail)

    def plan(self) -> list[Change]:
        """Menghasilkan perubahan jika hostname berbeda dari profil."""
        chk = self.check()
        if chk.compliant or self.profile.hostname is None:
            return []
        return [
            Change(
                step=self.name,
                action="set",
                target="hostname",
                before=chk.current,
                after=self.profile.hostname,
            )
        ]

    def apply(self, changes: list[Change]) -> None:
        """Menerapkan hostname baru lewat hostnamectl."""
        if self.profile.hostname is None:
            return
        res = self.runner.run(
            ["hostnamectl", "set-hostname", self.profile.hostname],
            mutates=True,
        )
        if not res.ok:
            raise RuntimeError(f"hostnamectl set-hostname gagal: {res.stderr.strip()}")

    def verify(self) -> CheckResult:
        """Memverifikasi hostname; memberi peringatan getent / cloud-init jika ada."""
        chk = self.check()
        target = self.profile.hostname or ""
        warnings: list[str] = []

        if target:
            getent_res = self.runner.run(["getent", "hosts", target], mutates=False)
            if not getent_res.ok:
                warnings.append(messages.HOSTNAME_WARN_GETENT.format(hostname=target))

        cloud_cfg = self.fs.read_text(Path("/etc/cloud/cloud.cfg"))
        if cloud_cfg is not None and "preserve_hostname: true" not in cloud_cfg.lower():
            warnings.append(messages.HOSTNAME_WARN_CLOUD_INIT)

        detail = (
            "; ".join(warnings)
            if warnings
            else (messages.STEP_COMPLIANT if chk.compliant else "")
        )
        return CheckResult(compliant=chk.compliant, current=chk.current, detail=detail)

    def undo(self, changes: list[Change]) -> None:
        """Mengembalikan hostname lama yang tercatat pada changes."""
        for change in changes:
            if change.target == "hostname" and change.before:
                self.runner.run(
                    ["hostnamectl", "set-hostname", change.before],
                    mutates=True,
                )
