from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


class ReadOnlyViolation(Exception):
    """Dilempar saat ada operasi mutasi di mode baca-saja (plan/verify/watch)."""


@dataclass(frozen=True)
class CmdResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


class Runner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        mutates: bool = False,
        timeout: float = 60.0,
        input: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CmdResult: ...


class SubprocessRunner:
    """Menjalankan perintah melalui subprocess.

    Tidak melempar saat returncode bukan nol. Mengatur timed_out=True saat timeout.
    Secara default mengatur LC_ALL=C dan DEBIAN_FRONTEND=noninteractive.
    """

    def run(
        self,
        argv: Sequence[str],
        *,
        mutates: bool = False,
        timeout: float = 60.0,
        input: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CmdResult:
        cmd_env = dict(os.environ)
        cmd_env["LC_ALL"] = "C"
        cmd_env["DEBIAN_FRONTEND"] = "noninteractive"
        if env is not None:
            cmd_env.update(env)

        start = time.monotonic()
        argv_tuple = tuple(argv)
        try:
            proc = subprocess.run(
                list(argv),
                capture_output=True,
                text=True,
                timeout=timeout,
                input=input,
                env=cmd_env,
                shell=False,
            )
            duration = time.monotonic() - start
            return CmdResult(
                argv=argv_tuple,
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration=duration,
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - start
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            return CmdResult(
                argv=argv_tuple,
                returncode=-1,
                stdout=stdout,
                stderr=stderr,
                duration=duration,
                timed_out=True,
            )


class ReadOnlyRunner:
    """Membungkus Runner asli, menolak mutates=True dengan ReadOnlyViolation."""

    def __init__(self, inner: Runner) -> None:
        self.inner = inner

    def run(
        self,
        argv: Sequence[str],
        *,
        mutates: bool = False,
        timeout: float = 60.0,
        input: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CmdResult:
        if mutates:
            msg = f"ReadOnlyRunner menolak perintah mutasi: {list(argv)}"
            raise ReadOnlyViolation(msg)
        return self.inner.run(
            argv,
            mutates=False,
            timeout=timeout,
            input=input,
            env=env,
        )
