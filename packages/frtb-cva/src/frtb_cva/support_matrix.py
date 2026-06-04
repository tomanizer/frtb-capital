"""
Runtime-readable CVA profile, method, and SA-CVA support matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from frtb_cva._unsupported import (
    EXPOSURE_SENSITIVITY_GENERATION_POLICY,
    MAR50_9_MATERIALITY_POLICY,
    MAR50_9_UNSUPPORTED_MESSAGE,
    SA_CVA_APPROVAL_GOVERNANCE_POLICY,
)
from frtb_cva.data_models import (
    CvaMethod,
    CvaRegulatoryProfile,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
)
from frtb_cva.sa_cva import _SUPPORTED_PATHS
from frtb_cva.validation import CvaInputError


class CvaSupportStatus(StrEnum):
    """Support status values used by code and traceability docs."""

    IMPLEMENTED_UNDER_AUDIT = "implemented_under_audit"
    UNSUPPORTED_FAIL_CLOSED = "unsupported_fail_closed"
    REGULATORY_ABSENCE = "regulatory_absence"
    OUT_OF_SCOPE = "out_of_scope"


class CvaProfileSupportStatus(StrEnum):
    """Capital-producing status for a CVA rule profile."""

    CAPITAL_PRODUCING = "capital_producing"
    COMPARISON_FAIL_CLOSED = "comparison_fail_closed"


@dataclass(frozen=True)
class CvaSupportCell:
    """One audited support-matrix cell."""

    profile: CvaRegulatoryProfile
    method: str
    status: CvaSupportStatus
    citation: str
    blocker: str
    tests: tuple[str, ...]
    risk_class: SaCvaRiskClass | None = None
    risk_measure: SaCvaRiskMeasure | None = None


_SUPPORTED_PROFILES = frozenset(
    {
        CvaRegulatoryProfile.BASEL_MAR50_2020,
        CvaRegulatoryProfile.US_NPR20_VB,
        CvaRegulatoryProfile.EU_CRR3_CVA,
        CvaRegulatoryProfile.UK_PRA_CVA,
    }
)
_BASEL_SUPPORTED_METHODS = frozenset(CvaMethod)
_BASEL_SUPPORTED_SA_PATHS = frozenset(_SUPPORTED_PATHS)
_CCS_VEGA_PATH = (
    SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
    SaCvaRiskMeasure.VEGA,
)


def cva_profile_support_status(
    profile: CvaRegulatoryProfile | str,
) -> CvaProfileSupportStatus:
    """Return the capital-producing status for a known CVA profile.

Parameters
----------
profile :
    Optional regulatory profile label or ``CvaRegulatoryProfile`` value; defaults to Basel MAR50 (2020).

Returns
-------
CvaProfileSupportStatus
    Result of ``cva_profile_support_status`` for audit and downstream aggregation."""

    resolved = _resolve_profile_id(profile)
    if resolved in _SUPPORTED_PROFILES:
        return CvaProfileSupportStatus.CAPITAL_PRODUCING
    return CvaProfileSupportStatus.COMPARISON_FAIL_CLOSED


def cva_capital_supported_methods(profile: CvaRegulatoryProfile | str) -> frozenset[CvaMethod]:
    """Return supported CVA methods for a profile without falling back to Basel.

Parameters
----------
profile :
    Optional regulatory profile label or ``CvaRegulatoryProfile`` value; defaults to Basel MAR50 (2020).

Returns
-------
frozenset[CvaMethod]
    Result of ``cva_capital_supported_methods`` for audit and downstream aggregation."""

    resolved = _resolve_profile_id(profile)
    if resolved in _SUPPORTED_PROFILES:
        return _BASEL_SUPPORTED_METHODS
    return frozenset()


def cva_sa_cva_supported_paths(
    profile: CvaRegulatoryProfile | str,
) -> frozenset[tuple[SaCvaRiskClass, SaCvaRiskMeasure]]:
    """Return supported SA-CVA risk-class and measure paths for a profile.

Parameters
----------
profile :
    Optional regulatory profile label or ``CvaRegulatoryProfile`` value; defaults to Basel MAR50 (2020).

Returns
-------
frozenset[tuple[SaCvaRiskClass, SaCvaRiskMeasure]]
    Result of ``cva_sa_cva_supported_paths`` for audit and downstream aggregation."""

    resolved = _resolve_profile_id(profile)
    if resolved in _SUPPORTED_PROFILES:
        return _BASEL_SUPPORTED_SA_PATHS
    return frozenset()


def ensure_cva_profile_method_supported(
    profile: CvaRegulatoryProfile | str,
    method: CvaMethod | str,
) -> None:
    """Fail closed when a CVA profile/method cell is not capital-producing.

Parameters
----------
profile :
    Optional regulatory profile label or ``CvaRegulatoryProfile`` value; defaults to Basel MAR50 (2020).

method :
    Requested CVA calculation method (BA-CVA, SA-CVA, or mixed carve-out)."""

    resolved = _resolve_profile_id(profile)
    resolved_method = _resolve_method_id(method)
    if resolved_method in cva_capital_supported_methods(resolved):
        return
    from frtb_common import UnsupportedRegulatoryFeatureError

    raise UnsupportedRegulatoryFeatureError(
        f"CVA method {resolved_method.value} is unsupported for profile {resolved.value}."
    )


def ensure_cva_sa_cva_path_supported(
    profile: CvaRegulatoryProfile | str,
    risk_class: SaCvaRiskClass | str,
    risk_measure: SaCvaRiskMeasure | str,
) -> None:
    """Fail closed when a profile/risk-class/measure cell is not supported.

Parameters
----------
profile :
    Optional regulatory profile label or ``CvaRegulatoryProfile`` value; defaults to Basel MAR50 (2020).

risk_class :
    SA-CVA risk class driving aggregation configuration.

risk_measure :
    SA-CVA risk measure (delta or vega) for the aggregation path."""

    resolved = _resolve_profile_id(profile)
    resolved_risk_class = _resolve_risk_class_id(risk_class)
    resolved_risk_measure = _resolve_risk_measure_id(risk_measure)
    path = (resolved_risk_class, resolved_risk_measure)
    if path in cva_sa_cva_supported_paths(resolved):
        return
    if path == _CCS_VEGA_PATH:
        raise CvaInputError(
            "CCS vega capital is not permitted for the selected CVA profile",
            field="sensitivities",
        )
    raise CvaInputError(
        f"unsupported SA-CVA path: {resolved_risk_class.value}/{resolved_risk_measure.value}",
        field="sensitivities",
    )


def cva_profile_support_matrix() -> tuple[CvaSupportCell, ...]:
    """Return the current CVA support matrix.

Returns
-------
tuple[CvaSupportCell, ...]
    Result of ``cva_profile_support_matrix`` for audit and downstream aggregation."""

    rows: list[CvaSupportCell] = []
    for profile in sorted(_SUPPORTED_PROFILES, key=lambda item: item.value):
        rows.extend(_method_rows(profile))
        rows.extend(_sa_path_rows(profile))
        rows.append(_ccs_vega_row(profile))
        rows.append(_materiality_row(profile))
        rows.extend(_out_of_scope_rows(profile))
    return tuple(rows)


def _method_rows(profile: CvaRegulatoryProfile) -> tuple[CvaSupportCell, ...]:
    citations = _method_citations(profile)
    return tuple(
        CvaSupportCell(
            profile=profile,
            method=method.value,
            status=CvaSupportStatus.IMPLEMENTED_UNDER_AUDIT,
            citation=citations[method],
            blocker="none",
            tests=("packages/frtb-cva/tests/test_cva_support_matrix.py",),
        )
        for method in sorted(_BASEL_SUPPORTED_METHODS, key=lambda item: item.value)
    )


def _method_citations(profile: CvaRegulatoryProfile) -> dict[CvaMethod, str]:
    if profile is CvaRegulatoryProfile.BASEL_MAR50_2020:
        return {
            CvaMethod.BA_CVA_REDUCED: "Basel MAR50.14-MAR50.16",
            CvaMethod.BA_CVA_FULL: "Basel MAR50.17-MAR50.26",
            CvaMethod.SA_CVA: "Basel MAR50.42-MAR50.77",
            CvaMethod.MIXED_CARVE_OUT: "Basel MAR50.8",
        }
    if profile is CvaRegulatoryProfile.US_NPR20_VB:
        return {method: "U.S. NPR 2.0 91 FR 14952 section V.B" for method in CvaMethod}
    if profile is CvaRegulatoryProfile.EU_CRR3_CVA:
        return {
            CvaMethod.BA_CVA_REDUCED: "Regulation (EU) 2024/1623 Article 384",
            CvaMethod.BA_CVA_FULL: "Regulation (EU) 2024/1623 Article 384",
            CvaMethod.SA_CVA: "Regulation (EU) 2024/1623 Articles 383-383z",
            CvaMethod.MIXED_CARVE_OUT: "Regulation (EU) 2024/1623 Article 382",
        }
    return {
        CvaMethod.BA_CVA_REDUCED: "PRA PS1/26; PRA Rulebook CVA Risk Part BA-CVA",
        CvaMethod.BA_CVA_FULL: "PRA PS1/26; PRA Rulebook CVA Risk Part BA-CVA",
        CvaMethod.SA_CVA: "PRA PS1/26; PRA Rulebook CVA Risk Part SA-CVA",
        CvaMethod.MIXED_CARVE_OUT: "PRA PS1/26; PRA Rulebook CVA Risk Part",
    }


def _sa_path_rows(profile: CvaRegulatoryProfile) -> tuple[CvaSupportCell, ...]:
    return tuple(
        CvaSupportCell(
            profile=profile,
            method=CvaMethod.SA_CVA.value,
            risk_class=risk_class,
            risk_measure=risk_measure,
            status=CvaSupportStatus.IMPLEMENTED_UNDER_AUDIT,
            citation=_sa_path_citation(profile),
            blocker="none",
            tests=("packages/frtb-cva/tests/test_cva_support_matrix.py",),
        )
        for risk_class, risk_measure in sorted(_BASEL_SUPPORTED_SA_PATHS, key=_path_sort_key)
    )


def _sa_path_citation(profile: CvaRegulatoryProfile) -> str:
    if profile is CvaRegulatoryProfile.BASEL_MAR50_2020:
        return "Basel MAR50.42-MAR50.77"
    if profile is CvaRegulatoryProfile.US_NPR20_VB:
        return "U.S. NPR 2.0 91 FR 14952 section V.B"
    if profile is CvaRegulatoryProfile.EU_CRR3_CVA:
        return "Regulation (EU) 2024/1623 Articles 383-383z"
    return "PRA PS1/26; PRA Rulebook CVA Risk Part SA-CVA"


def _ccs_vega_row(profile: CvaRegulatoryProfile) -> CvaSupportCell:
    return CvaSupportCell(
        profile=profile,
        method=CvaMethod.SA_CVA.value,
        risk_class=_CCS_VEGA_PATH[0],
        risk_measure=_CCS_VEGA_PATH[1],
        status=CvaSupportStatus.REGULATORY_ABSENCE,
        citation=_ccs_vega_citation(profile),
        blocker="regulatory_absence",
        tests=("packages/frtb-cva/tests/test_cva_support_matrix.py",),
    )


def _ccs_vega_citation(profile: CvaRegulatoryProfile) -> str:
    if profile is CvaRegulatoryProfile.BASEL_MAR50_2020:
        return "Basel MAR50.45; Basel MAR50.63"
    if profile is CvaRegulatoryProfile.US_NPR20_VB:
        return "U.S. NPR 2.0 91 FR 14952 section V.B"
    if profile is CvaRegulatoryProfile.EU_CRR3_CVA:
        return "Regulation (EU) 2024/1623 Articles 383-383z"
    return "PRA PS1/26; PRA Rulebook CVA Risk Part SA-CVA"


def _materiality_row(profile: CvaRegulatoryProfile) -> CvaSupportCell:
    return CvaSupportCell(
        profile=profile,
        method=MAR50_9_MATERIALITY_POLICY,
        status=CvaSupportStatus.UNSUPPORTED_FAIL_CLOSED,
        citation=_materiality_citation(profile),
        blocker="ccr_boundary",
        tests=("packages/frtb-cva/tests/test_cva_support_matrix.py",),
    )


def _materiality_citation(profile: CvaRegulatoryProfile) -> str:
    if profile is CvaRegulatoryProfile.BASEL_MAR50_2020:
        return "Basel MAR50.9"
    if profile is CvaRegulatoryProfile.US_NPR20_VB:
        return "U.S. NPR 2.0 91 FR 14952 section V.B"
    if profile is CvaRegulatoryProfile.EU_CRR3_CVA:
        return "Regulation (EU) 2024/1623 Article 385"
    return "PRA PS1/26; PRA Rulebook CVA Risk Part AA-CVA"


def _out_of_scope_rows(profile: CvaRegulatoryProfile) -> tuple[CvaSupportCell, ...]:
    return (
        CvaSupportCell(
            profile=profile,
            method=SA_CVA_APPROVAL_GOVERNANCE_POLICY,
            status=CvaSupportStatus.OUT_OF_SCOPE,
            citation=_sa_cva_approval_citation(profile),
            blocker="supervisory_approval_boundary",
            tests=("packages/frtb-cva/tests/test_cva_support_matrix.py",),
        ),
        CvaSupportCell(
            profile=profile,
            method=EXPOSURE_SENSITIVITY_GENERATION_POLICY,
            status=CvaSupportStatus.OUT_OF_SCOPE,
            citation=_exposure_generation_citation(profile),
            blocker="upstream_exposure_sensitivity_boundary",
            tests=("packages/frtb-cva/tests/test_cva_support_matrix.py",),
        ),
    )


def _sa_cva_approval_citation(profile: CvaRegulatoryProfile) -> str:
    if profile is CvaRegulatoryProfile.BASEL_MAR50_2020:
        return "Basel MAR50.7"
    if profile is CvaRegulatoryProfile.US_NPR20_VB:
        return "U.S. NPR 2.0 91 FR 14952 section V.B"
    if profile is CvaRegulatoryProfile.EU_CRR3_CVA:
        return "Regulation (EU) 2024/1623 Articles 383-383z"
    return "PRA PS1/26; PRA Rulebook CVA Risk Part SA-CVA"


def _exposure_generation_citation(profile: CvaRegulatoryProfile) -> str:
    if profile is CvaRegulatoryProfile.BASEL_MAR50_2020:
        return "Basel MAR50.31-MAR50.36"
    if profile is CvaRegulatoryProfile.US_NPR20_VB:
        return "U.S. NPR 2.0 91 FR 14952 section V.B"
    if profile is CvaRegulatoryProfile.EU_CRR3_CVA:
        return "Regulation (EU) 2024/1623 Articles 383-383z"
    return "PRA PS1/26; PRA Rulebook CVA Risk Part"


def _resolve_profile_id(profile: CvaRegulatoryProfile | str) -> CvaRegulatoryProfile:
    try:
        return CvaRegulatoryProfile(profile)
    except ValueError as exc:
        raise CvaInputError(
            f"unknown CVA regulatory profile: {profile!r}",
            field="profile",
        ) from exc


def _resolve_method_id(method: CvaMethod | str) -> CvaMethod:
    try:
        return CvaMethod(method)
    except ValueError as exc:
        raise CvaInputError(f"unknown CVA method: {method!r}", field="method") from exc


def _resolve_risk_class_id(risk_class: SaCvaRiskClass | str) -> SaCvaRiskClass:
    try:
        return SaCvaRiskClass(risk_class)
    except ValueError as exc:
        raise CvaInputError(
            f"unknown SA-CVA risk class: {risk_class!r}",
            field="risk_class",
        ) from exc


def _resolve_risk_measure_id(risk_measure: SaCvaRiskMeasure | str) -> SaCvaRiskMeasure:
    try:
        return SaCvaRiskMeasure(risk_measure)
    except ValueError as exc:
        raise CvaInputError(
            f"unknown SA-CVA risk measure: {risk_measure!r}",
            field="risk_measure",
        ) from exc


def _path_sort_key(path: tuple[SaCvaRiskClass, SaCvaRiskMeasure]) -> tuple[str, str]:
    risk_class, risk_measure = path
    return risk_class.value, risk_measure.value


__all__ = [
    "EXPOSURE_SENSITIVITY_GENERATION_POLICY",
    "MAR50_9_MATERIALITY_POLICY",
    "MAR50_9_UNSUPPORTED_MESSAGE",
    "SA_CVA_APPROVAL_GOVERNANCE_POLICY",
    "CvaProfileSupportStatus",
    "CvaSupportCell",
    "CvaSupportStatus",
    "cva_capital_supported_methods",
    "cva_profile_support_matrix",
    "cva_profile_support_status",
    "cva_sa_cva_supported_paths",
    "ensure_cva_profile_method_supported",
    "ensure_cva_sa_cva_path_supported",
]
