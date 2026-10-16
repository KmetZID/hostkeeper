"""Step pembuatan admin user dan konfigurasi sudoers (Tahap 2.2)."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from hostkeeper.engine.step import Change, CheckResult, Risk, Step
from hostkeeper.profile import Profile
from hostkeeper.system.fileops import FileOps
from hostkeeper.system.runner import Runner


class UserStep(Step):
    """Membuat pengguna administratif dan mengatur hak sudo."""

    name: ClassVar[str] = "user"
    risk: ClassVar[Risk] = Risk.LOW
    requires: ClassVar[tuple[str, ...]] = ()
    reversible: ClassVar[bool] = True

    def __init__(self, profile: Profile, runner: Runner, fs: FileOps) -> None:
        super().__init__(profile, runner, fs)
        self._visudo_tmp_file: Path | None = None

    def enabled(self) -> bool:
        return self.profile.admin_user is not None

    def _expected_sudoers_content(self, user: str) -> str:
        if self.profile.admin_sudo_nopasswd:
            return f"{user} ALL=(ALL:ALL) NOPASSWD:ALL\n"
        return f"{user} ALL=(ALL:ALL) ALL\n"

    def _sudoers_path(self, user: str) -> Path:
        return Path(f"/etc/sudoers.d/90-hostkeeper-{user}")

    def check(self) -> CheckResult:
        user = self.profile.admin_user
        if not user:
            return CheckResult(compliant=True, current="tidak dikonfigurasi")

        # 1. Cek keberadaan user
        res = self.runner.run(["id", user], mutates=False)
        user_exists = res.ok

        # 2. Cek keanggotaan grup sudo
        in_sudo = False
        if user_exists:
            res_groups = self.runner.run(["id", "-Gn", user], mutates=False)
            if res_groups.ok:
                in_sudo = "sudo" in res_groups.stdout.split()

        # 3. Cek file sudoers
        sudoers_path = self._sudoers_path(user)
        current_sudoers = self.fs.read_text(sudoers_path)
        expected_sudoers = self._expected_sudoers_content(user)
        sudoers_match = current_sudoers == expected_sudoers

        compliant = user_exists and in_sudo and sudoers_match
        details: list[str] = []
        if not user_exists:
            details.append(f"user '{user}' belum ada")
        elif not in_sudo:
            details.append(f"user '{user}' belum di grup sudo")
        if not sudoers_match:
            details.append("sudoers belum sesuai")

        curr_desc = f"user '{user}' (sudo)" if compliant else "; ".join(details)
        return CheckResult(
            compliant=compliant,
            current=curr_desc,
            detail="; ".join(details),
        )

    def plan(self) -> list[Change]:
        user = self.profile.admin_user
        if not user:
            return []

        changes: list[Change] = []
        res = self.runner.run(["id", user], mutates=False)
        user_exists = res.ok

        if not user_exists:
            changes.append(
                Change(
                    step=self.name,
                    action="create",
                    target=f"user:{user}",
                    before=None,
                    after=user,
                )
            )

        in_sudo = False
        if user_exists:
            res_groups = self.runner.run(["id", "-Gn", user], mutates=False)
            if res_groups.ok:
                in_sudo = "sudo" in res_groups.stdout.split()

        if not in_sudo:
            changes.append(
                Change(
                    step=self.name,
                    action="addgroup",
                    target=f"user:{user}:sudo",
                    before=None,
                    after="sudo",
                )
            )

        sudoers_path = self._sudoers_path(user)
        current_sudoers = self.fs.read_text(sudoers_path)
        expected_sudoers = self._expected_sudoers_content(user)
        if current_sudoers != expected_sudoers:
            changes.append(
                Change(
                    step=self.name,
                    action="write",
                    target=str(sudoers_path),
                    before=current_sudoers,
                    after=expected_sudoers,
                )
            )

        return changes

    def apply(self, changes: list[Change]) -> None:
        user = self.profile.admin_user
        if not user:
            return

        for ch in changes:
            if ch.action == "create":
                res = self.runner.run(
                    ["useradd", "-m", "-s", "/bin/bash", user],
                    mutates=True,
                )
                if not res.ok:
                    raise RuntimeError(
                        f"Gagal membuat user '{user}': {res.stderr.strip()}"
                    )

            elif ch.action == "addgroup":
                res = self.runner.run(
                    ["usermod", "-aG", "sudo", user],
                    mutates=True,
                )
                if not res.ok:
                    raise RuntimeError(
                        f"Gagal menambahkan '{user}' ke grup sudo: {res.stderr.strip()}"
                    )

            elif ch.action == "write" and ch.after is not None:
                # Validasi dengan visudo sebelum menulis ke /etc/sudoers.d
                tmp_path = self._visudo_tmp_file or Path(
                    f"/tmp/.hostkeeper_visudo_{user}.tmp"
                )
                self.fs.write_atomic(tmp_path, ch.after, mode=0o440)
                try:
                    res = self.runner.run(
                        ["visudo", "-cf", str(tmp_path)], mutates=False
                    )
                    if not res.ok:
                        err = res.stderr.strip()
                        raise RuntimeError(
                            f"Validasi visudo gagal untuk konfigurasi sudoers: {err}"
                        )
                    # Jika visudo lolos, pasang ke target
                    self.fs.write_atomic(
                        Path(ch.target),
                        ch.after,
                        mode=0o440,
                        owner="root",
                        group="root",
                    )
                finally:
                    self.fs.remove(tmp_path)

    def verify(self) -> CheckResult:
        return self.check()

    def undo(self, changes: list[Change]) -> None:
        user = self.profile.admin_user
        if not user:
            return

        # Hanya kembalikan file sudoers; user tidak dihapus demi keamanan
        sudoers_path = self._sudoers_path(user)
        for ch in changes:
            if ch.target == str(sudoers_path):
                if ch.before is not None:
                    self.fs.write_atomic(
                        sudoers_path,
                        ch.before,
                        mode=0o440,
                        owner="root",
                        group="root",
                    )
                else:
                    self.fs.remove(sudoers_path)
