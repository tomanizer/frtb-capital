from __future__ import annotations

import numpy as np
import pytest
from frtb_sbm import (
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    WeightedSensitivity,
)
from frtb_sbm.curvature import (
    _build_vectorized_curvature_intra_bucket_correlation_matrix,
    _curvature_intra_bucket_correlation,
    _CurvatureFactor,
)
from frtb_sbm.risk_classes.vega import (
    build_non_girr_vega_intra_bucket_correlation_matrix,
    non_girr_vega_intra_bucket_correlation,
)

PROFILE_ID = SbmRegulatoryProfile.BASEL_MAR21.value


@pytest.mark.parametrize(
    ("risk_class", "bucket_id", "risk_factors", "qualifiers", "option_tenors"),
    (
        (SbmRiskClass.FX, "EUR", ("EUR", "EUR", "EUR"), ("", "", ""), ("1y", "2y", "5y")),
        (
            SbmRiskClass.EQUITY,
            "5",
            ("SPOT", "SPOT", "SPOT"),
            ("ISS-A", "ISS-B", "ISS-A"),
            ("1y", "5y", "10y"),
        ),
        (
            SbmRiskClass.COMMODITY,
            "2",
            ("WTI", "BRENT", "WTI"),
            ("", "", ""),
            ("1y", "2y", "10y"),
        ),
        (
            SbmRiskClass.CSR_NONSEC,
            "17",
            ("BOND", "CDS", "BOND"),
            ("ISS-A", "ISS-B", "ISS-A"),
            ("1y", "5y", "10y"),
        ),
        (
            SbmRiskClass.CSR_SEC_NONCTP,
            "1",
            ("BOND", "CDS", "BOND"),
            ("TR-A", "TR-B", "TR-A"),
            ("1y", "5y", "10y"),
        ),
        (
            SbmRiskClass.CSR_SEC_CTP,
            "1",
            ("BOND", "CDS", "BOND"),
            ("NAME-A", "NAME-B", "NAME-A"),
            ("1y", "5y", "10y"),
        ),
    ),
)
def test_non_girr_vega_vectorized_matrix_matches_scalar_reference(
    risk_class: SbmRiskClass,
    bucket_id: str,
    risk_factors: tuple[str, ...],
    qualifiers: tuple[str, ...],
    option_tenors: tuple[str, ...],
) -> None:
    ordered = tuple(
        WeightedSensitivity(
            sensitivity_id=f"{risk_class.value.lower()}-{index}",
            risk_class=risk_class,
            risk_measure=SbmRiskMeasure.VEGA,
            bucket=bucket_id,
            raw_amount=100.0 + index,
            risk_weight=1.0,
            scaled_amount=100.0 + index,
            citation_ids=("basel_mar21_94",),
        )
        for index in range(len(risk_factors))
    )
    risk_factor_by_id = {
        sensitivity.sensitivity_id: risk_factors[index] for index, sensitivity in enumerate(ordered)
    }
    qualifier_by_id = {
        sensitivity.sensitivity_id: qualifiers[index]
        for index, sensitivity in enumerate(ordered)
        if qualifiers[index]
    }
    option_tenor_by_id = {
        sensitivity.sensitivity_id: option_tenors[index]
        for index, sensitivity in enumerate(ordered)
    }

    vectorized = build_non_girr_vega_intra_bucket_correlation_matrix(
        ordered,
        profile_id=PROFILE_ID,
        risk_class=risk_class,
        bucket_id=bucket_id,
        risk_factor_by_id=risk_factor_by_id,
        qualifier_by_id=qualifier_by_id,
        option_tenor_by_id=option_tenor_by_id,
    )
    scalar = _scalar_non_girr_vega_matrix(
        ordered,
        risk_class=risk_class,
        bucket_id=bucket_id,
        risk_factor_by_id=risk_factor_by_id,
        qualifier_by_id=qualifier_by_id,
        option_tenor_by_id=option_tenor_by_id,
    )

    assert np.array_equal(vectorized, scalar)


@pytest.mark.parametrize(
    ("risk_class", "bucket_id", "risk_factors", "qualifiers"),
    (
        (SbmRiskClass.GIRR, "1", ("USD", "EUR", "USD"), (None, None, None)),
        (SbmRiskClass.FX, "EUR", ("EUR", "EUR", "EUR"), (None, None, None)),
        (SbmRiskClass.EQUITY, "5", ("SPOT", "SPOT", "SPOT"), ("ISS-A", "ISS-B", "ISS-A")),
        (SbmRiskClass.EQUITY, "11", ("SPOT", "SPOT", "SPOT"), ("ISS-A", "ISS-B", "ISS-A")),
        (SbmRiskClass.COMMODITY, "2", ("WTI", "BRENT", "WTI"), ("NYMEX", "ICE", "NYMEX")),
        (
            SbmRiskClass.CSR_NONSEC,
            "17",
            ("CREDIT_SPREAD_CURVE", "CREDIT_SPREAD_CURVE", "CREDIT_SPREAD_CURVE"),
            ("ISS-A", "ISS-B", "ISS-A"),
        ),
        (
            SbmRiskClass.CSR_NONSEC,
            "16",
            ("CREDIT_SPREAD_CURVE", "CREDIT_SPREAD_CURVE", "CREDIT_SPREAD_CURVE"),
            ("ISS-A", "ISS-B", "ISS-A"),
        ),
        (
            SbmRiskClass.CSR_SEC_NONCTP,
            "1",
            ("CREDIT_SPREAD_CURVE", "CREDIT_SPREAD_CURVE", "CREDIT_SPREAD_CURVE"),
            ("TR-A", "TR-B", "TR-A"),
        ),
        (
            SbmRiskClass.CSR_SEC_NONCTP,
            "25",
            ("CREDIT_SPREAD_CURVE", "CREDIT_SPREAD_CURVE", "CREDIT_SPREAD_CURVE"),
            ("TR-A", "TR-B", "TR-A"),
        ),
        (
            SbmRiskClass.CSR_SEC_CTP,
            "1",
            ("CREDIT_SPREAD_CURVE", "CREDIT_SPREAD_CURVE", "CREDIT_SPREAD_CURVE"),
            ("NAME-A", "NAME-B", "NAME-A"),
        ),
    ),
)
def test_curvature_vectorized_matrix_matches_scalar_reference(
    risk_class: SbmRiskClass,
    bucket_id: str,
    risk_factors: tuple[str, ...],
    qualifiers: tuple[str | None, ...],
) -> None:
    factors = tuple(
        _curvature_factor(
            risk_class=risk_class,
            bucket_id=bucket_id,
            risk_factor=risk_factors[index],
            qualifier=qualifiers[index],
            index=index,
        )
        for index in range(len(risk_factors))
    )

    vectorized = _build_vectorized_curvature_intra_bucket_correlation_matrix(
        factors,
        profile_id=PROFILE_ID,
        risk_class=risk_class,
    )
    scalar = _scalar_curvature_matrix(factors, risk_class=risk_class)

    assert np.array_equal(vectorized, scalar)


def _scalar_non_girr_vega_matrix(
    ordered: tuple[WeightedSensitivity, ...],
    *,
    risk_class: SbmRiskClass,
    bucket_id: str,
    risk_factor_by_id: dict[str, str],
    qualifier_by_id: dict[str, str],
    option_tenor_by_id: dict[str, str],
) -> np.ndarray:
    matrix = np.eye(len(ordered), dtype=np.float64)
    for row_index, sensitivity_a in enumerate(ordered):
        for col_index in range(row_index + 1, len(ordered)):
            sensitivity_b = ordered[col_index]
            correlation, _ = non_girr_vega_intra_bucket_correlation(
                PROFILE_ID,
                risk_class=risk_class,
                bucket_id=bucket_id,
                risk_factor_a=risk_factor_by_id[sensitivity_a.sensitivity_id],
                risk_factor_b=risk_factor_by_id[sensitivity_b.sensitivity_id],
                qualifier_a=qualifier_by_id.get(sensitivity_a.sensitivity_id, ""),
                qualifier_b=qualifier_by_id.get(sensitivity_b.sensitivity_id, ""),
                option_tenor_a=option_tenor_by_id[sensitivity_a.sensitivity_id],
                option_tenor_b=option_tenor_by_id[sensitivity_b.sensitivity_id],
            )
            matrix[row_index, col_index] = correlation
            matrix[col_index, row_index] = correlation
    return matrix


def _scalar_curvature_matrix(
    factors: tuple[_CurvatureFactor, ...],
    *,
    risk_class: SbmRiskClass,
) -> np.ndarray:
    matrix = np.eye(len(factors), dtype=np.float64)
    for row_index, factor_a in enumerate(factors):
        for col_index in range(row_index + 1, len(factors)):
            factor_b = factors[col_index]
            correlation = _curvature_intra_bucket_correlation(
                PROFILE_ID,
                risk_class=risk_class,
                factor_a=factor_a,
                factor_b=factor_b,
            )
            matrix[row_index, col_index] = correlation
            matrix[col_index, row_index] = correlation
    return matrix


def _curvature_factor(
    *,
    risk_class: SbmRiskClass,
    bucket_id: str,
    risk_factor: str,
    qualifier: str | None,
    index: int,
) -> _CurvatureFactor:
    return _CurvatureFactor(
        risk_class=risk_class,
        bucket_id=bucket_id,
        factor_id=f"{bucket_id}|{risk_factor}|{qualifier or ''}|{index}",
        risk_factor=risk_factor,
        qualifier=qualifier,
        tenor=None,
        up_cvr=100.0 + index,
        down_cvr=50.0 + index,
        sensitivity_ids=(f"sens-{index}",),
        source_row_ids=(f"row-{index}",),
        citation_ids=("basel_mar21_100",),
    )
