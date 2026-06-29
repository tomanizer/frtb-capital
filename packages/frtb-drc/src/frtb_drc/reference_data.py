"""Cited reference data for DRC rule profiles.

Verification status (audit 2026-06-02): LGD ladder and flat 100% defaulted LGD
confirmed against US NPR 2.0 proposed section __.210(b)(1)(iv), 91 FR 15236,
and Basel MAR22.18-MAR22.20; PSE/GSE/not-recovery-linked entries are US-NPR
additions. Maturity policy and default risk weights are confirmed against
proposed section __.210(a)(2)(iii), 91 FR 15235, and Table 1 to proposed
section __.210, 91 FR 15237.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from frtb_drc.data_models import CreditQuality, DrcBucketType, DrcRiskClass, DrcSeniority
from frtb_drc.validation import (
    DrcInputError,
    chargeable_securitisation_non_ctp_bucket_keys,
)

US_NPR_2_0_PROFILE_ID = "US_NPR_2_0"
BASEL_MAR22_PROFILE_ID = "BASEL_MAR22"
EU_CRR3_PROFILE_ID = "EU_CRR3"


@dataclass(frozen=True)
class LgdRule:
    """LGD rule entry with citation lineage."""

    seniority: DrcSeniority
    lgd_rate: float
    citation_id: str
    description: str


@dataclass(frozen=True)
class MaturityPolicy:
    """Maturity weighting policy for a profile."""

    profile_id: str
    floor_years: float
    full_weight_years: float
    citation_id: str


@dataclass(frozen=True)
class BucketDefinition:
    """DRC bucket definition for a profile/category."""

    bucket_key: str
    bucket_type: DrcBucketType
    risk_class: DrcRiskClass
    citation_id: str
    description: str


@dataclass(frozen=True)
class RiskWeightRule:
    """Risk-weight lookup entry."""

    bucket_key: str
    credit_quality: CreditQuality
    risk_weight: float
    citation_id: str


def get_lgd_rule(
    seniority: DrcSeniority,
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
    is_defaulted: bool = False,
) -> LgdRule:
    """Return the cited LGD rule for seniority/defaulted status.
    Parameters
    ----------
    seniority : DrcSeniority
        Instrument seniority for LGD lookup.
    profile_id : str, optional
        Active DRC rule profile identifier.
    is_defaulted : bool, optional
        Whether the position is in defaulted status.

    Returns
    -------
    LgdRule
        Cited LGD rule for the selected seniority and defaulted-status treatment.
    """

    _ensure_profile_exists(profile_id)
    if is_defaulted and profile_id == US_NPR_2_0_PROFILE_ID:
        return _require_lgd_rule(profile_id, DrcSeniority.EQUITY, defaulted=True)
    return _require_lgd_rule(profile_id, seniority, defaulted=False)


def get_maturity_policy(
    profile_id: str = US_NPR_2_0_PROFILE_ID,
    *,
    risk_class: DrcRiskClass = DrcRiskClass.NON_SECURITISATION,
) -> MaturityPolicy:
    """Return the maturity weighting policy for a profile and risk class.
    Parameters
    ----------
    profile_id : str, optional
        Active DRC rule profile identifier.
    risk_class : DrcRiskClass, optional
        Default-risk class for the maturity weighting lookup.

    Returns
    -------
    MaturityPolicy
        Cited maturity weighting policy for the selected profile and risk class.
    """

    _ensure_profile_exists(profile_id)
    risk_class = DrcRiskClass(risk_class)
    try:
        return _MATURITY_POLICIES[(profile_id, risk_class)]
    except KeyError as exc:
        raise DrcInputError(
            f"missing maturity policy for profile/risk class: {profile_id}/{risk_class.value}"
        ) from exc


def get_bucket_definition(
    bucket_key: str,
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> BucketDefinition:
    """Return a bucket definition by key.
    Parameters
    ----------
    bucket_key : str
        DRC bucket key for the calculation scope.
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    BucketDefinition
        Cited DRC bucket definition for the selected profile and bucket key.
    """

    _ensure_profile_exists(profile_id)
    try:
        return _BUCKET_DEFINITIONS[(profile_id, bucket_key)]
    except KeyError as exc:
        raise DrcInputError(f"missing DRC bucket definition: {profile_id}/{bucket_key}") from exc


def get_risk_weight_rule(
    bucket_key: str,
    credit_quality: CreditQuality,
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> RiskWeightRule:
    """Return a strict risk-weight rule by bucket and credit quality.
    Parameters
    ----------
    bucket_key : str
        DRC bucket key for the calculation scope.
    credit_quality : CreditQuality
        Credit-quality bucket for risk-weight lookup.
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    RiskWeightRule
        Cited risk-weight rule for the selected bucket and credit quality.
    """

    _ensure_profile_exists(profile_id)
    try:
        return _RISK_WEIGHT_RULES[(profile_id, bucket_key, credit_quality)]
    except KeyError as exc:
        raise DrcInputError(
            f"missing DRC risk weight: {profile_id}/{bucket_key}/{credit_quality.value}"
        ) from exc


def iter_lgd_rules(profile_id: str = US_NPR_2_0_PROFILE_ID) -> tuple[LgdRule, ...]:
    """Return all non-defaulted LGD rules for a profile in stable order.
    Parameters
    ----------
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[LgdRule, ...]
        LGD rules for the selected profile in stable order.
    """

    _ensure_profile_exists(profile_id)
    return tuple(
        _LGD_RULES[key] for key in sorted(_LGD_RULES) if key[0] == profile_id and key[2] is False
    )


def iter_bucket_definitions(
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> tuple[BucketDefinition, ...]:
    """Return bucket definitions for a profile in stable order.
    Parameters
    ----------
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[BucketDefinition, ...]
        Bucket definitions for the selected profile in stable order.
    """

    _ensure_profile_exists(profile_id)
    return tuple(
        _BUCKET_DEFINITIONS[key] for key in sorted(_BUCKET_DEFINITIONS) if key[0] == profile_id
    )


def iter_risk_weight_rules(profile_id: str = US_NPR_2_0_PROFILE_ID) -> tuple[RiskWeightRule, ...]:
    """Return risk-weight entries for a profile in stable order.
    Parameters
    ----------
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[RiskWeightRule, ...]
        Risk-weight rules for the selected profile in stable order.
    """

    _ensure_profile_exists(profile_id)
    return tuple(
        _RISK_WEIGHT_RULES[key]
        for key in sorted(_RISK_WEIGHT_RULES, key=lambda item: (item[0], item[1], item[2].value))
        if key[0] == profile_id
    )


def _require_lgd_rule(profile_id: str, seniority: DrcSeniority, *, defaulted: bool) -> LgdRule:
    try:
        return _LGD_RULES[(profile_id, seniority, defaulted)]
    except KeyError as exc:
        defaulted_label = "defaulted" if defaulted else "non-defaulted"
        raise DrcInputError(
            f"missing DRC LGD rule: {profile_id}/{seniority.value}/{defaulted_label}"
        ) from exc


def profile_reference_data_payload(profile_id: str) -> dict[str, object]:
    """Return deterministic reference-data payload used in profile hashing.
    Parameters
    ----------
    profile_id : str
        Active DRC rule profile identifier.

    Returns
    -------
    dict[str, object]
        Deterministic reference-data payload used in rule-profile hashing.
    """

    return {
        "lgd_rules": [
            {
                "seniority": seniority.value,
                "defaulted": defaulted,
                "lgd_rate": rule.lgd_rate,
                "citation_id": rule.citation_id,
                "description": rule.description,
            }
            for current_profile_id, seniority, defaulted in sorted(_LGD_RULES)
            if current_profile_id == profile_id
            for rule in (_LGD_RULES[(current_profile_id, seniority, defaulted)],)
        ],
        "maturity_policies": [
            {
                "risk_class": risk_class.value,
                "profile_id": rule.profile_id,
                "floor_years": rule.floor_years,
                "full_weight_years": rule.full_weight_years,
                "citation_id": rule.citation_id,
            }
            for current_profile_id, risk_class in sorted(
                _MATURITY_POLICIES,
                key=lambda item: (item[0], item[1].value),
            )
            if current_profile_id == profile_id
            for rule in (_MATURITY_POLICIES[(current_profile_id, risk_class)],)
        ],
        "bucket_definitions": [
            {
                "bucket_key": bucket_key,
                "bucket_type": definition.bucket_type.value,
                "risk_class": definition.risk_class.value,
                "citation_id": definition.citation_id,
                "description": definition.description,
            }
            for current_profile_id, bucket_key in sorted(_BUCKET_DEFINITIONS)
            if current_profile_id == profile_id
            for definition in (_BUCKET_DEFINITIONS[(current_profile_id, bucket_key)],)
        ],
        "risk_weight_rules": [
            {
                "bucket_key": bucket_key,
                "credit_quality": credit_quality.value,
                "risk_weight": rule.risk_weight,
                "citation_id": rule.citation_id,
            }
            for current_profile_id, bucket_key, credit_quality in sorted(
                _RISK_WEIGHT_RULES, key=lambda item: (item[0], item[1], item[2].value)
            )
            if current_profile_id == profile_id
            for rule in (_RISK_WEIGHT_RULES[(current_profile_id, bucket_key, credit_quality)],)
        ],
    }


def _ensure_profile_exists(profile_id: str) -> None:
    from frtb_drc.regimes import get_rule_profile

    get_rule_profile(profile_id)


_LGD_RULES: Mapping[tuple[str, DrcSeniority, bool], LgdRule] = MappingProxyType(
    {
        (
            US_NPR_2_0_PROFILE_ID,
            DrcSeniority.EQUITY,
            False,
        ): LgdRule(
            seniority=DrcSeniority.EQUITY,
            lgd_rate=1.00,
            citation_id="US_NPR_210_B_1_IV",
            description="Equity positions.",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            DrcSeniority.NON_SENIOR_DEBT,
            False,
        ): LgdRule(
            seniority=DrcSeniority.NON_SENIOR_DEBT,
            lgd_rate=1.00,
            citation_id="US_NPR_210_B_1_IV",
            description="Non-senior debt positions.",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            DrcSeniority.SENIOR_DEBT,
            False,
        ): LgdRule(
            seniority=DrcSeniority.SENIOR_DEBT,
            lgd_rate=0.75,
            citation_id="US_NPR_210_B_1_IV",
            description="Senior debt unless a lower cited LGD is assigned.",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            DrcSeniority.GSE_ISSUED_NOT_GUARANTEED,
            False,
        ): LgdRule(
            seniority=DrcSeniority.GSE_ISSUED_NOT_GUARANTEED,
            lgd_rate=0.75,
            citation_id="US_NPR_210_B_1_IV",
            description="GSE debt issued but not guaranteed by GSEs.",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            DrcSeniority.PSE,
            False,
        ): LgdRule(
            seniority=DrcSeniority.PSE,
            lgd_rate=0.50,
            citation_id="US_NPR_210_B_1_IV",
            description="Positions in U.S. public sector entities.",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            DrcSeniority.GSE_GUARANTEED,
            False,
        ): LgdRule(
            seniority=DrcSeniority.GSE_GUARANTEED,
            lgd_rate=0.25,
            citation_id="US_NPR_210_B_1_IV",
            description="GSE-guaranteed debt.",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            DrcSeniority.COVERED_BOND,
            False,
        ): LgdRule(
            seniority=DrcSeniority.COVERED_BOND,
            lgd_rate=0.25,
            citation_id="US_NPR_210_B_1_IV",
            description="Covered bonds.",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            DrcSeniority.NOT_RECOVERY_LINKED,
            False,
        ): LgdRule(
            seniority=DrcSeniority.NOT_RECOVERY_LINKED,
            lgd_rate=0.00,
            citation_id="US_NPR_210_B_1_IV",
            description="Value is not linked to issuer recovery.",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            DrcSeniority.EQUITY,
            True,
        ): LgdRule(
            seniority=DrcSeniority.EQUITY,
            lgd_rate=1.00,
            citation_id="US_NPR_210_B_1_IV",
            description="Defaulted positions.",
        ),
    }
)

_LGD_RULES = MappingProxyType(
    {
        **dict(_LGD_RULES),
        (
            BASEL_MAR22_PROFILE_ID,
            DrcSeniority.EQUITY,
            False,
        ): LgdRule(
            seniority=DrcSeniority.EQUITY,
            lgd_rate=1.00,
            citation_id="BASEL_MAR22_12",
            description="Equity instruments.",
        ),
        (
            BASEL_MAR22_PROFILE_ID,
            DrcSeniority.NON_SENIOR_DEBT,
            False,
        ): LgdRule(
            seniority=DrcSeniority.NON_SENIOR_DEBT,
            lgd_rate=1.00,
            citation_id="BASEL_MAR22_12",
            description="Non-senior debt instruments.",
        ),
        (
            BASEL_MAR22_PROFILE_ID,
            DrcSeniority.SENIOR_DEBT,
            False,
        ): LgdRule(
            seniority=DrcSeniority.SENIOR_DEBT,
            lgd_rate=0.75,
            citation_id="BASEL_MAR22_12",
            description="Senior debt instruments.",
        ),
        (
            BASEL_MAR22_PROFILE_ID,
            DrcSeniority.COVERED_BOND,
            False,
        ): LgdRule(
            seniority=DrcSeniority.COVERED_BOND,
            lgd_rate=0.25,
            citation_id="BASEL_MAR22_12",
            description="Covered bonds as defined by the selected Basel profile.",
        ),
        (
            BASEL_MAR22_PROFILE_ID,
            DrcSeniority.NOT_RECOVERY_LINKED,
            False,
        ): LgdRule(
            seniority=DrcSeniority.NOT_RECOVERY_LINKED,
            lgd_rate=0.00,
            citation_id="BASEL_MAR22_12",
            description="Instrument value is not linked to issuer recovery.",
        ),
        (
            EU_CRR3_PROFILE_ID,
            DrcSeniority.EQUITY,
            False,
        ): LgdRule(
            seniority=DrcSeniority.EQUITY,
            lgd_rate=1.00,
            citation_id="EU_CRR3_ARTICLE_325W",
            description="Equity instruments.",
        ),
        (
            EU_CRR3_PROFILE_ID,
            DrcSeniority.NON_SENIOR_DEBT,
            False,
        ): LgdRule(
            seniority=DrcSeniority.NON_SENIOR_DEBT,
            lgd_rate=1.00,
            citation_id="EU_CRR3_ARTICLE_325W",
            description="Non-senior debt instruments.",
        ),
        (
            EU_CRR3_PROFILE_ID,
            DrcSeniority.SENIOR_DEBT,
            False,
        ): LgdRule(
            seniority=DrcSeniority.SENIOR_DEBT,
            lgd_rate=0.75,
            citation_id="EU_CRR3_ARTICLE_325W",
            description="Senior debt instruments.",
        ),
        (
            EU_CRR3_PROFILE_ID,
            DrcSeniority.COVERED_BOND,
            False,
        ): LgdRule(
            seniority=DrcSeniority.COVERED_BOND,
            lgd_rate=0.25,
            citation_id="EU_CRR3_ARTICLE_325W",
            description="Covered bonds.",
        ),
        (
            EU_CRR3_PROFILE_ID,
            DrcSeniority.NOT_RECOVERY_LINKED,
            False,
        ): LgdRule(
            seniority=DrcSeniority.NOT_RECOVERY_LINKED,
            lgd_rate=0.00,
            citation_id="EU_CRR3_ARTICLE_325W",
            description="Instrument value is not linked to issuer recovery.",
        ),
    }
)

_MATURITY_POLICIES: Mapping[tuple[str, DrcRiskClass], MaturityPolicy] = MappingProxyType(
    {
        (
            US_NPR_2_0_PROFILE_ID,
            DrcRiskClass.NON_SECURITISATION,
        ): MaturityPolicy(
            profile_id=US_NPR_2_0_PROFILE_ID,
            floor_years=0.25,
            full_weight_years=1.0,
            citation_id="US_NPR_210_A_2_III",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            DrcRiskClass.SECURITISATION_NON_CTP,
        ): MaturityPolicy(
            profile_id=US_NPR_2_0_PROFILE_ID,
            floor_years=1.0,
            full_weight_years=1.0,
            citation_id="US_NPR_210_C_1",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        ): MaturityPolicy(
            profile_id=US_NPR_2_0_PROFILE_ID,
            floor_years=1.0,
            full_weight_years=1.0,
            citation_id="US_NPR_210_D_1",
        ),
        (
            BASEL_MAR22_PROFILE_ID,
            DrcRiskClass.NON_SECURITISATION,
        ): MaturityPolicy(
            profile_id=BASEL_MAR22_PROFILE_ID,
            floor_years=0.25,
            full_weight_years=1.0,
            citation_id="BASEL_MAR22_15_18",
        ),
        (
            BASEL_MAR22_PROFILE_ID,
            DrcRiskClass.SECURITISATION_NON_CTP,
        ): MaturityPolicy(
            profile_id=BASEL_MAR22_PROFILE_ID,
            floor_years=1.0,
            full_weight_years=1.0,
            citation_id="BASEL_MAR22_27",
        ),
        (
            BASEL_MAR22_PROFILE_ID,
            DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        ): MaturityPolicy(
            profile_id=BASEL_MAR22_PROFILE_ID,
            floor_years=1.0,
            full_weight_years=1.0,
            citation_id="BASEL_MAR22_36",
        ),
        (
            EU_CRR3_PROFILE_ID,
            DrcRiskClass.NON_SECURITISATION,
        ): MaturityPolicy(
            profile_id=EU_CRR3_PROFILE_ID,
            floor_years=0.25,
            full_weight_years=1.0,
            citation_id="EU_CRR3_ARTICLE_325X",
        ),
    }
)


def _securitisation_bucket_description(bucket_key: str) -> str:
    if bucket_key == "SEC_CORPORATE":
        return "Securitisation non-CTP corporate bucket across all regions."
    suffix = bucket_key.removeprefix("SEC_").lower().replace("_", " ")
    return f"Securitisation non-CTP {suffix} bucket."


_NONSEC_BUCKET_DEFINITIONS: dict[tuple[str, str], BucketDefinition] = {
    (US_NPR_2_0_PROFILE_ID, "NON_US_SOVEREIGN"): BucketDefinition(
        bucket_key="NON_US_SOVEREIGN",
        bucket_type=DrcBucketType.NON_US_SOVEREIGN,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        citation_id="US_NPR_210_B_3_I",
        description="Non-U.S. sovereign exposures.",
    ),
    (US_NPR_2_0_PROFILE_ID, "PSE_GSE"): BucketDefinition(
        bucket_key="PSE_GSE",
        bucket_type=DrcBucketType.PSE_GSE,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        citation_id="US_NPR_210_B_3_I",
        description="PSE and GSE debt positions.",
    ),
    (US_NPR_2_0_PROFILE_ID, "CORPORATE"): BucketDefinition(
        bucket_key="CORPORATE",
        bucket_type=DrcBucketType.CORPORATE,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        citation_id="US_NPR_210_B_3_I",
        description="Corporate positions.",
    ),
    (US_NPR_2_0_PROFILE_ID, "DEFAULTED"): BucketDefinition(
        bucket_key="DEFAULTED",
        bucket_type=DrcBucketType.DEFAULTED,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        citation_id="US_NPR_210_B_3_I",
        description="Defaulted positions.",
    ),
    (BASEL_MAR22_PROFILE_ID, "CORPORATE"): BucketDefinition(
        bucket_key="CORPORATE",
        bucket_type=DrcBucketType.CORPORATE,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        citation_id="BASEL_MAR22_22",
        description="Corporate exposures.",
    ),
    (BASEL_MAR22_PROFILE_ID, "SOVEREIGN"): BucketDefinition(
        bucket_key="SOVEREIGN",
        bucket_type=DrcBucketType.SOVEREIGN,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        citation_id="BASEL_MAR22_22",
        description="Sovereign exposures.",
    ),
    (BASEL_MAR22_PROFILE_ID, "LOCAL_GOVERNMENT_MUNICIPAL"): BucketDefinition(
        bucket_key="LOCAL_GOVERNMENT_MUNICIPAL",
        bucket_type=DrcBucketType.LOCAL_GOVERNMENT_MUNICIPAL,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        citation_id="BASEL_MAR22_22",
        description="Local government and municipal exposures.",
    ),
    (EU_CRR3_PROFILE_ID, "CORPORATE"): BucketDefinition(
        bucket_key="CORPORATE",
        bucket_type=DrcBucketType.CORPORATE,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        citation_id="EU_CRR3_ARTICLE_325Y_1_2",
        description="Corporate exposures.",
    ),
    (EU_CRR3_PROFILE_ID, "SOVEREIGN"): BucketDefinition(
        bucket_key="SOVEREIGN",
        bucket_type=DrcBucketType.SOVEREIGN,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        citation_id="EU_CRR3_ARTICLE_325Y_1_2",
        description="Sovereign exposures.",
    ),
    (EU_CRR3_PROFILE_ID, "LOCAL_GOVERNMENT_MUNICIPAL"): BucketDefinition(
        bucket_key="LOCAL_GOVERNMENT_MUNICIPAL",
        bucket_type=DrcBucketType.LOCAL_GOVERNMENT_MUNICIPAL,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        citation_id="EU_CRR3_ARTICLE_325Y_1_2",
        description="Local government and municipal exposures.",
    ),
}

_SECURITISATION_BUCKET_DEFINITIONS: dict[tuple[str, str], BucketDefinition] = {
    (US_NPR_2_0_PROFILE_ID, bucket_key): BucketDefinition(
        bucket_key=bucket_key,
        bucket_type=DrcBucketType.SECURITISATION_ASSET_REGION,
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        citation_id="US_NPR_210_C_3_I_II",
        description=_securitisation_bucket_description(bucket_key),
    )
    for bucket_key in chargeable_securitisation_non_ctp_bucket_keys()
}
_SECURITISATION_BUCKET_DEFINITIONS.update(
    {
        (BASEL_MAR22_PROFILE_ID, bucket_key): BucketDefinition(
            bucket_key=bucket_key,
            bucket_type=DrcBucketType.SECURITISATION_ASSET_REGION,
            risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
            citation_id="BASEL_MAR22_31",
            description=_securitisation_bucket_description(bucket_key),
        )
        for bucket_key in chargeable_securitisation_non_ctp_bucket_keys()
    }
)

_BUCKET_DEFINITIONS: Mapping[tuple[str, str], BucketDefinition] = MappingProxyType(
    {
        **_NONSEC_BUCKET_DEFINITIONS,
        **_SECURITISATION_BUCKET_DEFINITIONS,
    }
)

_RISK_WEIGHT_RULES: Mapping[tuple[str, str, CreditQuality], RiskWeightRule] = MappingProxyType(
    {
        (
            US_NPR_2_0_PROFILE_ID,
            "NON_US_SOVEREIGN",
            CreditQuality.INVESTMENT_GRADE,
        ): RiskWeightRule(
            bucket_key="NON_US_SOVEREIGN",
            credit_quality=CreditQuality.INVESTMENT_GRADE,
            risk_weight=0.006,
            citation_id="US_NPR_210_B_3_II",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            "NON_US_SOVEREIGN",
            CreditQuality.SPECULATIVE_GRADE,
        ): RiskWeightRule(
            bucket_key="NON_US_SOVEREIGN",
            credit_quality=CreditQuality.SPECULATIVE_GRADE,
            risk_weight=0.22,
            citation_id="US_NPR_210_B_3_II",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            "NON_US_SOVEREIGN",
            CreditQuality.SUB_SPECULATIVE_GRADE,
        ): RiskWeightRule(
            bucket_key="NON_US_SOVEREIGN",
            credit_quality=CreditQuality.SUB_SPECULATIVE_GRADE,
            risk_weight=0.50,
            citation_id="US_NPR_210_B_3_II",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            "PSE_GSE",
            CreditQuality.INVESTMENT_GRADE,
        ): RiskWeightRule(
            bucket_key="PSE_GSE",
            credit_quality=CreditQuality.INVESTMENT_GRADE,
            risk_weight=0.021,
            citation_id="US_NPR_210_B_3_II",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            "PSE_GSE",
            CreditQuality.SPECULATIVE_GRADE,
        ): RiskWeightRule(
            bucket_key="PSE_GSE",
            credit_quality=CreditQuality.SPECULATIVE_GRADE,
            risk_weight=0.22,
            citation_id="US_NPR_210_B_3_II",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            "PSE_GSE",
            CreditQuality.SUB_SPECULATIVE_GRADE,
        ): RiskWeightRule(
            bucket_key="PSE_GSE",
            credit_quality=CreditQuality.SUB_SPECULATIVE_GRADE,
            risk_weight=0.50,
            citation_id="US_NPR_210_B_3_II",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            "CORPORATE",
            CreditQuality.INVESTMENT_GRADE,
        ): RiskWeightRule(
            bucket_key="CORPORATE",
            credit_quality=CreditQuality.INVESTMENT_GRADE,
            risk_weight=0.041,
            citation_id="US_NPR_210_B_3_II",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            "CORPORATE",
            CreditQuality.SPECULATIVE_GRADE,
        ): RiskWeightRule(
            bucket_key="CORPORATE",
            credit_quality=CreditQuality.SPECULATIVE_GRADE,
            risk_weight=0.22,
            citation_id="US_NPR_210_B_3_II",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            "CORPORATE",
            CreditQuality.SUB_SPECULATIVE_GRADE,
        ): RiskWeightRule(
            bucket_key="CORPORATE",
            credit_quality=CreditQuality.SUB_SPECULATIVE_GRADE,
            risk_weight=0.50,
            citation_id="US_NPR_210_B_3_II",
        ),
        (
            US_NPR_2_0_PROFILE_ID,
            "DEFAULTED",
            CreditQuality.DEFAULTED,
        ): RiskWeightRule(
            bucket_key="DEFAULTED",
            credit_quality=CreditQuality.DEFAULTED,
            risk_weight=1.00,
            citation_id="US_NPR_210_B_3_II",
        ),
    }
)

_BASEL_MAR22_RISK_WEIGHT_VALUES = {
    CreditQuality.AAA: 0.005,
    CreditQuality.AA: 0.02,
    CreditQuality.A: 0.03,
    CreditQuality.BBB: 0.06,
    CreditQuality.BB: 0.15,
    CreditQuality.B: 0.30,
    CreditQuality.CCC: 0.50,
    CreditQuality.UNRATED: 0.15,
    CreditQuality.DEFAULTED: 1.00,
}
_RISK_WEIGHT_RULES = MappingProxyType(
    {
        **dict(_RISK_WEIGHT_RULES),
        **{
            (BASEL_MAR22_PROFILE_ID, bucket_key, credit_quality): RiskWeightRule(
                bucket_key=bucket_key,
                credit_quality=credit_quality,
                risk_weight=risk_weight,
                citation_id="BASEL_MAR22_24",
            )
            for bucket_key in (
                "CORPORATE",
                "SOVEREIGN",
                "LOCAL_GOVERNMENT_MUNICIPAL",
            )
            for credit_quality, risk_weight in _BASEL_MAR22_RISK_WEIGHT_VALUES.items()
        },
        **{
            (EU_CRR3_PROFILE_ID, bucket_key, credit_quality): RiskWeightRule(
                bucket_key=bucket_key,
                credit_quality=credit_quality,
                risk_weight=risk_weight,
                citation_id="EU_CRR3_ARTICLE_325Y_1_2",
            )
            for bucket_key in (
                "CORPORATE",
                "SOVEREIGN",
                "LOCAL_GOVERNMENT_MUNICIPAL",
            )
            for credit_quality, risk_weight in _BASEL_MAR22_RISK_WEIGHT_VALUES.items()
        },
    }
)
