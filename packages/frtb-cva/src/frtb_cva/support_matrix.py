"""
Runtime-readable CVA profile, method, and SA-CVA support matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_cva._unsupported import MAR50_9_MATERIALITY_POLICY, MAR50_9_UNSUPPORTED_MESSAGE
from frtb_cva.data_models import (
    CvaMethod,
    CvaRegulatoryProfile,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
)
from frtb_cva.regimes import UNSUPPORTED_PROFILE_REASONS
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


_BASEL_PROFILE = CvaRegulatoryProfile.BASEL_MAR50_2020
_COMPARISON_PROFILES = frozenset(
    {
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
    """Return the capital-producing status for a known CVA profile."""

    resolved = _resolve_profile_id(profile)
    if resolved is _BASEL_PROFILE:
        return CvaProfileSupportStatus.CAPITAL_PRODUCING
    return CvaProfileSupportStatus.COMPARISON_FAIL_CLOSED


def cva_capital_supported_methods(profile: CvaRegulatoryProfile | str) -> frozenset[CvaMethod]:
    """Return supported CVA methods for a profile without falling back to Basel."""

    resolved = _resolve_profile_id(profile)
    if resolved is _BASEL_PROFILE:
        return _BASEL_SUPPORTED_METHODS
    return frozenset()


def cva_sa_cva_supported_paths(
    profile: CvaRegulatoryProfile | str,
) -> frozenset[tuple[SaCvaRiskClass, SaCvaRiskMeasure]]:
    """Return supported SA-CVA risk-class and measure paths for a profile."""

    resolved = _resolve_profile_id(profile)
    if resolved is _BASEL_PROFILE:
        return _BASEL_SUPPORTED_SA_PATHS
    return frozenset()


def ensure_cva_profile_method_supported(
    profile: CvaRegulatoryProfile | str,
    method: CvaMethod | str,
) -> None:
    """Fail closed when a CVA profile/method cell is not capital-producing."""

    resolved = _resolve_profile_id(profile)
    resolved_method = _resolve_method_id(method)
    if resolved_method in cva_capital_supported_methods(resolved):
        return
    if resolved in UNSUPPORTED_PROFILE_REASONS:
        raise UnsupportedRegulatoryFeatureError(UNSUPPORTED_PROFILE_REASONS[resolved])
    raise UnsupportedRegulatoryFeatureError(
        f"CVA method {resolved_method.value} is unsupported for profile {resolved.value}."
    )


def ensure_cva_sa_cva_path_supported(
    profile: CvaRegulatoryProfile | str,
    risk_class: SaCvaRiskClass | str,
    risk_measure: SaCvaRiskMeasure | str,
) -> None:
    """Fail closed when a profile/risk-class/measure cell is not supported."""

    resolved = _resolve_profile_id(profile)
    resolved_risk_class = _resolve_risk_class_id(risk_class)
    resolved_risk_measure = _resolve_risk_measure_id(risk_measure)
    path = (resolved_risk_class, resolved_risk_measure)
    if path in cva_sa_cva_supported_paths(resolved):
        return
    if resolved in UNSUPPORTED_PROFILE_REASONS:
        raise UnsupportedRegulatoryFeatureError(UNSUPPORTED_PROFILE_REASONS[resolved])
    if path == _CCS_VEGA_PATH:
        raise CvaInputError(
            "CCS vega capital is not permitted under MAR50.45 and MAR50.63",
            field="sensitivities",
        )
    raise CvaInputError(
        f"unsupported SA-CVA path: {resolved_risk_class.value}/{resolved_risk_measure.value}",
        field="sensitivities",
    )


def cva_profile_support_matrix() -> tuple[CvaSupportCell, ...]:
    """Return the current CVA support matrix."""

    rows: list[CvaSupportCell] = []
    rows.extend(_basel_method_rows())
    rows.extend(_basel_sa_path_rows())
    rows.append(
        CvaSupportCell(
            profile=_BASEL_PROFILE,
            method=CvaMethod.SA_CVA.value,
            risk_class=_CCS_VEGA_PATH[0],
            risk_measure=_CCS_VEGA_PATH[1],
            status=CvaSupportStatus.REGULATORY_ABSENCE,
            citation="Basel MAR50.45; Basel MAR50.63",
            blocker="regulatory_absence",
            tests=("packages/frtb-cva/tests/test_cva_support_matrix.py",),
        )
    )
    rows.append(
        CvaSupportCell(
            profile=_BASEL_PROFILE,
            method=MAR50_9_MATERIALITY_POLICY,
            status=CvaSupportStatus.UNSUPPORTED_FAIL_CLOSED,
            citation="Basel MAR50.9",
            blocker="ccr_boundary",
            tests=("packages/frtb-cva/tests/test_cva_support_matrix.py",),
        )
    )
    for profile in sorted(_COMPARISON_PROFILES, key=lambda item: item.value):
        rows.extend(_comparison_profile_rows(profile))
    return tuple(rows)


def _basel_method_rows() -> tuple[CvaSupportCell, ...]:
    citations = {
        CvaMethod.BA_CVA_REDUCED: "Basel MAR50.14-MAR50.16",
        CvaMethod.BA_CVA_FULL: "Basel MAR50.17-MAR50.26",
        CvaMethod.SA_CVA: "Basel MAR50.42-MAR50.77",
        CvaMethod.MIXED_CARVE_OUT: "Basel MAR50.8",
    }
    return tuple(
        CvaSupportCell(
            profile=_BASEL_PROFILE,
            method=method.value,
            status=CvaSupportStatus.IMPLEMENTED_UNDER_AUDIT,
            citation=citations[method],
            blocker="none",
            tests=("packages/frtb-cva/tests/test_cva_support_matrix.py",),
        )
        for method in sorted(_BASEL_SUPPORTED_METHODS, key=lambda item: item.value)
    )


def _basel_sa_path_rows() -> tuple[CvaSupportCell, ...]:
    return tuple(
        CvaSupportCell(
            profile=_BASEL_PROFILE,
            method=CvaMethod.SA_CVA.value,
            risk_class=risk_class,
            risk_measure=risk_measure,
            status=CvaSupportStatus.IMPLEMENTED_UNDER_AUDIT,
            citation="Basel MAR50.42-MAR50.77",
            blocker="none",
            tests=("packages/frtb-cva/tests/test_cva_support_matrix.py",),
        )
        for risk_class, risk_measure in sorted(_BASEL_SUPPORTED_SA_PATHS, key=_path_sort_key)
    )


def _comparison_profile_rows(profile: CvaRegulatoryProfile) -> tuple[CvaSupportCell, ...]:
    return tuple(
        CvaSupportCell(
            profile=profile,
            method=method.value,
            status=CvaSupportStatus.UNSUPPORTED_FAIL_CLOSED,
            citation=_comparison_profile_citation(profile),
            blocker="comparison_profile",
            tests=("packages/frtb-cva/tests/test_cva_support_matrix.py",),
        )
        for method in sorted(CvaMethod, key=lambda item: item.value)
    )


def _comparison_profile_citation(profile: CvaRegulatoryProfile) -> str:
    if profile is CvaRegulatoryProfile.US_NPR20_VB:
        return "U.S. NPR 2.0 91 FR 14952 section V.B"
    if profile is CvaRegulatoryProfile.EU_CRR3_CVA:
        return "Regulation (EU) 2024/1623 Articles 382-386"
    return "PRA PS1/26; PRA CP16/22"


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
    "MAR50_9_MATERIALITY_POLICY",
    "MAR50_9_UNSUPPORTED_MESSAGE",
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
