"""Steps package for individual configuration steps."""

from __future__ import annotations

from hostkeeper.engine.step import Step
from hostkeeper.steps.hostname import HostnameStep
from hostkeeper.steps.packages import PackagesStep
from hostkeeper.steps.timezone import TimezoneStep

REGISTRY: tuple[type[Step], ...] = (
    HostnameStep,
    TimezoneStep,
    PackagesStep,
)

__all__ = [
    "REGISTRY",
    "HostnameStep",
    "TimezoneStep",
    "PackagesStep",
]
