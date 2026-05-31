from __future__ import annotations

import math

import pytest
from frtb_cva import (
    CvaSector,
    SaCvaIndexTreatment,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
)
from frtb_cva.qualified_index import resolve_sa_cva_bucket
from frtb_cva.risk_classes.ccs import calculate_ccs_delta_capital
from frtb_cva.validation import CvaInputError


def _ccs_sensitivity(**overrides: object) -> SaCvaSensitivity:
    base = dict(
        sensitivity_id="sens-ccs-index",
        risk_class=SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="8",
        risk_factor_key="INDEX|INVESTMENT_GRADE",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-ccs-index",
        index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
        index_homogeneous_sector_quality=True,
    )
    base.update(overrides)
    return SaCvaSensitivity(**base)  # type: ignore[arg-type]


def test_qualified_ccs_index_uses_bucket_eight() -> None:
    sensitivity = _ccs_sensitivity()
    bucket, citations = resolve_sa_cva_bucket(sensitivity)
    assert bucket == "8"
    assert "basel_mar50_50" in citations


def test_non_qualified_index_without_look_through_fails() -> None:
    with pytest.raises(CvaInputError, match="look-through"):
        resolve_sa_cva_bucket(
            _ccs_sensitivity(
                index_treatment=SaCvaIndexTreatment.LOOK_THROUGH_REQUIRED,
                bucket_id="2",
            )
        )


def test_qualified_index_fixture_reconciles() -> None:
    capital = calculate_ccs_delta_capital((_ccs_sensitivity(),))
    assert capital.post_multiplier_capital == pytest.approx(1_000_000.0 * 0.015)


def test_sector_concentration_maps_dominant_ccs_sector() -> None:
    sensitivity = _ccs_sensitivity(
        index_max_sector_weight=0.8,
        index_dominant_sector=CvaSector.FINANCIALS,
    )
    bucket, _ = resolve_sa_cva_bucket(sensitivity)
    assert bucket == "3"


def test_sector_concentration_explicit_remap_bucket() -> None:
    sensitivity = _ccs_sensitivity(
        index_max_sector_weight=0.9,
        index_remap_bucket_id="5",
    )
    bucket, _ = resolve_sa_cva_bucket(sensitivity)
    assert bucket == "5"


def test_non_finite_sector_weight_fails() -> None:
    with pytest.raises(CvaInputError, match="index_max_sector_weight"):
        resolve_sa_cva_bucket(_ccs_sensitivity(index_max_sector_weight=math.nan))


def test_sector_concentration_without_remap_metadata_fails() -> None:
    with pytest.raises(CvaInputError, match="sector concentration"):
        resolve_sa_cva_bucket(
            _ccs_sensitivity(
                index_max_sector_weight=0.8,
                index_homogeneous_sector_quality=False,
            )
        )

    with pytest.raises(CvaInputError, match="index_dominant_sector"):
        resolve_sa_cva_bucket(
            _ccs_sensitivity(
                index_max_sector_weight=0.8,
            )
        )
