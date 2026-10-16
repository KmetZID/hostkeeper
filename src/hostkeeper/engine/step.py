"""Abstraksi dan kelas dasar Step serta tipe data eksekusi."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from hostkeeper.profile import Profile
from hostkeeper.system.fileops import FileOps
from hostkeeper.system.runner import Runner


class UnsupportedEnvironmentError(Exception):
    """Lingkungan sistem tidak didukung untuk menjalankan Step (exit code 5)."""


class Risk(str, Enum):
    """Tingkat risiko dari sebuah Step."""

    LOW = "rendah"
    MEDIUM = "sedang"
    HIGH = "tinggi"


@dataclass(frozen=True)
class Change:
    """Deskripsi satu perubahan yang akan dilakukan pada sistem."""

    step: str
    action: str  # 'set' | 'install' | 'write' | 'remove'
    target: str  # mis. 'hostname', 'pkg:htop', '/etc/x'
    before: str | None
    after: str | None


@dataclass(frozen=True)
class CheckResult:
    """Hasil pemeriksaan kondisi sistem oleh Step."""

    compliant: bool
    current: str  # nilai sekarang, untuk ditampilkan
    detail: str = ""


class Step(ABC):
    """Kelas dasar untuk setiap unit konfigurasi sistem."""

    name: ClassVar[str]
    risk: ClassVar[Risk]
    requires: ClassVar[tuple[str, ...]] = ()
    reversible: ClassVar[bool] = True

    def __init__(self, profile: Profile, runner: Runner, fs: FileOps) -> None:
        self.profile = profile
        self.runner = runner
        self.fs = fs

    @abstractmethod
    def enabled(self) -> bool:
        """Mengembalikan True jika profil mengatur bagian ini."""
        ...

    @abstractmethod
    def check(self) -> CheckResult:
        """Pemeriksaan kondisi sistem. Murni hanya membaca."""
        ...

    @abstractmethod
    def plan(self) -> list[Change]:
        """Menghasilkan daftar perubahan. Kosong jika sudah compliant."""
        ...

    @abstractmethod
    def apply(self, changes: list[Change]) -> None:
        """Menerapkan perubahan ke sistem."""
        ...

    def verify(self) -> CheckResult:
        """Default: periksa ulang kondisi sistem setelah apply."""
        return self.check()

    def undo(self, changes: list[Change]) -> None:
        """Mengembalikan perubahan jika Step gagal (hanya yang reversible)."""
        pass
