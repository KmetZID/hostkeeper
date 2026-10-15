from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from hostkeeper.system.runner import ReadOnlyViolation


@dataclass(frozen=True)
class FileChangeRecord:
    action: str  # "write" | "remove"
    path: Path
    content: str | None = None
    mode: int | None = None
    owner: str = "root"
    group: str = "root"


class FileOps(Protocol):
    def read_text(self, path: Path) -> str | None:
        """Membaca isi file teks. Mengembalikan None jika file tidak ada."""
        ...

    def write_atomic(
        self,
        path: Path,
        content: str,
        *,
        mode: int,
        owner: str = "root",
        group: str = "root",
    ) -> None:
        """Menulis file secara atomik dan membuat backup jika file lama ada."""
        ...

    def remove(self, path: Path) -> None:
        """Menghapus file jika ada."""
        ...


class RealFileOps:
    """Operasi file nyata ke sistem berkas (dipakai saat apply).

    Menulis secara atomik lewat file sementara di direktori yang sama,
    fsync, menetapkan mode dan pemilik, lalu os.replace.
    Jika file lama ada, salin dulu ke backup_dir/<run_id>/<path absolut>.
    """

    def __init__(
        self,
        backup_dir: Path | None = None,
        run_id: str | None = None,
    ) -> None:
        self.backup_dir = backup_dir or Path("/var/lib/hostkeeper/backups")
        self.run_id = run_id
        self.backups: list[tuple[Path, Path]] = []

    def read_text(self, path: Path) -> str | None:
        path = Path(path)
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def write_atomic(
        self,
        path: Path,
        content: str,
        *,
        mode: int,
        owner: str = "root",
        group: str = "root",
    ) -> None:
        path = Path(path)
        parent = path.resolve().parent
        parent.mkdir(parents=True, exist_ok=True)

        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as f:
                tmp_path = Path(f.name)
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            os.chmod(tmp_path, mode)

            # Impor fcntl/pwd/grp hanya di modul yang butuh
            import grp
            import pwd

            if os.geteuid() == 0:
                uid = pwd.getpwnam(owner).pw_uid
                gid = grp.getgrnam(group).gr_gid
                os.chown(tmp_path, uid, gid)
            else:
                try:
                    uid = pwd.getpwnam(owner).pw_uid
                    gid = grp.getgrnam(group).gr_gid
                    os.chown(tmp_path, uid, gid)
                except (PermissionError, KeyError):
                    pass

            if path.exists():
                resolved = path.resolve()
                rel_path = str(resolved).lstrip("/")
                backup_root = (
                    self.backup_dir / self.run_id if self.run_id else self.backup_dir
                )
                backup_dest = backup_root / rel_path
                backup_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, backup_dest)
                self.backups.append((path, backup_dest))

            os.replace(tmp_path, path)
            tmp_path = None
        finally:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def remove(self, path: Path) -> None:
        path = Path(path)
        path.unlink(missing_ok=True)


class RecordingFileOps:
    """FileOps pencatat untuk mode plan.

    Tidak menyentuh disk, hanya mencatat perubahan.
    """

    def __init__(self, base_fs: FileOps | None = None) -> None:
        self.base_fs = base_fs
        self.changes: list[FileChangeRecord] = []
        self._overlay: dict[Path, str] = {}
        self._removed: set[Path] = set()

    def read_text(self, path: Path) -> str | None:
        path = Path(path)
        if path in self._removed:
            return None
        if path in self._overlay:
            return self._overlay[path]
        if self.base_fs is not None:
            return self.base_fs.read_text(path)
        if path.is_file():
            return path.read_text(encoding="utf-8")
        return None

    def write_atomic(
        self,
        path: Path,
        content: str,
        *,
        mode: int,
        owner: str = "root",
        group: str = "root",
    ) -> None:
        path = Path(path)
        self._removed.discard(path)
        self._overlay[path] = content
        self.changes.append(
            FileChangeRecord(
                action="write",
                path=path,
                content=content,
                mode=mode,
                owner=owner,
                group=group,
            )
        )

    def remove(self, path: Path) -> None:
        path = Path(path)
        self._overlay.pop(path, None)
        self._removed.add(path)
        self.changes.append(
            FileChangeRecord(
                action="remove",
                path=path,
            )
        )


class ReadOnlyFileOps:
    """FileOps baca-saja untuk mode verify/watch.

    Operasi baca berjalan normal, tetapi tulis/hapus melempar ReadOnlyViolation.
    """

    def __init__(self, base_fs: FileOps | None = None) -> None:
        self.base_fs = base_fs

    def read_text(self, path: Path) -> str | None:
        path = Path(path)
        if self.base_fs is not None:
            return self.base_fs.read_text(path)
        if path.is_file():
            return path.read_text(encoding="utf-8")
        return None

    def write_atomic(
        self,
        path: Path,
        content: str,
        *,
        mode: int,
        owner: str = "root",
        group: str = "root",
    ) -> None:
        raise ReadOnlyViolation(f"ReadOnlyFileOps menolak penulisan file: {path}")

    def remove(self, path: Path) -> None:
        raise ReadOnlyViolation(f"ReadOnlyFileOps menolak penghapusan file: {path}")
