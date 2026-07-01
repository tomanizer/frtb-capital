"""Run-context and profile validation for SBM calculations.

Regulatory traceability:
    Basel MAR21.1 scope validation, U.S. NPR 2.0 section V.A.7.a profile
    gating, and SBM-NFR-004 fail-closed unsupported-feature handling.
"""

from __future__ import annotations

from collections.abc import Sequence

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm._errors import SbmInputError
from frtb_sbm._text import require_text as _require_text
from frtb_sbm.data_models import (
    SbmCalculationContext,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmRunControls,
    SbmSensitivity,
)
from frtb_sbm.validation.coercion import (
    coerce_pairwise_evidence_mode,
    coerce_risk_class,
    coerce_risk_measure,
    normalise_currency_code,
)

_STRICT_CITATION_POLICY = "strict"

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
    SbmRegulatoryProfile.EU_CRR3.value: frozenset(
        {
            (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
            (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
            (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
            (SbmRiskClass.FX, SbmRiskMeasure.DELTA),
            (SbmRiskClass.FX, SbmRiskMeasure.VEGA),
            (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE),
            (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA),
            (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
        }
    ),
    SbmRegulatoryProfile.PRA_UK_CRR.value: frozenset(),
}

_CURVATURE_CAPITAL_REQUIREMENT_ID = "SBM-CURV-001"


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


def _validate_citation_policy(citation_policy: str) -> None:
    if citation_policy.strip().lower() != _STRICT_CITATION_POLICY:
        raise SbmInputError(
            f"unsupported citation_policy: {citation_policy}",
            field="citation_policy",
        )


__all__ = [
    "ensure_sbm_capital_paths_supported",
    "ensure_sbm_profile_known",
    "ensure_sbm_risk_class_measure_supported",
    "ensure_sbm_run_supported",
    "phase1_capital_supported_paths",
    "validate_sbm_calculation_context",
]
