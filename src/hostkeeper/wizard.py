"""Wizard interaktif setup profil (Tahap 2.6)."""

from __future__ import annotations

import datetime
import socket
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any

import yaml

from hostkeeper import messages
from hostkeeper.profile import (
    ProfileValidationError,
    validate_admin_user,
    validate_firewall,
    validate_hostname,
    validate_packages,
    validate_ssh,
    validate_ssh_authorized_keys,
)
from hostkeeper.system.fileops import FileOps


def _to_yaml_safe(obj: Any) -> Any:
    """Konversi tuple ke list secara rekursif agar yaml.safe_load bisa membaca."""
    if isinstance(obj, dict):
        return {k: _to_yaml_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_yaml_safe(item) for item in obj]
    return obj


class Wizard:
    """Wizard interaktif untuk membuat profil hostkeeper.

    Fungsi input diinjeksi agar bisa dites.
    """

    def __init__(
        self,
        profile_path: Path,
        fs: FileOps,
        input_fn: Callable[[str], str] | None = None,
        print_fn: Callable[[str], None] | None = None,
        out: IO[str] | None = None,
        check_fn: Callable[[str, Any], bool] | None = None,
    ) -> None:
        self.profile_path = profile_path
        self.fs = fs
        self.input_fn = input_fn if input_fn is not None else input
        self._print_fn = print_fn
        self._out = out
        self._check_fn = check_fn

    def _print(self, msg: str) -> None:
        if self._print_fn is not None:
            self._print_fn(msg)
        elif self._out is not None:
            print(msg, file=self._out)
        else:
            print(msg)

    def _prompt(self, prompt: str) -> str:
        return self.input_fn(prompt)

    def _prompt_with_retry(
        self,
        prompt: str,
        validator: Callable[[str], Any],
        allow_empty: bool = False,
    ) -> str | None:
        """Mengulang prompt hingga validasi berhasil."""
        while True:
            answer = self._prompt(prompt).strip()
            if allow_empty and not answer:
                return None
            if not answer:
                continue
            try:
                validator(answer)
                return answer
            except (ProfileValidationError, ValueError) as exc:
                self._print(messages.WIZARD_INVALID_INPUT.format(detail=str(exc)))

    def _is_compliant(self, field: str, value: Any) -> bool:
        """Cek apakah field sudah sesuai dengan kondisi server."""
        if self._check_fn is not None:
            return self._check_fn(field, value)
        return False

    def _prompt_hostname(self) -> str | None:
        default = ""
        try:
            default = socket.gethostname()
        except OSError:
            pass

        if default and self._is_compliant("hostname", default):
            self._print(messages.WIZARD_SKIP_COMPLIANT.format(field="hostname"))
            return default

        prompt = messages.WIZARD_PROMPT_HOSTNAME.format(default=default)
        answer = self._prompt_with_retry(prompt, validate_hostname, allow_empty=True)
        return answer if answer else (default or None)

    def _prompt_timezone(self) -> str | None:
        default = "UTC"
        tz_link = Path("/etc/localtime")
        if tz_link.is_symlink():
            target = str(tz_link.resolve())
            zi = "/usr/share/zoneinfo/"
            if zi in target:
                default = target[target.index(zi) + len(zi) :]

        if default and self._is_compliant("timezone", default):
            self._print(messages.WIZARD_SKIP_COMPLIANT.format(field="timezone"))
            return default

        prompt = messages.WIZARD_PROMPT_TIMEZONE.format(default=default)
        answer = self._prompt(prompt).strip()
        return answer if answer else default

    def _prompt_packages(self) -> list[str]:
        default = ""
        prompt = messages.WIZARD_PROMPT_PACKAGES.format(default=default)
        answer = self._prompt(prompt).strip()
        if not answer:
            return []

        pkgs = answer.split()
        try:
            validate_packages(pkgs)
        except ProfileValidationError as exc:
            self._print(messages.WIZARD_INVALID_INPUT.format(detail=str(exc)))
            return self._prompt_packages()
        return pkgs

    def _prompt_admin_user(self) -> str | None:
        default = ""
        prompt = messages.WIZARD_PROMPT_ADMIN_USER.format(default=default)
        answer = self._prompt(prompt).strip()
        if not answer:
            return None

        try:
            validate_admin_user(answer)
        except ProfileValidationError as exc:
            self._print(messages.WIZARD_INVALID_INPUT.format(detail=str(exc)))
            return self._prompt_admin_user()
        return answer

    def _prompt_ssh_keys(self) -> list[str]:
        keys: list[str] = []
        while True:
            prompt = messages.WIZARD_PROMPT_SSH_KEY
            answer = self._prompt(prompt).strip()
            if not answer:
                break

            # Bisa berupa path ke file .pub
            key_path = Path(answer)
            if key_path.is_file() and answer.endswith(".pub"):
                key_content = key_path.read_text().strip()
                if key_content:
                    answer = key_content

            try:
                validate_ssh_authorized_keys([answer])
                keys.append(answer)
            except ProfileValidationError as exc:
                self._print(messages.WIZARD_INVALID_INPUT.format(detail=str(exc)))

        return keys

    def _prompt_ssh_hardening(self) -> dict[str, Any] | None:
        prompt = messages.WIZARD_PROMPT_SSH_HARDEN
        answer = self._prompt(prompt).strip().lower()
        if answer not in ("y", "yes", "ya"):
            return None

        ssh_conf: dict[str, Any] = {
            "permit_root_login": "no",
            "password_auth": False,
        }

        port_prompt = messages.WIZARD_PROMPT_SSH_PORT.format(default="22")
        port_answer = self._prompt(port_prompt).strip()
        if port_answer:
            try:
                port = int(port_answer)
                validate_ssh({"port": port})
                ssh_conf["port"] = port
            except (ValueError, ProfileValidationError) as exc:
                self._print(messages.WIZARD_INVALID_INPUT.format(detail=str(exc)))

        return ssh_conf

    def _prompt_firewall(self) -> dict[str, Any] | None:
        default = ""
        prompt = messages.WIZARD_PROMPT_FIREWALL_PORTS.format(default=default)
        answer = self._prompt(prompt).strip()
        if not answer:
            return None

        rules = answer.split()
        try:
            validated = validate_firewall({"allow": rules})
            return validated
        except ProfileValidationError as exc:
            self._print(messages.WIZARD_INVALID_INPUT.format(detail=str(exc)))
            return self._prompt_firewall()

    def _prompt_updates(self) -> bool | None:
        prompt = messages.WIZARD_PROMPT_UPDATES
        answer = self._prompt(prompt).strip().lower()
        if answer in ("", "y", "yes", "ya"):
            return True
        if answer in ("n", "no", "tidak"):
            return None
        return True

    def _build_profile_dict(self) -> dict[str, Any]:
        """Melalui pertanyaan berurutan dan membangun dict profil."""
        data: dict[str, Any] = {"version": 1}

        hostname = self._prompt_hostname()
        if hostname:
            data["hostname"] = hostname

        timezone = self._prompt_timezone()
        if timezone:
            data["timezone"] = timezone

        packages = self._prompt_packages()
        if packages:
            data["packages"] = packages

        admin_user = self._prompt_admin_user()
        if admin_user:
            data["admin_user"] = admin_user

            keys = self._prompt_ssh_keys()
            if keys:
                data["ssh_authorized_keys"] = keys

        ssh_conf = self._prompt_ssh_hardening()
        if ssh_conf:
            data["ssh"] = ssh_conf

        firewall = self._prompt_firewall()
        if firewall:
            data["firewall"] = firewall

        updates = self._prompt_updates()
        if updates is not None:
            data["unattended_upgrades"] = updates

        return data

    def _write_profile(self, data: dict[str, Any]) -> bool:
        """Menulis profil ke file. Menimpa hanya dengan konfirmasi dan backup."""
        # Konversi tuple ke list agar yaml.safe_load bisa membaca kembali
        safe_data = _to_yaml_safe(data)
        existing = self.fs.read_text(self.profile_path)
        if existing is not None:
            prompt = messages.WIZARD_PROMPT_OVERWRITE.format(path=self.profile_path)
            answer = self._prompt(prompt).strip().lower()
            if answer not in ("y", "yes", "ya"):
                self._print(messages.WIZARD_CANCELLED)
                return False

            # Backup file lama
            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            backup_path = self.profile_path.with_suffix(f".{ts}.bak")
            self.fs.write_atomic(backup_path, existing, mode=0o600)
            self._print(messages.WIZARD_BACKUP_CREATED.format(path=backup_path))

        yaml_content = yaml.dump(
            safe_data,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        self.fs.write_atomic(self.profile_path, yaml_content, mode=0o600)
        self._print(messages.WIZARD_PROFILE_WRITTEN.format(path=self.profile_path))
        return True

    def run(self) -> bool:
        """Menjalankan wizard. Mengembalikan True jika profil berhasil ditulis."""
        self._print(messages.WIZARD_WELCOME)

        data = self._build_profile_dict()
        written = self._write_profile(data)
        if not written:
            return False

        # Tawarkan menjalankan plan (TIDAK pernah apply)
        prompt = messages.WIZARD_PROMPT_RUN_PLAN
        answer = self._prompt(prompt).strip().lower()
        return answer in ("", "y", "yes", "ya")
