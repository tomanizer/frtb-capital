"""Shared package-status primitives for scaffolded capital components."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ImplementationStatus(StrEnum):
    """Implementation state for a suite package."""

    SCAFFOLDED = "scaffolded"
    PARTIAL = "partial"
    IMPLEMENTED = "implemented"


class ValidationStatus(StrEnum):
    """Validation evidence state for a suite package."""

    NOT_STARTED = "not_started"
    PENDING = "pending"
    AVAILABLE = "available"


@dataclass(frozen=True)
class CapitalComponentMetadata:
    """Immutable status metadata exposed by each workspace package."""

    package_name: str
    import_name: str
    component_name: str
    implementation_status: ImplementationStatus
    validation_status: ValidationStatus


class UnsupportedRegulatoryFeatureError(Exception):
    """Raised when a requested regulatory feature is explicitly unsupported."""


class NotImplementedCapitalComponentError(NotImplementedError):
    """Raised by scaffold packages instead of emitting placeholder capital."""

    def __init__(self, *, component: str, feature: str) -> None:
        self.component = component
        self.feature = feature
        super().__init__(f"{component} does not implement {feature} yet.")
