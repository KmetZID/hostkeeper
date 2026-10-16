"""Steps package for individual configuration steps."""

from __future__ import annotations

from hostkeeper.engine.step import Step
from hostkeeper.steps.firewall import FirewallStep
from hostkeeper.steps.hostname import HostnameStep
from hostkeeper.steps.packages import PackagesStep
from hostkeeper.steps.sshd import SshdStep
from hostkeeper.steps.sshkeys import SshKeysStep
from hostkeeper.steps.timezone import TimezoneStep
from hostkeeper.steps.updates import UpdatesStep
from hostkeeper.steps.user import UserStep

REGISTRY: tuple[type[Step], ...] = (
    HostnameStep,
    TimezoneStep,
    PackagesStep,
    UserStep,
    SshKeysStep,
    SshdStep,
    UpdatesStep,
    FirewallStep,
)

__all__ = [
    "REGISTRY",
    "HostnameStep",
    "TimezoneStep",
    "PackagesStep",
    "UserStep",
    "SshKeysStep",
    "SshdStep",
    "UpdatesStep",
    "FirewallStep",
]
