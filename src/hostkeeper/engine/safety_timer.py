"""Safety timer independen untuk Step berisiko tinggi (Tahap 2.4)."""

from __future__ import annotations

from collections.abc import Callable

from hostkeeper import messages
from hostkeeper.system.runner import Runner


class SafetyTimer:
    """Memasang timer systemd independen sebelum Step HIGH risk.

    Jika sesi terputus atau tidak dikonfirmasi, systemd akan memanggil:
    `hostkeeper rollback <run_id> --yes --reason timer`.
    """

    def __init__(
        self,
        runner: Runner,
        run_id: str,
        timeout_seconds: int = 90,
        print_fn: Callable[[str], None] | None = None,
    ) -> None:
        self.runner = runner
        self.run_id = run_id
        self.timeout_seconds = timeout_seconds
        self.print_fn = print_fn if print_fn is not None else print

    def start(self) -> None:
        """Memasang unit timer systemd-run."""
        cmd = [
            "systemd-run",
            f"--on-active={self.timeout_seconds}s",
            f"--unit=hostkeeper-rollback-{self.run_id}",
            "hostkeeper",
            "rollback",
            self.run_id,
            "--yes",
            "--reason",
            "timer",
        ]
        res = self.runner.run(cmd, mutates=True)
        if not res.ok:
            raise RuntimeError(
                messages.SAFETY_TIMER_FAILED.format(detail=res.stderr.strip())
            )
        self.print_fn(
            messages.SAFETY_TIMER_STARTED.format(seconds=self.timeout_seconds)
        )

    def stop(self) -> None:
        """Menghentikan dan membatalkan unit timer systemd."""
        cmd = ["systemctl", "stop", f"hostkeeper-rollback-{self.run_id}.timer"]
        self.runner.run(cmd, mutates=True)
        self.print_fn(messages.SAFETY_TIMER_STOPPED)
