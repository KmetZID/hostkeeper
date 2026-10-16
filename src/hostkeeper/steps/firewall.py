"""Step konfigurasi firewall nftables (Tahap 2.5)."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from hostkeeper.engine.step import Change, CheckResult, Risk, Step
from hostkeeper.profile import Profile
from hostkeeper.system.fileops import FileOps
from hostkeeper.system.runner import Runner

_NFT_RULESET_PATH = Path("/etc/hostkeeper/firewall.nft")
_SERVICE_PATH = Path("/etc/systemd/system/hostkeeper-firewall.service")

_SERVICE_CONTENT = """\
[Unit]
Description=hostkeeper nftables firewall
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/nft -f /etc/hostkeeper/firewall.nft
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""


class FirewallStep(Step):
    """Mengelola firewall nftables dengan tabel inet hostkeeper."""

    name: ClassVar[str] = "firewall"
    risk: ClassVar[Risk] = Risk.HIGH
    requires: ClassVar[tuple[str, ...]] = ("sshd",)
    reversible: ClassVar[bool] = True

    def __init__(
        self,
        profile: Profile,
        runner: Runner,
        fs: FileOps,
    ) -> None:
        super().__init__(profile, runner, fs)

    def enabled(self) -> bool:
        return self.profile.firewall is not None

    def _get_effective_ssh_port(self) -> int:
        """Ambil port SSH efektif dari profil."""
        if self.profile.ssh and "port" in self.profile.ssh:
            return int(self.profile.ssh["port"])
        return 22

    def _check_conflicting_firewall(self) -> str | None:
        """Kembalikan nama firewall yang konflik, atau None."""
        for svc in ("ufw", "firewalld"):
            res = self.runner.run(["systemctl", "is-active", svc], mutates=False)
            if res.ok and res.stdout.strip() == "active":
                return svc
        return None

    def _is_nftables_installed(self) -> bool:
        res = self.runner.run(
            ["dpkg-query", "-W", "-f=${Package} ${Status}\\n", "nftables"],
            mutates=False,
        )
        return res.ok and "install ok installed" in res.stdout

    @staticmethod
    def generate_ruleset(profile: Profile) -> str:
        """Buat ruleset nftables untuk profil."""
        ssh_port = 22
        if profile.ssh and "port" in profile.ssh:
            ssh_port = int(profile.ssh["port"])

        allow_rules: list[str] = []
        if profile.firewall and "allow" in profile.firewall:
            allow_rules = list(profile.firewall["allow"])

        # Kumpulkan port TCP dan UDP
        tcp_ports: list[int] = []
        udp_ports: list[int] = []

        # SSH port SELALU disertakan
        tcp_ports.append(ssh_port)

        for rule in allow_rules:
            parts = rule.split("/")
            port = int(parts[0])
            proto = parts[1]
            if proto == "tcp":
                if port not in tcp_ports:
                    tcp_ports.append(port)
            elif proto == "udp":
                if port not in udp_ports:
                    udp_ports.append(port)

        lines = [
            "#!/usr/sbin/nft -f",
            "",
            "# Hapus tabel lama jika ada",
            "delete table inet hostkeeper",
            "",
            "table inet hostkeeper {",
            "    chain input {",
            "        type filter hook input priority 0; policy drop;",
            "",
            "        # Koneksi yang sudah terbentuk",
            "        ct state established,related accept",
            "",
            "        # Loopback",
            "        iif lo accept",
            "",
            "        # ICMP",
            "        ip protocol icmp accept",
            "        ip6 nexthdr icmpv6 accept",
        ]

        # Port TCP
        if tcp_ports:
            port_str = ", ".join(str(p) for p in sorted(set(tcp_ports)))
            lines.append("")
            lines.append("        # Port TCP yang diizinkan")
            lines.append(f"        tcp dport {{ {port_str} }} accept")

        # Port UDP
        if udp_ports:
            port_str = ", ".join(str(p) for p in sorted(set(udp_ports)))
            lines.append("")
            lines.append("        # Port UDP yang diizinkan")
            lines.append(f"        udp dport {{ {port_str} }} accept")

        lines.append("    }")
        lines.append("}")
        lines.append("")

        return "\n".join(lines)

    def check(self) -> CheckResult:
        if not self.enabled():
            return CheckResult(compliant=True, current="tidak dikonfigurasi")

        expected = self.generate_ruleset(self.profile)
        current = self.fs.read_text(_NFT_RULESET_PATH)
        service_content = self.fs.read_text(_SERVICE_PATH)

        issues: list[str] = []
        if current != expected:
            issues.append("ruleset belum sesuai")
        if service_content != _SERVICE_CONTENT:
            issues.append("service belum terpasang")

        compliant = len(issues) == 0
        desc = "aktif dan sesuai" if compliant else "; ".join(issues)
        return CheckResult(compliant=compliant, current=desc, detail=desc)

    def plan(self) -> list[Change]:
        if not self.enabled():
            return []

        chk = self.check()
        if chk.compliant:
            return []

        changes: list[Change] = []

        # Cek paket nftables
        if not self._is_nftables_installed():
            changes.append(
                Change(
                    step=self.name,
                    action="install",
                    target="pkg:nftables",
                    before=None,
                    after="nftables",
                )
            )

        expected = self.generate_ruleset(self.profile)
        current = self.fs.read_text(_NFT_RULESET_PATH)
        if current != expected:
            changes.append(
                Change(
                    step=self.name,
                    action="write",
                    target=str(_NFT_RULESET_PATH),
                    before=current,
                    after=expected,
                )
            )

        service_content = self.fs.read_text(_SERVICE_PATH)
        if service_content != _SERVICE_CONTENT:
            changes.append(
                Change(
                    step=self.name,
                    action="write",
                    target=str(_SERVICE_PATH),
                    before=service_content,
                    after=_SERVICE_CONTENT,
                )
            )

        return changes

    def apply(self, changes: list[Change]) -> None:
        # 1. Tolak jika ufw atau firewalld aktif
        conflict = self._check_conflicting_firewall()
        if conflict is not None:
            raise RuntimeError(
                f"{conflict} aktif. Nonaktifkan terlebih dahulu sebelum "
                "menggunakan firewall hostkeeper."
            )

        # 2. Pasang nftables jika belum terpasang
        for ch in changes:
            if ch.action == "install" and ch.target == "pkg:nftables":
                res = self.runner.run(
                    [
                        "apt-get",
                        "install",
                        "-y",
                        "--no-install-recommends",
                        "nftables",
                    ],
                    mutates=True,
                )
                if not res.ok:
                    raise RuntimeError(f"Gagal memasang nftables: {res.stderr.strip()}")

        # 3. Tulis ruleset
        expected = self.generate_ruleset(self.profile)
        self.fs.write_atomic(_NFT_RULESET_PATH, expected, mode=0o644)

        # 4. Validasi dengan nft -c -f
        check_res = self.runner.run(
            ["nft", "-c", "-f", str(_NFT_RULESET_PATH)], mutates=False
        )
        if not check_res.ok:
            self.fs.remove(_NFT_RULESET_PATH)
            raise RuntimeError(f"Validasi nft -c gagal: {check_res.stderr.strip()}")

        # 5. Terapkan ruleset
        apply_res = self.runner.run(["nft", "-f", str(_NFT_RULESET_PATH)], mutates=True)
        if not apply_res.ok:
            self.fs.remove(_NFT_RULESET_PATH)
            raise RuntimeError(f"nft -f gagal: {apply_res.stderr.strip()}")

        # 6. Tulis dan aktifkan service persistensi
        self.fs.write_atomic(_SERVICE_PATH, _SERVICE_CONTENT, mode=0o644)
        self.runner.run(["systemctl", "daemon-reload"], mutates=True)
        self.runner.run(
            ["systemctl", "enable", "hostkeeper-firewall.service"],
            mutates=True,
        )

    def verify(self) -> CheckResult:
        return self.check()

    def undo(self, changes: list[Change]) -> None:
        # Hapus tabel nft milik sendiri
        self.runner.run(["nft", "delete", "table", "inet", "hostkeeper"], mutates=True)

        # Nonaktifkan dan hapus service
        self.runner.run(
            ["systemctl", "stop", "hostkeeper-firewall.service"],
            mutates=True,
        )
        self.runner.run(
            ["systemctl", "disable", "hostkeeper-firewall.service"],
            mutates=True,
        )
        self.runner.run(["systemctl", "daemon-reload"], mutates=True)

        # Hapus file
        self.fs.remove(_SERVICE_PATH)
        self.fs.remove(_NFT_RULESET_PATH)
