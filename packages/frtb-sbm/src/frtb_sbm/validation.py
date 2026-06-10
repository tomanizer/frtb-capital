"""
Validation helpers for canonical SBM inputs.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for validation.py, Basel MAR21.1,
    U.S. NPR 2.0 section V.A.7.a, and SBM-NFR-004.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TypeVar

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm._errors import SbmInputError
from frtb_sbm._text import require_text as _require_text
from frtb_sbm.data_models import (
    SbmCalculationContext,
    SbmPairwiseEvidenceMode,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmRunControls,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
)

EnumT = TypeVar(
    "EnumT",
    SbmPairwiseEvidenceMode,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSignConvention,
)

_STRICT_CITATION_POLICY = "strict"

_TENOR_REQUIRED: frozenset[tuple[SbmRiskClass, SbmRiskMeasure]] = frozenset(
    {
        (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA),
    }
)

_OPTION_TENOR_REQUIRED: frozenset[tuple[SbmRiskClass, SbmRiskMeasure]] = frozenset(
    {
        (risk_class, SbmRiskMeasure.VEGA)
        for risk_class in (
            SbmRiskClass.GIRR,
            SbmRiskClass.FX,
            SbmRiskClass.EQUITY,
            SbmRiskClass.COMMODITY,
            SbmRiskClass.CSR_NONSEC,
            SbmRiskClass.CSR_SEC_NONCTP,
            SbmRiskClass.CSR_SEC_CTP,
        )
    }
)

_QUALIFIER_REQUIRED: frozenset[SbmRiskClass] = frozenset(
    {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskClass.EQUITY,
        SbmRiskClass.COMMODITY,
    }
)

_PHASE1_SUPPORTED: dict[str, frozenset[tuple[SbmRiskClass, SbmRiskMeasure]]] = {
    SbmRegulatoryProfile.US_NPR_2_0.value: frozenset(
        {
            (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
        }
    ),
    SbmRegulatoryProfile.BASEL_MAR21.value: frozenset(
        {
            (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
            (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
            (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
            (SbmRiskClass.FX, SbmRiskMeasure.DELTA),
            (SbmRiskClass.FX, SbmRiskMeasure.VEGA),
            (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE),
            (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA),
            (SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA),
            (SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE),
            (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
            (SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA),
            (SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE),
            (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA),
            (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA),
            (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE),
            (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA),
            (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.VEGA),
            (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.CURVATURE),
            (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA),
            (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.VEGA),
            (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.CURVATURE),
        }
    ),
    SbmRegulatoryProfile.EU_CRR3.value: frozenset(),
    SbmRegulatoryProfile.PRA_UK_CRR.value: frozenset(),
}


_CURVATURE_CAPITAL_REQUIREMENT_ID = "SBM-CURV-001"


def normalise_sensitivity_amount(value: float, *, sensitivity_id: str = "") -> float:
    """Return a finite sensitivity amount.
    Parameters
    ----------
    value : float
        See signature.
    sensitivity_id : str, optional
        See signature.

    Returns
    -------
    float
    """

    return _finite_float(value, field="amount", sensitivity_id=sensitivity_id)


def normalise_currency_code(
    value: str,
    *,
    field: str = "amount_currency",
    sensitivity_id: str = "",
) -> str:
    """Return an upper-case ISO-style currency code.
    Parameters
    ----------
    value : str
        See signature.
    field : str, optional
        See signature.
    sensitivity_id : str, optional
        See signature.

    Returns
    -------
    str
    """

    code = _require_text(value, field, sensitivity_id)
    normalised = code.upper()
    if len(normalised) != 3 or not normalised.isalpha():
        raise SbmInputError(
            "currency code must be a three-letter alphabetic code",
            field=field,
            sensitivity_id=sensitivity_id,
        )
    return normalised


def coerce_risk_class(value: SbmRiskClass | str) -> SbmRiskClass:
    """Normalise a risk-class identifier to the canonical enum.
    Parameters
    ----------
    value : SbmRiskClass | str
        See signature.

    Returns
    -------
    SbmRiskClass
    """

    return _coerce_enum(value, SbmRiskClass, "risk_class")


def coerce_risk_measure(value: SbmRiskMeasure | str) -> SbmRiskMeasure:
    """Normalise a risk-measure identifier to the canonical enum.
    Parameters
    ----------
    value : SbmRiskMeasure | str
        See signature.

    Returns
    -------
    SbmRiskMeasure
    """

    return _coerce_enum(value, SbmRiskMeasure, "risk_measure")


def coerce_sign_convention(value: SbmSignConvention | str) -> SbmSignConvention:
    """Normalise a sign-convention identifier to the canonical enum.
    Parameters
    ----------
    value : SbmSignConvention | str
        See signature.

    Returns
    -------
    SbmSignConvention
    """

    return _coerce_enum(value, SbmSignConvention, "sign_convention")


def coerce_pairwise_evidence_mode(
    value: SbmPairwiseEvidenceMode | str,
) -> SbmPairwiseEvidenceMode:
    """Normalise a pairwise evidence mode to the canonical enum.
    Parameters
    ----------
    value : SbmPairwiseEvidenceMode | str
        See signature.

    Returns
    -------
    SbmPairwiseEvidenceMode
    """

    return _coerce_enum(value, SbmPairwiseEvidenceMode, "pairwise_evidence_mode")


def sensitivity_sort_key(sensitivity: SbmSensitivity) -> tuple[str, str, str, str, str]:
    """Return a deterministic ordering key for one sensitivity.
    Parameters
    ----------
    sensitivity : SbmSensitivity
        See signature.

    Returns
    -------
    tuple[str, str, str, str, str]
    """

    return (
        sensitivity.risk_class.value,
        sensitivity.risk_measure.value,
        sensitivity.bucket,
        sensitivity.risk_factor,
        sensitivity.sensitivity_id,
    )


def sort_sensitivities_deterministic(
    sensitivities: Sequence[SbmSensitivity],
) -> tuple[SbmSensitivity, ...]:
    """Return sensitivities in stable risk-class, bucket, and id order.
    Parameters
    ----------
    sensitivities : Sequence[SbmSensitivity]
        See signature.

    Returns
    -------
    tuple[SbmSensitivity, ...]
    """

    return tuple(sorted(sensitivities, key=sensitivity_sort_key))


def validate_sbm_calculation_context(context: SbmCalculationContext) -> SbmCalculationContext:
    """Validate run-level SBM context and return it unchanged.
    Parameters
    ----------
    context : SbmCalculationContext
        See signature.

    Returns
    -------
    SbmCalculationContext
    """

    _require_text(context.run_id, "run_id")
    _require_text(context.profile_id, "profile_id")
    normalise_currency_code(context.base_currency, field="base_currency")
    normalise_currency_code(context.reporting_currency, field="reporting_currency")
    _validate_citation_policy(context.citation_policy)
    ensure_sbm_profile_known(context.profile_id)
    _validate_run_controls(context.run_controls)
    if context.desk_id is not None and context.desk_id != context.desk_id.strip():
        raise SbmInputError(
            "desk_id must not contain leading or trailing whitespace",
            field="desk_id",
        )
    if context.legal_entity is not None and context.legal_entity != context.legal_entity.strip():
        raise SbmInputError(
            "legal_entity must not contain leading or trailing whitespace",
            field="legal_entity",
        )
    return context


def _validate_run_controls(controls: SbmRunControls | None) -> None:
    if controls is None:
        return
    if not isinstance(controls, SbmRunControls):
        raise SbmInputError("run_controls must be SbmRunControls", field="run_controls")
    coerce_pairwise_evidence_mode(controls.pairwise_evidence_mode)
    if (
        isinstance(controls.pairwise_evidence_limit, bool)
        or not isinstance(controls.pairwise_evidence_limit, int)
        or controls.pairwise_evidence_limit < 0
    ):
        raise SbmInputError(
            "pairwise_evidence_limit must be a non-negative integer",
            field="pairwise_evidence_limit",
        )


def validate_sbm_sensitivities(sensitivities: object) -> tuple[SbmSensitivity, ...]:
    """Validate canonical SBM sensitivities and return them in input order.
    Parameters
    ----------
    sensitivities : object
        See signature.

    Returns
    -------
    tuple[SbmSensitivity, ...]
    """

    if isinstance(sensitivities, SbmSensitivity):
        raise SbmInputError("sensitivities must be an iterable of SbmSensitivity objects")
    try:
        candidates: tuple[object, ...] = tuple(sensitivities)  # type: ignore[arg-type]
    except TypeError as exc:
        raise SbmInputError("sensitivities must be an iterable of SbmSensitivity objects") from exc

    seen_sensitivity_ids: set[str] = set()
    validated: list[SbmSensitivity] = []
    for candidate in candidates:
        if not isinstance(candidate, SbmSensitivity):
            raise SbmInputError("sensitivities must contain only SbmSensitivity objects")
        sensitivity = candidate
        _validate_sensitivity(sensitivity, seen_sensitivity_ids)
        seen_sensitivity_ids.add(sensitivity.sensitivity_id)
        validated.append(sensitivity)
    return tuple(validated)


def ensure_sbm_profile_known(profile_id: str) -> SbmRegulatoryProfile:
    """Raise when a requested profile id is unknown.
    Parameters
    ----------
    profile_id : str
        See signature.

    Returns
    -------
    SbmRegulatoryProfile
    """

    normalised = _require_text(profile_id, "profile_id")
    try:
        return SbmRegulatoryProfile(normalised)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in SbmRegulatoryProfile)
        raise SbmInputError(
            f"profile_id must be one of: {allowed}",
            field="profile_id",
        ) from exc


def phase1_capital_supported_paths(
    profile_id: str,
) -> frozenset[tuple[SbmRiskClass, SbmRiskMeasure]]:
    """Return risk-class/measure paths supported for phase-1 capital on a profile.
    Parameters
    ----------
    profile_id : str
        See signature.

    Returns
    -------
    frozenset[tuple[SbmRiskClass, SbmRiskMeasure]]
    """

    profile = ensure_sbm_profile_known(profile_id)
    return _PHASE1_SUPPORTED.get(profile.value, frozenset())


def _raise_unsupported_capital_path(
    profile: SbmRegulatoryProfile,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> None:
    supported = _PHASE1_SUPPORTED.get(profile.value, frozenset())
    if not supported:
        raise UnsupportedRegulatoryFeatureError(
            f"frtb-sbm phase-1 capital is unsupported for profile={profile.value}; "
            f"use profile={SbmRegulatoryProfile.BASEL_MAR21.value}"
        )
    if (
        risk_measure is SbmRiskMeasure.CURVATURE
        and (
            risk_class,
            risk_measure,
        )
        not in supported
    ):
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm curvature capital is unsupported for the requested profile "
            f"or risk class ({_CURVATURE_CAPITAL_REQUIREMENT_ID}); "
            f"received profile_id={profile.value}; "
            f"received risk_class={risk_class.value}; "
            "use validate_curvature_sensitivities to validate up/down shock inputs"
        )
    if risk_measure is SbmRiskMeasure.CURVATURE:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm curvature capital is unsupported for "
            f"risk_class={risk_class.value}, profile={profile.value}"
        )
    raise UnsupportedRegulatoryFeatureError(
        "frtb-sbm phase-1 capital is unsupported for the requested profile path; "
        f"received profile_id={profile.value}, "
        f"received risk_class={risk_class.value}, "
        f"risk_measure={risk_measure.value}"
    )


def ensure_sbm_risk_class_measure_supported(
    profile_id: str,
    risk_class: SbmRiskClass | str,
    risk_measure: SbmRiskMeasure | str,
) -> None:
    """Raise explicitly when a profile/risk-class/measure path is unsupported.
    Parameters
    ----------
    profile_id : str
        See signature.
    risk_class : SbmRiskClass | str
        See signature.
    risk_measure : SbmRiskMeasure | str
        See signature.
    """

    profile = ensure_sbm_profile_known(profile_id)
    resolved_risk_class = coerce_risk_class(risk_class)
    resolved_measure = coerce_risk_measure(risk_measure)
    supported = phase1_capital_supported_paths(profile_id)
    if (resolved_risk_class, resolved_measure) in supported:
        return
    _raise_unsupported_capital_path(profile, resolved_risk_class, resolved_measure)


def ensure_sbm_capital_paths_supported(
    profile_id: str,
    sensitivities: Sequence[SbmSensitivity],
) -> None:
    """Raise when profile or sensitivity paths are outside phase-1 capital support.
    Parameters
    ----------
    profile_id : str
        See signature.
    sensitivities : Sequence[SbmSensitivity]
        See signature.
    """

    profile = ensure_sbm_profile_known(profile_id)
    supported = phase1_capital_supported_paths(profile_id)
    if not supported:
        raise UnsupportedRegulatoryFeatureError(
            f"frtb-sbm phase-1 capital is unsupported for profile={profile.value}; "
            f"use profile={SbmRegulatoryProfile.BASEL_MAR21.value}"
        )
    if not sensitivities:
        raise SbmInputError("sensitivities must not be empty", field="sensitivities")
    for sensitivity in sensitivities:
        path = (sensitivity.risk_class, sensitivity.risk_measure)
        if path not in supported:
            _raise_unsupported_capital_path(
                profile,
                sensitivity.risk_class,
                sensitivity.risk_measure,
            )


def ensure_sbm_run_supported(
    context: SbmCalculationContext,
    sensitivities: Sequence[SbmSensitivity],
) -> None:
    """Validate run context scope against already-validated sensitivities.
    Parameters
    ----------
    context : SbmCalculationContext
        See signature.
    sensitivities : Sequence[SbmSensitivity]
        See signature.
    """

    validated_context = validate_sbm_calculation_context(context)
    scoped_desk_id = validated_context.desk_id.strip()
    scoped_legal_entity = validated_context.legal_entity.strip()
    for sensitivity in sensitivities:
        if scoped_desk_id and sensitivity.desk_id != scoped_desk_id:
            raise SbmInputError(
                f"desk_id {sensitivity.desk_id} does not match context desk_id {scoped_desk_id}",
                field="desk_id",
                sensitivity_id=sensitivity.sensitivity_id,
            )
        if scoped_legal_entity and sensitivity.legal_entity != scoped_legal_entity:
            raise SbmInputError(
                f"legal_entity {sensitivity.legal_entity} does not match "
                f"context legal_entity {scoped_legal_entity}",
                field="legal_entity",
                sensitivity_id=sensitivity.sensitivity_id,
            )


def _validate_sensitivity(sensitivity: SbmSensitivity, seen_sensitivity_ids: set[str]) -> None:
    sensitivity_id = _require_text(sensitivity.sensitivity_id, "sensitivity_id")
    if sensitivity_id in seen_sensitivity_ids:
        raise SbmInputError(
            "duplicate sensitivity id",
            field="sensitivity_id",
            sensitivity_id=sensitivity_id,
        )

    _require_text(sensitivity.source_row_id, "source_row_id", sensitivity_id)
    _require_text(sensitivity.desk_id, "desk_id", sensitivity_id)
    _require_text(sensitivity.legal_entity, "legal_entity", sensitivity_id)
    _require_text(sensitivity.bucket, "bucket", sensitivity_id)
    _require_text(sensitivity.risk_factor, "risk_factor", sensitivity_id)
    normalise_currency_code(
        sensitivity.amount_currency,
        field="amount_currency",
        sensitivity_id=sensitivity_id,
    )
    normalise_sensitivity_amount(sensitivity.amount, sensitivity_id=sensitivity_id)

    risk_class = _coerce_enum(
        sensitivity.risk_class,
        SbmRiskClass,
        "risk_class",
        sensitivity_id,
    )
    risk_measure = _coerce_enum(
        sensitivity.risk_measure,
        SbmRiskMeasure,
        "risk_measure",
        sensitivity_id,
    )
    _coerce_enum(
        sensitivity.sign_convention,
        SbmSignConvention,
        "sign_convention",
        sensitivity_id,
    )

    if sensitivity.position_id is not None:
        _require_text(sensitivity.position_id, "position_id", sensitivity_id)

    _validate_lineage(sensitivity.lineage, sensitivity_id)
    if sensitivity.source_row_id != sensitivity.lineage.source_row_id:
        raise SbmInputError(
            "source_row_id must match lineage.source_row_id",
            field="source_row_id",
            sensitivity_id=sensitivity_id,
        )

    for citation_id in sensitivity.mapping_citation_ids:
        _require_text(citation_id, "mapping_citation_ids", sensitivity_id)

    _validate_risk_class_fields(
        sensitivity,
        risk_class=risk_class,
        risk_measure=risk_measure,
    )


def _validate_lineage(lineage: SbmSourceLineage, sensitivity_id: str) -> None:
    if not isinstance(lineage, SbmSourceLineage):
        raise SbmInputError(
            "invalid source lineage",
            field="lineage",
            sensitivity_id=sensitivity_id,
        )

    _require_text(lineage.source_system, "lineage.source_system", sensitivity_id)
    _require_text(lineage.source_file, "lineage.source_file", sensitivity_id)
    _require_text(lineage.source_row_id, "lineage.source_row_id", sensitivity_id)
    for mapping in lineage.source_column_map:
        if not isinstance(mapping, tuple | list) or len(mapping) != 2:
            raise SbmInputError(
                "source column map entries must be field pairs",
                field="lineage.source_column_map",
                sensitivity_id=sensitivity_id,
            )
        source_field, canonical_field = mapping
        _require_text(source_field, "lineage.source_column_map.source", sensitivity_id)
        _require_text(canonical_field, "lineage.source_column_map.canonical", sensitivity_id)


def _validate_risk_class_fields(
    sensitivity: SbmSensitivity,
    *,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> None:
    sensitivity_id = sensitivity.sensitivity_id

    if _qualifier_is_required(risk_class, risk_measure) and _is_blank(sensitivity.qualifier):
        raise SbmInputError(
            "qualifier is required for the selected risk class",
            field="qualifier",
            sensitivity_id=sensitivity_id,
        )

    if (risk_class, risk_measure) in _TENOR_REQUIRED:
        _require_text(sensitivity.tenor, "tenor", sensitivity_id)

    if (risk_class, risk_measure) in _OPTION_TENOR_REQUIRED:
        _require_text(sensitivity.option_tenor, "option_tenor", sensitivity_id)

    if sensitivity.liquidity_horizon_days is not None:
        require_positive_int(
            sensitivity.liquidity_horizon_days,
            "liquidity_horizon_days",
            sensitivity_id,
        )

    for field_name in ("tenor", "option_tenor", "maturity", "qualifier"):
        value = getattr(sensitivity, field_name)
        if value is not None:
            _require_text(value, field_name, sensitivity_id)

    if risk_measure is SbmRiskMeasure.CURVATURE:
        _validate_curvature_amounts(sensitivity)

    if risk_class is SbmRiskClass.FX and risk_measure is SbmRiskMeasure.DELTA:
        _validate_fx_delta_fields(sensitivity)
    if risk_class is SbmRiskClass.FX and risk_measure is SbmRiskMeasure.VEGA:
        _validate_fx_vega_fields(sensitivity)
    if risk_class is SbmRiskClass.EQUITY and risk_measure is SbmRiskMeasure.DELTA:
        _validate_equity_delta_fields(sensitivity)
    if risk_class is SbmRiskClass.EQUITY and risk_measure is SbmRiskMeasure.VEGA:
        _validate_equity_vega_fields(sensitivity)
    if risk_class is SbmRiskClass.COMMODITY and risk_measure is SbmRiskMeasure.DELTA:
        _validate_commodity_delta_fields(sensitivity)
    if risk_class is SbmRiskClass.COMMODITY and risk_measure is SbmRiskMeasure.VEGA:
        _validate_commodity_vega_fields(sensitivity)
    if risk_class is SbmRiskClass.CSR_NONSEC and risk_measure is SbmRiskMeasure.VEGA:
        _validate_csr_nonsec_vega_fields(sensitivity)
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP and risk_measure is SbmRiskMeasure.VEGA:
        _validate_csr_sec_nonctp_vega_fields(sensitivity)
    if risk_class is SbmRiskClass.CSR_SEC_CTP and risk_measure is SbmRiskMeasure.VEGA:
        _validate_csr_sec_ctp_vega_fields(sensitivity)


def _qualifier_is_required(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> bool:
    if risk_class is SbmRiskClass.COMMODITY and risk_measure is SbmRiskMeasure.VEGA:
        return False
    return risk_class in _QUALIFIER_REQUIRED


def _validate_fx_delta_fields(sensitivity: SbmSensitivity) -> None:
    # Local import: reference_data -> commodity_reference_data -> validation.
    from frtb_sbm.reference_data import normalise_fx_delta_currency_code

    sensitivity_id = sensitivity.sensitivity_id
    bucket = normalise_fx_delta_currency_code(
        normalise_currency_code(
            sensitivity.bucket,
            field="bucket",
            sensitivity_id=sensitivity_id,
        )
    )
    risk_factor = normalise_fx_delta_currency_code(
        normalise_currency_code(
            sensitivity.risk_factor,
            field="risk_factor",
            sensitivity_id=sensitivity_id,
        )
    )
    if bucket != risk_factor:
        raise SbmInputError(
            "FX delta bucket must match risk_factor currency",
            field="bucket",
            sensitivity_id=sensitivity_id,
        )


def _validate_fx_vega_fields(sensitivity: SbmSensitivity) -> None:
    # Local import: reference_data -> commodity_reference_data -> validation.
    from frtb_sbm.reference_data import (
        girr_vega_option_tenor_definition,
        normalise_fx_delta_currency_code,
    )

    sensitivity_id = sensitivity.sensitivity_id
    bucket = normalise_fx_delta_currency_code(
        normalise_currency_code(
            sensitivity.bucket,
            field="bucket",
            sensitivity_id=sensitivity_id,
        )
    )
    risk_factor = normalise_fx_delta_currency_code(
        normalise_currency_code(
            sensitivity.risk_factor,
            field="risk_factor",
            sensitivity_id=sensitivity_id,
        )
    )
    if bucket != risk_factor:
        raise SbmInputError(
            "FX vega bucket must match risk_factor currency",
            field="bucket",
            sensitivity_id=sensitivity_id,
        )
    girr_vega_option_tenor_definition(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        sensitivity.option_tenor or "",
    )


def _validate_equity_delta_fields(sensitivity: SbmSensitivity) -> None:
    from frtb_sbm.equity_reference_data import (
        EQUITY_REPO_RISK_FACTOR,
        EQUITY_SPOT_RISK_FACTOR,
        equity_bucket_definition,
    )

    sensitivity_id = sensitivity.sensitivity_id
    equity_bucket_definition(SbmRegulatoryProfile.BASEL_MAR21.value, sensitivity.bucket)
    risk_factor = sensitivity.risk_factor.strip().upper()
    if risk_factor not in {EQUITY_SPOT_RISK_FACTOR, EQUITY_REPO_RISK_FACTOR}:
        raise SbmInputError(
            "equity delta risk_factor must be SPOT or REPO",
            field="risk_factor",
            sensitivity_id=sensitivity_id,
        )


def _validate_equity_vega_fields(sensitivity: SbmSensitivity) -> None:
    from frtb_sbm.equity_reference_data import (
        EQUITY_REPO_RISK_FACTOR,
        EQUITY_SPOT_RISK_FACTOR,
        equity_bucket_definition,
    )
    from frtb_sbm.reference_data import girr_vega_option_tenor_definition

    sensitivity_id = sensitivity.sensitivity_id
    equity_bucket_definition(SbmRegulatoryProfile.BASEL_MAR21.value, sensitivity.bucket)
    risk_factor = sensitivity.risk_factor.strip().upper()
    if risk_factor == EQUITY_REPO_RISK_FACTOR:
        raise UnsupportedRegulatoryFeatureError(
            "equity vega has no capital requirement for equity repo rates (MAR21.12(2)(b))"
        )
    if risk_factor != EQUITY_SPOT_RISK_FACTOR:
        raise SbmInputError(
            "equity vega risk_factor must be SPOT",
            field="risk_factor",
            sensitivity_id=sensitivity_id,
        )
    girr_vega_option_tenor_definition(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        sensitivity.option_tenor or "",
    )


def _validate_commodity_delta_fields(sensitivity: SbmSensitivity) -> None:
    from frtb_sbm.commodity_reference_data import commodity_bucket_definition

    commodity_bucket_definition(SbmRegulatoryProfile.BASEL_MAR21.value, sensitivity.bucket)


def _validate_commodity_vega_fields(sensitivity: SbmSensitivity) -> None:
    from frtb_sbm.commodity_reference_data import commodity_bucket_definition
    from frtb_sbm.reference_data import girr_vega_option_tenor_definition

    commodity_bucket_definition(SbmRegulatoryProfile.BASEL_MAR21.value, sensitivity.bucket)
    girr_vega_option_tenor_definition(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        sensitivity.option_tenor or "",
    )


def _validate_csr_nonsec_vega_fields(sensitivity: SbmSensitivity) -> None:
    from frtb_sbm.csr_nonsec_reference_data import csr_nonsec_validate_vega_inputs
    from frtb_sbm.reference_data import girr_vega_option_tenor_definition

    csr_nonsec_validate_vega_inputs(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        bucket_id=sensitivity.bucket,
        risk_factor=sensitivity.risk_factor,
        qualifier=sensitivity.qualifier or "",
    )
    girr_vega_option_tenor_definition(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        sensitivity.option_tenor or "",
    )


def _validate_csr_sec_nonctp_vega_fields(sensitivity: SbmSensitivity) -> None:
    from frtb_sbm.csr_sec_nonctp_reference_data import csr_sec_nonctp_validate_vega_inputs
    from frtb_sbm.reference_data import girr_vega_option_tenor_definition

    csr_sec_nonctp_validate_vega_inputs(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        bucket_id=sensitivity.bucket,
        risk_factor=sensitivity.risk_factor,
        qualifier=sensitivity.qualifier or "",
    )
    girr_vega_option_tenor_definition(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        sensitivity.option_tenor or "",
    )


def _validate_csr_sec_ctp_vega_fields(sensitivity: SbmSensitivity) -> None:
    from frtb_sbm.csr_sec_ctp_reference_data import csr_sec_ctp_validate_vega_inputs
    from frtb_sbm.reference_data import girr_vega_option_tenor_definition

    csr_sec_ctp_validate_vega_inputs(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        bucket_id=sensitivity.bucket,
        risk_factor=sensitivity.risk_factor,
        qualifier=sensitivity.qualifier or "",
    )
    girr_vega_option_tenor_definition(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        sensitivity.option_tenor or "",
    )


def _validate_curvature_amounts(sensitivity: SbmSensitivity) -> None:
    sensitivity_id = sensitivity.sensitivity_id
    if sensitivity.up_shock_amount is None or sensitivity.down_shock_amount is None:
        raise SbmInputError(
            "curvature inputs require up_shock_amount and down_shock_amount",
            field="up_shock_amount",
            sensitivity_id=sensitivity_id,
        )
    normalise_sensitivity_amount(sensitivity.up_shock_amount, sensitivity_id=sensitivity_id)
    normalise_sensitivity_amount(sensitivity.down_shock_amount, sensitivity_id=sensitivity_id)


def _validate_citation_policy(citation_policy: str) -> None:
    if citation_policy.strip().lower() != _STRICT_CITATION_POLICY:
        raise SbmInputError(
            f"unsupported citation_policy: {citation_policy}",
            field="citation_policy",
        )


def _coerce_enum(
    value: object,
    enum_type: type[EnumT],
    field: str,
    sensitivity_id: str = "",
) -> EnumT:
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise SbmInputError(f"invalid {field}", field=field, sensitivity_id=sensitivity_id)
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise SbmInputError(
            f"{field} must be one of: {allowed}",
            field=field,
            sensitivity_id=sensitivity_id,
        ) from exc


def _finite_float(value: object, *, field: str, sensitivity_id: str = "") -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SbmInputError("value must be numeric", field=field, sensitivity_id=sensitivity_id)
    number = float(value)
    if not math.isfinite(number):
        raise SbmInputError("value must be finite", field=field, sensitivity_id=sensitivity_id)
    return number


def _is_blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def require_positive_int(value: object, field: str, sensitivity_id: str = "") -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SbmInputError(
            "value must be a positive integer",
            field=field,
            sensitivity_id=sensitivity_id,
        )
    if value <= 0:
        raise SbmInputError(
            "value must be a positive integer",
            field=field,
            sensitivity_id=sensitivity_id,
        )
    return value


__all__ = [
    "SbmInputError",
    "coerce_risk_class",
    "coerce_risk_measure",
    "coerce_sign_convention",
    "ensure_sbm_capital_paths_supported",
    "ensure_sbm_profile_known",
    "ensure_sbm_risk_class_measure_supported",
    "ensure_sbm_run_supported",
    "normalise_currency_code",
    "normalise_sensitivity_amount",
    "phase1_capital_supported_paths",
    "require_positive_int",
    "sensitivity_sort_key",
    "sort_sensitivities_deterministic",
    "validate_sbm_calculation_context",
    "validate_sbm_sensitivities",
]
