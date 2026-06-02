"""Validation helpers for canonical DRC inputs."""

from __future__ import annotations

import math
from collections.abc import Iterable

from frtb_drc.data_models import CreditQuality, DrcPosition, DrcRiskClass


class DrcInputError(ValueError):
    """Raised when canonical DRC inputs fail deterministic validation."""


_STRICT_CITATION_POLICY = "strict"
_CHARGEABLE_NONSEC_CREDIT_QUALITIES = (
    CreditQuality.INVESTMENT_GRADE,
    CreditQuality.SPECULATIVE_GRADE,
    CreditQuality.SUB_SPECULATIVE_GRADE,
    CreditQuality.DEFAULTED,
)
_CHARGEABLE_NONSEC_BUCKET_KEYS = (
    "NON_US_SOVEREIGN",
    "PSE_GSE",
    "CORPORATE",
    "DEFAULTED",
)
_NON_CHARGEABLE_US_NPR_NONSEC_BUCKET_REASONS = {
    "US_SOVEREIGN": "U.S. sovereign is not one of the four chargeable buckets",
    "SPECIFIED_SUPRANATIONAL": "specified supranational is not one of the four chargeable buckets",
    "MULTILATERAL_DEVELOPMENT_BANK": "MDB is not one of the four chargeable buckets",
    "MDB": "MDB is not one of the four chargeable buckets",
    "MUNICIPAL": "municipal is not a separate bucket; map cited PSE debt to PSE_GSE",
    "LOCAL_GOVERNMENT": "local-government is not a separate bucket; map cited PSE debt to PSE_GSE",
}


def validate_position(
    position: DrcPosition,
    *,
    citation_policy: str = _STRICT_CITATION_POLICY,
) -> DrcPosition:
    """Validate one canonical DRC position and return it unchanged."""

    _validate_citation_policy(citation_policy)
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
    _require_citation_ids(position)

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


def validate_positions(
    positions: Iterable[DrcPosition],
    *,
    citation_policy: str = _STRICT_CITATION_POLICY,
) -> tuple[DrcPosition, ...]:
    """Validate a deterministic collection of canonical DRC positions."""

    _validate_citation_policy(citation_policy)
    validated: list[DrcPosition] = []
    seen: set[str] = set()
    for position in positions:
        validate_position(position, citation_policy=citation_policy)
        if position.position_id in seen:
            raise DrcInputError(f"duplicate position_id: {position.position_id}")
        seen.add(position.position_id)
        validated.append(position)
    return tuple(validated)


def ensure_chargeable_credit_quality(
    credit_quality: CreditQuality | str,
    *,
    position_id: str | None = None,
) -> None:
    """Reject input-only credit-quality sentinels before risk-weight lookup."""

    quality = CreditQuality(credit_quality)
    if quality is not CreditQuality.UNRATED:
        return
    allowed = ", ".join(item.value for item in _CHARGEABLE_NONSEC_CREDIT_QUALITIES)
    position_label = "" if position_id is None else f" for position {position_id}"
    raise DrcInputError(
        f"credit_quality UNRATED{position_label} is not a chargeable U.S. NPR 2.0 "
        f"DRC non-securitisation credit-quality category; map it to one of {allowed} "
        "before capital calculation (US_NPR_210_B_3_II)"
    )


def chargeable_non_securitisation_bucket_keys() -> tuple[str, ...]:
    """Return U.S. NPR 2.0 non-securitisation bucket keys with DRC weights."""

    return _CHARGEABLE_NONSEC_BUCKET_KEYS


def ensure_chargeable_non_securitisation_bucket(
    bucket_key: str,
    *,
    position_id: str | None = None,
) -> None:
    """Reject invented or excluded non-securitisation bucket keys early."""

    if bucket_key in _CHARGEABLE_NONSEC_BUCKET_KEYS:
        return

    allowed = ", ".join(_CHARGEABLE_NONSEC_BUCKET_KEYS)
    position_label = "" if position_id is None else f" for position {position_id}"
    reason = _NON_CHARGEABLE_US_NPR_NONSEC_BUCKET_REASONS.get(
        bucket_key,
        "not a supported U.S. NPR 2.0 DRC non-securitisation bucket",
    )
    raise DrcInputError(
        f"bucket_key {bucket_key}{position_label} is not a chargeable U.S. NPR 2.0 "
        f"DRC non-securitisation bucket: {reason}. Use one of {allowed}; do not "
        "create a zero-risk-weight bucket outside proposed section __.210(b)(3)(i) "
        "(US_NPR_210_B_3_I)"
    )


def _validate_non_securitisation_identity(position: DrcPosition) -> None:
    _require_non_empty(position.issuer_id, "issuer_id")
    _require_non_empty(position.bucket_key, "bucket_key")
    bucket_key = position.bucket_key
    assert bucket_key is not None
    ensure_chargeable_non_securitisation_bucket(
        bucket_key,
        position_id=position.position_id,
    )
    if position.seniority is None:
        raise DrcInputError("seniority is required for non-securitisation positions")
    if position.credit_quality is None:
        raise DrcInputError("credit_quality is required for non-securitisation positions")
    ensure_chargeable_credit_quality(position.credit_quality, position_id=position.position_id)


def _validate_securitisation_identity(position: DrcPosition) -> None:
    _require_non_empty(position.tranche_id, "tranche_id")


def _validate_ctp_identity(position: DrcPosition) -> None:
    if _is_blank(position.tranche_id) and _is_blank(position.index_series_id):
        raise DrcInputError("CTP positions require tranche_id or index_series_id")


def _validate_citation_policy(citation_policy: str) -> None:
    if citation_policy.strip().lower() != _STRICT_CITATION_POLICY:
        raise DrcInputError(f"unsupported citation_policy: {citation_policy}")


def _require_citation_ids(position: DrcPosition) -> None:
    if not position.citation_ids:
        raise DrcInputError("citation_ids must contain at least one citation")
    for citation_id in position.citation_ids:
        if not isinstance(citation_id, str) or _is_blank(citation_id):
            raise DrcInputError("citation_ids must contain non-empty citations")


def _require_non_empty(value: str | None, field_name: str) -> None:
    if _is_blank(value):
        raise DrcInputError(f"{field_name} must be non-empty")


def _is_blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def _require_finite(value: float, field_name: str) -> None:
    if not math.isfinite(value):
        raise DrcInputError(f"{field_name} must be finite")
