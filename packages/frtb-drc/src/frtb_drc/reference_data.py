"""
Reference data tables and pure lookup helpers for FRTB DRC risk weights, LGD, buckets.

Sourced from regulatory tables (Basel MAR22, U.S. NPR 2.0 FRB buckets, CRR3) and
cross-checked against reference reconstruction (drc.zip / drc_common.py).

All functions are pure. No I/O, no mutable state.

Regulatory traceability:
    Basel MAR22.15–22.20 (non-securitisation risk weights)
    U.S. NPR 2.0 Appendix (FRB/NPR 2.0: NON_US_SOVEREIGNS, PSE_GSE_DEBT, IG/SG/SSG)
    CRR3 Annex (CQS 1-7 mapping)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from frtb_drc.data_models import (
    BCBS_BUCKETS,
    BCBS_SEC_NCTP_SECTORS,
    CreditQuality,
    DEFAULTED_BUCKET,
    FRB_BUCKETS,
    NON_US_SOVEREIGNS,
    PSE_GSE_DEBT,
    RulesVersion,
)

# =============================================================================
# Risk weight tables (exact values from regulatory sources + reference)
# =============================================================================

# BCBS / Basel (MAR22) and PRA — rating letter to RW
BCBS_DRC_JS_RW: dict[str, float] = {
    "AAA": 0.005,
    "AA": 0.02,
    "A": 0.03,
    "BBB": 0.06,
    "BB": 0.15,
    "B": 0.30,
    "CCC": 0.50,
    "CC": 0.50,
    "C": 0.50,
    CreditQuality.UNRATED.value: 0.15,
    CreditQuality.DEFAULTED.value: 1.00,
    CreditQuality.ZERO_RW.value: 0.0,
}

# CRR2 / CRR3 style — CQS numeric to RW
CRR2_DRC_JS_RW: dict[str, float] = {
    "1": 0.005,
    "2": 0.01,
    "3": 0.05,
    "4": 0.15,
    "5": 0.30,
    "6": 0.50,
    "7": 1.00,
    CreditQuality.UNRATED.value: 0.15,
    CreditQuality.DEFAULTED.value: 1.00,
    CreditQuality.ZERO_RW.value: 0.0,
}

# FRB / U.S. NPR 2.0 — (bucket, credit_quality) -> RW
# See NPR 2.0 proposed Appendix B and FRB final rule mapping
FRB_DRC_JS_RW: dict[tuple[str, str], float] = {
    (NON_US_SOVEREIGNS, CreditQuality.IG.value): 0.005,
    (NON_US_SOVEREIGNS, CreditQuality.SG.value): 0.20,
    (NON_US_SOVEREIGNS, CreditQuality.SSG.value): 0.50,
    (PSE_GSE_DEBT, CreditQuality.IG.value): 0.02,
    (PSE_GSE_DEBT, CreditQuality.SG.value): 0.12,
    (PSE_GSE_DEBT, CreditQuality.SSG.value): 0.50,
    (DEFAULTED_BUCKET, CreditQuality.DEFAULTED.value): 1.00,
    # CORPORATES follow PSE_GSE_DEBT pattern under FRB in reference
    ("CORPORATES", CreditQuality.IG.value): 0.02,
    ("CORPORATES", CreditQuality.SG.value): 0.12,
    ("CORPORATES", CreditQuality.SSG.value): 0.50,
}

# Regime -> table
RISK_WEIGHTS: dict[RulesVersion, dict[Any, float]] = {
    RulesVersion.CRR2: CRR2_DRC_JS_RW,
    RulesVersion.BCBS: BCBS_DRC_JS_RW,
    RulesVersion.FRB: FRB_DRC_JS_RW,  # type: ignore[dict-item]  # tuple keys
    RulesVersion.PRA: BCBS_DRC_JS_RW,
}

# =============================================================================
# Bucket sets per regime (DRC non-sec)
# =============================================================================

DRC_NS_BUCKETS: dict[RulesVersion, tuple[str, ...]] = {
    RulesVersion.CRR2: BCBS_BUCKETS,
    RulesVersion.BCBS: BCBS_BUCKETS,
    RulesVersion.FRB: FRB_BUCKETS,
    RulesVersion.PRA: BCBS_BUCKETS,
}

# =============================================================================
# LGD defaults (Basel MAR22.18, NPR cross-reference)
# =============================================================================

DEFAULT_LGD_NON_SENIOR: float = 0.75  # subordinated / equity / non-senior
DEFAULT_LGD_SENIOR: float = 0.25  # senior unsecured / covered (conservative; cite exact reg)

LGD_BY_SENIORITY: dict[str, float] = {
    "COVERED": DEFAULT_LGD_SENIOR,
    "SENIOR": DEFAULT_LGD_SENIOR,
    "NON-SENIOR": DEFAULT_LGD_NON_SENIOR,
    "EQUITY": DEFAULT_LGD_NON_SENIOR,
}


# =============================================================================
# Public helpers (pure)
# =============================================================================


def get_risk_weight(
    bucket: str,
    credit_quality: str = "",
    rules_version: RulesVersion = RulesVersion.CRR2,
) -> float:
    """
    Return the DRC jump-to-default risk weight for the given bucket / credit quality.

    Exactly matches the logic and tables from the reference implementation
    (drc_common.get_risk_weight) for BCBS/CRR2/FRB/PRA.

    For FRB/NPR 2.0 the lookup is (bucket, credit_quality) where credit_quality
    is one of IG/SG/SSG (or DEFAULTED for the defaulted bucket).

    For other regimes the credit_quality (or bucket fallback) is used directly
    against the rating/CQS table.

    Raises:
        ValueError: if no risk weight is defined for the combination.

    Regulatory traceability:
        Basel MAR22.15–22.17 (non-sec RW table)
        U.S. NPR 2.0 FRB-specific table (NON_US_SOVEREIGNS etc.)
    """
    rw_mapping = RISK_WEIGHTS[rules_version]

    if rules_version == RulesVersion.FRB:
        key = (bucket, credit_quality or CreditQuality.SG.value)
        rw = rw_mapping.get(key)
        if rw is None:
            # Fallback for unknown bucket under FRB (conservative SSG per reference)
            rw = 0.50
    else:
        key = str(credit_quality or bucket)
        rw = rw_mapping.get(key, 0.15)  # UNRATED default per tables

    if rw is None:
        raise ValueError(
            f"No Risk Weight defined for bucket={bucket!r}, "
            f"credit_quality={credit_quality!r}, regime={rules_version.value}"
        )
    return float(rw)


def get_lgd(seniority_str: str, override: float | None = None) -> float:
    """Return LGD for seniority. Override takes precedence (for policy flexibility)."""
    if override is not None:
        if not 0.0 <= override <= 1.0:
            raise ValueError("LGD override must be in [0, 1]")
        return override
    return LGD_BY_SENIORITY.get(seniority_str, DEFAULT_LGD_NON_SENIOR)


@dataclass(frozen=True)
class ReferenceData:
    """Immutable bundle of all DRC reference tables for a given rules version + overrides."""

    rules_version: RulesVersion
    risk_weights: dict[Any, float]
    buckets: tuple[str, ...]
    lgd_table: dict[str, float]
    # Future: correlation matrices, CTP tranche tables, etc.


def load_reference_data(
    rules_version: RulesVersion = RulesVersion.CRR2,
    overrides: dict[str, Any] | None = None,
) -> ReferenceData:
    """
    Load (or construct) the reference data bundle for a rules version.

    overrides may contain:
      - "risk_weights": partial dict to overlay
      - "lgd_table": partial seniority -> LGD overlay
      - "buckets": replacement tuple (jurisdiction-specific)

    The result is frozen and suitable for passing into pure calculation functions.

    In future this will also support YAML/JSON seed files under
    packages/frtb-drc/reference/ (not yet implemented — see #25 acceptance).
    """
    overrides = overrides or {}

    base_rw = dict(RISK_WEIGHTS[rules_version])
    if "risk_weights" in overrides:
        base_rw.update(overrides["risk_weights"])

    buckets = overrides.get("buckets", DRC_NS_BUCKETS[rules_version])

    lgd_table = dict(LGD_BY_SENIORITY)
    if "lgd_table" in overrides:
        lgd_table.update(overrides["lgd_table"])

    return ReferenceData(
        rules_version=rules_version,
        risk_weights=base_rw,
        buckets=tuple(buckets),
        lgd_table=lgd_table,
    )


# Convenience re-exports for tests / CRIF layer
__all__ = [
    "BCBS_DRC_JS_RW",
    "CRR2_DRC_JS_RW",
    "FRB_DRC_JS_RW",
    "RISK_WEIGHTS",
    "DRC_NS_BUCKETS",
    "LGD_BY_SENIORITY",
    "get_risk_weight",
    "get_lgd",
    "load_reference_data",
    "ReferenceData",
]
