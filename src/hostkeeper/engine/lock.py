"""Lock eksklusif untuk mencegah dua instance hostkeeper berjalan bersamaan."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
from types import TracebackType
from typing import IO


class LockConflict(Exception):
    """Dilempar saat instance hostkeeper lain sedang berjalan."""


class LockManager:
    """Mengelola flock eksklusif non-blocking di file lock.

    Dipakai sebagai context manager:

        with LockManager() as lock:
            ...  # kode yang butuh eksklusivitas

    Melempar LockConflict jika lock tidak bisa diperoleh.
    """

    DEFAULT_PATH: Path = Path("/run/hostkeeper.lock")

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else self.DEFAULT_PATH
        self._fd: IO[str] | None = None

    def acquire(self) -> None:
        """Mengambil lock eksklusif non-blocking. Melempar LockConflict jika gagal."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = open(self.path, "w")  # noqa: WPS515
            self._fd = fd
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Tulis PID untuk debugging
            fd.write(str(os.getpid()))
            fd.flush()
        except OSError:
            if self._fd is not None:
                self._fd.close()
                self._fd = None
            raise LockConflict("Lock tidak bisa diperoleh")

    def release(self) -> None:
        """Melepas lock."""
        if self._fd is not None:
            try:
                fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
                self._fd.close()
            except OSError:
                pass
            finally:
                self._fd = None

    def __enter__(self) -> "LockManager":
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.release()
