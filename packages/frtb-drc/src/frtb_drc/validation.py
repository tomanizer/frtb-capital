"""Validation helpers for canonical DRC inputs."""

from __future__ import annotations

import math
from collections.abc import Iterable

from frtb_drc.data_models import DrcPosition, DrcRiskClass


class DrcInputError(ValueError):
    """Raised when canonical DRC inputs fail deterministic validation."""


def validate_position(position: DrcPosition) -> DrcPosition:
    """Validate one canonical DRC position and return it unchanged."""

    _require_non_empty(position.position_id, "position_id")
    _require_non_empty(position.source_row_id, "source_row_id")
    _require_non_empty(position.desk_id, "desk_id")
    _require_non_empty(position.legal_entity, "legal_entity")
    _require_non_empty(position.currency, "currency")
    _require_non_empty(position.bucket_key, "bucket_key")
    if position.lineage is None:
        raise DrcInputError("lineage is required")
    _require_non_empty(position.lineage.source_system, "lineage.source_system")
    _require_non_empty(position.lineage.source_file, "lineage.source_file")
    _require_non_empty(position.lineage.source_row_id, "lineage.source_row_id")
    if position.source_row_id != position.lineage.source_row_id:
        raise DrcInputError("source_row_id must match lineage.source_row_id")

    _require_finite(position.notional, "notional")
    _require_finite(position.maturity_years, "maturity_years")
    if position.maturity_years < 0:
        raise DrcInputError("maturity_years must be non-negative")
    if position.market_value is not None:
        _require_finite(position.market_value, "market_value")
    if position.cumulative_pnl is not None:
        _require_finite(position.cumulative_pnl, "cumulative_pnl")
    if position.lgd_override is not None:
        _require_finite(position.lgd_override, "lgd_override")
        if not 0 <= position.lgd_override <= 1:
            raise DrcInputError("lgd_override must be between 0 and 1")

    if position.risk_class == DrcRiskClass.NON_SECURITISATION:
        _validate_non_securitisation_identity(position)
    elif position.risk_class == DrcRiskClass.SECURITISATION_NON_CTP:
        _validate_securitisation_identity(position)
    elif position.risk_class == DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        _validate_ctp_identity(position)
    else:  # pragma: no cover - DrcPosition normalises the enum before validation.
        raise DrcInputError(f"unsupported risk_class: {position.risk_class}")

    return position


def validate_positions(positions: Iterable[DrcPosition]) -> tuple[DrcPosition, ...]:
    """Validate a deterministic collection of canonical DRC positions."""

    validated: list[DrcPosition] = []
    seen: set[str] = set()
    for position in positions:
        validate_position(position)
        if position.position_id in seen:
            raise DrcInputError(f"duplicate position_id: {position.position_id}")
        seen.add(position.position_id)
        validated.append(position)
    return tuple(validated)


def _validate_non_securitisation_identity(position: DrcPosition) -> None:
    _require_non_empty(position.issuer_id, "issuer_id")
    if position.seniority is None:
        raise DrcInputError("seniority is required for non-securitisation positions")
    if position.credit_quality is None:
        raise DrcInputError("credit_quality is required for non-securitisation positions")


def _validate_securitisation_identity(position: DrcPosition) -> None:
    _require_non_empty(position.tranche_id, "tranche_id")


def _validate_ctp_identity(position: DrcPosition) -> None:
    if _is_blank(position.tranche_id) and _is_blank(position.index_series_id):
        raise DrcInputError("CTP positions require tranche_id or index_series_id")


def _require_non_empty(value: str | None, field_name: str) -> None:
    if _is_blank(value):
        raise DrcInputError(f"{field_name} must be non-empty")


def _is_blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def _require_finite(value: float, field_name: str) -> None:
    if not math.isfinite(value):
        raise DrcInputError(f"{field_name} must be finite")
