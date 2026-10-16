"""Step hardening SSHD dengan gerbang anti-terkunci (Tahap 2.3)."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

from hostkeeper.engine.step import Change, CheckResult, Risk, Step
from hostkeeper.profile import Profile
from hostkeeper.system.fileops import FileOps
from hostkeeper.system.runner import Runner


class SshdStep(Step):
    """Mengonfigurasi drop-in sshd dengan perlindungan anti-terkunci."""

    name: ClassVar[str] = "sshd"
    risk: ClassVar[Risk] = Risk.HIGH
    requires: ClassVar[tuple[str, ...]] = ("user", "sshkeys")
    reversible: ClassVar[bool] = True

    DROP_IN_PATH: Path = Path("/etc/ssh/sshd_config.d/00-hostkeeper.conf")

    def __init__(
        self,
        profile: Profile,
        runner: Runner,
        fs: FileOps,
        confirm_fn: Callable[[str], str] | None = None,
        bypass_human_gate: bool = False,
    ) -> None:
        super().__init__(profile, runner, fs)
        self.confirm_fn = confirm_fn if confirm_fn is not None else input
        self.bypass_human_gate = bypass_human_gate

    def enabled(self) -> bool:
        return self.profile.ssh is not None

    def _check_socket_active(self) -> bool:
        res = self.runner.run(["systemctl", "is-active", "ssh.socket"], mutates=False)
        return res.ok and res.stdout.strip() == "active"

    def _get_user_home(self, user: str) -> Path:
        res = self.runner.run(["getent", "passwd", user], mutates=False)
        if res.ok and res.stdout.strip():
            parts = res.stdout.strip().split(":")
            if len(parts) >= 6 and parts[5]:
                return Path(parts[5])
        return Path(f"/home/{user}")

    def _parse_sshd_effective(self) -> dict[str, str]:
        res = self.runner.run(["sshd", "-T"], mutates=False)
        if not res.ok:
            return {}
        cfg: dict[str, str] = {}
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line or " " not in line:
                continue
            key, val = line.split(" ", 1)
            cfg[key.lower()] = val.strip()
        return cfg

    def _build_dropin_content(self) -> str:
        if not self.profile.ssh:
            return ""
        lines = ["# Konfigurasi SSH dikelola oleh hostkeeper"]
        if "port" in self.profile.ssh:
            lines.append(f"Port {self.profile.ssh['port']}")
        if "permit_root_login" in self.profile.ssh:
            lines.append(f"PermitRootLogin {self.profile.ssh['permit_root_login']}")
        if "password_auth" in self.profile.ssh:
            pwa = "yes" if self.profile.ssh["password_auth"] else "no"
            lines.append(f"PasswordAuthentication {pwa}")
        return "\n".join(lines) + "\n"

    def check(self) -> CheckResult:
        if not self.profile.ssh:
            return CheckResult(compliant=True, current="tidak dikonfigurasi")

        effective = self._parse_sshd_effective()
        drifts: list[str] = []

        if "port" in self.profile.ssh:
            expected_port = str(self.profile.ssh["port"])
            current_port = effective.get("port", "22")
            if current_port != expected_port:
                drifts.append(f"Port: {current_port} != {expected_port}")

        if "permit_root_login" in self.profile.ssh:
            expected_prl = str(self.profile.ssh["permit_root_login"]).lower()
            current_prl = effective.get("permitrootlogin", "").lower()
            if current_prl != expected_prl:
                drifts.append(f"PermitRootLogin: {current_prl} != {expected_prl}")

        if "password_auth" in self.profile.ssh:
            expected_pwa = "yes" if self.profile.ssh["password_auth"] else "no"
            current_pwa = effective.get("passwordauthentication", "").lower()
            if current_pwa != expected_pwa:
                drifts.append(
                    f"PasswordAuthentication: {current_pwa} != {expected_pwa}"
                )

        compliant = len(drifts) == 0
        desc = "sesuai profil" if compliant else "; ".join(drifts)
        return CheckResult(compliant=compliant, current=desc, detail=desc)

    def plan(self) -> list[Change]:
        if not self.profile.ssh:
            return []

        chk = self.check()
        if chk.compliant:
            return []

        current_content = self.fs.read_text(self.DROP_IN_PATH)
        expected_content = self._build_dropin_content()
        return [
            Change(
                step=self.name,
                action="write",
                target=str(self.DROP_IN_PATH),
                before=current_content,
                after=expected_content,
            )
        ]

    def _test_ssh_login_mechanism(self, user: str, port: int) -> bool:
        """Menguji mekanisme login kunci via localhost dengan keypair sementara."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_key = Path(tmp_dir) / "id_hostkeeper_test"
            gen_res = self.runner.run(
                ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(tmp_key)],
                mutates=False,
            )
            if not gen_res.ok:
                return False

            pub_key_path = Path(f"{tmp_key}.pub")
            pub_content = self.fs.read_text(pub_key_path) or ""
            if not pub_content:
                return False

            auth_file = self._get_user_home(user) / ".ssh" / "authorized_keys"
            old_auth = self.fs.read_text(auth_file) or ""

            # Pasang kunci sementara
            temp_auth = (
                f"{old_auth.rstrip()}\n# TEMP hostkeeper\n{pub_content.strip()}\n"
            )
            self.fs.write_atomic(
                auth_file, temp_auth, mode=0o600, owner=user, group=user
            )

            try:
                # Tes login ssh
                ssh_cmd = [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-i",
                    str(tmp_key),
                    "-p",
                    str(port),
                    f"{user}@127.0.0.1",
                    "true",
                ]
                res = self.runner.run(ssh_cmd, mutates=False, timeout=10.0)
                return res.ok
            finally:
                # SELALU hapus kunci sementara dalam finally
                restored_auth = old_auth
                self.fs.write_atomic(
                    auth_file, restored_auth, mode=0o600, owner=user, group=user
                )

    def apply(self, changes: list[Change]) -> None:
        if not self.profile.ssh:
            return

        # 1. Periksa larangan ssh.socket aktif jika port != 22
        target_port = int(self.profile.ssh.get("port", 22))
        if self._check_socket_active() and target_port != 22:
            raise RuntimeError(
                f"Port tidak dapat diubah ke {target_port} karena ssh.socket aktif; "
                "ubah listen port socket terlebih dahulu atau gunakan port 22."
            )

        # 2. Gerbang konfirmasi manusia jika password_auth dimatikan
        if (
            self.profile.ssh.get("password_auth") is False
            and not self.bypass_human_gate
        ):
            prompt = (
                "\nPERINGATAN: Password authentication akan dimatikan.\n"
                "Uji login SSH dengan kunci dari terminal kedua sebelum melanjutkan.\n"
                "Ketik 'ya' untuk melanjutkan: "
            )
            try:
                ans = self.confirm_fn(prompt)
            except (EOFError, KeyboardInterrupt):
                raise RuntimeError("Gerbang anti-terkunci: konfirmasi dibatalkan.")
            if ans.strip().lower() != "ya":
                raise RuntimeError("Gerbang anti-terkunci: konfirmasi dibatalkan.")

        # 3. Tes mekanisme login awal
        user = self.profile.admin_user or "root"
        if not self._test_ssh_login_mechanism(user=user, port=target_port):
            raise RuntimeError(
                "Gerbang anti-terkunci: "
                "uji coba login SSH dengan kunci sementara gagal."
            )

        # 4. Tulis drop-in
        content = self._build_dropin_content()
        self.fs.write_atomic(self.DROP_IN_PATH, content, mode=0o644)

        # 5. sshd -t (gagal = hapus drop-in)
        check_res = self.runner.run(["sshd", "-t"], mutates=False)
        if not check_res.ok:
            self.fs.remove(self.DROP_IN_PATH)
            raise RuntimeError(
                f"Validasi konfigurasi sshd -t gagal: {check_res.stderr.strip()}"
            )

        # 6. Reload ssh (bukan restart)
        reload_res = self.runner.run(["systemctl", "reload", "ssh"], mutates=True)
        if not reload_res.ok:
            self.fs.remove(self.DROP_IN_PATH)
            self.runner.run(["systemctl", "reload", "ssh"], mutates=True)
            raise RuntimeError(
                f"systemctl reload ssh gagal: {reload_res.stderr.strip()}"
            )

        # 7. Tes mekanisme lagi setelah reload
        if not self._test_ssh_login_mechanism(user=user, port=target_port):
            self.fs.remove(self.DROP_IN_PATH)
            self.runner.run(["systemctl", "reload", "ssh"], mutates=True)
            raise RuntimeError(
                "Gerbang anti-terkunci: uji coba login SSH setelah reload gagal."
            )

    def verify(self) -> CheckResult:
        return self.check()

    def undo(self, changes: list[Change]) -> None:
        self.fs.remove(self.DROP_IN_PATH)
        self.runner.run(["systemctl", "reload", "ssh"], mutates=True)
