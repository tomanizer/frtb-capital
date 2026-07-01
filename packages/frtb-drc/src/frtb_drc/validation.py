"""Validation helpers for canonical DRC inputs."""

from __future__ import annotations

import math
from collections.abc import Iterable

from frtb_drc.data_models import CreditQuality, DrcPosition, DrcRiskClass


class DrcInputError(ValueError):
    """Raised when canonical DRC inputs fail deterministic validation."""


US_NPR_2_0_PROFILE_ID = "US_NPR_2_0"
BASEL_MAR22_PROFILE_ID = "BASEL_MAR22"
EU_CRR3_PROFILE_ID = "EU_CRR3"
PRA_UK_CRR_PROFILE_ID = "PRA_UK_CRR"

_STRICT_CITATION_POLICY = "strict"
_US_NPR_NONSEC_CREDIT_QUALITIES = (
    CreditQuality.INVESTMENT_GRADE,
    CreditQuality.SPECULATIVE_GRADE,
    CreditQuality.SUB_SPECULATIVE_GRADE,
    CreditQuality.DEFAULTED,
)
_BASEL_MAR22_NONSEC_CREDIT_QUALITIES = (
    CreditQuality.AAA,
    CreditQuality.AA,
    CreditQuality.A,
    CreditQuality.BBB,
    CreditQuality.BB,
    CreditQuality.B,
    CreditQuality.CCC,
    CreditQuality.UNRATED,
    CreditQuality.DEFAULTED,
)
_NONSEC_CREDIT_QUALITIES_BY_PROFILE = {
    US_NPR_2_0_PROFILE_ID: _US_NPR_NONSEC_CREDIT_QUALITIES,
    BASEL_MAR22_PROFILE_ID: _BASEL_MAR22_NONSEC_CREDIT_QUALITIES,
    EU_CRR3_PROFILE_ID: _BASEL_MAR22_NONSEC_CREDIT_QUALITIES,
    PRA_UK_CRR_PROFILE_ID: _BASEL_MAR22_NONSEC_CREDIT_QUALITIES,
}
_US_NPR_NONSEC_BUCKET_KEYS = (
    "NON_US_SOVEREIGN",
    "PSE_GSE",
    "CORPORATE",
    "DEFAULTED",
)
_BASEL_MAR22_NONSEC_BUCKET_KEYS = (
    "CORPORATE",
    "SOVEREIGN",
    "LOCAL_GOVERNMENT_MUNICIPAL",
)
_NONSEC_BUCKET_KEYS_BY_PROFILE = {
    US_NPR_2_0_PROFILE_ID: _US_NPR_NONSEC_BUCKET_KEYS,
    BASEL_MAR22_PROFILE_ID: _BASEL_MAR22_NONSEC_BUCKET_KEYS,
    EU_CRR3_PROFILE_ID: _BASEL_MAR22_NONSEC_BUCKET_KEYS,
    PRA_UK_CRR_PROFILE_ID: _BASEL_MAR22_NONSEC_BUCKET_KEYS,
}
_SEC_NON_CTP_ASSET_CLASSES = (
    "ABCP",
    "AUTO_LOANS_LEASES",
    "RMBS",
    "CREDIT_CARDS",
    "CMBS",
    "CLO",
    "CDO_SQUARED",
    "SME",
    "STUDENT_LOANS",
    "OTHER_RETAIL",
    "OTHER_WHOLESALE",
)
_SEC_NON_CTP_REGIONS = ("ASIA", "EUROPE", "NORTH_AMERICA", "OTHER")
_CHARGEABLE_SEC_NONCTP_BUCKET_KEYS = (
    "SEC_CORPORATE",
    *(
        f"SEC_{asset_class}_{region}"
        for asset_class in _SEC_NON_CTP_ASSET_CLASSES
        for region in _SEC_NON_CTP_REGIONS
    ),
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
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> DrcPosition:
    """Validate one canonical DRC position and return it unchanged.
    Parameters
    ----------
    position : DrcPosition
        Position.
    citation_policy : str, optional
        Citation validation policy (strict by default).
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    DrcPosition
        Validated position with DRC enum values and required fields checked.
    """

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
        _validate_non_securitisation_identity(position, profile_id=profile_id)
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
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> tuple[DrcPosition, ...]:
    """Validate a deterministic collection of canonical DRC positions.
    Parameters
    ----------
    positions : Iterable[DrcPosition]
        Canonical DRC position records.
    citation_policy : str, optional
        Citation validation policy (strict by default).
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[DrcPosition, ...]
        Tuple of validated positions in their original input order.
    """

    _validate_citation_policy(citation_policy)
    validated: list[DrcPosition] = []
    seen: set[str] = set()
    for position in positions:
        validate_position(position, citation_policy=citation_policy, profile_id=profile_id)
        if position.position_id in seen:
            raise DrcInputError(f"duplicate position_id: {position.position_id}")
        seen.add(position.position_id)
        validated.append(position)
    return tuple(validated)


def ensure_chargeable_credit_quality(
    credit_quality: CreditQuality | str,
    *,
    position_id: str | None = None,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> None:
    """Reject credit-quality values outside a profile's non-securitisation table.
    Parameters
    ----------
    credit_quality : CreditQuality | str
        Credit-quality bucket for risk-weight lookup.
    position_id : str | None, optional
        Position identifier for error context.
    profile_id : str, optional
        Active DRC rule profile identifier.
    """

    quality = CreditQuality(credit_quality)
    allowed_qualities = _chargeable_non_securitisation_credit_qualities(profile_id)
    if quality in allowed_qualities:
        return
    allowed = ", ".join(item.value for item in allowed_qualities)
    position_label = "" if position_id is None else f" for position {position_id}"
    citation_hint = _nonsec_credit_quality_citation(profile_id)
    raise DrcInputError(
        f"credit_quality {quality.value}{position_label} is not a chargeable {profile_id} "
        f"DRC non-securitisation credit-quality category; map it to one of {allowed} "
        f"before capital calculation ({citation_hint})"
    )


def chargeable_non_securitisation_bucket_keys(
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> tuple[str, ...]:
    """Return non-securitisation bucket keys with DRC weights for a profile.
    Parameters
    ----------
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[str, ...]
        Deterministically ordered string identifiers.
    """

    return _chargeable_non_securitisation_bucket_keys(profile_id)


def chargeable_securitisation_non_ctp_bucket_keys() -> tuple[str, ...]:
    """Return U.S. NPR 2.0 securitisation non-CTP bucket keys.
    Returns
    -------
    tuple[str, ...]
        Supported securitisation non-CTP bucket keys for chargeable positions.
    """

    return _CHARGEABLE_SEC_NONCTP_BUCKET_KEYS


def ensure_chargeable_non_securitisation_bucket(
    bucket_key: str,
    *,
    position_id: str | None = None,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> None:
    """Reject invented or excluded non-securitisation bucket keys early.
    Parameters
    ----------
    bucket_key : str
        DRC bucket key for the calculation scope.
    position_id : str | None, optional
        Position identifier for error context.
    profile_id : str, optional
        Active DRC rule profile identifier.
    """

    allowed_bucket_keys = _chargeable_non_securitisation_bucket_keys(profile_id)
    if bucket_key in allowed_bucket_keys:
        return

    allowed = ", ".join(allowed_bucket_keys)
    position_label = "" if position_id is None else f" for position {position_id}"
    citation_hint = _nonsec_bucket_citation(profile_id)
    reason = _NON_CHARGEABLE_US_NPR_NONSEC_BUCKET_REASONS.get(
        bucket_key,
        f"not a supported {profile_id} DRC non-securitisation bucket",
    )
    raise DrcInputError(
        f"bucket_key {bucket_key}{position_label} is not a chargeable {profile_id} "
        f"DRC non-securitisation bucket: {reason}. Use one of {allowed}; do not "
        f"create a zero-risk-weight bucket outside the selected rule profile ({citation_hint})"
    )


def ensure_chargeable_securitisation_non_ctp_bucket(
    bucket_key: str,
    *,
    position_id: str | None = None,
) -> None:
    """Reject invented securitisation non-CTP bucket keys early.
    Parameters
    ----------
    bucket_key : str
        DRC bucket key for the calculation scope.
    position_id : str | None, optional
        Position identifier for error context.
    """

    if bucket_key in _CHARGEABLE_SEC_NONCTP_BUCKET_KEYS:
        return

    allowed = ", ".join(_CHARGEABLE_SEC_NONCTP_BUCKET_KEYS)
    position_label = "" if position_id is None else f" for position {position_id}"
    raise DrcInputError(
        f"bucket_key {bucket_key}{position_label} is not a chargeable U.S. NPR 2.0 "
        "DRC securitisation non-CTP bucket. Use SEC_CORPORATE or one SEC_<asset>_<region> "
        "bucket for the eleven asset classes and four regions in proposed section "
        "__.210(c)(3)(i)-(ii) (US_NPR_210_C_3_I_II); do not create a zero-risk-weight "
        f"bucket outside the cited taxonomy. Allowed values: {allowed}"
    )


def _validate_non_securitisation_identity(
    position: DrcPosition,
    *,
    profile_id: str,
) -> None:
    _require_non_empty(position.issuer_id, "issuer_id")
    _require_non_empty(position.bucket_key, "bucket_key")
    bucket_key = position.bucket_key
    assert bucket_key is not None
    ensure_chargeable_non_securitisation_bucket(
        bucket_key,
        position_id=position.position_id,
        profile_id=profile_id,
    )
    if position.seniority is None:
        raise DrcInputError("seniority is required for non-securitisation positions")
    if position.credit_quality is None:
        raise DrcInputError("credit_quality is required for non-securitisation positions")
    ensure_chargeable_credit_quality(
        position.credit_quality,
        position_id=position.position_id,
        profile_id=profile_id,
    )


def _chargeable_non_securitisation_bucket_keys(profile_id: str) -> tuple[str, ...]:
    try:
        return _NONSEC_BUCKET_KEYS_BY_PROFILE[profile_id]
    except KeyError as exc:
        raise DrcInputError(
            f"profile {profile_id} does not define chargeable non-securitisation buckets"
        ) from exc


def _chargeable_non_securitisation_credit_qualities(
    profile_id: str,
) -> tuple[CreditQuality, ...]:
    try:
        return _NONSEC_CREDIT_QUALITIES_BY_PROFILE[profile_id]
    except KeyError as exc:
        raise DrcInputError(
            f"profile {profile_id} does not define chargeable non-securitisation credit qualities"
        ) from exc


def _nonsec_bucket_citation(profile_id: str) -> str:
    return {
        US_NPR_2_0_PROFILE_ID: "US_NPR_210_B_3_I",
        BASEL_MAR22_PROFILE_ID: "BASEL_MAR22_22",
        EU_CRR3_PROFILE_ID: "EU_CRR3_ARTICLE_325Y_1_2",
        PRA_UK_CRR_PROFILE_ID: "PRA_DRC_ARTICLE_325Y",
    }.get(profile_id, profile_id)


def _nonsec_credit_quality_citation(profile_id: str) -> str:
    return {
        US_NPR_2_0_PROFILE_ID: "US_NPR_210_B_3_II",
        BASEL_MAR22_PROFILE_ID: "BASEL_MAR22_24",
        EU_CRR3_PROFILE_ID: "EU_CRR3_ARTICLE_325Y_6",
        PRA_UK_CRR_PROFILE_ID: "PRA_DRC_ARTICLE_325Y",
    }.get(profile_id, profile_id)


def _validate_securitisation_identity(position: DrcPosition) -> None:
    _require_non_empty(position.tranche_id, "tranche_id")
    _require_non_empty(position.bucket_key, "bucket_key")
    bucket_key = position.bucket_key
    assert bucket_key is not None
    ensure_chargeable_securitisation_non_ctp_bucket(
        bucket_key,
        position_id=position.position_id,
    )


def _validate_ctp_identity(position: DrcPosition) -> None:
    if (
        _is_blank(position.tranche_id)
        and _is_blank(position.index_series_id)
        and _is_blank(position.issuer_id)
    ):
        raise DrcInputError("CTP positions require tranche_id, index_series_id, or issuer_id")


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
