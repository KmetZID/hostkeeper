"""System package for system interaction abstraction."""

from hostkeeper.system.fakes import FakeCall, FakeFileOps, FakeRunner
from hostkeeper.system.fileops import (
    FileChangeRecord,
    FileOps,
    ReadOnlyFileOps,
    RealFileOps,
    RecordingFileOps,
)
from hostkeeper.system.runner import (
    CmdResult,
    ReadOnlyRunner,
    ReadOnlyViolation,
    Runner,
    SubprocessRunner,
)

__all__ = [
    "CmdResult",
    "FakeCall",
    "FakeFileOps",
    "FakeRunner",
    "FileChangeRecord",
    "FileOps",
    "ReadOnlyFileOps",
    "ReadOnlyRunner",
    "ReadOnlyViolation",
    "RealFileOps",
    "RecordingFileOps",
    "Runner",
    "SubprocessRunner",
]
