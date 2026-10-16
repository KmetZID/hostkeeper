"""Unit test untuk FirewallStep (Tahap 2.5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hostkeeper.engine.step import Change, Risk
from hostkeeper.profile import Profile
from hostkeeper.steps.firewall import FirewallStep
from hostkeeper.system.fakes import FakeFileOps, FakeRunner


def test_firewall_step_metadata() -> None:
    step = FirewallStep(Profile(), FakeRunner(), FakeFileOps())
    assert step.name == "firewall"
    assert step.risk == Risk.HIGH
    assert step.requires == ("sshd",)
    assert step.reversible is True


def test_firewall_step_disabled_when_none() -> None:
    step = FirewallStep(Profile(), FakeRunner(), FakeFileOps())
    assert step.enabled() is False


def test_firewall_step_rejects_when_ufw_or_firewalld_active() -> None:
    profile = Profile(firewall={"allow": ("80/tcp",)})
    runner = FakeRunner(
        {
            ("systemctl", "is-active", "ufw"): "active\n",
        }
    )
    step = FirewallStep(profile, runner, FakeFileOps())
    with pytest.raises(RuntimeError, match="ufw aktif"):
        step.apply(
            [
                Change(
                    step="firewall",
                    action="write",
                    target="fw",
                    before=None,
                    after="",
                )
            ]
        )


def test_firewall_step_always_includes_effective_ssh_port() -> None:
    # Port SSH diubah ke 2222 pada profil
    profile = Profile(
        ssh={"port": 2222},
        firewall={"allow": ("80/tcp", "443/tcp", "53/udp")},
    )
    ruleset = FirewallStep.generate_ruleset(profile)
    # Port SSH 2222 WAJIB ada di ruleset walau allow hanya ada 80, 443, 53
    assert "2222" in ruleset
    assert "80" in ruleset
    assert "443" in ruleset
    assert "53" in ruleset
    assert "table inet hostkeeper" in ruleset
    assert "policy drop" in ruleset


def test_firewall_step_invalid_ruleset_rejected() -> None:
    profile = Profile(firewall={"allow": ("80/tcp",)})
    runner = FakeRunner(
        {
            ("systemctl", "is-active", "ufw"): ("inactive\n", 3, "inactive"),
            ("systemctl", "is-active", "firewalld"): ("inactive\n", 3, "inactive"),
            ("dpkg-query", "-W", "-f=${Package} ${Status}\\n", "nftables"): (
                "nftables install ok installed\n"
            ),
        }
    )
    runner.register(["systemctl", "is-active", "ufw"], "", returncode=3)
    runner.register(["systemctl", "is-active", "firewalld"], "", returncode=3)
    runner.register(
        ["nft", "-c", "-f", "/etc/hostkeeper/firewall.nft"],
        "",
        returncode=1,
        stderr="syntax error",
    )

    fs = FakeFileOps()
    step = FirewallStep(profile, runner, fs)

    changes = [
        Change(
            step="firewall",
            action="write",
            target="/etc/hostkeeper/firewall.nft",
            before=None,
            after="INVALID RULESET\n",
        )
    ]
    with pytest.raises(RuntimeError, match="Validasi nft -c gagal"):
        step.apply(changes)

    # File ruleset asli tidak boleh diterapkan jika validasi nft -c gagal
    assert not any("nft -f" in " ".join(c.argv) for c in runner.calls)


def test_firewall_step_undo_only_deletes_own_table() -> None:
    profile = Profile(firewall={"allow": ("80/tcp",)})
    runner = FakeRunner(
        {
            ("nft", "delete", "table", "inet", "hostkeeper"): "",
            ("systemctl", "stop", "hostkeeper-firewall.service"): "",
            ("systemctl", "disable", "hostkeeper-firewall.service"): "",
            ("systemctl", "daemon-reload"): "",
        }
    )
    service_path = Path("/etc/systemd/system/hostkeeper-firewall.service")
    nft_path = Path("/etc/hostkeeper/firewall.nft")
    fs = FakeFileOps({service_path: "unit", nft_path: "rules"})

    step = FirewallStep(profile, runner, fs)
    changes = [
        Change(
            step="firewall",
            action="write",
            target=str(nft_path),
            before=None,
            after="rules",
        )
    ]
    step.undo(changes)

    # Memastikan nft delete table inet hostkeeper dipanggil
    assert any(
        c.argv == ("nft", "delete", "table", "inet", "hostkeeper") for c in runner.calls
    )
    # File service dan ruleset dihapus
    assert fs.read_text(service_path) is None
    assert fs.read_text(nft_path) is None
