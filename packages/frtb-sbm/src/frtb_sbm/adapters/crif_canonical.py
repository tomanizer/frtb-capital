"""Canonical field mapping rules for SBM CRIF row adapters."""

from __future__ import annotations

from frtb_sbm.adapters.crif_constants import _CSR_RISK_CLASSES
from frtb_sbm.adapters.crif_models import SbmAdapterWarning
from frtb_sbm.csr_nonsec_reference_data import CSR_BOND_RISK_FACTOR, CSR_CDS_RISK_FACTOR
from frtb_sbm.csr_sec_nonctp_reference_data import CSR_SEC_BOND_RISK_FACTOR, CSR_SEC_CDS_RISK_FACTOR
from frtb_sbm.data_models import SbmRiskClass, SbmRiskMeasure
from frtb_sbm.equity_reference_data import EQUITY_REPO_RISK_FACTOR, EQUITY_SPOT_RISK_FACTOR
from frtb_sbm.validation import SbmInputError


def _canonical_risk_factor(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    *,
    risk_factor_hint: str | None,
    risk_factor_hint_source: str | None,
    crif_qualifier: str | None,
    crif_qualifier_source: str | None,
    bucket_hint: str | None,
    bucket_hint_source: str | None,
    amount_currency: str,
    amount_currency_source: str | None,
    label2: str | None,
    label2_source: str | None,
) -> tuple[str, str | None]:
    if risk_class is SbmRiskClass.GIRR:
        value = risk_factor_hint or crif_qualifier or amount_currency
        source = risk_factor_hint_source or crif_qualifier_source or amount_currency_source
        normalised = value.strip().upper()
        if risk_measure is SbmRiskMeasure.CURVATURE and normalised in {"INFL", "XCCY"}:
            raise SbmInputError(
                "GIRR curvature has no capital requirement for inflation or "
                "cross-currency basis risk factors (MAR21.8(5)(b))",
                field=source or "RiskFactor",
            )
        return normalised, source
    if risk_class is SbmRiskClass.FX:
        fx_value = risk_factor_hint or crif_qualifier or bucket_hint
        source = risk_factor_hint_source or crif_qualifier_source or bucket_hint_source
        if not fx_value:
            raise SbmInputError(
                "FX CRIF rows require currency in RiskFactor, Qualifier, or Bucket",
                field="RiskFactor",
            )
        return fx_value.strip().upper(), source
    if risk_class is SbmRiskClass.EQUITY:
        value = risk_factor_hint or EQUITY_SPOT_RISK_FACTOR
        source = risk_factor_hint_source or "RiskType"
        normalised = value.strip().upper()
        if normalised not in {EQUITY_SPOT_RISK_FACTOR, EQUITY_REPO_RISK_FACTOR}:
            raise SbmInputError(
                "equity CRIF RiskFactor must be SPOT or REPO",
                field=risk_factor_hint_source or "RiskFactor",
            )
        if risk_measure is not SbmRiskMeasure.DELTA and normalised == EQUITY_REPO_RISK_FACTOR:
            raise SbmInputError(
                "equity vega and curvature have no capital requirement for "
                "equity repo rates (MAR21.12(2)(b), MAR21.12(3))",
                field=risk_factor_hint_source or "RiskFactor",
            )
        return normalised, source
    if risk_class is SbmRiskClass.COMMODITY:
        commodity_value = risk_factor_hint or crif_qualifier
        source = risk_factor_hint_source or crif_qualifier_source
        if not commodity_value:
            raise SbmInputError(
                "commodity CRIF rows require RiskFactor or Qualifier",
                field="RiskFactor",
            )
        return commodity_value.strip(), source
    if risk_class in _CSR_RISK_CLASSES:
        csr_value = risk_factor_hint
        source = risk_factor_hint_source
        if csr_value is None and label2 is not None and _is_csr_basis(risk_class, label2):
            csr_value = label2
            source = label2_source
        if csr_value is None:
            raise SbmInputError(
                "CSR CRIF rows require RiskFactor or Label2 set to BOND or CDS",
                field="RiskFactor",
            )
        normalised = csr_value.strip().upper()
        if not _is_csr_basis(risk_class, normalised):
            raise SbmInputError(
                "CSR CRIF RiskFactor must be BOND or CDS",
                field=source or "RiskFactor",
            )
        return normalised, source
    raise SbmInputError(
        f"unsupported CRIF risk class {risk_class.value!r}",
        field="RiskType",
    )


def _canonical_bucket(
    risk_class: SbmRiskClass,
    *,
    bucket_hint: str | None,
    bucket_hint_source: str | None,
    risk_factor: str,
    risk_factor_source: str | None,
) -> tuple[str, str | None]:
    if bucket_hint:
        bucket = bucket_hint.strip()
        if risk_class is SbmRiskClass.FX:
            bucket = bucket.upper()
        return bucket, bucket_hint_source
    if risk_class is SbmRiskClass.GIRR:
        return "1", "RiskType"
    if risk_class is SbmRiskClass.FX:
        return risk_factor.strip().upper(), risk_factor_source
    raise SbmInputError(
        f"{risk_class.value} CRIF rows require Bucket",
        field="Bucket",
    )


def _canonical_qualifier(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    *,
    risk_factor_hint: str | None,
    crif_qualifier: str | None,
    crif_qualifier_source: str | None,
    location: str | None,
    location_source: str | None,
) -> tuple[str | None, str | None]:
    if risk_class in {SbmRiskClass.GIRR, SbmRiskClass.FX}:
        return None, None
    if risk_class in {SbmRiskClass.EQUITY, *_CSR_RISK_CLASSES}:
        return crif_qualifier, crif_qualifier_source
    if risk_class is SbmRiskClass.COMMODITY:
        if location:
            return location, location_source
        if risk_measure is SbmRiskMeasure.VEGA and risk_factor_hint and crif_qualifier is None:
            return None, None
        return crif_qualifier, crif_qualifier_source
    return crif_qualifier, crif_qualifier_source


def _canonical_tenor(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    *,
    label1: str | None,
    label1_source: str | None,
    label2: str | None,
    label2_source: str | None,
    underlying_tenor_hint: str | None,
    underlying_tenor_hint_source: str | None,
) -> tuple[str | None, str | None]:
    if underlying_tenor_hint:
        return underlying_tenor_hint, underlying_tenor_hint_source
    if risk_measure is SbmRiskMeasure.VEGA:
        if risk_class is SbmRiskClass.GIRR:
            return label2, label2_source
        return None, None
    if risk_measure is SbmRiskMeasure.DELTA and risk_class in {
        SbmRiskClass.GIRR,
        SbmRiskClass.COMMODITY,
        *_CSR_RISK_CLASSES,
    }:
        return label1, label1_source
    if risk_measure is SbmRiskMeasure.CURVATURE and risk_class is SbmRiskClass.GIRR:
        if label2:
            return label2, label2_source
        return label1, label1_source
    return None, None


def _canonical_option_tenor(
    risk_measure: SbmRiskMeasure,
    *,
    label1: str | None,
    label1_source: str | None,
    option_tenor_hint: str | None,
    option_tenor_hint_source: str | None,
) -> tuple[str | None, str | None]:
    if risk_measure is not SbmRiskMeasure.VEGA:
        return None, None
    if option_tenor_hint:
        return option_tenor_hint, option_tenor_hint_source
    return label1, label1_source


def _is_csr_basis(risk_class: SbmRiskClass, value: str) -> bool:
    normalised = value.strip().upper()
    if risk_class in {SbmRiskClass.CSR_NONSEC, SbmRiskClass.CSR_SEC_CTP}:
        return normalised in {CSR_BOND_RISK_FACTOR, CSR_CDS_RISK_FACTOR}
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return normalised in {CSR_SEC_BOND_RISK_FACTOR, CSR_SEC_CDS_RISK_FACTOR}
    return False


def _append_inference_warnings(
    warnings: list[SbmAdapterWarning],
    *,
    source_row_id: str,
    risk_class: SbmRiskClass,
    bucket_hint: str | None,
    risk_factor_hint: str | None,
    risk_factor_source: str | None,
    label2_source: str | None,
) -> None:
    if risk_class is SbmRiskClass.FX and bucket_hint is None:
        warnings.append(
            SbmAdapterWarning(
                source_row_id=source_row_id,
                field="Bucket",
                message="FX bucket inferred from mapped currency",
            )
        )
    if risk_class is SbmRiskClass.EQUITY and risk_factor_hint is None:
        warnings.append(
            SbmAdapterWarning(
                source_row_id=source_row_id,
                field="RiskFactor",
                message="equity risk_factor defaulted to SPOT from CRIF risk type",
            )
        )
    if (
        risk_class in _CSR_RISK_CLASSES
        and risk_factor_hint is None
        and risk_factor_source == label2_source
    ):
        warnings.append(
            SbmAdapterWarning(
                source_row_id=source_row_id,
                field="RiskFactor",
                message="CSR basis risk_factor inferred from Label2",
            )
        )
