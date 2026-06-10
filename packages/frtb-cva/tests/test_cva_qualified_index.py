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


def test_unsupported_risk_class_qualified_index() -> None:
    sens = SaCvaSensitivity(
        sensitivity_id="sens-girr-index",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="USD",
        risk_factor_key="5y",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-girr-index",
        index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
    )
    with pytest.raises(CvaInputError, match="qualified-index routing is only supported"):
        resolve_sa_cva_bucket(sens)


def test_ccs_bucket_unsupported_qualified_index() -> None:
    sens = _ccs_sensitivity(bucket_id="9")
    with pytest.raises(CvaInputError, match="does not support qualified-index"):
        resolve_sa_cva_bucket(sens)


def test_ccs_qualified_index_wrong_bucket() -> None:
    sens = _ccs_sensitivity(bucket_id="1")
    with pytest.raises(CvaInputError, match="qualified CCS index must use bucket 8"):
        resolve_sa_cva_bucket(sens)


def test_rcs_qualified_index_resolves() -> None:
    sens = SaCvaSensitivity(
        sensitivity_id="sens-rcs-index",
        risk_class=SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="16",
        risk_factor_key="INDEX",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-rcs-index",
        index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
    )
    bucket, citations = resolve_sa_cva_bucket(sens)
    assert bucket == "16"
    assert "basel_mar50_50" in citations

    sens_remap = SaCvaSensitivity(
        sensitivity_id="sens-rcs-index-remap",
        risk_class=SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="17",
        risk_factor_key="INDEX",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-rcs-index-remap",
        index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
        index_max_sector_weight=0.8,
        index_homogeneous_sector_quality=True,
        index_remap_bucket_id="1",
    )
    bucket, _ = resolve_sa_cva_bucket(sens_remap)
    assert bucket == "1"


def test_rcs_bucket_eight_resolves_as_single_name_bucket() -> None:
    sens = SaCvaSensitivity(
        sensitivity_id="sens-rcs-hynr-sovereign",
        risk_class=SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="8",
        risk_factor_key="SOVEREIGN|HIGH_YIELD_OR_NOT_RATED",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-rcs-hynr-sovereign",
    )
    bucket, citations = resolve_sa_cva_bucket(sens)
    assert bucket == "8"
    assert not citations


def test_rcs_qualified_index_wrong_bucket() -> None:
    sens = SaCvaSensitivity(
        sensitivity_id="sens-rcs-index",
        risk_class=SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="1",
        risk_factor_key="INDEX",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-rcs-index",
        index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
    )
    with pytest.raises(CvaInputError, match="RCS qualified index must use buckets 16 or 17"):
        resolve_sa_cva_bucket(sens)


def test_rcs_bucket_eight_rejects_qualified_index_treatment() -> None:
    sens = SaCvaSensitivity(
        sensitivity_id="sens-rcs-hynr-index",
        risk_class=SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="8",
        risk_factor_key="INDEX",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-rcs-hynr-index",
        index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
    )
    with pytest.raises(CvaInputError, match="RCS qualified index must use buckets 16 or 17"):
        resolve_sa_cva_bucket(sens)


def test_equity_qualified_index_resolves() -> None:
    sens = SaCvaSensitivity(
        sensitivity_id="sens-eq-index",
        risk_class=SaCvaRiskClass.EQUITY,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="12",
        risk_factor_key="INDEX",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-eq-index",
        index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
    )
    bucket, citations = resolve_sa_cva_bucket(sens)
    assert bucket == "12"
    assert "basel_mar50_72" in citations


def test_equity_qualified_index_wrong_bucket() -> None:
    sens = SaCvaSensitivity(
        sensitivity_id="sens-eq-index",
        risk_class=SaCvaRiskClass.EQUITY,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="1",
        risk_factor_key="INDEX",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-eq-index",
        index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
    )
    with pytest.raises(CvaInputError, match="qualified equity index must use buckets 12 or 13"):
        resolve_sa_cva_bucket(sens)


def test_sector_concentration_under_threshold() -> None:
    sensitivity = _ccs_sensitivity(
        index_max_sector_weight=0.6,
        index_dominant_sector=CvaSector.FINANCIALS,
    )
    bucket, _ = resolve_sa_cva_bucket(sensitivity)
    assert bucket == "8"


def test_remap_empty_bucket_fails() -> None:
    sensitivity = _ccs_sensitivity(
        index_max_sector_weight=0.8,
        index_remap_bucket_id="  ",
    )
    with pytest.raises(CvaInputError, match="must be a non-empty bucket id"):
        resolve_sa_cva_bucket(sensitivity)


def test_rcs_homogeneous_without_remap_bucket_fails() -> None:
    sens = SaCvaSensitivity(
        sensitivity_id="sens-rcs-index",
        risk_class=SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="16",
        risk_factor_key="INDEX",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-rcs-index",
        index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
        index_max_sector_weight=0.8,
        index_homogeneous_sector_quality=True,
    )
    with pytest.raises(CvaInputError, match="requires index_remap_bucket_id"):
        resolve_sa_cva_bucket(sens)


def test_ccs_remap_not_single_name() -> None:
    sensitivity = _ccs_sensitivity(
        index_max_sector_weight=0.8,
        index_remap_bucket_id="8",
    )
    with pytest.raises(CvaInputError, match="is not a single-name bucket"):
        resolve_sa_cva_bucket(sensitivity)


def test_rcs_remap_not_single_name() -> None:
    sens = SaCvaSensitivity(
        sensitivity_id="sens-rcs-index",
        risk_class=SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="16",
        risk_factor_key="INDEX",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-rcs-index",
        index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
        index_max_sector_weight=0.8,
        index_homogeneous_sector_quality=True,
        index_remap_bucket_id="17",
    )
    with pytest.raises(CvaInputError, match="is not a single-name bucket"):
        resolve_sa_cva_bucket(sens)
