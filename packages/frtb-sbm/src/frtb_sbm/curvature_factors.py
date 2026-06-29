"""Curvature factor records and row-wise factor key helpers.

Regulatory traceability:
    Basel MAR21.5, MAR21.96-MAR21.99, and SBM-CURV-001.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm._citations import merge_citation_ids as _merge_citation_ids
from frtb_sbm.data_models import SbmRiskClass, SbmSensitivity
from frtb_sbm.equity_reference_data import EQUITY_SPOT_RISK_FACTOR
from frtb_sbm.reference_citation_routing import profile_citation_id, profile_citation_ids
from frtb_sbm.reference_data import curvature_citation_ids, normalise_fx_delta_currency_code
from frtb_sbm.validation import SbmInputError, normalise_sensitivity_amount

FX_CURVATURE_SCALAR_1_5_FLAG = "fx_curvature_scalar_1_5"


@dataclass(frozen=True)
class _CurvatureFactor:
    risk_class: SbmRiskClass
    bucket_id: str
    factor_id: str
    risk_factor: str
    qualifier: str | None
    tenor: str | None
    up_cvr: float
    down_cvr: float
    sensitivity_ids: tuple[str, ...]
    source_row_ids: tuple[str, ...]
    citation_ids: tuple[str, ...]


def _curvature_factor_key(sensitivity: SbmSensitivity) -> tuple[str, ...]:
    risk_class = sensitivity.risk_class
    bucket = sensitivity.bucket
    risk_factor = sensitivity.risk_factor.strip()
    qualifier = sensitivity.qualifier.strip() if sensitivity.qualifier else ""
    if risk_class is SbmRiskClass.GIRR:
        return (bucket, risk_factor)
    if risk_class is SbmRiskClass.FX:
        currency = normalise_fx_delta_currency_code(risk_factor)
        return (currency, currency)
    if risk_class is SbmRiskClass.EQUITY:
        return (bucket, EQUITY_SPOT_RISK_FACTOR, qualifier)
    if risk_class is SbmRiskClass.COMMODITY:
        return (bucket, risk_factor, qualifier)
    if risk_class in {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskClass.CSR_SEC_NONCTP,
    }:
        return (bucket, qualifier)
    return (bucket, risk_factor, qualifier)


def _curvature_factor_risk_factor(
    risk_class: SbmRiskClass,
    key: tuple[str, ...],
    sensitivity: SbmSensitivity,
) -> str:
    if risk_class is SbmRiskClass.GIRR:
        return key[1]
    if risk_class is SbmRiskClass.FX:
        return key[1]
    if risk_class is SbmRiskClass.EQUITY:
        return EQUITY_SPOT_RISK_FACTOR
    if risk_class is SbmRiskClass.COMMODITY:
        return key[1]
    if risk_class in {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskClass.CSR_SEC_NONCTP,
    }:
        del sensitivity
        return "CREDIT_SPREAD_CURVE"
    return sensitivity.risk_factor


def _curvature_factor_qualifier(
    risk_class: SbmRiskClass,
    key: tuple[str, ...],
    sensitivity: SbmSensitivity,
) -> str | None:
    if risk_class is SbmRiskClass.EQUITY:
        return key[2]
    if risk_class is SbmRiskClass.COMMODITY:
        return key[2]
    if risk_class in {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskClass.CSR_SEC_NONCTP,
    }:
        return key[1]
    return sensitivity.qualifier


def _curvature_factor_citation_ids(
    profile_id: str,
    *,
    risk_class: SbmRiskClass,
    bucket_id: str,
    risk_factor: str,
) -> tuple[str, ...]:
    del bucket_id, risk_factor
    return _merge_citation_ids(
        curvature_citation_ids(profile_id),
        _curvature_definition_citation_ids(profile_id, risk_class),
        _curvature_weight_rule_citation_ids(profile_id, risk_class),
    )


def _curvature_definition_citation_ids(
    profile_id: str,
    risk_class: SbmRiskClass,
) -> tuple[str, ...]:
    if risk_class is SbmRiskClass.GIRR:
        return profile_citation_ids(
            profile_id,
            ("basel_mar21_8", "basel_mar21_96", "basel_mar21_97"),
        )
    if risk_class is SbmRiskClass.FX:
        return profile_citation_ids(
            profile_id,
            ("basel_mar21_14", "basel_mar21_96", "basel_mar21_97"),
        )
    if risk_class is SbmRiskClass.EQUITY:
        return profile_citation_ids(
            profile_id,
            ("basel_mar21_12", "basel_mar21_96", "basel_mar21_97"),
        )
    if risk_class is SbmRiskClass.COMMODITY:
        return profile_citation_ids(
            profile_id,
            ("basel_mar21_13", "basel_mar21_96", "basel_mar21_97"),
        )
    if risk_class is SbmRiskClass.CSR_NONSEC:
        return profile_citation_ids(
            profile_id,
            ("basel_mar21_9", "basel_mar21_96", "basel_mar21_97"),
        )
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        return profile_citation_ids(
            profile_id,
            ("basel_mar21_11", "basel_mar21_96", "basel_mar21_97"),
        )
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return profile_citation_ids(
            profile_id,
            ("basel_mar21_10", "basel_mar21_96", "basel_mar21_97"),
        )
    return profile_citation_ids(profile_id, ("basel_mar21_96", "basel_mar21_97"))


def _curvature_weight_rule_citation_ids(
    profile_id: str,
    risk_class: SbmRiskClass,
) -> tuple[str, ...]:
    if risk_class is SbmRiskClass.GIRR:
        return profile_citation_ids(profile_id, ("basel_mar21_99", "basel_mar21_39"))
    if risk_class is SbmRiskClass.FX:
        return profile_citation_ids(
            profile_id,
            ("basel_mar21_98", "basel_mar21_87", "basel_mar21_88"),
        )
    if risk_class is SbmRiskClass.EQUITY:
        return profile_citation_ids(profile_id, ("basel_mar21_98", "basel_mar21_77"))
    if risk_class is SbmRiskClass.COMMODITY:
        return profile_citation_ids(profile_id, ("basel_mar21_99", "basel_mar21_82"))
    if risk_class is SbmRiskClass.CSR_NONSEC:
        return profile_citation_ids(profile_id, ("basel_mar21_99", "basel_mar21_53"))
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        return profile_citation_ids(profile_id, ("basel_mar21_99", "basel_mar21_59"))
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return profile_citation_ids(
            profile_id,
            ("basel_mar21_99", "basel_mar21_65", "basel_mar21_66"),
        )
    return (profile_citation_id(profile_id, "basel_mar21_99"),)


def _required_curvature_shock(sensitivity: SbmSensitivity, *, field: str) -> float:
    value = (
        sensitivity.up_shock_amount if field == "up_shock_amount" else sensitivity.down_shock_amount
    )
    if value is None:
        raise SbmInputError(
            "curvature inputs require up_shock_amount and down_shock_amount",
            field=field,
            sensitivity_id=sensitivity.sensitivity_id,
        )
    return normalise_sensitivity_amount(value, sensitivity_id=sensitivity.sensitivity_id)


def _scaled_curvature_shock(sensitivity: SbmSensitivity, *, field: str) -> float:
    shock = _required_curvature_shock(sensitivity, field=field)
    if (
        sensitivity.risk_class is SbmRiskClass.FX
        and FX_CURVATURE_SCALAR_1_5_FLAG in sensitivity.mapping_citation_ids
    ):
        return shock / 1.5
    return shock


def _validate_fx_curvature_scalar_flag(
    sensitivity: SbmSensitivity,
    *,
    reporting_currency: str,
) -> None:
    if FX_CURVATURE_SCALAR_1_5_FLAG not in sensitivity.mapping_citation_ids:
        return
    qualifier = sensitivity.qualifier.strip().upper() if sensitivity.qualifier else ""
    if qualifier:
        tokens = tuple(
            token for token in qualifier.replace("/", " ").replace("-", " ").split() if token
        )
        if len(tokens) == 2 and all(len(token) == 3 and token.isalpha() for token in tokens):
            if reporting_currency in tokens:
                raise UnsupportedRegulatoryFeatureError(
                    "FX curvature MAR21.98 scalar applies only when the option does not "
                    "reference the reporting currency"
                )
            return
    raise UnsupportedRegulatoryFeatureError(
        "FX curvature MAR21.98 scalar requires a two-currency qualifier such as "
        "'EUR/GBP' so audit evidence identifies the non-reporting-currency pair"
    )


__all__ = [
    "FX_CURVATURE_SCALAR_1_5_FLAG",
    "_CurvatureFactor",
    "_curvature_factor_citation_ids",
    "_curvature_factor_key",
    "_curvature_factor_qualifier",
    "_curvature_factor_risk_factor",
    "_required_curvature_shock",
    "_scaled_curvature_shock",
    "_validate_fx_curvature_scalar_flag",
]
