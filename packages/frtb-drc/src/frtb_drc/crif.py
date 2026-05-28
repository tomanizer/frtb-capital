"""
CRIF column mapping for DRC (Issue #28).

Matches the reference reconstruction (drc_crif_mapping.py) exactly for
column rename compatibility with ISDA CRIF feeds.

Regulatory: ISDA CRIF v2+ DRC fields (RiskType, Qualifier, Label2=Seniority,
CreditQuality, LongShortInd, CoveredBondInd, etc.).
"""

from __future__ import annotations

from frtb_drc.data_models import RiskClassDRC

# CRIF column names (ISDA standard)
SENSITIVITY_ID = "Sensitivity ID"
RISK_TYPE = "RiskType"
QUALIFIER = "Qualifier"
BUCKET = "Bucket"
LABEL_1 = "Label1"
LABEL_2 = "Label2"
AMOUNT = "Amount"
AMOUNT_USD = "AmountUSD"
CREDIT_QUALITY = "CreditQuality"
LONG_SHORT_INDICATOR = "LongShortInd"
COVERED_BOND_INDICATOR = "CoveredBondInd"

# Internal canonical names (used in Position etc.)
ISSUER_ID = "issuer_id"
FRTB_BUCKET_NAME = "FRTB_Bucket_Name"
INSTRUMENT_SENIORITY = "Instrument_Seniority"
LONG_SHORT = "Long_Short_Indicator"

DRC_NONSEC_MAPPING: dict[str, str] = {
    QUALIFIER: ISSUER_ID,
    BUCKET: FRTB_BUCKET_NAME,
    LABEL_2: INSTRUMENT_SENIORITY,
    CREDIT_QUALITY: "credit_quality",
    LONG_SHORT_INDICATOR: LONG_SHORT,
    COVERED_BOND_INDICATOR: "covered_bond_flag",
}

DRC_SEC_CTP_MAPPING: dict[str, str] = {
    BUCKET: FRTB_BUCKET_NAME,
    QUALIFIER: ISSUER_ID,
    LABEL_1: "tranche",
    CREDIT_QUALITY: "credit_quality",
    LONG_SHORT_INDICATOR: LONG_SHORT,
}

CRIF_MAPPING: dict[RiskClassDRC, dict[str, str]] = {
    RiskClassDRC.NONSEC: DRC_NONSEC_MAPPING,
    RiskClassDRC.SEC_CTP: DRC_SEC_CTP_MAPPING,
    RiskClassDRC.SEC_NCTP: DRC_NONSEC_MAPPING,  # similar for now
}


def get_rename_cols(risk_class: RiskClassDRC) -> dict[str, str]:
    """Return clean CRIF -> internal rename dict (no spaces or dots allowed in values)."""
    mapping = CRIF_MAPPING.get(risk_class, {})
    clean = {}
    for k, v in mapping.items():
        if v is None:
            continue
        if " " in v or "." in v:
            raise ValueError(f"Internal column name {v!r} must not contain space or dot")
        clean[k] = v
    return clean
