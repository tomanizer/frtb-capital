"""SBM profile citations and correlation-scenario reference rules.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for reference_data.py, Basel
    MAR21.6, MAR21.38-MAR21.43, and SBM-REF-001.
"""

from __future__ import annotations

import math

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.data_models import SbmCitation, SbmRegulatoryProfile, SbmRiskClass, SbmScenarioLabel
from frtb_sbm.reference_citations_basel_core import BASEL_CORE_CITATIONS
from frtb_sbm.reference_citations_basel_risk_classes import BASEL_RISK_CLASS_CITATIONS
from frtb_sbm.reference_citations_eu_crr3 import EU_CRR3_CITATIONS, eu_crr3_citation_id_for_basel
from frtb_sbm.reference_citations_pra_uk_crr import PRA_UK_CRR_CITATIONS, PRA_UK_CRR_URL
from frtb_sbm.reference_citations_us_npr import US_NPR_2_0_CITATIONS
from frtb_sbm.reference_types import SbmCorrelationScenarioDefinition
from frtb_sbm.validation import SbmInputError

BASEL_MAR21_URL = "https://www.bis.org/basel_framework/chapter/MAR/21.htm"
US_NPR_2_0_URL = "https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959"

BASEL_CITATIONS: dict[str, SbmCitation] = {
    **BASEL_CORE_CITATIONS,
    **BASEL_RISK_CLASS_CITATIONS,
}

PROFILE_CITATIONS: dict[SbmRegulatoryProfile, dict[str, SbmCitation]] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_CITATIONS,
    SbmRegulatoryProfile.US_NPR_2_0: US_NPR_2_0_CITATIONS,
    SbmRegulatoryProfile.EU_CRR3: EU_CRR3_CITATIONS,
    SbmRegulatoryProfile.PRA_UK_CRR: PRA_UK_CRR_CITATIONS,
}

BASEL_CORRELATION_SCENARIOS: tuple[SbmCorrelationScenarioDefinition, ...] = (
    SbmCorrelationScenarioDefinition(
        SbmScenarioLabel.LOW,
        multiplier=0.75,
        floor_factor=0.75,
        cap=None,
        citation_id="basel_mar21_6_correlation_scenarios",
    ),
    SbmCorrelationScenarioDefinition(
        SbmScenarioLabel.MEDIUM,
        multiplier=1.0,
        floor_factor=None,
        cap=None,
        citation_id="basel_mar21_6_correlation_scenarios",
    ),
    SbmCorrelationScenarioDefinition(
        SbmScenarioLabel.HIGH,
        multiplier=1.25,
        floor_factor=None,
        cap=1.0,
        citation_id="basel_mar21_6_correlation_scenarios",
    ),
)

US_NPR_CORRELATION_SCENARIOS: tuple[SbmCorrelationScenarioDefinition, ...] = (
    SbmCorrelationScenarioDefinition(
        SbmScenarioLabel.LOW,
        multiplier=0.75,
        floor_factor=0.75,
        cap=None,
        citation_id="us_npr_91_fr_14952_va7a_correlation_scenarios",
    ),
    SbmCorrelationScenarioDefinition(
        SbmScenarioLabel.MEDIUM,
        multiplier=1.0,
        floor_factor=None,
        cap=None,
        citation_id="us_npr_91_fr_14952_va7a_correlation_scenarios",
    ),
    SbmCorrelationScenarioDefinition(
        SbmScenarioLabel.HIGH,
        multiplier=1.25,
        floor_factor=None,
        cap=1.0,
        citation_id="us_npr_91_fr_14952_va7a_correlation_scenarios",
    ),
)

EU_CRR3_CORRELATION_SCENARIOS: tuple[SbmCorrelationScenarioDefinition, ...] = tuple(
    SbmCorrelationScenarioDefinition(
        definition.scenario,
        multiplier=definition.multiplier,
        floor_factor=definition.floor_factor,
        cap=definition.cap,
        citation_id=eu_crr3_citation_id_for_basel("basel_mar21_6_correlation_scenarios"),
    )
    for definition in BASEL_CORRELATION_SCENARIOS
)

PRA_UK_CRR_CORRELATION_SCENARIOS: tuple[SbmCorrelationScenarioDefinition, ...] = (
    SbmCorrelationScenarioDefinition(
        SbmScenarioLabel.LOW,
        multiplier=0.75,
        floor_factor=0.75,
        cap=None,
        citation_id="pra_uk_crr_325h_correlation_scenarios",
    ),
    SbmCorrelationScenarioDefinition(
        SbmScenarioLabel.MEDIUM,
        multiplier=1.0,
        floor_factor=None,
        cap=None,
        citation_id="pra_uk_crr_325h_correlation_scenarios",
    ),
    SbmCorrelationScenarioDefinition(
        SbmScenarioLabel.HIGH,
        multiplier=1.25,
        floor_factor=None,
        cap=1.0,
        citation_id="pra_uk_crr_325h_correlation_scenarios",
    ),
)

PROFILE_CORRELATION_SCENARIOS: dict[
    SbmRegulatoryProfile,
    tuple[SbmCorrelationScenarioDefinition, ...],
] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_CORRELATION_SCENARIOS,
    SbmRegulatoryProfile.US_NPR_2_0: US_NPR_CORRELATION_SCENARIOS,
    SbmRegulatoryProfile.EU_CRR3: EU_CRR3_CORRELATION_SCENARIOS,
    SbmRegulatoryProfile.PRA_UK_CRR: PRA_UK_CRR_CORRELATION_SCENARIOS,
}


def citations_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> dict[str, SbmCitation]:
    """Return citations for a supported SBM profile.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    dict[str, SbmCitation]
    """

    resolved = _resolve_supported_profile(profile)
    return dict(PROFILE_CITATIONS[resolved])


def correlation_scenarios_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> tuple[SbmCorrelationScenarioDefinition, ...]:
    """Return low, medium, and high correlation scenario definitions.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    tuple[SbmCorrelationScenarioDefinition, ...]
    """

    resolved = _resolve_supported_profile(profile)
    return PROFILE_CORRELATION_SCENARIOS[resolved]


def correlation_scenario_definition(
    profile: SbmRegulatoryProfile | str,
    scenario: SbmScenarioLabel | str,
) -> SbmCorrelationScenarioDefinition:
    """Return one correlation scenario definition.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    scenario : SbmScenarioLabel | str
        See signature.

    Returns
    -------
    SbmCorrelationScenarioDefinition
    """

    resolved_scenario = _coerce_scenario(scenario)
    for definition in correlation_scenarios_for_profile(profile):
        if definition.scenario is resolved_scenario:
            return definition
    raise SbmInputError(
        f"no correlation scenario definition for {resolved_scenario.value}",
        field="scenario",
    )


def apply_correlation_scenario_definition(
    base_correlation: float,
    definition: SbmCorrelationScenarioDefinition,
) -> float:
    """Apply one profile-owned MAR21.6 correlation-scenario rule to a base parameter.
    Parameters
    ----------
    base_correlation : float
        See signature.
    definition : SbmCorrelationScenarioDefinition
        See signature.

    Returns
    -------
    float
    """

    if not math.isfinite(base_correlation):
        raise SbmInputError("base_correlation must be finite", field="base_correlation")
    if definition.scenario is SbmScenarioLabel.LOW:
        return max(
            2.0 * base_correlation - 1.0,
            definition.multiplier * base_correlation,
        )
    if definition.scenario is SbmScenarioLabel.HIGH:
        cap = definition.cap if definition.cap is not None else 1.0
        return min(cap, definition.multiplier * base_correlation)
    return definition.multiplier * base_correlation


def apply_correlation_scenario(
    profile: SbmRegulatoryProfile | str,
    *,
    base_correlation: float,
    scenario: SbmScenarioLabel | str,
) -> tuple[float, tuple[str, ...]]:
    """Apply a profile correlation scenario to a base correlation parameter.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    base_correlation : float
        See signature.
    scenario : SbmScenarioLabel | str
        See signature.

    Returns
    -------
    tuple[float, tuple[str, ...]]
    """

    definition = correlation_scenario_definition(profile, scenario)
    adjusted = apply_correlation_scenario_definition(base_correlation, definition)
    return adjusted, (definition.citation_id,)


def _resolve_supported_profile(profile: SbmRegulatoryProfile | str) -> SbmRegulatoryProfile:
    try:
        resolved = SbmRegulatoryProfile(profile)
    except ValueError as exc:
        raise SbmInputError(
            f"unknown SBM regulatory profile: {profile!r}",
            field="profile_id",
        ) from exc

    if resolved not in PROFILE_CITATIONS:
        raise UnsupportedRegulatoryFeatureError(
            f"SBM profile {resolved.value} is unsupported until mapped and fixture-tested."
        )
    return resolved


def _coerce_risk_class(value: SbmRiskClass | str) -> SbmRiskClass:
    if isinstance(value, SbmRiskClass):
        return value
    try:
        return SbmRiskClass(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in SbmRiskClass)
        raise SbmInputError(
            f"risk_class must be one of: {allowed}",
            field="risk_class",
        ) from exc


def _coerce_scenario(value: SbmScenarioLabel | str) -> SbmScenarioLabel:
    if isinstance(value, SbmScenarioLabel):
        return value
    try:
        return SbmScenarioLabel(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in SbmScenarioLabel)
        raise SbmInputError(
            f"scenario must be one of: {allowed}",
            field="scenario",
        ) from exc


__all__ = [
    "BASEL_CITATIONS",
    "BASEL_CORRELATION_SCENARIOS",
    "BASEL_MAR21_URL",
    "EU_CRR3_CORRELATION_SCENARIOS",
    "PRA_UK_CRR_CITATIONS",
    "PRA_UK_CRR_CORRELATION_SCENARIOS",
    "PRA_UK_CRR_URL",
    "PROFILE_CITATIONS",
    "PROFILE_CORRELATION_SCENARIOS",
    "US_NPR_2_0_CITATIONS",
    "US_NPR_2_0_URL",
    "US_NPR_CORRELATION_SCENARIOS",
    "apply_correlation_scenario",
    "apply_correlation_scenario_definition",
    "citations_for_profile",
    "correlation_scenario_definition",
    "correlation_scenarios_for_profile",
]
