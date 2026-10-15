"""Unit test untuk LockManager dan LockConflict."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hostkeeper.engine.lock import LockConflict, LockManager


def test_lock_acquire_and_release(tmp_path: Path) -> None:
    lock_file = tmp_path / "hostkeeper.lock"
    lock = LockManager(path=lock_file)
    lock.acquire()
    assert lock_file.exists()
    assert lock_file.read_text(encoding="utf-8") == str(os.getpid())
    lock.release()
    assert lock._fd is None


def test_lock_context_manager(tmp_path: Path) -> None:
    lock_file = tmp_path / "hostkeeper.lock"
    with LockManager(path=lock_file) as lock:
        assert lock.path == lock_file
        assert lock_file.exists()
    assert lock._fd is None


def test_lock_conflict(tmp_path: Path) -> None:
    lock_file = tmp_path / "hostkeeper.lock"
    lock1 = LockManager(path=lock_file)
    lock1.acquire()

    lock2 = LockManager(path=lock_file)
    with pytest.raises(LockConflict):
        lock2.acquire()

    lock1.release()

    # Setelah dilepas, lock2 bisa memperolehnya
    lock2.acquire()
    lock2.release()
