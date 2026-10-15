import sys

import pytest

from hostkeeper.system.fakes import FakeCall, FakeRunner
from hostkeeper.system.runner import (
    CmdResult,
    ReadOnlyRunner,
    ReadOnlyViolation,
    Runner,
    SubprocessRunner,
)


def test_cmd_result_properties() -> None:
    res_ok = CmdResult(
        argv=("echo", "hi"),
        returncode=0,
        stdout="hi\n",
        stderr="",
        duration=0.01,
        timed_out=False,
    )
    assert res_ok.ok is True
    assert res_ok.argv == ("echo", "hi")
    assert res_ok.returncode == 0
    assert res_ok.stdout == "hi\n"
    assert res_ok.stderr == ""
    assert res_ok.timed_out is False

    res_fail = CmdResult(
        argv=("false",),
        returncode=1,
        stdout="",
        stderr="error",
        duration=0.01,
        timed_out=False,
    )
    assert res_fail.ok is False

    res_timeout = CmdResult(
        argv=("sleep", "10"),
        returncode=-1,
        stdout="",
        stderr="",
        duration=1.0,
        timed_out=True,
    )
    assert res_timeout.ok is False


def test_subprocess_runner_success() -> None:
    runner: Runner = SubprocessRunner()
    result = runner.run(["echo", "hello world"])
    assert result.ok is True
    assert result.returncode == 0
    assert result.stdout.strip() == "hello world"
    assert result.stderr == ""
    assert result.duration >= 0.0
    assert result.timed_out is False


def test_subprocess_runner_nonzero_returncode_does_not_raise() -> None:
    runner = SubprocessRunner()
    # Running a command that exits with non-zero
    code = "import sys; sys.stderr.write('fail'); sys.exit(42)"
    result = runner.run([sys.executable, "-c", code])
    assert result.ok is False
    assert result.returncode == 42
    assert result.stderr == "fail"
    assert result.timed_out is False


def test_subprocess_runner_timeout() -> None:
    runner = SubprocessRunner()
    # sleep for 2 seconds with timeout 0.1s
    code = "import time; time.sleep(2)"
    result = runner.run([sys.executable, "-c", code], timeout=0.1)
    assert result.timed_out is True
    assert result.ok is False
    assert result.returncode != 0


def test_subprocess_runner_env_defaults_and_override() -> None:
    runner = SubprocessRunner()
    # Test LC_ALL=C and DEBIAN_FRONTEND=noninteractive
    code = (
        "import os; "
        "print(os.environ.get('LC_ALL')); "
        "print(os.environ.get('DEBIAN_FRONTEND')); "
        "print(os.environ.get('CUSTOM_VAR'))"
    )
    result = runner.run([sys.executable, "-c", code], env={"CUSTOM_VAR": "custom_val"})
    assert result.ok is True
    lines = result.stdout.strip().splitlines()
    assert lines[0] == "C"
    assert lines[1] == "noninteractive"
    assert lines[2] == "custom_val"


def test_subprocess_runner_input() -> None:
    runner = SubprocessRunner()
    code = "import sys; data = sys.stdin.read(); sys.stdout.write('got:' + data)"
    result = runner.run([sys.executable, "-c", code], input="test input")
    assert result.ok is True
    assert result.stdout == "got:test input"


def test_readonly_runner_rejects_mutates() -> None:
    inner = SubprocessRunner()
    ro_runner: Runner = ReadOnlyRunner(inner)

    # mutates=False should work
    res = ro_runner.run(["echo", "safe"], mutates=False)
    assert res.ok is True
    assert res.stdout.strip() == "safe"

    # mutates=True must be rejected with ReadOnlyViolation
    with pytest.raises(ReadOnlyViolation):
        ro_runner.run(["touch", "/tmp/should_fail"], mutates=True)


def test_fake_runner_records_calls_and_returns_responses() -> None:
    runner = FakeRunner()
    cmd = ["hostnamectl", "--static"]
    runner.register(cmd, "web-01\n")

    res = runner.run(cmd, mutates=False, timeout=30.0)
    assert res.ok is True
    assert res.stdout == "web-01\n"
    assert res.returncode == 0

    assert len(runner.calls) == 1
    call: FakeCall = runner.calls[0]
    assert call.argv == ("hostnamectl", "--static")
    assert call.mutates is False
    assert call.timeout == 30.0
    assert call.input is None
    assert call.env is None


def test_fake_runner_rejects_unprogrammed_commands() -> None:
    runner = FakeRunner()
    runner.register(["hostnamectl", "--static"], "web-01")

    with pytest.raises(RuntimeError, match="Perintah tak terprogram"):
        runner.run(["hostnamectl", "set-hostname", "new-host"], mutates=True)


def test_fake_runner_init_with_responses() -> None:
    cmd_res = CmdResult(
        argv=("uptime",),
        returncode=0,
        stdout="up 1 day",
        stderr="",
        duration=0.0,
    )
    runner = FakeRunner(
        responses={
            ("uname", "-r"): "6.1.0-custom",
            ("uptime",): cmd_res,
        }
    )
    res1 = runner.run(["uname", "-r"])
    assert res1.ok is True
    assert res1.stdout == "6.1.0-custom"

    res2 = runner.run(["uptime"])
    assert res2.ok is True
    assert res2.stdout == "up 1 day"
