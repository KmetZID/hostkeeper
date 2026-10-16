"""Step konfigurasi pembaruan keamanan otomatis (Tahap 2.5)."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from hostkeeper.engine.step import Change, CheckResult, Risk, Step

CONFIG_CONTENT = (
    'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
)


class UpdatesStep(Step):
    """Memasang dan mengonfigurasi unattended-upgrades."""

    name: ClassVar[str] = "updates"
    risk: ClassVar[Risk] = Risk.LOW
    requires: ClassVar[tuple[str, ...]] = ()
    reversible: ClassVar[bool] = True

    CONFIG_PATH: Path = Path("/etc/apt/apt.conf.d/20auto-upgrades")

    def enabled(self) -> bool:
        return self.profile.unattended_upgrades is not None

    def _is_package_installed(self) -> bool:
        res = self.runner.run(
            ["dpkg-query", "-W", "-f=${Package} ${Status}\\n", "unattended-upgrades"],
            mutates=False,
        )
        return res.ok and "install ok installed" in res.stdout

    def check(self) -> CheckResult:
        if not self.enabled():
            return CheckResult(compliant=True, current="tidak dikonfigurasi")

        pkg_ok = self._is_package_installed()
        current_cfg = self.fs.read_text(self.CONFIG_PATH)
        cfg_ok = current_cfg == CONFIG_CONTENT

        compliant = pkg_ok and cfg_ok
        details: list[str] = []
        if not pkg_ok:
            details.append("paket unattended-upgrades belum terpasang")
        if not cfg_ok:
            details.append("20auto-upgrades belum sesuai")

        curr_desc = "otomatis aktif" if compliant else "; ".join(details)
        return CheckResult(
            compliant=compliant,
            current=curr_desc,
            detail="; ".join(details),
        )

    def plan(self) -> list[Change]:
        if not self.enabled():
            return []

        changes: list[Change] = []
        if not self._is_package_installed():
            changes.append(
                Change(
                    step=self.name,
                    action="install",
                    target="pkg:unattended-upgrades",
                    before=None,
                    after="unattended-upgrades",
                )
            )

        current_cfg = self.fs.read_text(self.CONFIG_PATH)
        if current_cfg != CONFIG_CONTENT:
            changes.append(
                Change(
                    step=self.name,
                    action="write",
                    target=str(self.CONFIG_PATH),
                    before=current_cfg,
                    after=CONFIG_CONTENT,
                )
            )

        return changes

    def apply(self, changes: list[Change]) -> None:
        for ch in changes:
            if ch.action == "install":
                res = self.runner.run(
                    [
                        "apt-get",
                        "install",
                        "-y",
                        "--no-install-recommends",
                        "unattended-upgrades",
                    ],
                    mutates=True,
                )
                if not res.ok:
                    raise RuntimeError(
                        f"Gagal memasang unattended-upgrades: {res.stderr.strip()}"
                    )
            elif ch.action == "write" and ch.after is not None:
                self.fs.write_atomic(self.CONFIG_PATH, ch.after, mode=0o644)

    def verify(self) -> CheckResult:
        return self.check()

    def undo(self, changes: list[Change]) -> None:
        self.fs.remove(self.CONFIG_PATH)
