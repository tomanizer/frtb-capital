"""Shared RRAO validation error contracts."""

from __future__ import annotations

from typing import Literal

NotionalSignConvention = Literal["gross", "signed_absolute"]


class RraoInputError(ValueError):
    """Raised when canonical RRAO inputs fail deterministic validation."""

    def __init__(self, message: str, *, field: str = "", position_id: str = "") -> None:
        self.field = field
        self.position_id = position_id
        prefix = f"position {position_id}: " if position_id else ""
        suffix = f" [{field}]" if field else ""
        super().__init__(f"{prefix}{message}{suffix}")


__all__ = ["NotionalSignConvention", "RraoInputError"]
