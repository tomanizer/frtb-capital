from __future__ import annotations

from typing import cast

import pytest
from frtb_cva import (
    CvaRegulatoryProfile,
    CvaSourceLineage,
    SaCvaIndexTreatment,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
    build_sa_cva_sensitivity_batch_from_sensitivities,
)
from frtb_cva._batch_contracts import CvaHedgeBatch
from frtb_cva._sa_batch_weighting import _compute_weighted_sensitivities_from_batch
from frtb_cva.sa_cva import SA_CVA_PATH_REGISTRY, calculate_sa_cva_capital
from frtb_cva.validation import CvaInputError
from frtb_cva.weighted_sensitivity import (
    SA_CVA_WEIGHTING_REGISTRY,
    compute_weighted_sensitivities,
)

_SUPPORTED_PATHS = {
    (SaCvaRiskClass.GIRR, SaCvaRiskMeasure.DELTA),
    (SaCvaRiskClass.GIRR, SaCvaRiskMeasure.VEGA),
    (SaCvaRiskClass.FX, SaCvaRiskMeasure.DELTA),
    (SaCvaRiskClass.FX, SaCvaRiskMeasure.VEGA),
    (SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD, SaCvaRiskMeasure.DELTA),
    (SaCvaRiskClass.REFERENCE_CREDIT_SPREAD, SaCvaRiskMeasure.DELTA),
    (SaCvaRiskClass.REFERENCE_CREDIT_SPREAD, SaCvaRiskMeasure.VEGA),
    (SaCvaRiskClass.EQUITY, SaCvaRiskMeasure.DELTA),
    (SaCvaRiskClass.EQUITY, SaCvaRiskMeasure.VEGA),
    (SaCvaRiskClass.COMMODITY, SaCvaRiskMeasure.DELTA),
    (SaCvaRiskClass.COMMODITY, SaCvaRiskMeasure.VEGA),
}
_UNSUPPORTED_PATHS = {
    (SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD, SaCvaRiskMeasure.VEGA),
}
_ALL_REGISTRY_PATHS = _SUPPORTED_PATHS | _UNSUPPORTED_PATHS


def _lineage(row_id: str) -> CvaSourceLineage:
    return CvaSourceLineage(
        source_system="synthetic",
        source_file="sensitivities.csv",
        source_row_id=row_id,
    )


def _sensitivity(
    sensitivity_id: str,
    risk_class: SaCvaRiskClass,
    risk_measure: SaCvaRiskMeasure,
    bucket_id: str,
    risk_factor_key: str,
    *,
    tenor: str | None = None,
    volatility_input: float | None = None,
    index_treatment: SaCvaIndexTreatment | None = None,
) -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id=sensitivity_id,
        risk_class=risk_class,
        risk_measure=risk_measure,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id=bucket_id,
        risk_factor_key=risk_factor_key,
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id=f"row-{sensitivity_id}",
        tenor=tenor,
        volatility_input=volatility_input,
        index_treatment=index_treatment,
        lineage=_lineage(f"row-{sensitivity_id}"),
    )


def test_sa_cva_registries_cover_supported_and_explicit_unsupported_paths() -> None:
    assert set(SA_CVA_WEIGHTING_REGISTRY) == _ALL_REGISTRY_PATHS
    assert set(SA_CVA_PATH_REGISTRY) == _ALL_REGISTRY_PATHS

    for key in _SUPPORTED_PATHS:
        assert SA_CVA_WEIGHTING_REGISTRY[key].weight_fn is not None
        assert SA_CVA_PATH_REGISTRY[key].capital_fn is not None
        assert SA_CVA_WEIGHTING_REGISTRY[key].unsupported_message is None
        assert SA_CVA_PATH_REGISTRY[key].unsupported_message is None

    for key in _UNSUPPORTED_PATHS:
        assert SA_CVA_WEIGHTING_REGISTRY[key].weight_fn is None
        assert SA_CVA_PATH_REGISTRY[key].capital_fn is None
        assert "CCS vega" in (SA_CVA_WEIGHTING_REGISTRY[key].unsupported_message or "")
        assert "CCS vega" in (SA_CVA_PATH_REGISTRY[key].unsupported_message or "")


def test_batch_and_row_weighting_use_same_registry_dispatch() -> None:
    sensitivity = _sensitivity(
        "sens-fx-delta",
        SaCvaRiskClass.FX,
        SaCvaRiskMeasure.DELTA,
        "EUR",
        "EUR",
    )
    batch = build_sa_cva_sensitivity_batch_from_sensitivities((sensitivity,))

    row_weighted = compute_weighted_sensitivities((sensitivity,), reporting_currency="USD")
    batch_weighted = _compute_weighted_sensitivities_from_batch(
        batch,
        [0],
        hedge_batch=cast(CvaHedgeBatch, None),
        eligible_hedge_ids=frozenset(),
        reporting_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
    )

    assert batch_weighted == row_weighted


def test_ccs_vega_fails_closed_through_registries() -> None:
    sensitivity = _sensitivity(
        "sens-ccs-vega",
        SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        SaCvaRiskMeasure.VEGA,
        "1",
        "ISSUER|INVESTMENT_GRADE",
        tenor="5y",
        volatility_input=0.4,
    )

    with pytest.raises(CvaInputError, match="CCS vega capital is not permitted"):
        compute_weighted_sensitivities((sensitivity,))
    with pytest.raises(CvaInputError, match="CCS vega capital is not permitted"):
        calculate_sa_cva_capital((sensitivity,))
