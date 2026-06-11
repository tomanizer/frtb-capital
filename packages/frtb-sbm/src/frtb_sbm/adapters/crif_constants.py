"""CRIF field aliases and risk-type routing constants for SBM adapters."""

from __future__ import annotations

from frtb_common import (
    CRIF_SOURCE_ROW_ID_COLUMN,
    CrifColumnSpec,
    CrifRiskTypeMapping,
    TabularLogicalType,
)

from frtb_sbm.data_models import SbmRiskClass, SbmRiskMeasure
from frtb_sbm.validation import SbmInputError

_CRIF_GIRR_DELTA = frozenset({"RISK_IRCURVE", "IR_CURVE", "GIRR_DELTA"})
_CRIF_GIRR_VEGA = frozenset({"RISK_IRVOL", "IR_VOL", "GIRR_VEGA"})
_CRIF_GIRR_CURVATURE = frozenset(
    {"RISK_IRCURVECURVATURE", "RISK_IRCURVE_CURVATURE", "IR_CURVATURE", "GIRR_CURVATURE"}
)
_CRIF_FX_DELTA = frozenset({"RISK_FX", "FX_DELTA"})
_CRIF_FX_VEGA = frozenset({"RISK_FXVOL", "RISK_FX_VOL", "FX_VOL", "FX_VEGA"})
_CRIF_FX_CURVATURE = frozenset({"RISK_FXCURVATURE", "RISK_FX_CURVATURE", "FX_CURVATURE"})
_CRIF_EQUITY_DELTA = frozenset({"RISK_EQ", "RISK_EQUITY", "EQ_DELTA", "EQUITY_DELTA"})
_CRIF_EQUITY_VEGA = frozenset(
    {
        "RISK_EQVOL",
        "RISK_EQ_VOL",
        "RISK_EQUITYVOL",
        "RISK_EQUITY_VOL",
        "EQ_VOL",
        "EQ_VEGA",
        "EQUITY_VEGA",
    }
)
_CRIF_EQUITY_CURVATURE = frozenset(
    {
        "RISK_EQCURVATURE",
        "RISK_EQ_CURVATURE",
        "RISK_EQUITYCURVATURE",
        "RISK_EQUITY_CURVATURE",
        "EQ_CURVATURE",
        "EQUITY_CURVATURE",
    }
)
_CRIF_COMMODITY_DELTA = frozenset({"RISK_CM", "RISK_COMMODITY", "CM_DELTA", "COMMODITY_DELTA"})
_CRIF_COMMODITY_VEGA = frozenset(
    {
        "RISK_CMVOL",
        "RISK_CM_VOL",
        "RISK_COMMODITYVOL",
        "RISK_COMMODITY_VOL",
        "CM_VOL",
        "CM_VEGA",
        "COMMODITY_VEGA",
    }
)
_CRIF_COMMODITY_CURVATURE = frozenset(
    {
        "RISK_CMCURVATURE",
        "RISK_CM_CURVATURE",
        "RISK_COMMODITYCURVATURE",
        "RISK_COMMODITY_CURVATURE",
        "CM_CURVATURE",
        "COMMODITY_CURVATURE",
    }
)
_CRIF_CSR_NONSEC_DELTA = frozenset({"RISK_CSRNONSEC", "RISK_CREDIT_NONSEC", "CSR_NONSEC_DELTA"})
_CRIF_CSR_NONSEC_VEGA = frozenset(
    {
        "RISK_CSRNONSECVOL",
        "RISK_CSRNONSEC_VOL",
        "RISK_CREDIT_NONSECVOL",
        "RISK_CREDIT_NONSEC_VOL",
        "CSR_NONSEC_VEGA",
    }
)
_CRIF_CSR_NONSEC_CURVATURE = frozenset(
    {
        "RISK_CSRNONSECCURVATURE",
        "RISK_CSRNONSEC_CURVATURE",
        "RISK_CREDIT_NONSECCURVATURE",
        "RISK_CREDIT_NONSEC_CURVATURE",
        "CSR_NONSEC_CURVATURE",
    }
)
_CRIF_CSR_SEC_NONCTP_DELTA = frozenset(
    {"RISK_CSRSECNONCTP", "RISK_CREDIT_SEC_NONCTP", "CSR_SEC_NONCTP_DELTA"}
)
_CRIF_CSR_SEC_NONCTP_VEGA = frozenset(
    {
        "RISK_CSRSECNONCTPVOL",
        "RISK_CSRSECNONCTP_VOL",
        "RISK_CREDIT_SEC_NONCTPVOL",
        "RISK_CREDIT_SEC_NONCTP_VOL",
        "CSR_SEC_NONCTP_VEGA",
    }
)
_CRIF_CSR_SEC_NONCTP_CURVATURE = frozenset(
    {
        "RISK_CSRSECNONCTPCURVATURE",
        "RISK_CSRSECNONCTP_CURVATURE",
        "RISK_CREDIT_SEC_NONCTPCURVATURE",
        "RISK_CREDIT_SEC_NONCTP_CURVATURE",
        "CSR_SEC_NONCTP_CURVATURE",
    }
)
_CRIF_CSR_SEC_CTP_DELTA = frozenset({"RISK_CSRSECCTP", "RISK_CREDIT_SEC_CTP", "CSR_SEC_CTP_DELTA"})
_CRIF_CSR_SEC_CTP_VEGA = frozenset(
    {
        "RISK_CSRSECCTPVOL",
        "RISK_CSRSECCTP_VOL",
        "RISK_CREDIT_SEC_CTPVOL",
        "RISK_CREDIT_SEC_CTP_VOL",
        "CSR_SEC_CTP_VEGA",
    }
)
_CRIF_CSR_SEC_CTP_CURVATURE = frozenset(
    {
        "RISK_CSRSECCTPCURVATURE",
        "RISK_CSRSECCTP_CURVATURE",
        "RISK_CREDIT_SEC_CTPCURVATURE",
        "RISK_CREDIT_SEC_CTP_CURVATURE",
        "CSR_SEC_CTP_CURVATURE",
    }
)

_SENSITIVITY_ID_FIELDS = ("SensitivityId", "Sensitivity ID", "sensitivity_id", "TradeId", "TradeID")
_SOURCE_ROW_ID_FIELDS = ("RowId", "RowID", "source_row_id")
_RISK_TYPE_FIELDS = ("RiskType", "risk_type", "RiskClass")
_QUALIFIER_FIELDS = ("Qualifier", "qualifier")
_BUCKET_FIELDS = ("Bucket", "bucket")
_LABEL1_FIELDS = ("Label1", "label1", "Tenor", "tenor")
_LABEL2_FIELDS = ("Label2", "label2")
_RISK_FACTOR_FIELDS = (
    "RiskFactor",
    "Risk Factor",
    "risk_factor",
    "Underlying",
    "UnderlyingName",
    "Name",
)
_LOCATION_FIELDS = ("Location", "location", "DeliveryLocation", "delivery_location")
_OPTION_TENOR_FIELDS = ("OptionTenor", "Option Tenor", "option_tenor", "OptionMaturity")
_UNDERLYING_TENOR_FIELDS = ("UnderlyingTenor", "Underlying Tenor", "underlying_tenor")
_AMOUNT_FIELDS = ("Amount", "amount", "AmountUSD", "AmountUsd")
_AMOUNT_CCY_FIELDS = ("AmountCurrency", "amount_currency", "Currency", "currency")
_UP_SHOCK_FIELDS = ("CvrUp", "UpShock", "up_shock_amount")
_DOWN_SHOCK_FIELDS = ("CvrDown", "DownShock", "down_shock_amount")
_DESK_FIELDS = ("DeskId", "DeskID", "desk_id", "Desk")
_LEGAL_ENTITY_FIELDS = ("LegalEntity", "LegalEntityID", "legal_entity", "Entity")

_GIRR_DELTA_CRIF_COLUMN_SPECS: tuple[CrifColumnSpec, ...] = (
    CrifColumnSpec("sensitivity_id", aliases=_SENSITIVITY_ID_FIELDS),
    CrifColumnSpec(CRIF_SOURCE_ROW_ID_COLUMN, aliases=_SOURCE_ROW_ID_FIELDS),
    CrifColumnSpec("risk_type", aliases=_RISK_TYPE_FIELDS, required=True),
    CrifColumnSpec("qualifier", aliases=_QUALIFIER_FIELDS),
    CrifColumnSpec("bucket", aliases=_BUCKET_FIELDS),
    CrifColumnSpec("label1", aliases=_LABEL1_FIELDS),
    CrifColumnSpec(
        "amount",
        aliases=_AMOUNT_FIELDS,
        logical_type=TabularLogicalType.FLOAT,
        required=True,
    ),
    CrifColumnSpec("amount_currency", aliases=_AMOUNT_CCY_FIELDS),
    CrifColumnSpec("desk_id", aliases=_DESK_FIELDS),
    CrifColumnSpec("legal_entity", aliases=_LEGAL_ENTITY_FIELDS),
)
_GIRR_DELTA_CRIF_RISK_TYPE_MAPPINGS: tuple[CrifRiskTypeMapping, ...] = (
    CrifRiskTypeMapping(
        tuple(sorted(_CRIF_GIRR_DELTA)),
        {
            "risk_class": SbmRiskClass.GIRR.value,
            "risk_measure": SbmRiskMeasure.DELTA.value,
        },
    ),
)


_CSR_RISK_CLASSES = frozenset(
    {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskClass.CSR_SEC_CTP,
    }
)


def _map_risk_type(risk_type: str) -> tuple[SbmRiskClass, SbmRiskMeasure]:
    normalised = risk_type.strip().upper()
    if normalised in _CRIF_GIRR_DELTA:
        return SbmRiskClass.GIRR, SbmRiskMeasure.DELTA
    if normalised in _CRIF_GIRR_VEGA:
        return SbmRiskClass.GIRR, SbmRiskMeasure.VEGA
    if normalised in _CRIF_GIRR_CURVATURE:
        return SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE
    if normalised in _CRIF_FX_DELTA:
        return SbmRiskClass.FX, SbmRiskMeasure.DELTA
    if normalised in _CRIF_FX_VEGA:
        return SbmRiskClass.FX, SbmRiskMeasure.VEGA
    if normalised in _CRIF_FX_CURVATURE:
        return SbmRiskClass.FX, SbmRiskMeasure.CURVATURE
    if normalised in _CRIF_EQUITY_DELTA:
        return SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA
    if normalised in _CRIF_EQUITY_VEGA:
        return SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA
    if normalised in _CRIF_EQUITY_CURVATURE:
        return SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE
    if normalised in _CRIF_COMMODITY_DELTA:
        return SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA
    if normalised in _CRIF_COMMODITY_VEGA:
        return SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA
    if normalised in _CRIF_COMMODITY_CURVATURE:
        return SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE
    if normalised in _CRIF_CSR_NONSEC_DELTA:
        return SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA
    if normalised in _CRIF_CSR_NONSEC_VEGA:
        return SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA
    if normalised in _CRIF_CSR_NONSEC_CURVATURE:
        return SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE
    if normalised in _CRIF_CSR_SEC_NONCTP_DELTA:
        return SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA
    if normalised in _CRIF_CSR_SEC_NONCTP_VEGA:
        return SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.VEGA
    if normalised in _CRIF_CSR_SEC_NONCTP_CURVATURE:
        return SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.CURVATURE
    if normalised in _CRIF_CSR_SEC_CTP_DELTA:
        return SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA
    if normalised in _CRIF_CSR_SEC_CTP_VEGA:
        return SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.VEGA
    if normalised in _CRIF_CSR_SEC_CTP_CURVATURE:
        return SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.CURVATURE
    raise SbmInputError(
        f"unsupported CRIF RiskType {normalised!r}",
        field="RiskType",
    )
