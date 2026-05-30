"""Test-only helpers for JSON-ready audit payload normalisation."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any


def normalise_audit_value(value: object) -> Any:
    if isinstance(value, dict):
        return {str(key): normalise_audit_value(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple | list):
        return [normalise_audit_value(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    return value
