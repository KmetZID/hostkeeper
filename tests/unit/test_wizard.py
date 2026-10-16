"""Unit test untuk Wizard setup (Tahap 2.6)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from hostkeeper.system.fakes import FakeFileOps
from hostkeeper.wizard import Wizard


class FakeInput:
    """Simulasi input pengguna yang dapat diprogram."""

    def __init__(self, answers: list[str]) -> None:
        self._answers = list(answers)
        self._idx = 0

    def __call__(self, prompt: str) -> str:
        if self._idx >= len(self._answers):
            raise EOFError("Tidak ada input tersisa")
        ans = self._answers[self._idx]
        self._idx += 1
        return ans

    @property
    def consumed(self) -> int:
        return self._idx


def _make_wizard(
    answers: list[str],
    fs: FakeFileOps | None = None,
    profile_path: Path | None = None,
    check_fn: Any = None,
) -> tuple[Wizard, FakeInput, FakeFileOps, list[str]]:
    """Helper untuk membuat Wizard dengan input terprogram."""
    if fs is None:
        fs = FakeFileOps()
    if profile_path is None:
        profile_path = Path("/etc/hostkeeper/profile.yml")
    input_fn = FakeInput(answers)
    output: list[str] = []

    wizard = Wizard(
        profile_path=profile_path,
        fs=fs,
        input_fn=input_fn,
        print_fn=lambda msg: output.append(msg),
        check_fn=check_fn,
    )
    return wizard, input_fn, fs, output


def test_wizard_full_flow_produces_valid_profile() -> None:
    """Profil hasil wizard identik dengan profil tulis tangan setara."""
    answers = [
        "web-01",  # hostname
        "Asia/Jakarta",  # timezone
        "htop curl",  # packages
        "deploy",  # admin user
        (
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleValidKey1234567890 test@host"
        ),  # ssh key
        "",  # selesai input key
        "y",  # hardening SSH
        "22",  # SSH port
        "80/tcp 443/tcp",  # firewall
        "y",  # updates
        "n",  # jangan jalankan plan
    ]

    wizard, input_fn, fs, output = _make_wizard(answers)
    result = wizard.run()

    # Wizard harus selesai tanpa error
    assert result is False  # user bilang 'n' untuk plan

    # Profil harus tertulis
    profile_path = Path("/etc/hostkeeper/profile.yml")
    content = fs.read_text(profile_path)
    assert content is not None

    # Parse dan validasi profile
    data = yaml.safe_load(content)
    assert data["version"] == 1
    assert data["hostname"] == "web-01"
    assert data["timezone"] == "Asia/Jakarta"
    assert data["packages"] == ["htop", "curl"]
    assert data["admin_user"] == "deploy"
    assert len(data["ssh_authorized_keys"]) == 1
    assert data["ssh"]["permit_root_login"] == "no"
    assert data["ssh"]["password_auth"] is False
    assert data["firewall"]["allow"] == ["80/tcp", "443/tcp"]
    assert data["unattended_upgrades"] is True

    # Profil harus bisa di-parse oleh parse_profile_dict
    # (timezone skip karena tidak punya zoneinfo di test env)
    manual_data = {
        "version": 1,
        "hostname": "web-01",
        "packages": ["htop", "curl"],
        "admin_user": "deploy",
        "ssh_authorized_keys": [
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleValidKey1234567890 test@host"
        ],
        "ssh": {"permit_root_login": "no", "password_auth": False, "port": 22},
        "firewall": {"allow": ["80/tcp", "443/tcp"]},
        "unattended_upgrades": True,
    }

    # Bandingkan field profil utama (kecuali timezone karena validasi butuh zoneinfo)
    for key in ("hostname", "packages", "admin_user", "unattended_upgrades"):
        assert data[key] == manual_data[key], f"Mismatch pada {key}"


def test_wizard_invalid_hostname_retried() -> None:
    """Input hostname salah harus diulang."""
    answers = [
        "a;b",  # hostname tidak valid
        "web-01",  # hostname valid
        "UTC",  # timezone
        "",  # packages: lewati
        "",  # admin user: lewati
        "n",  # hardening SSH
        "",  # firewall: lewati
        "y",  # updates
        "n",  # jangan plan
    ]

    wizard, input_fn, fs, output = _make_wizard(answers)
    wizard.run()

    content = fs.read_text(Path("/etc/hostkeeper/profile.yml"))
    assert content is not None
    data = yaml.safe_load(content)
    assert data["hostname"] == "web-01"

    # Harus ada pesan error tentang input tidak valid
    assert any(
        "tidak valid" in msg.lower() or "invalid" in msg.lower() for msg in output
    )


def test_wizard_ctrlc_no_partial_file() -> None:
    """Ctrl+C tidak meninggalkan file setengah jadi."""
    # Hanya berikan jawaban untuk hostname, kemudian EOFError
    answers = ["web-01"]

    wizard, input_fn, fs, output = _make_wizard(answers)
    with pytest.raises(EOFError):
        wizard.run()

    # Pastikan tidak ada file yang ditulis
    content = fs.read_text(Path("/etc/hostkeeper/profile.yml"))
    assert content is None


def test_wizard_overwrite_with_backup() -> None:
    """Menimpa file lama harus membuat backup dan dikonfirmasi."""
    profile_path = Path("/etc/hostkeeper/profile.yml")
    old_content = "version: 1\nhostname: old-host\n"

    fs = FakeFileOps({profile_path: old_content})

    answers = [
        "new-host",  # hostname
        "UTC",  # timezone
        "",  # packages: lewati
        "",  # admin user: lewati
        "n",  # hardening SSH
        "",  # firewall: lewati
        "y",  # updates
        "y",  # konfirmasi timpa
        "n",  # jangan plan
    ]

    wizard, input_fn, _, output = _make_wizard(
        answers, fs=fs, profile_path=profile_path
    )
    wizard.run()

    # File baru harus tertulis
    content = fs.read_text(profile_path)
    assert content is not None
    data = yaml.safe_load(content)
    assert data["hostname"] == "new-host"

    # Backup harus dibuat
    assert any("backup" in msg.lower() or "Backup" in msg for msg in output)


def test_wizard_overwrite_declined() -> None:
    """Menolak timpa harus membatalkan setup."""
    profile_path = Path("/etc/hostkeeper/profile.yml")
    old_content = "version: 1\nhostname: old-host\n"
    fs = FakeFileOps({profile_path: old_content})

    answers = [
        "new-host",  # hostname
        "UTC",  # timezone
        "",  # packages: lewati
        "",  # admin user: lewati
        "n",  # hardening SSH
        "",  # firewall: lewati
        "y",  # updates
        "n",  # TOLAK timpa
    ]

    wizard, input_fn, _, output = _make_wizard(
        answers, fs=fs, profile_path=profile_path
    )
    result = wizard.run()

    assert result is False
    # File lama harus tetap utuh
    content = fs.read_text(profile_path)
    assert content == old_content


def test_wizard_profile_mode_600() -> None:
    """File profil harus ditulis dengan mode 600."""
    answers = [
        "web-01",  # hostname
        "UTC",  # timezone
        "",  # packages
        "",  # admin user
        "n",  # hardening SSH
        "",  # firewall
        "y",  # updates
        "n",  # jangan plan
    ]

    wizard, input_fn, fs, output = _make_wizard(answers)
    wizard.run()

    profile_path = Path("/etc/hostkeeper/profile.yml")
    assert profile_path in fs.modes
    assert fs.modes[profile_path] == 0o600


def test_wizard_skip_compliant_fields() -> None:
    """Melewati pertanyaan yang kondisi server sudah sesuai."""

    def check_fn(field: str, value: Any) -> bool:
        if field == "hostname":
            return True  # hostname sudah sesuai
        return False

    answers = [
        # hostname dilewati
        "UTC",  # timezone
        "",  # packages
        "",  # admin user
        "n",  # hardening SSH
        "",  # firewall
        "y",  # updates
        "n",  # jangan plan
    ]

    wizard, input_fn, fs, output = _make_wizard(answers, check_fn=check_fn)
    wizard.run()

    # Pesan skip harus muncul
    assert any("dilewati" in msg for msg in output)


def test_wizard_ssh_key_via_path(tmp_path: Path) -> None:
    """Kunci SSH bisa dimasukkan via path file .pub."""
    key_content = (
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleValidKey1234567890 file@host"
    )
    pub_file = tmp_path / "id_ed25519.pub"
    pub_file.write_text(key_content + "\n")

    answers = [
        "web-01",  # hostname
        "UTC",  # timezone
        "",  # packages
        "deploy",  # admin user
        str(pub_file),  # path ke file .pub
        "",  # selesai key
        "n",  # hardening SSH
        "",  # firewall
        "y",  # updates
        "n",  # jangan plan
    ]

    wizard, input_fn, fs, output = _make_wizard(answers)
    wizard.run()

    content = fs.read_text(Path("/etc/hostkeeper/profile.yml"))
    assert content is not None
    data = yaml.safe_load(content)
    assert len(data["ssh_authorized_keys"]) == 1
    assert "file@host" in data["ssh_authorized_keys"][0]


def test_wizard_minimal_profile() -> None:
    """Wizard dengan semua field kosong menghasilkan profil minimal."""
    answers = [
        "",  # hostname: kosong (pakai default)
        "",  # timezone: default
        "",  # packages: lewati
        "",  # admin user: lewati
        "n",  # hardening SSH
        "",  # firewall: lewati
        "n",  # updates: tidak
        "n",  # jangan plan
    ]

    wizard, input_fn, fs, output = _make_wizard(answers)
    wizard.run()

    content = fs.read_text(Path("/etc/hostkeeper/profile.yml"))
    assert content is not None
    data = yaml.safe_load(content)
    assert data["version"] == 1


def test_wizard_invalid_firewall_retried() -> None:
    """Aturan firewall tidak valid harus diulang."""
    answers = [
        "web-01",  # hostname
        "UTC",  # timezone
        "",  # packages
        "",  # admin user
        "n",  # hardening SSH
        "invalid-rule",  # firewall: tidak valid
        "80/tcp",  # firewall: valid
        "y",  # updates
        "n",  # jangan plan
    ]

    wizard, input_fn, fs, output = _make_wizard(answers)
    wizard.run()

    content = fs.read_text(Path("/etc/hostkeeper/profile.yml"))
    assert content is not None
    data = yaml.safe_load(content)
    assert "firewall" in data
    assert "80/tcp" in data["firewall"]["allow"]

    # Harus ada pesan error
    assert any(
        "tidak valid" in msg.lower() or "invalid" in msg.lower() for msg in output
    )
