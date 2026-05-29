"""Shared primitives for the frtb-capital suite."""

from frtb_common._version import __version__
from frtb_common.status import (
    CapitalComponentMetadata,
    ImplementationStatus,
    NotImplementedCapitalComponentError,
    UnsupportedRegulatoryFeatureError,
    ValidationStatus,
)

__all__ = [
    "CapitalComponentMetadata",
    "ImplementationStatus",
    "NotImplementedCapitalComponentError",
    "UnsupportedRegulatoryFeatureError",
    "ValidationStatus",
    "__version__",
]
