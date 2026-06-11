"""Public result models for SBM CRIF adapters."""

from __future__ import annotations

from dataclasses import dataclass

from frtb_sbm.data_models import SbmSensitivity


@dataclass(frozen=True)
class SbmAdapterWarning:
    """Auditable non-fatal CRIF mapping warning."""

    source_row_id: str
    field: str
    message: str


@dataclass(frozen=True)
class SbmRejectedRow:
    """Auditable rejected CRIF row."""

    source_row_id: str
    reason: str
    field: str
    source_row: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class SbmAdapterResult:
    """Adapter output: canonical sensitivities plus warnings and rejected rows."""

    sensitivities: tuple[SbmSensitivity, ...]
    warnings: tuple[SbmAdapterWarning, ...] = ()
    rejected_rows: tuple[SbmRejectedRow, ...] = ()


__all__ = ["SbmAdapterResult", "SbmAdapterWarning", "SbmRejectedRow"]
