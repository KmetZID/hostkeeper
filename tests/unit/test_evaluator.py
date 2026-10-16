"""Unit test untuk monitor/evaluator.py (Tahap 3.2)."""

from __future__ import annotations

from pathlib import Path

import yaml

from hostkeeper.monitor.collector import Metric
from hostkeeper.monitor.evaluator import Evaluator
from hostkeeper.monitor.state import AlertRecord


def test_evaluator_default_thresholds_ok() -> None:
    evaluator = Evaluator()
    metrics = [
        Metric(name="mem.used_percent", value=50.0, unit="%"),
        Metric(name="cpu.load1_per_core", value=0.5, unit=""),
        Metric(name="disk./.used_percent", value=60.0, unit="%"),
        Metric(name="services.failed_count", value=0, unit=""),
    ]
    results = evaluator.evaluate(metrics, previous_alerts={})
    for res in results:
        assert res.status == "ok"
        assert not res.alert_needed


def test_evaluator_warn_and_crit_thresholds() -> None:
    evaluator = Evaluator()
    metrics = [
        Metric(name="mem.used_percent", value=85.0, unit="%"),  # warn >= 80
        Metric(name="disk./.used_percent", value=95.0, unit="%"),  # crit >= 90
        Metric(name="services.failed_count", value=2, unit=""),  # crit >= 1
    ]
    results = {
        r.metric_name: r for r in evaluator.evaluate(metrics, previous_alerts={})
    }

    assert results["mem.used_percent"].status == "warn"
    assert results["mem.used_percent"].is_transition is True
    assert results["mem.used_percent"].alert_needed is True

    assert results["disk./.used_percent"].status == "crit"
    used_pct_key = "disk./.used_percent"
    assert results[used_pct_key].alert_needed is True
    assert results["services.failed_count"].status == "crit"
    assert results["services.failed_count"].alert_needed is True


def test_evaluator_no_repeat_alert_without_transition() -> None:
    evaluator = Evaluator()
    metrics = [
        Metric(name="mem.used_percent", value=85.0, unit="%"),
    ]
    # Skenario 1: sudah warn sebelumnya
    prev = {
        "mem.used_percent": AlertRecord(
            name="mem.used_percent",
            status="warn",
            since=1000.0,
            last_notified=1000.0,
        )
    }
    results = evaluator.evaluate(metrics, previous_alerts=prev, now=1100.0)
    assert len(results) == 1
    assert results[0].status == "warn"
    assert results[0].is_transition is False
    # Tidak ada alert berulang untuk kondisi yang sama
    assert results[0].alert_needed is False


def test_evaluator_hysteresis_recovery() -> None:
    evaluator = Evaluator()
    # mem_used_percent: warn=80.0, recover=75.0
    prev = {
        "mem.used_percent": AlertRecord(
            name="mem.used_percent",
            status="warn",
            since=1000.0,
            last_notified=1000.0,
        )
    }

    # Kasus 1: Turun ke 78% (di bawah 80, tapi belum di bawah recover 75)
    m1 = [Metric(name="mem.used_percent", value=78.0, unit="%")]
    r1 = evaluator.evaluate(m1, previous_alerts=prev, now=1100.0)[0]
    assert r1.status == "warn"  # Tetap warn karena hysteresis!
    assert r1.alert_needed is False

    # Kasus 2: Turun ke 74% (melewati batas recover 75)
    m2 = [Metric(name="mem.used_percent", value=74.0, unit="%")]
    r2 = evaluator.evaluate(m2, previous_alerts=prev, now=1200.0)[0]
    assert r2.status == "ok"  # Pulih!
    assert r2.is_transition is True
    assert r2.alert_needed is True  # Transisi pemulihan mengirim notifikasi


def test_evaluator_custom_watch_yml(tmp_path: Path) -> None:
    cfg = tmp_path / "watch.yml"
    cfg.write_text(
        yaml.safe_dump(
            {
                "thresholds": {
                    "mem_used_percent": {"warn": 70.0, "crit": 80.0, "recover": 65.0}
                },
                "cooldown_seconds": 1800,
            }
        ),
        encoding="utf-8",
    )
    evaluator = Evaluator(config_path=cfg)
    m = [Metric(name="mem.used_percent", value=72.0, unit="%")]
    r = evaluator.evaluate(m, previous_alerts={})[0]
    assert r.status == "warn"
