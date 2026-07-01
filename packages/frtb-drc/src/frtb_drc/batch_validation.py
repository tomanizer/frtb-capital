"""Validation stage for DRC columnar batch inputs."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, cast

import numpy as np

from frtb_drc._batch_columns import ObjectArray
from frtb_drc._validation_utils import require_text as _required_text
from frtb_drc.data_models import DrcCalculationContext, DrcRiskClass
from frtb_drc.fair_value_cap import validate_fair_value_cap_evidence
from frtb_drc.fx import validate_fx_rates
from frtb_drc.regimes import (
    EU_CRR3_PROFILE_ID,
    PRA_UK_CRR_PROFILE_ID,
    DrcRuleProfile,
    ensure_risk_class_supported,
)
from frtb_drc.risk_weight_evidence import effective_risk_weights
from frtb_drc.validation import (
    DrcInputError,
    chargeable_non_securitisation_bucket_keys,
    chargeable_securitisation_non_ctp_bucket_keys,
    ensure_chargeable_credit_quality,
    ensure_chargeable_non_securitisation_bucket,
    ensure_chargeable_securitisation_non_ctp_bucket,
)

if TYPE_CHECKING:
    from frtb_drc.batch import DrcPositionBatch

_COMPLETE_SEC_NON_CTP_EVIDENCE_PROFILES = {EU_CRR3_PROFILE_ID, PRA_UK_CRR_PROFILE_ID}


def validate_batch_context(context: DrcCalculationContext) -> None:
    """Validate DRC batch calculation context before capital aggregation.

    Parameters
    ----------
    context : DrcCalculationContext
        Run context containing profile, scope, FX, citation policy, and risk
        weight evidence used by batch capital calculation.
    """

    if context.run_id.strip() == "":
        raise DrcInputError("run_id must be non-empty")
    if context.base_currency.strip() == "":
        raise DrcInputError("base_currency must be non-empty")
    if context.profile_id.strip() == "":
        raise DrcInputError("profile_id must be non-empty")
    if context.citation_policy.strip() == "":
        raise DrcInputError("citation_policy must be non-empty")
    if context.citation_policy.strip().lower() != "strict":
        raise DrcInputError(f"unsupported citation_policy: {context.citation_policy}")
    validate_fx_rates(context)
    effective_risk_weights(context, risk_class=DrcRiskClass.SECURITISATION_NON_CTP)
    validate_fair_value_cap_evidence(
        context.securitisation_non_ctp_fair_value_cap_evidence,
        context=context,
    )
    _validate_context_text_map(
        context.securitisation_non_ctp_offset_groups,
        field_name="context.securitisation_non_ctp_offset_groups",
    )
    effective_risk_weights(context, risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO)
    _validate_context_text_map(context.ctp_offset_groups, field_name="context.ctp_offset_groups")


def validate_supported_batch_run(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
    profile: DrcRuleProfile,
) -> None:
    """Validate that a batch is compatible with the scoped run context.

    Parameters
    ----------
    batch : DrcPositionBatch
        Canonical columnar DRC position batch.
    context : DrcCalculationContext
        Run context whose desk, legal entity, profile, and evidence maps scope
        the calculation.
    profile : DrcRuleProfile
        Active profile metadata used to reject unsupported risk-class paths.
    """

    risk_class = batch_risk_class(batch)
    ensure_risk_class_supported(profile, risk_class)
    scoped_desk_id = context.desk_id.strip()
    scoped_legal_entity = context.legal_entity.strip()
    if scoped_desk_id:
        _raise_first_mismatch(
            batch.desk_ids,
            scoped_desk_id,
            message=lambda index: (
                f"position {batch.position_ids[index]} desk_id {batch.desk_ids[index]} "
                f"does not match context desk_id {scoped_desk_id}"
            ),
        )
    if scoped_legal_entity:
        _raise_first_mismatch(
            batch.legal_entities,
            scoped_legal_entity,
            message=lambda index: (
                f"position {batch.position_ids[index]} legal_entity "
                f"{batch.legal_entities[index]} does not match context legal_entity "
                f"{scoped_legal_entity}"
            ),
        )
    if risk_class is DrcRiskClass.SECURITISATION_NON_CTP:
        risk_weights = effective_risk_weights(
            context,
            risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        )
        _validate_context_position_map(
            batch,
            risk_weights,
            field_name="context.securitisation_non_ctp_risk_weights",
        )
        _validate_context_position_map(
            batch,
            context.securitisation_non_ctp_offset_groups,
            field_name="context.securitisation_non_ctp_offset_groups",
            require_all=context.profile_id in _COMPLETE_SEC_NON_CTP_EVIDENCE_PROFILES,
        )
        _validate_context_position_map(
            batch,
            context.securitisation_non_ctp_fair_value_cap_evidence,
            field_name="context.securitisation_non_ctp_fair_value_cap_evidence",
            require_all=context.profile_id in _COMPLETE_SEC_NON_CTP_EVIDENCE_PROFILES,
        )
    elif risk_class is DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        risk_weights = effective_risk_weights(
            context,
            risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        )
        _validate_context_position_map(
            batch,
            risk_weights,
            field_name="context.ctp_risk_weights",
        )
        _validate_context_position_map(
            batch,
            context.ctp_offset_groups,
            field_name="context.ctp_offset_groups",
            require_all=context.profile_id == EU_CRR3_PROFILE_ID,
        )


def batch_risk_class(batch: DrcPositionBatch) -> DrcRiskClass:
    """Return the single risk class represented by a DRC batch.

    Parameters
    ----------
    batch : DrcPositionBatch
        Canonical columnar DRC position batch.

    Returns
    -------
    DrcRiskClass
        The unique risk class carried by the batch.
    """

    unique = tuple(sorted(np.unique(batch.risk_classes)))
    if len(unique) != 1:
        raise DrcInputError(
            "DRC batch calculation requires one risk_class; mixed risk classes must "
            "be split into class-specific batches"
        )
    return DrcRiskClass(cast(str, unique[0]))


def validate_batch_columns(
    batch: DrcPositionBatch,
    *,
    expected_risk_class: DrcRiskClass,
    profile_id: str,
) -> None:
    """Validate canonical DRC batch columns for one risk class.

    Parameters
    ----------
    batch : DrcPositionBatch
        Canonical columnar DRC position batch.
    expected_risk_class : DrcRiskClass
        Risk class selected by the builder path.
    profile_id : str
        Active DRC rule profile identifier.
    """

    if not np.all(batch.risk_classes == expected_risk_class.value):
        unique = ", ".join(str(value) for value in sorted(np.unique(batch.risk_classes)))
        raise DrcInputError(
            "DRC batch builder requires a single supported risk_class "
            f"{expected_risk_class.value}; received {unique}"
        )
    _validate_common_batch_fields(batch)
    if expected_risk_class is DrcRiskClass.NON_SECURITISATION:
        _validate_nonsec_batch(batch, profile_id=profile_id)
    elif expected_risk_class is DrcRiskClass.SECURITISATION_NON_CTP:
        _validate_securitisation_non_ctp_batch(batch)
    elif expected_risk_class is DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        _validate_ctp_batch(batch)
    else:  # pragma: no cover - all enum values are handled above.
        raise DrcInputError(f"unsupported DRC batch risk_class: {expected_risk_class.value}")


def _validate_context_text_map(values: Mapping[str, str], *, field_name: str) -> None:
    for position_id, value in values.items():
        _required_text(position_id, f"{field_name} position_id")
        _required_text(value, f"{field_name}[{position_id!r}]")


def _validate_context_position_map(
    batch: DrcPositionBatch,
    values: Mapping[str, object],
    *,
    field_name: str,
    require_all: bool = True,
) -> None:
    position_ids = {cast(str, position_id) for position_id in batch.position_ids.tolist()}
    keys = {str(position_id) for position_id in values}
    if require_all:
        missing = sorted(position_ids - keys)
        if missing:
            raise DrcInputError(f"{field_name} is required for positions: " + ", ".join(missing))
    unused = sorted(keys - position_ids)
    if unused:
        raise DrcInputError(f"{field_name} contains unused position ids: " + ", ".join(unused))


def _validate_common_batch_fields(batch: DrcPositionBatch) -> None:
    if not np.all(np.isfinite(batch.notionals)):
        raise DrcInputError("notional values must be finite")
    if not np.all(np.isfinite(batch.maturity_years)):
        raise DrcInputError("maturity_years values must be finite")
    if np.any(batch.maturity_years < 0.0):
        raise DrcInputError("maturity_years values must be non-negative")
    for field_name, values in (
        ("market_value", batch.market_values),
        ("cumulative_pnl", batch.cumulative_pnls),
        ("lgd_override", batch.lgd_overrides),
    ):
        mask = ~np.isnan(values)
        if bool(np.any(mask & ~np.isfinite(values))):
            raise DrcInputError(f"{field_name} values must be finite when present")
    if bool(np.any(~batch.lineage_present)):
        raise DrcInputError("lineage is required")
    _raise_first_mismatch(
        batch.lineage_source_systems,
        "",
        mismatch_when_equal=True,
        message=lambda _index: "lineage.source_system must be non-empty",
    )
    _raise_first_mismatch(
        batch.lineage_source_files,
        "",
        mismatch_when_equal=True,
        message=lambda _index: "lineage.source_file must be non-empty",
    )


def _validate_nonsec_batch(batch: DrcPositionBatch, *, profile_id: str) -> None:
    if np.any(batch.issuer_ids == None):  # noqa: E711
        raise DrcInputError("issuer_id is required for non-securitisation DRC batch")
    if np.any(batch.seniorities == None):  # noqa: E711
        raise DrcInputError("seniority is required for non-securitisation DRC batch")
    if np.any(batch.credit_qualities == None):  # noqa: E711
        raise DrcInputError("credit_quality is required for non-securitisation DRC batch")
    bucket_mask = np.isin(
        batch.bucket_keys,
        chargeable_non_securitisation_bucket_keys(profile_id=profile_id),
    )
    if not bool(np.all(bucket_mask)):
        first = int(np.argmax(~bucket_mask))
        ensure_chargeable_non_securitisation_bucket(
            cast(str, batch.bucket_keys[first]),
            position_id=cast(str, batch.position_ids[first]),
            profile_id=profile_id,
        )
    for quality in sorted(set(cast(str, item) for item in batch.credit_qualities.tolist())):
        first = int(np.argmax(batch.credit_qualities == quality))
        ensure_chargeable_credit_quality(
            quality,
            position_id=cast(str, batch.position_ids[first]),
            profile_id=profile_id,
        )


def _validate_securitisation_non_ctp_batch(batch: DrcPositionBatch) -> None:
    if np.any(batch.tranche_ids == None):  # noqa: E711
        raise DrcInputError("tranche_id is required for securitisation non-CTP DRC batch")
    bucket_mask = np.isin(
        batch.bucket_keys,
        chargeable_securitisation_non_ctp_bucket_keys(),
    )
    if not bool(np.all(bucket_mask)):
        first = int(np.argmax(~bucket_mask))
        ensure_chargeable_securitisation_non_ctp_bucket(
            cast(str, batch.bucket_keys[first]),
            position_id=cast(str, batch.position_ids[first]),
        )
    _validate_market_value_default_exposure_batch(
        batch,
        risk_class_label="securitisation non-CTP",
    )


def _validate_ctp_batch(batch: DrcPositionBatch) -> None:
    missing_identity = (
        (batch.tranche_ids == None)  # noqa: E711
        & (batch.index_series_ids == None)  # noqa: E711
        & (batch.issuer_ids == None)  # noqa: E711
    )
    if bool(np.any(missing_identity)):
        first = int(np.nonzero(missing_identity)[0][0])
        raise DrcInputError(
            "CTP positions require tranche_id, index_series_id, or issuer_id: "
            f"{batch.position_ids[first]}"
        )
    _validate_market_value_default_exposure_batch(batch, risk_class_label="CTP")


def _validate_market_value_default_exposure_batch(
    batch: DrcPositionBatch,
    *,
    risk_class_label: str,
) -> None:
    missing_market_value = np.isnan(batch.market_values)
    if bool(np.any(missing_market_value)):
        first = int(np.nonzero(missing_market_value)[0][0])
        raise DrcInputError(
            f"{risk_class_label} position {batch.position_ids[first]} requires market_value"
        )
    if bool(np.any(~np.isnan(batch.lgd_overrides))):
        raise DrcInputError(
            f"{risk_class_label} gross JTD uses market value; lgd_override is not supported"
        )


def _raise_first_mismatch(
    values: ObjectArray,
    expected: str,
    *,
    mismatch_when_equal: bool = False,
    message: Callable[[int], str],
) -> None:
    mismatch = values == expected if mismatch_when_equal else values != expected
    if bool(np.any(mismatch)):
        index = int(np.nonzero(mismatch)[0][0])
        raise DrcInputError(message(index))


__all__ = [
    "batch_risk_class",
    "validate_batch_columns",
    "validate_batch_context",
    "validate_supported_batch_run",
]
