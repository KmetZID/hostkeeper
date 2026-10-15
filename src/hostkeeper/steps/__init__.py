"""Steps package for individual configuration steps."""

from __future__ import annotations

from hostkeeper.engine.step import Step
from hostkeeper.steps.hostname import HostnameStep
from hostkeeper.steps.timezone import TimezoneStep

REGISTRY: tuple[type[Step], ...] = (
    HostnameStep,
    TimezoneStep,
)

__all__ = [
    "REGISTRY",
    "HostnameStep",
    "TimezoneStep",
]
