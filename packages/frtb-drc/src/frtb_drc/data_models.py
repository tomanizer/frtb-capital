"""
Core data models for FRTB DRC.

Frozen dataclasses and enums only. No business logic.

Regulatory traceability:
    Basel MAR22.3–22.7 (definitions), MAR22.15–22.20 (risk weights and buckets),
    U.S. NPR 2.0 __.212 and Appendix (FRB-specific buckets and IG/SG/SSG mapping).
    See docs/REGULATORY_TRACEABILITY.md and docs/FRTB-DRC-Requirements-Specification.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Any


class RiskClassDRC(StrEnum):
    """DRC risk classes per Basel MAR22 and NPR 2.0."""

    NONSEC = "DRC_NONSEC"
    SEC_CTP = "DRC_SEC_CTP"
    SEC_NCTP = "DRC_SEC_NCTP"


class Seniority(IntEnum):
    """
    Instrument seniority for DRC netting and LGD.

    Values align with reference implementation Zinc/Axiom codes:
    COVERED (covered bonds), SENIOR, NON_SENIOR (subordinated), EQUITY.
    """

    COVERED = 1
    SENIOR = 2
    NON_SENIOR = 3
    EQUITY = 4


class CreditQuality(StrEnum):
    """
    Credit quality categories for risk-weight lookup.

    - IG / SG / SSG: FRB / U.S. NPR 2.0-style (NON_US_SOVEREIGNS, PSE_GSE_DEBT etc.)
    - Letter ratings (AAA–C) + UNRATED / DEFAULTED: BCBS / CRR2 / PRA style.
    - Numeric CQS "1"–"7" also accepted for CRR2 compatibility.
    """

    # FRB / NPR 2.0
    IG = "IG"
    SG = "SG"
    SSG = "SSG"
    # BCBS / Basel letter ratings (used in RW tables)
    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    B = "B"
    CCC = "CCC"
    CC = "CC"
    C = "C"
    # CRR2 / CRR3 CQS numeric
    CQS_1 = "1"
    CQS_2 = "2"
    CQS_3 = "3"
    CQS_4 = "4"
    CQS_5 = "5"
    CQS_6 = "6"
    CQS_7 = "7"
    UNRATED = "UNRATED"
    DEFAULTED = "DEFAULTED"
    ZERO_RW = "ZERO_RW"  # explicit zero for certain gov exposures


class RulesVersion(StrEnum):
    """Regulatory rule set for risk weights, buckets, and formulas."""

    BCBS = "BCBS"
    CRR2 = "CRR2"
    FRB = "FRB"  # U.S. NPR 2.0 / FRB final (proposed in NPR)
    PRA = "PRA"


# Canonical bucket names (non-securitisation)
CORPORATES = "CORPORATES"
SOVEREIGNS = "SOVEREIGNS"
LOCAL_GOV = "LOCAL_GOV"
NON_US_SOVEREIGNS = "NON_US_SOVEREIGNS"
PSE_GSE_DEBT = "PSE_GSE_DEBT"
DEFAULTED_BUCKET = "DEFAULTED"

BCBS_BUCKETS: tuple[str, ...] = (CORPORATES, SOVEREIGNS, LOCAL_GOV)
FRB_BUCKETS: tuple[str, ...] = (NON_US_SOVEREIGNS, PSE_GSE_DEBT, CORPORATES, DEFAULTED_BUCKET)

# Securitisation (non-CTP) sector buckets (abbreviated; full list in reference_data)
BCBS_SEC_NCTP_SECTORS: tuple[str, ...] = (
    "CORPORATES",
    "ABCP",
    "AUTO",
    "RMBS",
    "CREDIT_CARDS",
    "CMBS",
    "CLO",
    "CDO_SQUARED",
    "SME",
    "STUDENT_LOANS",
    "OTHER_RETAIL",
    "OTHER_WHOLESALES",
)

# Seniority string constants (for CRIF / audit columns)
COVERED = "COVERED"
SENIOR = "SENIOR"
NON_SENIOR_STR = "NON-SENIOR"
EQUITY = "EQUITY"

SENIORITY_TO_STR: dict[Seniority, str] = {
    Seniority.COVERED: COVERED,
    Seniority.SENIOR: SENIOR,
    Seniority.NON_SENIOR: NON_SENIOR_STR,
    Seniority.EQUITY: EQUITY,
}


@dataclass(frozen=True)
class Position:
    """
    A single DRC exposure position (pre-netting JTD input).

    Represents one row from CRIF or upstream exposure feed for a given
    issuer / seniority / credit quality combination.

    Sign convention: long_jtd and short_jtd are positive quantities
    (gross loss exposure if default occurs). Netting happens downstream.

    Regulatory traceability:
        Basel MAR22.8–22.14 (JTD definition, long/short, seniority).
    """

    issuer_id: str
    bucket: str  # FRTB bucket (NON_US_SOVEREIGNS, CORPORATES, etc.)
    seniority: Seniority
    credit_quality: CreditQuality
    long_jtd: float = 0.0  # gross long jump-to-default exposure (positive = loss)
    short_jtd: float = 0.0  # gross short jump-to-default exposure (positive = loss)
    notional: float | None = None
    maturity_days: int | None = None
    covered_bond_flag: bool = False
    risk_class: RiskClassDRC = RiskClassDRC.NONSEC
    # Audit / lineage
    source_row_id: str = ""

    def __post_init__(self) -> None:
        if not self.issuer_id or not isinstance(self.issuer_id, str):
            raise ValueError("issuer_id must be non-empty string")
        if self.long_jtd < 0 or self.short_jtd < 0:
            raise ValueError("JTD amounts must be non-negative (use separate long/short fields)")
        if self.long_jtd == 0 and self.short_jtd == 0:
            raise ValueError("At least one of long_jtd or short_jtd must be > 0")

    def as_dict(self) -> dict[str, Any]:
        """Serialisable form for audit records and logging."""
        return {
            "issuer_id": self.issuer_id,
            "bucket": self.bucket,
            "seniority": SENIORITY_TO_STR[self.seniority],
            "credit_quality": self.credit_quality.value,
            "long_jtd": self.long_jtd,
            "short_jtd": self.short_jtd,
            "notional": self.notional,
            "maturity_days": self.maturity_days,
            "covered_bond_flag": self.covered_bond_flag,
            "risk_class": self.risk_class.value,
            "source_row_id": self.source_row_id,
        }


@dataclass(frozen=True)
class NettedIssuerSeniority:
    """
    Post-netting exposure for one issuer + seniority combination.

    Per Basel MAR22.11: no cross-seniority netting within an issuer.
    Long and short are netted within the same seniority only.
    """

    issuer_id: str
    bucket: str
    seniority: Seniority
    credit_quality: CreditQuality
    net_long: float  # max(0, gross_long - gross_short) after any offsets
    net_short: float  # max(0, gross_short - gross_long)
    risk_weight: float
    lgd: float
    # Full audit trail
    gross_long: float
    gross_short: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "issuer_id": self.issuer_id,
            "bucket": self.bucket,
            "seniority": SENIORITY_TO_STR[self.seniority],
            "credit_quality": self.credit_quality.value,
            "net_long": self.net_long,
            "net_short": self.net_short,
            "risk_weight": self.risk_weight,
            "lgd": self.lgd,
            "gross_long": self.gross_long,
            "gross_short": self.gross_short,
        }


@dataclass(frozen=True)
class UnsupportedRegulatoryFeature:
    """Descriptor for a DRC feature not yet implemented for a given regime."""

    feature_name: str
    regime: RulesVersion
    regulatory_source: str
    notes: str = ""


class UnsupportedRegulatoryFeatureError(NotImplementedError):
    """Raised when a policy/regime requests a DRC feature not implemented."""

    def __init__(self, feature: UnsupportedRegulatoryFeature) -> None:
        self.feature = feature
        super().__init__(
            f"{feature.regime.value} requires unsupported DRC feature "
            f"'{feature.feature_name}' ({feature.regulatory_source}). {feature.notes}"
        )
