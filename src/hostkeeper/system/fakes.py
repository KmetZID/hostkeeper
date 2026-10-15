from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from hostkeeper.system.runner import CmdResult


@dataclass(frozen=True)
class FakeCall:
    argv: tuple[str, ...]
    mutates: bool
    timeout: float
    input: str | None
    env: Mapping[str, str] | None


class FakeRunner:
    """Runner tiruan untuk tes unit.

    Menerima tabel respons terprogram, mencatat setiap pemanggilan di .calls,
    dan melempar RuntimeError jika dipanggil dengan perintah yang tidak terprogram.
    """

    def __init__(
        self,
        responses: Mapping[Sequence[str], CmdResult | str] | None = None,
    ) -> None:
        self.calls: list[FakeCall] = []
        self._responses: dict[tuple[str, ...], CmdResult] = {}
        if responses:
            for cmd, resp in responses.items():
                self.register(cmd, resp)

    def register(
        self,
        argv: Sequence[str],
        result: CmdResult | str,
        returncode: int = 0,
        stderr: str = "",
        duration: float = 0.0,
        timed_out: bool = False,
    ) -> None:
        key = tuple(argv)
        if isinstance(result, CmdResult):
            self._responses[key] = result
        else:
            self._responses[key] = CmdResult(
                argv=key,
                returncode=returncode,
                stdout=result,
                stderr=stderr,
                duration=duration,
                timed_out=timed_out,
            )

    def run(
        self,
        argv: Sequence[str],
        *,
        mutates: bool = False,
        timeout: float = 60.0,
        input: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CmdResult:
        key = tuple(argv)
        self.calls.append(
            FakeCall(
                argv=key,
                mutates=mutates,
                timeout=timeout,
                input=input,
                env=env,
            )
        )
        if key not in self._responses:
            raise RuntimeError(f"Perintah tak terprogram: {list(argv)}")
        return self._responses[key]


class FakeFileOps:
    """Implementasi FileOps dalam memori untuk pengujian unit tanpa menyentuh disk."""

    def __init__(self, files: Mapping[Path | str, str] | None = None) -> None:
        self.files: dict[Path, str] = {Path(p): c for p, c in (files or {}).items()}
        self.modes: dict[Path, int] = {}
        self.owners: dict[Path, tuple[str, str]] = {}
        self.written: list[tuple[Path, str, int, str, str]] = []
        self.removed: list[Path] = []

    def read_text(self, path: Path) -> str | None:
        return self.files.get(Path(path))

    def write_atomic(
        self,
        path: Path,
        content: str,
        *,
        mode: int,
        owner: str = "root",
        group: str = "root",
    ) -> None:
        p = Path(path)
        self.files[p] = content
        self.modes[p] = mode
        self.owners[p] = (owner, group)
        self.written.append((p, content, mode, owner, group))

    def remove(self, path: Path) -> None:
        p = Path(path)
        self.files.pop(p, None)
        self.removed.append(p)
