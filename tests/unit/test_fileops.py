from pathlib import Path
from unittest.mock import patch

import pytest

from hostkeeper.system.fakes import FakeFileOps
from hostkeeper.system.fileops import (
    FileChangeRecord,
    FileOps,
    ReadOnlyFileOps,
    RealFileOps,
    RecordingFileOps,
)
from hostkeeper.system.runner import ReadOnlyViolation


def test_real_fileops_read_and_write_atomic(tmp_path: Path) -> None:
    fs: FileOps = RealFileOps(backup_dir=tmp_path / "backups", run_id="run-1")
    target = tmp_path / "test.txt"

    # File does not exist yet
    assert fs.read_text(target) is None

    # Write atomic
    fs.write_atomic(target, "hello world", mode=0o644)
    assert target.exists()
    assert fs.read_text(target) == "hello world"
    # Check permissions (mode & 0o777)
    assert (target.stat().st_mode & 0o777) == 0o644


def test_real_fileops_backup_before_overwrite(tmp_path: Path) -> None:
    backup_root = tmp_path / "backups"
    fs = RealFileOps(backup_dir=backup_root, run_id="run-42")
    target = tmp_path / "conf" / "app.cfg"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("v1", encoding="utf-8")

    # Overwrite
    fs.write_atomic(target, "v2", mode=0o600)
    assert target.read_text(encoding="utf-8") == "v2"

    # Backup must exist and contain "v1"
    assert len(fs.backups) == 1
    src, backup_path = fs.backups[0]
    assert src == target
    assert backup_path.exists()
    assert backup_path.read_text(encoding="utf-8") == "v1"


def test_real_fileops_write_atomic_cleans_up_on_failure(tmp_path: Path) -> None:
    fs = RealFileOps(backup_dir=tmp_path / "backups", run_id="run-err")
    target = tmp_path / "important.txt"
    target.write_text("initial", encoding="utf-8")

    # Simulate error during fsync
    with patch("os.fsync", side_effect=OSError("Disk write failed")):
        with pytest.raises(OSError, match="Disk write failed"):
            fs.write_atomic(target, "partial data", mode=0o644)

    # Target should be untouched
    assert target.read_text(encoding="utf-8") == "initial"

    # No leftover temporary files in directory
    temp_files = list(tmp_path.glob(".*.tmp"))
    assert temp_files == []


def test_real_fileops_remove(tmp_path: Path) -> None:
    fs = RealFileOps(backup_dir=tmp_path / "backups")
    target = tmp_path / "to_delete.txt"
    target.write_text("bye", encoding="utf-8")
    assert target.exists()

    fs.remove(target)
    assert not target.exists()

    # Removing non-existent file does not raise
    fs.remove(target)


def test_recording_fileops_does_not_touch_disk(tmp_path: Path) -> None:
    target = tmp_path / "record_me.txt"
    target.write_text("on disk", encoding="utf-8")

    fs = RecordingFileOps()
    # Read initially gets from disk (or base)
    assert fs.read_text(target) == "on disk"

    # Write atomic should NOT write to disk
    fs.write_atomic(target, "new content", mode=0o600)
    assert target.read_text(encoding="utf-8") == "on disk"  # disk untouched!
    assert fs.read_text(target) == "new content"  # overlay shows new content

    # Remove should NOT delete from disk
    fs.remove(target)
    assert target.exists()  # still on disk!
    assert fs.read_text(target) is None  # overlay shows removed

    # Changes should be recorded
    assert len(fs.changes) == 2
    rec_write: FileChangeRecord = fs.changes[0]
    assert rec_write.action == "write"
    assert rec_write.path == target
    assert rec_write.content == "new content"
    assert rec_write.mode == 0o600

    rec_remove: FileChangeRecord = fs.changes[1]
    assert rec_remove.action == "remove"
    assert rec_remove.path == target


def test_readonly_fileops_rejects_write_and_remove(tmp_path: Path) -> None:
    target = tmp_path / "ro.txt"
    target.write_text("existing", encoding="utf-8")

    fs = ReadOnlyFileOps()
    # Reading works
    assert fs.read_text(target) == "existing"

    # Writing is rejected with ReadOnlyViolation
    with pytest.raises(ReadOnlyViolation):
        fs.write_atomic(target, "new", mode=0o644)
    assert target.read_text(encoding="utf-8") == "existing"

    # Removing is rejected with ReadOnlyViolation
    with pytest.raises(ReadOnlyViolation):
        fs.remove(target)
    assert target.exists()


def test_fake_fileops_in_memory() -> None:
    fs = FakeFileOps({Path("/etc/test"): "initial"})
    assert fs.read_text(Path("/etc/test")) == "initial"
    assert fs.read_text(Path("/nonexistent")) is None

    fs.write_atomic(
        Path("/etc/test"), "updated", mode=0o644, owner="root", group="root"
    )
    assert fs.read_text(Path("/etc/test")) == "updated"
    assert len(fs.written) == 1

    fs.remove(Path("/etc/test"))
    assert fs.read_text(Path("/etc/test")) is None
    assert len(fs.removed) == 1


def test_fileops_with_base_fs_and_nonexistent(tmp_path: Path) -> None:
    base = FakeFileOps({Path("/base/file"): "base content"})

    rec_fs = RecordingFileOps(base_fs=base)
    assert rec_fs.read_text(Path("/base/file")) == "base content"
    assert rec_fs.read_text(tmp_path / "missing") is None

    ro_fs = ReadOnlyFileOps(base_fs=base)
    assert ro_fs.read_text(Path("/base/file")) == "base content"
    assert ro_fs.read_text(tmp_path / "missing") is None


def test_real_fileops_backup_without_run_id(tmp_path: Path) -> None:
    backup_root = tmp_path / "backups"
    fs = RealFileOps(backup_dir=backup_root, run_id=None)
    target = tmp_path / "file.txt"
    target.write_text("v1", encoding="utf-8")

    fs.write_atomic(target, "v2", mode=0o644)
    assert target.read_text(encoding="utf-8") == "v2"
    assert len(fs.backups) == 1
