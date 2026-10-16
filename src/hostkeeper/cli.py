"""CLI hostkeeper: argparse, dispatch subcommand, exit code."""

from __future__ import annotations

import argparse
import os
import socket
import sys
import time
import traceback
from pathlib import Path
from typing import IO, Sequence

import yaml

from hostkeeper import __version__, messages
from hostkeeper.engine.audit import AuditWriter
from hostkeeper.engine.executor import Executor, make_run_id, sha256_file
from hostkeeper.engine.journal import JournalWriter
from hostkeeper.engine.lock import LockConflict, LockManager
from hostkeeper.engine.planner import Planner
from hostkeeper.engine.rollback import RollbackError, RollbackManager
from hostkeeper.env import detect_env
from hostkeeper.monitor.collector import CollectContext, Metric, collect_all
from hostkeeper.monitor.evaluator import Evaluator
from hostkeeper.monitor.notify import (
    check_watch_config_permissions,
    format_payload,
    mask_url,
    send_webhook,
)
from hostkeeper.monitor.profile_checker import (
    StepCompliance,
    check_profile_compliance,
    load_profile_if_exists,
)
from hostkeeper.monitor.state import StateManager
from hostkeeper.output import (
    format_plan_summary,
    print_plan_json,
    print_plan_table,
    print_status_json,
    print_status_table,
    print_verify_json,
    print_verify_table,
)
from hostkeeper.profile import ProfileValidationError, load_profile
from hostkeeper.steps import REGISTRY
from hostkeeper.system.fileops import ReadOnlyFileOps, RealFileOps
from hostkeeper.system.runner import ReadOnlyRunner, SubprocessRunner
from hostkeeper.wizard import Wizard

# Exit codes sesuai SPEC bagian 7
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_DRIFT = 3
EXIT_LOCK = 4
EXIT_ENV = 5


def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-c",
        "--config",
        default="/etc/hostkeeper/profile.yml",
        metavar="FILE",
        help="Path ke file profil (default: /etc/hostkeeper/profile.yml)",
    )
    common.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output dalam format JSON",
    )
    common.add_argument(
        "--no-color",
        action="store_true",
        default=False,
        help="Matikan output berwarna",
    )
    common.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Tampilkan stack trace saat error",
    )

    parser = argparse.ArgumentParser(
        prog="hostkeeper",
        description="Server setup and maintenance tool",
        parents=[common],
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"hostkeeper {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    # version
    subparsers.add_parser(
        "version",
        parents=[common],
        help="Tampilkan versi dan info lingkungan",
    )

    # plan
    plan_p = subparsers.add_parser(
        "plan",
        parents=[common],
        help="Tampilkan perubahan tanpa menerapkan",
    )
    plan_p.add_argument(
        "--check",
        action="store_true",
        default=False,
        help="Exit 3 jika ada perubahan yang dibutuhkan",
    )

    # apply
    apply_p = subparsers.add_parser(
        "apply",
        parents=[common],
        help="Terapkan perubahan dengan konfirmasi",
    )
    apply_p.add_argument(
        "--yes",
        "-y",
        action="store_true",
        default=False,
        help="Terapkan tanpa konfirmasi",
    )
    apply_p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Identik dengan plan tetapi lewat jalur apply",
    )
    apply_p.add_argument(
        "--confirm-timeout",
        type=int,
        default=90,
        help="Timeout safety timer dalam detik (default: 90)",
    )
    apply_p.add_argument(
        "--saya-sudah-uji-login-kunci",
        action="store_true",
        default=False,
        help="Bypass gerbang konfirmasi manusia SSH jika kunci sudah diuji",
    )

    # verify
    subparsers.add_parser(
        "verify",
        parents=[common],
        help="Cek kesesuaian tanpa mengubah",
    )

    # rollback
    rollback_p = subparsers.add_parser(
        "rollback",
        parents=[common],
        help="Kembalikan run dari journal",
    )
    rollback_p.add_argument(
        "run_id",
        nargs="?",
        default=None,
        help="ID run yang ingin di-rollback (default: run terakhir)",
    )
    rollback_p.add_argument(
        "--list",
        action="store_true",
        default=False,
        help="Daftar run yang tersimpan dalam journal",
    )
    rollback_p.add_argument(
        "--yes",
        "-y",
        action="store_true",
        default=False,
        help="Lanjutkan tanpa konfirmasi",
    )
    rollback_p.add_argument(
        "--reason",
        default="manual",
        choices=["manual", "timer"],
        help="Alasan rollback (default: manual)",
    )

    # watch
    watch_p = subparsers.add_parser(
        "watch",
        parents=[common],
        help="Monitoring sistem berkala",
    )
    watch_sub = watch_p.add_subparsers(dest="watch_command")

    watch_run_p = watch_sub.add_parser(
        "run",
        parents=[common],
        help="Jalankan satu siklus monitoring",
    )
    watch_run_p.add_argument(
        "--watch-config",
        default="/etc/hostkeeper/watch.yml",
        help="Path ke file watch.yml",
    )
    watch_run_p.add_argument(
        "--state-db",
        default="/var/lib/hostkeeper/state.db",
        help="Path ke file state.db",
    )
    watch_run_p.add_argument(
        "--lock-path",
        default="/run/hostkeeper.lock",
        help="Path ke file lock",
    )

    watch_sub.add_parser(
        "enable",
        parents=[common],
        help="Aktifkan timer monitoring systemd",
    )

    watch_sub.add_parser(
        "disable",
        parents=[common],
        help="Nonaktifkan timer monitoring systemd",
    )

    watch_test_p = watch_sub.add_parser(
        "test-notify",
        parents=[common],
        help="Uji coba pengiriman webhook",
    )
    watch_test_p.add_argument(
        "--watch-config",
        default="/etc/hostkeeper/watch.yml",
        help="Path ke file watch.yml",
    )

    # status
    status_p = subparsers.add_parser(
        "status",
        parents=[common],
        help="Kartu kesehatan dan kesesuaian profil",
    )
    status_p.add_argument(
        "--watch-config",
        default="/etc/hostkeeper/watch.yml",
        help="Path ke file watch.yml",
    )
    status_p.add_argument(
        "--state-db",
        default="/var/lib/hostkeeper/state.db",
        help="Path ke file state.db",
    )

    # setup
    subparsers.add_parser(
        "setup",
        parents=[common],
        help="Wizard interaktif untuk membuat profil",
    )

    return parser


def cmd_version(args: argparse.Namespace, out: IO[str] = sys.stdout) -> int:
    """Menampilkan versi dan info lingkungan."""
    profile_path = Path(args.config)
    env = detect_env(profile_path=profile_path)
    support = (
        messages.VERSION_SUPPORTED if env.is_supported else messages.VERSION_UNSUPPORTED
    )
    systemd_status = (
        messages.VERSION_SYSTEMD_ACTIVE
        if env.systemd_active
        else messages.VERSION_SYSTEMD_INACTIVE
    )
    profile_exists = (
        messages.PROFILE_EXISTS
        if profile_path.is_file()
        else messages.PROFILE_NOT_FOUND
    )

    print(f"hostkeeper {__version__}", file=out)
    print(
        messages.VERSION_OS.format(os_name=env.os_name, support=support),
        file=out,
    )
    print(
        messages.VERSION_PYTHON.format(python_version=env.python_version),
        file=out,
    )
    print(messages.VERSION_SYSTEMD.format(status=systemd_status), file=out)
    print(
        messages.VERSION_PROFILE.format(path=profile_path, exists=profile_exists),
        file=out,
    )
    return EXIT_OK


def cmd_plan(args: argparse.Namespace, out: IO[str] = sys.stdout) -> int:
    """Menjalankan plan dan menampilkan perubahan."""
    profile_path = Path(args.config)
    try:
        profile = load_profile(profile_path)
    except ProfileValidationError as exc:
        print(
            f"ERROR: {messages.ERROR_PROFILE_INVALID.format(detail=exc)}",
            file=sys.stderr,
        )
        return EXIT_USAGE

    use_json: bool = getattr(args, "json", False)

    runner = ReadOnlyRunner(SubprocessRunner())
    fs = ReadOnlyFileOps()
    planner = Planner(profile, runner, fs)

    plan_report = planner.plan()

    print(f"hostkeeper {__version__} plan", file=out)
    print(
        messages.PLAN_PROFILE_LINE.format(path=profile_path, version=profile.version),
        file=out,
    )

    # Tampilkan host saat ini
    current_host = ""
    for item in plan_report.items:
        if item.step.name == "hostname":
            current_host = item.check_result.current
            break
    if not current_host:
        try:
            current_host = socket.gethostname()
        except OSError:
            current_host = "-"

    print(messages.PLAN_HOST_LINE.format(hostname=current_host), file=out)

    if use_json:
        print_plan_json(
            version=__version__,
            profile_path=str(profile_path),
            plan_items=plan_report.items,
            out=out,
        )
    else:
        print("", file=out)
        print_plan_table(plan_report.items, out=out)

        print("", file=out)
        summary = format_plan_summary(
            changes=plan_report.total_changes,
            ok=plan_report.total_compliant,
            high_risk=plan_report.total_high_risk,
        )
        print(summary, file=out)
        if plan_report.total_changes > 0:
            print(messages.PLAN_FOOTER, file=out)

    check_flag: bool = getattr(args, "check", False)
    if check_flag and plan_report.total_changes > 0:
        return EXIT_DRIFT

    return EXIT_OK


def cmd_apply(args: argparse.Namespace, out: IO[str] = sys.stdout) -> int:
    """Menerapkan perubahan ke sistem."""
    profile_path = Path(args.config)

    # Harus root
    if os.geteuid() != 0:
        print(f"ERROR: {messages.ERROR_APPLY_NEEDS_ROOT}", file=sys.stderr)
        return EXIT_ENV

    try:
        profile = load_profile(profile_path)
    except ProfileValidationError as exc:
        print(
            f"ERROR: {messages.ERROR_PROFILE_INVALID.format(detail=exc)}",
            file=sys.stderr,
        )
        return EXIT_USAGE

    dry_run: bool = getattr(args, "dry_run", False)
    yes: bool = getattr(args, "yes", False)

    run_id = make_run_id()
    profile_hash = sha256_file(profile_path)

    print(
        messages.APPLY_HEADER.format(version=__version__, run_id=run_id),
        file=out,
    )

    # Ambil lock
    lock = LockManager()
    try:
        lock.acquire()
    except LockConflict:
        print(f"ERROR: {messages.LOCK_CONFLICT}", file=sys.stderr)
        return EXIT_LOCK

    try:
        runner = SubprocessRunner()
        fs = RealFileOps(run_id=run_id)
        planner = Planner(profile, runner, fs)

        plan_report = planner.plan()

        # Tampilkan tabel plan
        print("", file=out)
        print_plan_table(plan_report.items, out=out)

        # Setup audit dan journal
        audit = AuditWriter(run_id=run_id)
        audit.log_run_start(str(profile_path))
        journal = JournalWriter(
            run_id=run_id,
            profile_sha256=profile_hash,
        )

        # Siapkan pasangan (step, changes)
        bypass_human_gate: bool = getattr(args, "saya_sudah_uji_login_kunci", False)
        for item in plan_report.items:
            if hasattr(item.step, "bypass_human_gate"):
                setattr(item.step, "bypass_human_gate", bypass_human_gate)

        steps_with_changes = [(item.step, item.changes) for item in plan_report.items]

        confirm_timeout: int = getattr(args, "confirm_timeout", 90)

        executor = Executor(
            steps_with_changes=steps_with_changes,
            run_id=run_id,
            profile_path=profile_path,
            audit=audit,
            journal=journal,
            out=out,
            dry_run=dry_run,
            yes=yes,
            runner=runner,
            confirm_timeout=confirm_timeout,
        )

        report = executor.run()

        if report.aborted:
            return EXIT_OK

        if report.n_failed > 0:
            return EXIT_ERROR

        return EXIT_OK

    finally:
        lock.release()


def cmd_verify(args: argparse.Namespace, out: IO[str] = sys.stdout) -> int:
    """Memeriksa kesesuaian tanpa mengubah sistem."""
    profile_path = Path(args.config)
    try:
        profile = load_profile(profile_path)
    except ProfileValidationError as exc:
        print(
            f"ERROR: {messages.ERROR_PROFILE_INVALID.format(detail=exc)}",
            file=sys.stderr,
        )
        return EXIT_USAGE

    use_json: bool = getattr(args, "json", False)

    runner = ReadOnlyRunner(SubprocessRunner())
    fs = ReadOnlyFileOps()
    steps = [cls(profile, runner, fs) for cls in REGISTRY]
    verify_items = [(s, s.check()) for s in steps if s.enabled()]

    if use_json:
        drift = print_verify_json(verify_items, out=out)
    else:
        drift = print_verify_table(verify_items, out=out)
        if drift == 0:
            print(messages.VERIFY_ALL_OK, file=out)
        else:
            print(
                messages.VERIFY_DRIFT.format(n=drift),
                file=out,
            )

    return EXIT_DRIFT if drift > 0 else EXIT_OK


def cmd_rollback(args: argparse.Namespace, out: IO[str] = sys.stdout) -> int:
    """Mengembalikan konfigurasi sistem dari journal run terdahulu."""
    mgr = RollbackManager(print_fn=lambda msg: print(msg, file=out))

    if getattr(args, "list", False):
        runs = mgr.list_runs()
        if not runs:
            print(messages.ROLLBACK_LIST_EMPTY, file=out)
            return EXIT_OK
        print(messages.ROLLBACK_LIST_HEADER, file=out)
        for r in runs:
            print(
                f"  {r['run_id']} (v{r['hostkeeper']}, {r['steps_count']} steps)",
                file=out,
            )
        return EXIT_OK

    if os.geteuid() != 0:
        print(f"ERROR: {messages.ROLLBACK_ERROR_NEEDS_ROOT}", file=sys.stderr)
        return EXIT_ENV

    lock_mgr = LockManager(Path("/run/hostkeeper.lock"))
    try:
        lock_mgr.acquire()
    except LockConflict:
        print(f"ERROR: {messages.LOCK_CONFLICT}", file=sys.stderr)
        return EXIT_LOCK

    try:
        ok = mgr.rollback(
            run_id=getattr(args, "run_id", None),
            yes=getattr(args, "yes", False),
            reason=getattr(args, "reason", "manual"),
        )
        return EXIT_OK if ok else EXIT_ERROR
    except RollbackError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USAGE
    finally:
        lock_mgr.release()


def cmd_setup(args: argparse.Namespace, out: IO[str] = sys.stdout) -> int:
    """Menjalankan wizard interaktif untuk membuat profil."""
    profile_path = Path(args.config)
    fs = RealFileOps()

    wizard = Wizard(
        profile_path=profile_path,
        fs=fs,
        out=out,
    )

    try:
        should_plan = wizard.run()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{messages.WIZARD_CANCELLED}", file=out)
        return EXIT_OK

    if should_plan:
        # Jalankan plan, TIDAK pernah apply
        return cmd_plan(args, out=out)

    return EXIT_OK


def cmd_watch(args: argparse.Namespace, out: IO[str] = sys.stdout) -> int:
    """Menangani subperintah hostkeeper watch."""
    watch_cmd = getattr(args, "watch_command", None)

    if watch_cmd == "enable":
        runner = SubprocessRunner()
        res = runner.run(
            ["systemctl", "enable", "--now", "hostkeeper-watch.timer"],
            mutates=True,
        )
        if res.ok:
            print(messages.WATCH_TIMER_ENABLED, file=out)
            return EXIT_OK
        print(f"ERROR: {res.stderr or res.stdout}", file=sys.stderr)
        return EXIT_ERROR

    elif watch_cmd == "disable":
        runner = SubprocessRunner()
        res = runner.run(
            ["systemctl", "disable", "--now", "hostkeeper-watch.timer"],
            mutates=True,
        )
        if res.ok:
            print(messages.WATCH_TIMER_DISABLED, file=out)
            return EXIT_OK
        print(f"ERROR: {res.stderr or res.stdout}", file=sys.stderr)
        return EXIT_ERROR

    elif watch_cmd == "test-notify":
        watch_cfg_path = Path(
            getattr(args, "watch_config", "/etc/hostkeeper/watch.yml")
        )
        check_watch_config_permissions(watch_cfg_path, out_err=sys.stderr)
        if not watch_cfg_path.is_file():
            print(
                messages.WATCH_NO_WEBHOOK_URL.format(path=watch_cfg_path),
                file=sys.stderr,
            )
            return EXIT_USAGE

        webhook_url = ""
        fmt = "slack"
        try:
            raw = yaml.safe_load(watch_cfg_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                webhook_url = str(raw.get("webhook_url", "")).strip()
                fmt = str(raw.get("webhook_format", "slack")).strip()
        except Exception as exc:
            print(f"ERROR: Format {watch_cfg_path} tidak valid: {exc}", file=sys.stderr)
            return EXIT_USAGE

        if not webhook_url:
            print(
                messages.WATCH_NO_WEBHOOK_URL.format(path=watch_cfg_path),
                file=sys.stderr,
            )
            return EXIT_USAGE

        hostname = socket.gethostname()
        payload = format_payload(
            fmt,
            hostname,
            ["Uji coba notifikasi hostkeeper watch."],
            level="ok",
        )
        ok = send_webhook(webhook_url, payload, out_err=sys.stderr)
        masked = mask_url(webhook_url)
        if ok:
            print(messages.WATCH_TEST_SUCCESS.format(url=masked), file=out)
            return EXIT_OK
        else:
            print(messages.WATCH_TEST_FAILED.format(url=masked), file=sys.stderr)
            return EXIT_ERROR

    elif watch_cmd == "run":
        # Ambil lock non-blocking
        lock_file = Path(getattr(args, "lock_path", "/run/hostkeeper.lock"))
        lock = LockManager(lock_file)
        try:
            lock.acquire()
        except LockConflict:
            print(messages.WATCH_CYCLE_SKIPPED, file=out)
            return EXIT_OK

        try:
            ctx = CollectContext()
            metrics = collect_all(ctx)

            # Cek profil jika ada
            profile_path = Path(args.config)
            prof = load_profile_if_exists(profile_path)
            if prof is not None:
                prof_metrics, _ = check_profile_compliance(
                    prof, ctx.runner, ctx.fileops
                )
                metrics.extend(prof_metrics)

            state_db_path = Path(
                getattr(args, "state_db", "/var/lib/hostkeeper/state.db")
            )
            state = StateManager(state_db_path)
            now_ts = time.time()
            state.save_metrics(metrics, ts=now_ts)

            previous_alerts = state.get_alerts()
            watch_cfg_path = Path(
                getattr(args, "watch_config", "/etc/hostkeeper/watch.yml")
            )
            check_watch_config_permissions(watch_cfg_path, out_err=sys.stderr)
            evaluator = Evaluator(watch_cfg_path)
            results = evaluator.evaluate(
                metrics, previous_alerts=previous_alerts, now=now_ts
            )

            # Identifikasi alert yang perlu dinotifikasikan
            alerts_to_notify: list[str] = []
            highest_level = "ok"

            for r in results:
                if r.alert_needed:
                    alerts_to_notify.append(r.message)
                    if r.status == "crit":
                        highest_level = "crit"
                    elif r.status == "warn" and highest_level != "crit":
                        highest_level = "warn"

                if r.is_transition:
                    if r.status == "ok":
                        state.clear_alert(r.metric_name)
                    else:
                        state.set_alert(
                            r.metric_name,
                            status=r.status,
                            since=now_ts,
                            last_notified=now_ts,
                        )

            # Kirim webhook jika ada alert
            if alerts_to_notify and watch_cfg_path.is_file():
                try:
                    raw = yaml.safe_load(watch_cfg_path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict) and raw.get("webhook_url"):
                        webhook_url = str(raw["webhook_url"]).strip()
                        fmt = str(raw.get("webhook_format", "slack")).strip()
                        hostname = socket.gethostname()
                        payload = format_payload(
                            fmt,
                            hostname,
                            alerts_to_notify,
                            level=highest_level,
                        )
                        send_webhook(webhook_url, payload, out_err=sys.stderr)
                except Exception:
                    pass

            state.prune_retention(now=now_ts)
            return EXIT_OK
        finally:
            lock.release()

    else:
        print(
            "Subperintah watch dibutuhkan: run, enable, disable, test-notify",
            file=sys.stderr,
        )
        return EXIT_USAGE


def cmd_status(args: argparse.Namespace, out: IO[str] = sys.stdout) -> int:
    """Menampilkan status kesehatan metrik sistem dan kesesuaian profil."""
    ctx = CollectContext()
    metrics = collect_all(ctx)

    watch_cfg_path = Path(getattr(args, "watch_config", "/etc/hostkeeper/watch.yml"))
    evaluator = Evaluator(watch_cfg_path)
    eval_results = evaluator.evaluate(metrics, previous_alerts={})
    eval_map = {r.metric_name: r for r in eval_results}

    metrics_evaluated: list[Metric] = []
    for m in metrics:
        evaluated_status = (
            eval_map[m.name].status if m.name in eval_map else m.status_hint
        )
        metrics_evaluated.append(
            Metric(
                name=m.name,
                value=m.value,
                unit=m.unit,
                status_hint=evaluated_status,
            )
        )

    profile_path = Path(args.config)
    prof = load_profile_if_exists(profile_path)
    compliances: list[StepCompliance] = []
    if prof is not None:
        _, compliances = check_profile_compliance(prof, ctx.runner, ctx.fileops)

    hostname = socket.gethostname()
    json_mode: bool = getattr(args, "json", False)
    no_color: bool = getattr(args, "no_color", False)

    if json_mode:
        warn_cnt, crit_cnt, drift_cnt = print_status_json(
            __version__,
            hostname,
            metrics_evaluated,
            compliances,
            out=out,
        )
    else:
        warn_cnt, crit_cnt, drift_cnt = print_status_table(
            __version__,
            hostname,
            metrics_evaluated,
            compliances,
            no_color=no_color,
            out=out,
        )

    if warn_cnt > 0 or crit_cnt > 0 or drift_cnt > 0:
        return EXIT_DRIFT
    return EXIT_OK


def main(argv: Sequence[str] | None = None, out: IO[str] = sys.stdout) -> int:
    """Entrypoint utama CLI. Mengembalikan exit code."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE

    verbose: bool = getattr(args, "verbose", False)
    command = getattr(args, "command", None)

    if command is None or command == "version":
        return cmd_version(args, out=out)

    try:
        if command == "plan":
            return cmd_plan(args, out=out)
        elif command == "apply":
            return cmd_apply(args, out=out)
        elif command == "verify":
            return cmd_verify(args, out=out)
        elif command == "rollback":
            return cmd_rollback(args, out=out)
        elif command == "setup":
            return cmd_setup(args, out=out)
        elif command == "watch":
            return cmd_watch(args, out=out)
        elif command == "status":
            return cmd_status(args, out=out)
        else:
            parser.print_help(file=sys.stderr)
            return EXIT_USAGE
    except ProfileValidationError as exc:
        print(
            f"ERROR: {messages.ERROR_PROFILE_INVALID.format(detail=exc)}",
            file=sys.stderr,
        )
        return EXIT_USAGE
    except Exception as exc:
        if verbose:
            traceback.print_exc(file=sys.stderr)
        print(
            f"ERROR: {messages.ERROR_UNEXPECTED.format(detail=exc)}",
            file=sys.stderr,
        )
        return EXIT_ERROR
