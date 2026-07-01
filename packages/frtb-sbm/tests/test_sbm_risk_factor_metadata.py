from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from frtb_sbm import (
    SbmCalculationContext,
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    build_sbm_batch_from_columns,
    calculate_sbm_capital,
    calculate_sbm_capital_from_batch,
    serialize_sbm_result,
)


def _context() -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="sbm-risk-factor-metadata",
        calculation_date=date(2026, 7, 1),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def _sensitivity(
    index: int,
    *,
    amount: float,
    risk_factor: str,
    risk_factor_id: str | None = None,
    mapping_version: str | None = None,
    bucket_label: str | None = None,
) -> SbmSensitivity:
    row_id = f"row-{index:04d}"
    return SbmSensitivity(
        sensitivity_id=f"sens-{index:04d}",
        source_row_id=row_id,
        desk_id="rates",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket="2",
        risk_factor=risk_factor,
        amount=amount,
        amount_currency="USD",
        sign_convention=SbmSignConvention.RECEIVE,
        tenor="5y",
        lineage=SbmSourceLineage(
            source_system="unit-test",
            source_file="sbm-risk-factor-metadata.csv",
            source_row_id=row_id,
        ),
        risk_factor_id=risk_factor_id,
        risk_factor_mapping_version=mapping_version,
        bucket_label=bucket_label,
    )


def _metadata_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _sensitivity(
            1,
            amount=100.0,
            risk_factor="USD-OIS",
            risk_factor_id="rf:girr/usd-ois/5y",
            mapping_version="sbm-map-2026.07",
            bucket_label="USD rates",
        ),
        _sensitivity(
            2,
            amount=25.0,
            risk_factor="EUR-OIS",
            risk_factor_id="rf:girr/eur-ois/5y",
            mapping_version="sbm-map-2026.07",
            bucket_label="USD rates",
        ),
    )


def _batch_columns(sensitivities: tuple[SbmSensitivity, ...]) -> dict[str, list[object]]:
    return {
        "sensitivity_ids": [item.sensitivity_id for item in sensitivities],
        "source_row_ids": [item.source_row_id for item in sensitivities],
        "desk_ids": [item.desk_id for item in sensitivities],
        "legal_entities": [item.legal_entity for item in sensitivities],
        "risk_classes": [item.risk_class.value for item in sensitivities],
        "risk_measures": [item.risk_measure.value for item in sensitivities],
        "buckets": [item.bucket for item in sensitivities],
        "risk_factors": [item.risk_factor for item in sensitivities],
        "amounts": [item.amount for item in sensitivities],
        "amount_currencies": [item.amount_currency for item in sensitivities],
        "sign_conventions": [item.sign_convention.value for item in sensitivities],
        "tenors": [item.tenor for item in sensitivities],
        "lineage_source_systems": [item.lineage.source_system for item in sensitivities],
        "lineage_source_files": [item.lineage.source_file for item in sensitivities],
    }


def _weighted_by_sensitivity_id(result, sensitivity_id: str):
    return next(
        item
        for bucket in result.risk_classes[0].buckets
        for item in bucket.weighted_sensitivities
        if item.sensitivity_id == sensitivity_id
    )


def test_row_path_preserves_supplied_risk_factor_metadata_without_changing_capital() -> None:
    sensitivities = _metadata_sensitivities()
    baseline = tuple(
        replace(
            item,
            risk_factor_id=None,
            risk_factor_mapping_version=None,
            bucket_label=None,
        )
        for item in sensitivities
    )

    result = calculate_sbm_capital(sensitivities, context=_context())
    baseline_result = calculate_sbm_capital(baseline, context=_context())

    assert result.total_capital == pytest.approx(baseline_result.total_capital)
    weighted = _weighted_by_sensitivity_id(result, "sens-0001")
    assert weighted.risk_factor_id == "rf:girr/usd-ois/5y"
    assert weighted.risk_factor_mapping_version == "sbm-map-2026.07"
    assert weighted.bucket_label == "USD rates"
    assert weighted.source_system == "unit-test"
    assert weighted.source_row_id == "row-0001"

    payload = serialize_sbm_result(result)
    payload_weighted = next(
        item
        for bucket in payload["risk_classes"][0]["buckets"]
        for item in bucket["weighted_sensitivities"]
        if item["sensitivity_id"] == "sens-0001"
    )
    assert payload_weighted["risk_factor_id"] == weighted.risk_factor_id
    assert payload_weighted["risk_factor_mapping_version"] == weighted.risk_factor_mapping_version
    assert payload_weighted["bucket_label"] == weighted.bucket_label
    assert payload_weighted["source_system"] == weighted.source_system
    assert payload_weighted["source_row_id"] == weighted.source_row_id


def test_batch_path_preserves_supplied_risk_factor_metadata_without_changing_capital() -> None:
    sensitivities = _metadata_sensitivities()
    columns = _batch_columns(sensitivities)
    batch = build_sbm_batch_from_columns(
        **columns,
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        risk_factor_ids=[item.risk_factor_id for item in sensitivities],
        risk_factor_mapping_versions=[item.risk_factor_mapping_version for item in sensitivities],
        bucket_labels=[item.bucket_label for item in sensitivities],
    )
    baseline_batch = build_sbm_batch_from_columns(
        **columns,
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.DELTA,
    )

    result = calculate_sbm_capital_from_batch(batch, context=_context())
    baseline_result = calculate_sbm_capital_from_batch(baseline_batch, context=_context())

    assert result.total_capital == pytest.approx(baseline_result.total_capital)
    weighted = _weighted_by_sensitivity_id(result, "sens-0001")
    assert weighted.risk_factor_id == "rf:girr/usd-ois/5y"
    assert weighted.risk_factor_mapping_version == "sbm-map-2026.07"
    assert weighted.bucket_label == "USD rates"
    assert weighted.source_system == "unit-test"
    assert weighted.source_row_id == "row-0001"


def test_missing_risk_factor_metadata_remains_absent_and_deterministic() -> None:
    sensitivities = tuple(
        replace(
            item,
            risk_factor_id=None,
            risk_factor_mapping_version=None,
            bucket_label=None,
        )
        for item in _metadata_sensitivities()
    )

    result = calculate_sbm_capital(sensitivities, context=_context())
    weighted = _weighted_by_sensitivity_id(result, "sens-0001")

    assert weighted.risk_factor_id is None
    assert weighted.risk_factor_mapping_version is None
    assert weighted.bucket_label is None
    assert weighted.source_system == "unit-test"
    assert weighted.source_row_id == "row-0001"


def test_invalid_risk_factor_metadata_fails_deterministically() -> None:
    invalid = replace(_metadata_sensitivities()[0], risk_factor_id="not valid")

    with pytest.raises(SbmInputError, match="invalid risk_factor_id"):
        calculate_sbm_capital((invalid,), context=_context())

    columns = _batch_columns(_metadata_sensitivities()[:1])
    with pytest.raises(SbmInputError, match="invalid risk_factor_mapping_version"):
        build_sbm_batch_from_columns(
            **columns,
            expected_risk_class=SbmRiskClass.GIRR,
            expected_risk_measure=SbmRiskMeasure.DELTA,
            risk_factor_mapping_versions=["not valid"],
        )
