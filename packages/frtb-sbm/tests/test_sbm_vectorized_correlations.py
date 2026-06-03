from __future__ import annotations

import numpy as np
import pytest
from frtb_sbm import (
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    WeightedSensitivity,
    build_non_girr_vega_intra_bucket_correlation_matrix,
    non_girr_vega_intra_bucket_correlation,
)
from frtb_sbm.curvature import (
    _build_curvature_intra_bucket_correlation_matrix,
    _curvature_intra_bucket_correlation,
    _CurvatureFactor,
)

_PROFILE = SbmRegulatoryProfile.BASEL_MAR21.value


def _weighted(
    sensitivity_id: str,
    *,
    risk_class: SbmRiskClass,
    bucket: str,
) -> WeightedSensitivity:
    return WeightedSensitivity(
        sensitivity_id=sensitivity_id,
        risk_class=risk_class,
        risk_measure=SbmRiskMeasure.VEGA,
        bucket=bucket,
        raw_amount=1.0,
        risk_weight=1.0,
        scaled_amount=1.0,
        citation_ids=("basel_mar21_94",),
    )


def _curvature_factor(
    *,
    risk_class: SbmRiskClass,
    bucket_id: str,
    factor_id: str,
    risk_factor: str,
    qualifier: str | None = None,
) -> _CurvatureFactor:
    return _CurvatureFactor(
        risk_class=risk_class,
        bucket_id=bucket_id,
        factor_id=factor_id,
        risk_factor=risk_factor,
        qualifier=qualifier,
        tenor=None,
        up_cvr=1.0,
        down_cvr=-1.0,
        sensitivity_ids=(factor_id,),
        source_row_ids=(factor_id,),
        citation_ids=("basel_mar21_curvature",),
    )


@pytest.mark.parametrize(
    ("risk_class", "bucket", "risk_factors", "qualifiers", "option_tenors"),
    [
        (
            SbmRiskClass.FX,
            "EUR",
            ("EUR", "GBP"),
            ("", ""),
            ("1y", "5y"),
        ),
        (
            SbmRiskClass.EQUITY,
            "5",
            ("SPOT", "SPOT"),
            ("ISS-A", "ISS-B"),
            ("1y", "5y"),
        ),
        (
            SbmRiskClass.COMMODITY,
            "2",
            ("WTI", "BRENT"),
            ("", ""),
            ("1y", "5y"),
        ),
        (
            SbmRiskClass.CSR_NONSEC,
            "4",
            ("BOND", "CDS"),
            ("ISS-A", "ISS-B"),
            ("1y", "5y"),
        ),
        (
            SbmRiskClass.CSR_NONSEC,
            "17",
            ("BOND", "CDS"),
            ("ISS-A", "ISS-B"),
            ("1y", "5y"),
        ),
        (
            SbmRiskClass.CSR_SEC_NONCTP,
            "1",
            ("BOND", "CDS"),
            ("TR-A", "TR-B"),
            ("1y", "5y"),
        ),
        (
            SbmRiskClass.CSR_SEC_CTP,
            "4",
            ("BOND", "CDS"),
            ("UND-A", "UND-B"),
            ("1y", "5y"),
        ),
    ],
)
def test_vectorized_non_girr_vega_matrix_matches_scalar_reference(
    risk_class: SbmRiskClass,
    bucket: str,
    risk_factors: tuple[str, ...],
    qualifiers: tuple[str, ...],
    option_tenors: tuple[str, ...],
) -> None:
    ordered = tuple(
        _weighted(f"vega-{index}", risk_class=risk_class, bucket=bucket)
        for index in range(len(risk_factors))
    )
    risk_factor_by_id = {
        item.sensitivity_id: risk_factor for item, risk_factor in zip(ordered, risk_factors)
    }
    qualifier_by_id = {
        item.sensitivity_id: qualifier for item, qualifier in zip(ordered, qualifiers)
    }
    option_tenor_by_id = {
        item.sensitivity_id: option_tenor for item, option_tenor in zip(ordered, option_tenors)
    }

    vectorized = build_non_girr_vega_intra_bucket_correlation_matrix(
        ordered,
        profile_id=_PROFILE,
        risk_class=risk_class,
        bucket_id=bucket,
        risk_factor_by_id=risk_factor_by_id,
        qualifier_by_id=qualifier_by_id,
        option_tenor_by_id=option_tenor_by_id,
    )
    scalar = _scalar_non_girr_vega_matrix(
        ordered,
        risk_class=risk_class,
        bucket=bucket,
        risk_factor_by_id=risk_factor_by_id,
        qualifier_by_id=qualifier_by_id,
        option_tenor_by_id=option_tenor_by_id,
    )

    assert np.allclose(vectorized, scalar)


@pytest.mark.parametrize(
    ("risk_class", "bucket_id", "factors"),
    [
        (
            SbmRiskClass.GIRR,
            "1",
            (
                ("girr-a", "USD-OIS", None),
                ("girr-b", "EUR-OIS", None),
            ),
        ),
        (
            SbmRiskClass.FX,
            "EUR",
            (
                ("fx-a", "EUR", None),
                ("fx-b", "GBP", None),
            ),
        ),
        (
            SbmRiskClass.EQUITY,
            "5",
            (
                ("eq-a", "SPOT", "ISS-A"),
                ("eq-b", "SPOT", "ISS-B"),
            ),
        ),
        (
            SbmRiskClass.EQUITY,
            "11",
            (
                ("eq-other-a", "SPOT", "ISS-A"),
                ("eq-other-b", "SPOT", "ISS-B"),
            ),
        ),
        (
            SbmRiskClass.COMMODITY,
            "2",
            (
                ("cmdty-a", "WTI", "LOC-A"),
                ("cmdty-b", "BRENT", "LOC-B"),
            ),
        ),
        (
            SbmRiskClass.CSR_NONSEC,
            "4",
            (
                ("csr-a", "CREDIT_SPREAD_CURVE", "ISS-A"),
                ("csr-b", "CREDIT_SPREAD_CURVE", "ISS-B"),
            ),
        ),
        (
            SbmRiskClass.CSR_NONSEC,
            "17",
            (
                ("csr-idx-a", "CREDIT_SPREAD_CURVE", "ISS-A"),
                ("csr-idx-b", "CREDIT_SPREAD_CURVE", "ISS-B"),
            ),
        ),
        (
            SbmRiskClass.CSR_SEC_NONCTP,
            "1",
            (
                ("sec-a", "CREDIT_SPREAD_CURVE", "TR-A"),
                ("sec-b", "CREDIT_SPREAD_CURVE", "TR-B"),
            ),
        ),
        (
            SbmRiskClass.CSR_SEC_CTP,
            "4",
            (
                ("ctp-a", "CREDIT_SPREAD_CURVE", "UND-A"),
                ("ctp-b", "CREDIT_SPREAD_CURVE", "UND-B"),
            ),
        ),
    ],
)
def test_vectorized_curvature_matrix_matches_scalar_reference(
    risk_class: SbmRiskClass,
    bucket_id: str,
    factors: tuple[tuple[str, str, str | None], ...],
) -> None:
    ordered = tuple(
        _curvature_factor(
            risk_class=risk_class,
            bucket_id=bucket_id,
            factor_id=factor_id,
            risk_factor=risk_factor,
            qualifier=qualifier,
        )
        for factor_id, risk_factor, qualifier in factors
    )

    vectorized = _build_curvature_intra_bucket_correlation_matrix(
        ordered,
        profile_id=_PROFILE,
        risk_class=risk_class,
    )
    scalar = _scalar_curvature_matrix(ordered, risk_class=risk_class)

    assert np.allclose(vectorized, scalar)


def _scalar_non_girr_vega_matrix(
    ordered: tuple[WeightedSensitivity, ...],
    *,
    risk_class: SbmRiskClass,
    bucket: str,
    risk_factor_by_id: dict[str, str],
    qualifier_by_id: dict[str, str],
    option_tenor_by_id: dict[str, str],
) -> np.ndarray:
    size = len(ordered)
    matrix = np.eye(size, dtype=np.float64)
    for row_index, sensitivity_a in enumerate(ordered):
        for col_index in range(row_index, size):
            sensitivity_b = ordered[col_index]
            correlation, _ = non_girr_vega_intra_bucket_correlation(
                _PROFILE,
                risk_class=risk_class,
                bucket_id=bucket,
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
    ordered: tuple[_CurvatureFactor, ...],
    *,
    risk_class: SbmRiskClass,
) -> np.ndarray:
    size = len(ordered)
    matrix = np.zeros((size, size), dtype=np.float64)
    for row_index, factor_a in enumerate(ordered):
        for col_index in range(row_index, size):
            factor_b = ordered[col_index]
            correlation = _curvature_intra_bucket_correlation(
                _PROFILE,
                risk_class=risk_class,
                factor_a=factor_a,
                factor_b=factor_b,
            )
            matrix[row_index, col_index] = correlation
            matrix[col_index, row_index] = correlation
    np.fill_diagonal(matrix, 1.0)
    return matrix
