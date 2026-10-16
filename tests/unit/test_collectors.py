"""Unit test untuk collector metrik (Tahap 3.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hostkeeper.monitor.collector import CollectContext, collect_all
from hostkeeper.monitor.collectors.cpu import collect_cpu
from hostkeeper.monitor.collectors.disk import collect_disk
from hostkeeper.monitor.collectors.memory import collect_memory
from hostkeeper.monitor.collectors.psi import collect_psi
from hostkeeper.monitor.collectors.services import collect_services
from hostkeeper.monitor.collectors.ssh_failed import collect_ssh_failed
from hostkeeper.monitor.collectors.time_sync import collect_time_sync
from hostkeeper.monitor.collectors.updates import collect_updates
from hostkeeper.system.fakes import FakeRunner
from hostkeeper.system.runner import ReadOnlyViolation


def test_collect_cpu_success(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "loadavg").write_text("0.50 0.75 1.00 1/200 1234\n", encoding="utf-8")
    (proc / "cpuinfo").write_text("processor : 0\nprocessor : 1\n", encoding="utf-8")

    ctx = CollectContext(proc_path=proc, runner=FakeRunner({}))
    metrics = {m.name: m for m in collect_cpu(ctx)}

    assert metrics["cpu.load1"].value == 0.50
    assert metrics["cpu.load5"].value == 0.75
    assert metrics["cpu.load15"].value == 1.00
    assert metrics["cpu.cores"].value == 2
    assert metrics["cpu.load1_per_core"].value == 0.25
    assert metrics["cpu.load1"].status_hint == "ok"


def test_collect_cpu_missing_proc_file(tmp_path: Path) -> None:
    proc = tmp_path / "proc_empty"
    proc.mkdir()
    ctx = CollectContext(proc_path=proc, runner=FakeRunner({}))
    metrics = {m.name: m for m in collect_cpu(ctx)}
    assert metrics["cpu.load1"].status_hint == "unknown"


def test_collect_memory_success(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    proc.mkdir()
    meminfo_content = (
        "MemTotal:        16000000 kB\n"
        "MemFree:          2000000 kB\n"
        "MemAvailable:     8000000 kB\n"
        "SwapTotal:        4000000 kB\n"
        "SwapFree:         3000000 kB\n"
    )
    (proc / "meminfo").write_text(meminfo_content, encoding="utf-8")

    ctx = CollectContext(proc_path=proc, runner=FakeRunner({}))
    metrics = {m.name: m for m in collect_memory(ctx)}

    assert metrics["mem.total_mb"].value == 15625.0
    assert metrics["mem.available_mb"].value == 7812.5
    assert metrics["mem.used_percent"].value == 50.0
    assert metrics["swap.total_mb"].value == 3906.2
    assert metrics["swap.used_percent"].value == 25.0


def test_collect_psi_files_present(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    pressure = proc / "pressure"
    pressure.mkdir(parents=True)
    cpu_text = "some avg10=2.50 avg60=1.20 avg300=0.50 total=12345\n"
    (pressure / "cpu").write_text(cpu_text, encoding="utf-8")
    mem_text = (
        "some avg10=0.10 avg60=0.05 avg300=0.01 total=50\n"
        "full avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
    )
    (pressure / "memory").write_text(mem_text, encoding="utf-8")
    io_text = "some avg10=1.00 avg60=0.50 avg300=0.20 total=99\n"
    (pressure / "io").write_text(io_text, encoding="utf-8")

    ctx = CollectContext(proc_path=proc, runner=FakeRunner({}))
    metrics = {m.name: m for m in collect_psi(ctx)}

    assert metrics["psi.cpu.some_avg10"].value == 2.50
    assert metrics["psi.memory.some_avg10"].value == 0.10
    assert metrics["psi.io.some_avg10"].value == 1.00
    assert metrics["psi.cpu.some_avg10"].status_hint == "ok"


def test_collect_psi_files_missing_returns_unknown_not_error(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    proc.mkdir()
    ctx = CollectContext(proc_path=proc, runner=FakeRunner({}))
    metrics = {m.name: m for m in collect_psi(ctx)}

    assert "psi.cpu.some_avg10" in metrics
    assert metrics["psi.cpu.some_avg10"].status_hint == "unknown"


def test_collect_disk_success() -> None:
    class MockStat:
        f_blocks = 1000
        f_frsize = 1024 * 1024  # 1MB per block -> 1000MB total
        f_bfree = 400
        f_bavail = 400  # 400MB free -> 600MB used (60%)
        f_files = 100000
        f_ffree = 80000
        f_favail = 80000  # 20% inodes used

    def mock_statvfs(path: str) -> Any:
        return MockStat()

    ctx = CollectContext(
        mount_points=["/"],
        statvfs_fn=mock_statvfs,
        runner=FakeRunner({}),
    )
    metrics = {m.name: m for m in collect_disk(ctx)}

    assert metrics["disk./.used_percent"].value == 60.0
    assert metrics["disk./.inodes_used_percent"].value == 20.0


def test_collect_time_sync(tmp_path: Path) -> None:
    runner = FakeRunner(
        {
            ("timedatectl", "show"): "NTPSynchronized=yes\nTimezone=Asia/Jakarta\n",
        }
    )
    ctx = CollectContext(runner=runner)
    metrics = {m.name: m for m in collect_time_sync(ctx)}

    assert metrics["time.ntp_synchronized"].value is True
    assert metrics["time.ntp_synchronized"].status_hint == "ok"

    runner_unsync = FakeRunner(
        {
            ("timedatectl", "show"): "NTPSynchronized=no\n",
        }
    )
    ctx_unsync = CollectContext(runner=runner_unsync)
    metrics_unsync = {m.name: m for m in collect_time_sync(ctx_unsync)}
    assert metrics_unsync["time.ntp_synchronized"].value is False
    assert metrics_unsync["time.ntp_synchronized"].status_hint == "warn"


def test_collect_services() -> None:
    svc_out = "nginx.service loaded failed failed A high performance web server\n"
    runner = FakeRunner(
        {
            ("systemctl", "--failed", "--no-legend"): svc_out,
        }
    )
    ctx = CollectContext(runner=runner)
    metrics = {m.name: m for m in collect_services(ctx)}

    assert metrics["services.failed_count"].value == 1
    assert metrics["services.failed_count"].status_hint == "crit"

    runner_clean = FakeRunner(
        {
            ("systemctl", "--failed", "--no-legend"): "",
        }
    )
    ctx_clean = CollectContext(runner=runner_clean)
    metrics_clean = {m.name: m for m in collect_services(ctx_clean)}
    assert metrics_clean["services.failed_count"].value == 0
    assert metrics_clean["services.failed_count"].status_hint == "ok"


def test_collect_updates(tmp_path: Path) -> None:
    reboot_file = tmp_path / "reboot-required"
    reboot_file.write_text("*** System restart required ***\n", encoding="utf-8")

    apt_out = (
        "Inst libc6 [2.36-9] "
        "(2.36-9+deb12u3 Debian-Security:"
        "12/stable-security [amd64])\n"
        "Inst curl [7.88.1-10] "
        "(7.88.1-10+deb12u4 Debian:"
        "12/stable [amd64])\n"
        "Conf libc6\n"
    )
    runner = FakeRunner(
        {
            ("apt-get", "-s", "upgrade"): apt_out,
        }
    )
    ctx = CollectContext(runner=runner, reboot_required_path=reboot_file)
    metrics = {m.name: m for m in collect_updates(ctx)}

    assert metrics["updates.pending"].value == 2
    assert metrics["updates.security"].value == 1
    assert metrics["updates.reboot_required"].value is True


def test_collect_ssh_failed() -> None:
    ssh_log = (
        "Oct 16 10:00:01 host sshd[123]: "
        "Failed password for root from "
        "1.2.3.4 port 12345 ssh2\n"
        "Oct 16 10:00:02 host sshd[124]: "
        "Invalid user admin from "
        "1.2.3.4 port 12346\n"
        "Oct 16 10:00:03 host sshd[125]: "
        "Accepted publickey for user\n"
    )
    ssh_key = (
        "journalctl",
        "-u",
        "ssh",
        "--since",
        "-10min",
    )
    runner = FakeRunner({ssh_key: ssh_log})
    ctx = CollectContext(runner=runner)
    metrics = {m.name: m for m in collect_ssh_failed(ctx)}

    assert metrics["ssh.failed_logins_10m"].value == 2


def test_collectors_are_strictly_read_only() -> None:
    from hostkeeper.system.runner import CmdResult

    class MutatingAttemptRunner(FakeRunner):
        def run(
            self,
            argv: Any,
            *,
            mutates: bool = False,
            **kwargs: Any,
        ) -> CmdResult:
            if mutates:
                msg = "Tidak boleh memanggil mutates=True dalam collector"
                raise ReadOnlyViolation(msg)
            return CmdResult(
                argv=tuple(argv),
                returncode=0,
                stdout="",
                stderr="",
                duration=0.0,
            )

    ctx = CollectContext(runner=MutatingAttemptRunner({}))
    # Semua collector harus lulus tanpa memanggil mutates=True
    collect_all(ctx)
