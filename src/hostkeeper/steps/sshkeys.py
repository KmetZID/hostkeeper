"""Step pengelolaan kunci publik SSH admin (Tahap 2.2)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar

from hostkeeper.engine.step import Change, CheckResult, Risk, Step

BEGIN_MARKER = "# BEGIN hostkeeper"
END_MARKER = "# END hostkeeper"


class SshKeysStep(Step):
    """Memasang kunci publik SSH ke authorized_keys pengguna admin."""

    name: ClassVar[str] = "sshkeys"
    risk: ClassVar[Risk] = Risk.LOW
    requires: ClassVar[tuple[str, ...]] = ("user",)
    reversible: ClassVar[bool] = True

    def enabled(self) -> bool:
        return bool(self.profile.ssh_authorized_keys) and (
            self.profile.admin_user is not None
        )

    def _get_user_home(self, user: str) -> Path:
        res = self.runner.run(["getent", "passwd", user], mutates=False)
        if res.ok and res.stdout.strip():
            parts = res.stdout.strip().split(":")
            if len(parts) >= 6 and parts[5]:
                return Path(parts[5])
        return Path(f"/home/{user}")

    def _auth_keys_path(self, user: str) -> Path:
        return self._get_user_home(user) / ".ssh" / "authorized_keys"

    def _build_block(self, keys: tuple[str, ...]) -> str:
        lines = [BEGIN_MARKER, *keys, END_MARKER]
        return "\n".join(lines) + "\n"

    def _extract_managed_keys(self, content: str) -> tuple[str, ...]:
        pattern = re.compile(
            rf"{re.escape(BEGIN_MARKER)}\n(.*?)\n{re.escape(END_MARKER)}",
            re.DOTALL,
        )
        match = pattern.search(content)
        if not match:
            return ()
        raw_keys = match.group(1).strip()
        if not raw_keys:
            return ()
        return tuple(line.strip() for line in raw_keys.splitlines() if line.strip())

    def _merge_content(self, current: str, block: str) -> str:
        pattern = re.compile(
            rf"{re.escape(BEGIN_MARKER)}\n.*?\n{re.escape(END_MARKER)}\n?",
            re.DOTALL,
        )
        if pattern.search(current):
            return pattern.sub(block, current)

        # Jika belum ada blok, tambahkan di akhir
        trimmed = current.rstrip()
        if not trimmed:
            return block
        return f"{trimmed}\n\n{block}"

    def _strip_block(self, current: str) -> str:
        pattern = re.compile(
            rf"{re.escape(BEGIN_MARKER)}\n.*?\n{re.escape(END_MARKER)}\n?",
            re.DOTALL,
        )
        return pattern.sub("", current).rstrip() + "\n"

    def check(self) -> CheckResult:
        user = self.profile.admin_user
        if not user or not self.profile.ssh_authorized_keys:
            return CheckResult(compliant=True, current="tidak dikonfigurasi")

        auth_path = self._auth_keys_path(user)
        content = self.fs.read_text(auth_path)
        if content is None:
            return CheckResult(
                compliant=False,
                current=f"file {auth_path} belum ada",
                detail="kunci SSH belum dipasang",
            )

        managed = self._extract_managed_keys(content)
        compliant = managed == self.profile.ssh_authorized_keys
        detail = (
            f"{len(managed)} kunci hostkeeper terpasang"
            if compliant
            else "kunci SSH belum sesuai profil"
        )
        return CheckResult(
            compliant=compliant,
            current=f"{len(managed)} kunci" if compliant else "belum sesuai",
            detail=detail,
        )

    def plan(self) -> list[Change]:
        user = self.profile.admin_user
        if not user or not self.profile.ssh_authorized_keys:
            return []

        auth_path = self._auth_keys_path(user)
        content = self.fs.read_text(auth_path) or ""
        managed = self._extract_managed_keys(content)
        if managed == self.profile.ssh_authorized_keys:
            return []

        block = self._build_block(self.profile.ssh_authorized_keys)
        new_content = self._merge_content(content, block)
        return [
            Change(
                step=self.name,
                action="write",
                target=str(auth_path),
                before=content if content else None,
                after=new_content,
            )
        ]

    def apply(self, changes: list[Change]) -> None:
        user = self.profile.admin_user
        if not user:
            return

        ssh_dir = self._get_user_home(user) / ".ssh"
        # Pastikan direktori .ssh ada dengan mode 700 dan kepemilikan user
        res = self.runner.run(
            ["install", "-d", "-m", "700", "-o", user, "-g", user, str(ssh_dir)],
            mutates=True,
        )
        if not res.ok:
            raise RuntimeError(
                f"Gagal menyiapkan direktori '{ssh_dir}': {res.stderr.strip()}"
            )

        auth_path = self._auth_keys_path(user)
        for ch in changes:
            if ch.action == "write" and ch.after is not None:
                self.fs.write_atomic(
                    auth_path,
                    ch.after,
                    mode=0o600,
                    owner=user,
                    group=user,
                )

    def verify(self) -> CheckResult:
        return self.check()

    def undo(self, changes: list[Change]) -> None:
        user = self.profile.admin_user
        if not user:
            return

        auth_path = self._auth_keys_path(user)
        content = self.fs.read_text(auth_path)
        if content is None:
            return

        remaining = self._strip_block(content)
        self.fs.write_atomic(
            auth_path,
            remaining,
            mode=0o600,
            owner=user,
            group=user,
        )
