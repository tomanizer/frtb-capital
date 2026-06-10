"""Package-local exception types for SBM validation paths."""

from __future__ import annotations


class SbmInputError(ValueError):
    """Raised when canonical SBM inputs fail deterministic validation."""

    def __init__(self, message: str, *, field: str = "", sensitivity_id: str = "") -> None:
        self.field = field
        self.sensitivity_id = sensitivity_id
        prefix = f"sensitivity {sensitivity_id}: " if sensitivity_id else ""
        suffix = f" [{field}]" if field else ""
        super().__init__(f"{prefix}{message}{suffix}")
