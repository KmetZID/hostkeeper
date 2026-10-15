"""Journal per-run untuk hostkeeper (dipakai oleh rollback di v0.2)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from hostkeeper import __version__
from hostkeeper.engine.step import Change


@dataclass
class JournalStepRecord:
    """Catatan satu Step dalam journal run."""

    name: str
    status: str  # 'applied' | 'skipped' | 'failed' | 'undone'
    reversible: bool
    changes: list[dict[str, object]]
    backups: list[str]  # path file backup


@dataclass
class JournalRun:
    """Seluruh data journal untuk satu run."""

    run_id: str
    hostkeeper: str
    profile_sha256: str
    steps: list[JournalStepRecord]


class JournalWriter:
    """Menulis journal satu run ke file JSON.

    Path injectable untuk tes (default: /var/lib/hostkeeper/journal/<run_id>.json).
    """

    DEFAULT_DIR: Path = Path("/var/lib/hostkeeper/journal")

    def __init__(
        self,
        run_id: str,
        profile_sha256: str,
        journal_dir: Path | None = None,
    ) -> None:
        self.run_id = run_id
        self.journal_dir = journal_dir if journal_dir is not None else self.DEFAULT_DIR
        self._run = JournalRun(
            run_id=run_id,
            hostkeeper=__version__,
            profile_sha256=profile_sha256,
            steps=[],
        )

    def record_step(
        self,
        name: str,
        status: str,
        reversible: bool,
        changes: list[Change],
        backups: list[str] | None = None,
    ) -> None:
        """Mencatat satu Step ke journal."""
        changes_dicts: list[dict[str, object]] = []
        for ch in changes:
            changes_dicts.append(
                {
                    "action": ch.action,
                    "target": ch.target,
                    "before": ch.before,
                    "after": ch.after,
                }
            )
        self._run.steps.append(
            JournalStepRecord(
                name=name,
                status=status,
                reversible=reversible,
                changes=changes_dicts,
                backups=backups or [],
            )
        )

    def write(self) -> Path:
        """Menulis journal ke disk dan mengembalikan path file."""
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        journal_path = self.journal_dir / f"{self.run_id}.json"

        data: dict[str, object] = {
            "run_id": self._run.run_id,
            "hostkeeper": self._run.hostkeeper,
            "profile_sha256": self._run.profile_sha256,
            "steps": [asdict(s) for s in self._run.steps],
        }
        journal_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return journal_path
