"""Engine rollback: membaca journal, undo Step reversible, memulihkan backup."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from hostkeeper import messages
from hostkeeper.engine.audit import AuditWriter
from hostkeeper.engine.step import Change, Step
from hostkeeper.profile import Profile
from hostkeeper.steps import REGISTRY
from hostkeeper.system.fileops import FileOps, RealFileOps
from hostkeeper.system.runner import Runner, SubprocessRunner


class RollbackError(Exception):
    """Kesalahan saat menjalankan rollback."""


class RollbackManager:
    """Mengelola pembacaan journal dan eksekusi rollback run terdahulu."""

    DEFAULT_JOURNAL_DIR: Path = Path("/var/lib/hostkeeper/journal")
    DEFAULT_BACKUP_DIR: Path = Path("/var/lib/hostkeeper/backups")
    DEFAULT_AUDIT_PATH: Path = Path("/var/log/hostkeeper/audit.jsonl")

    def __init__(
        self,
        journal_dir: Path | None = None,
        backup_dir: Path | None = None,
        audit_path: Path | None = None,
        runner: Runner | None = None,
        fs: FileOps | None = None,
        step_registry: Sequence[type[Step]] | None = None,
        confirm_fn: Callable[[str], str] | None = None,
        print_fn: Callable[[str], None] | None = None,
    ) -> None:
        self.journal_dir = (
            journal_dir if journal_dir is not None else self.DEFAULT_JOURNAL_DIR
        )
        self.backup_dir = (
            backup_dir if backup_dir is not None else self.DEFAULT_BACKUP_DIR
        )
        self.audit_path = (
            audit_path if audit_path is not None else self.DEFAULT_AUDIT_PATH
        )
        self.runner = runner if runner is not None else SubprocessRunner()
        self.fs = fs if fs is not None else RealFileOps()
        self.step_registry = step_registry if step_registry is not None else REGISTRY
        self.confirm_fn = confirm_fn if confirm_fn is not None else input
        self.print_fn = print_fn if print_fn is not None else print

    def list_runs(self) -> list[dict[str, Any]]:
        """Mencari semua journal run di direktori journal."""
        if not self.journal_dir.exists():
            return []
        runs: list[dict[str, Any]] = []
        for jfile in sorted(self.journal_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(jfile.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    runs.append(
                        {
                            "run_id": data.get("run_id", jfile.stem),
                            "hostkeeper": data.get("hostkeeper", ""),
                            "profile_sha256": data.get("profile_sha256", ""),
                            "steps_count": len(data.get("steps", [])),
                        }
                    )
            except Exception:
                continue
        return runs

    def get_latest_run_id(self) -> str | None:
        """Mengambil run_id paling baru dari nama file journal."""
        if not self.journal_dir.exists():
            return None
        json_files = sorted(self.journal_dir.glob("*.json"), reverse=True)
        if not json_files:
            return None
        return json_files[0].stem

    def rollback(
        self,
        run_id: str | None = None,
        yes: bool = False,
        reason: str = "manual",
    ) -> bool:
        """Menjalankan rollback mundur untuk satu run."""
        target_run_id = run_id or self.get_latest_run_id()
        if not target_run_id:
            raise RollbackError(messages.ROLLBACK_NO_RUNS)

        jfile = self.journal_dir / f"{target_run_id}.json"
        if not jfile.is_file():
            raise RollbackError(
                messages.ROLLBACK_RUN_NOT_FOUND.format(
                    run_id=target_run_id, dir=self.journal_dir
                )
            )

        try:
            content = jfile.read_text(encoding="utf-8")
            data = json.loads(content)
            if not isinstance(data, dict) or "steps" not in data:
                raise ValueError("Format data journal tidak lengkap")
        except Exception as exc:
            raise RollbackError(
                messages.ROLLBACK_JOURNAL_INVALID.format(
                    run_id=target_run_id, detail=str(exc)
                )
            ) from exc

        # Konfirmasi jika tidak --yes
        if not yes:
            prompt = messages.ROLLBACK_CONFIRM_PROMPT.format(run_id=target_run_id)
            try:
                ans = self.confirm_fn(prompt)
            except (EOFError, KeyboardInterrupt):
                self.print_fn(messages.ROLLBACK_ABORT)
                return False
            if ans.strip().lower() != "y":
                self.print_fn(messages.ROLLBACK_ABORT)
                return False

        audit = AuditWriter(path=self.audit_path, run_id=target_run_id)
        registry_map: dict[str, type[Step]] = {
            cls.name: cls for cls in self.step_registry
        }
        undone_count = 0

        steps_data: list[dict[str, Any]] = data.get("steps", [])
        for step_rec in reversed(steps_data):
            name = str(step_rec.get("name", ""))
            status = step_rec.get("status", "")
            reversible = bool(step_rec.get("reversible", False))

            if status != "applied":
                continue

            if not reversible:
                self.print_fn(messages.ROLLBACK_STEP_CANNOT_UNDO.format(name=name))
                continue

            raw_changes = step_rec.get("changes", [])
            changes: list[Change] = []
            for c in raw_changes:
                if isinstance(c, dict):
                    changes.append(
                        Change(
                            step=name,
                            action=str(c.get("action", "")),
                            target=str(c.get("target", "")),
                            before=(
                                str(c["before"])
                                if c.get("before") is not None
                                else None
                            ),
                            after=(
                                str(c["after"]) if c.get("after") is not None else None
                            ),
                        )
                    )

            # 1. Jalankan undo() pada Step
            step_cls = registry_map.get(name)
            if step_cls is not None:
                step_inst = step_cls(Profile(), self.runner, self.fs)
                step_inst.undo(changes)

            # 2. Pulihkan backup file jika ada
            backups: list[str] = step_rec.get("backups", [])
            run_backup_root = self.backup_dir / target_run_id
            for bpath_str in backups:
                bpath = Path(bpath_str)
                orig_target: Path | None = None
                try:
                    rel = bpath.relative_to(run_backup_root)
                    orig_target = Path("/") / rel
                except ValueError:
                    orig_target = None

                if orig_target is None:
                    for ch in changes:
                        if (
                            ch.target.startswith("/")
                            and bpath.name == Path(ch.target).name
                        ):
                            orig_target = Path(ch.target)
                            break

                if orig_target is not None:
                    backup_content = self.fs.read_text(bpath)
                    if backup_content is not None:
                        self.fs.write_atomic(orig_target, backup_content, mode=0o644)

            try:
                audit.log_undo(name, reason=reason)
            except OSError:
                pass
            self.print_fn(messages.ROLLBACK_STEP_UNDONE.format(name=name))
            undone_count += 1

        try:
            audit.log_run_end("ok")
        except OSError:
            pass
        self.print_fn(
            messages.ROLLBACK_DONE.format(run_id=target_run_id, undone=undone_count)
        )
        return True
