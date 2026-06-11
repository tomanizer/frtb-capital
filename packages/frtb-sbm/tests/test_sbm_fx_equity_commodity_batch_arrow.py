from __future__ import annotations

import inspect
from datetime import date

import numpy as np
import pyarrow as pa
import pytest
from frtb_common import source_content_hash
from frtb_sbm import (
    SbmCalculationContext,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    build_sbm_batch,
    calculate_sbm_capital,
    calculate_sbm_capital_from_batch,
    input_hash_for_sensitivities,
    weight_commodity_delta_sensitivity_batch,
    weight_equity_delta_sensitivity_batch,
    weight_fx_delta_sensitivity_batch,
)
from frtb_sbm.equity_reference_data import (
    EQUITY_OTHER_SECTOR_BUCKET,
    EQUITY_REPO_RISK_FACTOR,
    EQUITY_SPOT_RISK_FACTOR,
)
from frtb_sbm.risk_classes.commodity import (
    calculate_commodity_delta_risk_class_capital_from_batch,
)
from frtb_sbm.risk_classes.equity import calculate_equity_delta_risk_class_capital_from_batch
from sbm_registry_helpers import (
    build_sbm_path_from_arrow,
    calculate_sbm_capital_from_path_arrow,
    normalize_sbm_path,
)


def build_fx_delta_batch_from_sensitivities(sensitivities: object):
    return build_sbm_batch(sensitivities, SbmRiskClass.FX, SbmRiskMeasure.DELTA)


def build_equity_delta_batch_from_sensitivities(sensitivities: object):
    return build_sbm_batch(sensitivities, SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA)


def build_commodity_delta_batch_from_sensitivities(sensitivities: object):
    return build_sbm_batch(sensitivities, SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA)


def sample_context(run_id: str) -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id=run_id,
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def sample_lineage(row_id: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm-delta.csv",
        source_row_id=row_id,
    )


def fx_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _sensitivity(
            sensitivity_id="fx-eur",
            source_row_id="row-fx-001",
            risk_class=SbmRiskClass.FX,
            bucket="EUR",
            risk_factor="EUR",
            desk_id="fx-desk",
            amount=1_000_000.0,
        ),
        _sensitivity(
            sensitivity_id="fx-gbp",
            source_row_id="row-fx-002",
            risk_class=SbmRiskClass.FX,
            bucket="GBP",
            risk_factor="GBP",
            desk_id="fx-desk",
            amount=-600_000.0,
        ),
    )


def equity_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _sensitivity(
            sensitivity_id="eq-spot-a",
            source_row_id="row-eq-001",
            risk_class=SbmRiskClass.EQUITY,
            bucket="5",
            risk_factor=EQUITY_SPOT_RISK_FACTOR,
            qualifier="ISS-A",
            desk_id="eq-desk",
            amount=1_000_000.0,
        ),
        _sensitivity(
            sensitivity_id="eq-repo-a",
            source_row_id="row-eq-002",
            risk_class=SbmRiskClass.EQUITY,
            bucket="5",
            risk_factor=EQUITY_REPO_RISK_FACTOR,
            qualifier="ISS-A",
            desk_id="eq-desk",
            amount=-500_000.0,
        ),
        _sensitivity(
            sensitivity_id="eq-spot-b",
            source_row_id="row-eq-003",
            risk_class=SbmRiskClass.EQUITY,
            bucket="6",
            risk_factor=EQUITY_SPOT_RISK_FACTOR,
            qualifier="ISS-B",
            desk_id="eq-desk",
            amount=750_000.0,
        ),
    )


def commodity_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _sensitivity(
            sensitivity_id="com-wti-3m",
            source_row_id="row-com-001",
            risk_class=SbmRiskClass.COMMODITY,
            bucket="2",
            risk_factor="WTI",
            qualifier="NYMEX",
            tenor="3m",
            desk_id="com-desk",
            amount=2_000_000.0,
        ),
        _sensitivity(
            sensitivity_id="com-wti-6m",
            source_row_id="row-com-002",
            risk_class=SbmRiskClass.COMMODITY,
            bucket="2",
            risk_factor="WTI",
            qualifier="ICE",
            tenor="6m",
            desk_id="com-desk",
            amount=-1_100_000.0,
        ),
        _sensitivity(
            sensitivity_id="com-alum-1y",
            source_row_id="row-com-003",
            risk_class=SbmRiskClass.COMMODITY,
            bucket="5",
            risk_factor="ALU",
            qualifier="LME",
            tenor="1y",
            desk_id="com-desk",
            amount=900_000.0,
        ),
    )


def _sensitivity(
    *,
    sensitivity_id: str,
    source_row_id: str,
    risk_class: SbmRiskClass,
    bucket: str,
    risk_factor: str,
    desk_id: str,
    amount: float,
    qualifier: str | None = None,
    tenor: str | None = None,
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=source_row_id,
        desk_id=desk_id,
        legal_entity="LE-001",
        risk_class=risk_class,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=bucket,
        risk_factor=risk_factor,
        qualifier=qualifier,
        tenor=tenor,
        amount=amount,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=sample_lineage(source_row_id),
    )


def arrow_table(sensitivities: tuple[SbmSensitivity, ...], *, include_tenor: bool) -> pa.Table:
    columns: dict[str, object] = {
        "sensitivity_id": [item.sensitivity_id for item in sensitivities],
        "source_row_id": [item.source_row_id for item in sensitivities],
        "desk_id": [item.desk_id for item in sensitivities],
        "legal_entity": [item.legal_entity for item in sensitivities],
        "risk_class": _dictionary([item.risk_class.value for item in sensitivities]),
        "risk_measure": _dictionary([item.risk_measure.value for item in sensitivities]),
        "bucket": _dictionary([item.bucket for item in sensitivities]),
        "risk_factor": _dictionary([item.risk_factor for item in sensitivities]),
        "amount": pa.array([item.amount for item in sensitivities], type=pa.float64()),
        "amount_currency": _dictionary([item.amount_currency for item in sensitivities]),
        "sign_convention": _dictionary([item.sign_convention.value for item in sensitivities]),
        "lineage_source_system": [item.lineage.source_system for item in sensitivities],
        "lineage_source_file": [item.lineage.source_file for item in sensitivities],
    }
    if include_tenor:
        columns["tenor"] = _dictionary([item.tenor for item in sensitivities])
    if any(item.qualifier is not None for item in sensitivities):
        columns["qualifier"] = _dictionary([item.qualifier for item in sensitivities])
    return pa.table(columns)


def _dictionary(values: list[str | None]) -> pa.Array:
    return pa.array(values).dictionary_encode()


def test_fx_delta_batch_and_handoff_match_row_capital() -> None:
    context = sample_context("fx-batch-run")
    sensitivities = fx_sensitivities()
    source_hash = source_content_hash("synthetic FX delta source")
    handoff = normalize_sbm_path(
        SbmRiskClass.FX,
        SbmRiskMeasure.DELTA,
        arrow_table(sensitivities, include_tenor=False),
        source_hash=source_hash,
    )

    row_result = calculate_sbm_capital(sensitivities, context=context)
    row_batch = build_fx_delta_batch_from_sensitivities(sensitivities)
    arrow_batch = build_sbm_path_from_arrow(SbmRiskClass.FX, SbmRiskMeasure.DELTA, handoff)
    batch_result = calculate_sbm_capital_from_batch(arrow_batch, context=context)
    handoff_result = calculate_sbm_capital_from_path_arrow(
        SbmRiskClass.FX, SbmRiskMeasure.DELTA, handoff, context=context
    )

    assert row_batch.input_hash == input_hash_for_sensitivities(sensitivities)
    assert arrow_batch.input_hash == row_batch.input_hash
    assert arrow_batch.source_hash == source_hash
    assert arrow_batch.handoff_hash is not None
    assert batch_result.input_hash == row_result.input_hash
    assert handoff_result.input_hash == row_result.input_hash
    assert batch_result.total_capital == pytest.approx(row_result.total_capital)
    assert handoff_result.risk_classes[0].buckets == row_result.risk_classes[0].buckets
    assert [
        item.sensitivity_id
        for item in weight_fx_delta_sensitivity_batch(
            arrow_batch,
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
            reporting_currency="USD",
        )
    ] == ["fx-eur", "fx-gbp"]


def test_equity_delta_batch_and_handoff_match_row_capital() -> None:
    context = sample_context("equity-batch-run")
    sensitivities = equity_sensitivities()
    handoff = normalize_sbm_path(
        SbmRiskClass.EQUITY,
        SbmRiskMeasure.DELTA,
        arrow_table(sensitivities, include_tenor=False),
        source_hash=source_content_hash("synthetic equity delta source"),
    )

    row_result = calculate_sbm_capital(sensitivities, context=context)
    row_batch = build_equity_delta_batch_from_sensitivities(sensitivities)
    arrow_batch = build_sbm_path_from_arrow(SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA, handoff)
    batch_result = calculate_sbm_capital_from_batch(arrow_batch, context=context)
    handoff_result = calculate_sbm_capital_from_path_arrow(
        SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA, handoff, context=context
    )

    assert arrow_batch.input_hash == row_batch.input_hash
    np.testing.assert_array_equal(arrow_batch.qualifiers, row_batch.qualifiers)
    assert batch_result.input_hash == row_result.input_hash
    assert handoff_result.input_hash == row_result.input_hash
    assert batch_result.total_capital == pytest.approx(row_result.total_capital)
    assert handoff_result.risk_classes[0].buckets == row_result.risk_classes[0].buckets
    assert [
        item.qualifier
        for item in weight_equity_delta_sensitivity_batch(
            arrow_batch,
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        )
    ] == ["ISS-A", "ISS-A", "ISS-B"]


def test_commodity_delta_batch_and_handoff_match_row_capital() -> None:
    context = sample_context("commodity-batch-run")
    sensitivities = commodity_sensitivities()
    handoff = normalize_sbm_path(
        SbmRiskClass.COMMODITY,
        SbmRiskMeasure.DELTA,
        arrow_table(sensitivities, include_tenor=True),
        source_hash=source_content_hash("synthetic commodity delta source"),
    )

    row_result = calculate_sbm_capital(sensitivities, context=context)
    row_batch = build_commodity_delta_batch_from_sensitivities(sensitivities)
    arrow_batch = build_sbm_path_from_arrow(SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA, handoff)
    batch_result = calculate_sbm_capital_from_batch(arrow_batch, context=context)
    handoff_result = calculate_sbm_capital_from_path_arrow(
        SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA, handoff, context=context
    )

    assert arrow_batch.input_hash == row_batch.input_hash
    np.testing.assert_array_equal(arrow_batch.tenors, row_batch.tenors)
    np.testing.assert_array_equal(arrow_batch.qualifiers, row_batch.qualifiers)
    assert batch_result.input_hash == row_result.input_hash
    assert handoff_result.input_hash == row_result.input_hash
    assert batch_result.total_capital == pytest.approx(row_result.total_capital)
    assert handoff_result.risk_classes[0].buckets == row_result.risk_classes[0].buckets
    assert [
        item.qualifier
        for item in weight_commodity_delta_sensitivity_batch(
            arrow_batch,
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        )
    ] == ["NYMEX", "ICE", "LME"]


def test_equity_and_commodity_batches_preserve_factor_grid_axes() -> None:
    equity_batch = build_equity_delta_batch_from_sensitivities(equity_sensitivities())
    equity_result = calculate_equity_delta_risk_class_capital_from_batch(
        equity_batch,
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )
    equity_bucket_5 = next(bucket for bucket in equity_result.buckets if bucket.bucket_id == "5")

    commodity_batch = build_commodity_delta_batch_from_sensitivities(commodity_sensitivities())
    commodity_result = calculate_commodity_delta_risk_class_capital_from_batch(
        commodity_batch,
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )
    commodity_bucket_2 = next(
        bucket for bucket in commodity_result.buckets if bucket.bucket_id == "2"
    )

    assert [item.sensitivity_id for item in equity_bucket_5.weighted_sensitivities] == [
        "eq-repo-a",
        "eq-spot-a",
    ]
    assert [item.sensitivity_id for item in commodity_bucket_2.weighted_sensitivities] == [
        "com-wti-3m",
        "com-wti-6m",
    ]


def test_equity_other_sector_batch_preserves_absolute_weight_treatment() -> None:
    sensitivities = (
        _sensitivity(
            sensitivity_id="eq11-long",
            source_row_id="row-eq11-001",
            risk_class=SbmRiskClass.EQUITY,
            bucket=EQUITY_OTHER_SECTOR_BUCKET,
            risk_factor=EQUITY_SPOT_RISK_FACTOR,
            qualifier="ISS-X",
            desk_id="eq-desk",
            amount=1_000_000.0,
        ),
        _sensitivity(
            sensitivity_id="eq11-short",
            source_row_id="row-eq11-002",
            risk_class=SbmRiskClass.EQUITY,
            bucket=EQUITY_OTHER_SECTOR_BUCKET,
            risk_factor=EQUITY_SPOT_RISK_FACTOR,
            qualifier="ISS-Y",
            desk_id="eq-desk",
            amount=-800_000.0,
        ),
    )
    result = calculate_equity_delta_risk_class_capital_from_batch(
        build_equity_delta_batch_from_sensitivities(sensitivities),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )
    bucket_11 = next(
        bucket for bucket in result.buckets if bucket.bucket_id == EQUITY_OTHER_SECTOR_BUCKET
    )

    assert bucket_11.kb == pytest.approx(1_260_000.0)
    assert bucket_11.sb == pytest.approx(140_000.0)
    assert "basel_mar21_79" in bucket_11.citation_ids


def test_delta_handoff_contracts_require_path_specific_axes() -> None:
    fx_handoff = normalize_sbm_path(
        SbmRiskClass.FX, SbmRiskMeasure.DELTA, arrow_table(fx_sensitivities(), include_tenor=False)
    )
    equity_table = arrow_table(equity_sensitivities(), include_tenor=False).drop(["qualifier"])
    commodity_table = arrow_table(commodity_sensitivities(), include_tenor=True).drop(["tenor"])

    assert build_sbm_path_from_arrow(
        SbmRiskClass.FX, SbmRiskMeasure.DELTA, fx_handoff
    ).tenors.tolist() == [None, None]
    with pytest.raises(ValueError, match="qualifier"):
        normalize_sbm_path(SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA, equity_table)
    with pytest.raises(ValueError, match="tenor"):
        normalize_sbm_path(SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA, commodity_table)


def test_delta_arrow_batch_builders_do_not_construct_row_dataclasses() -> None:
    import frtb_sbm.arrow_batch as arrow_batch

    source = inspect.getsource(arrow_batch)

    assert "SbmSensitivity(" not in source
    assert "from frtb_sbm.data_models import SbmSensitivity" not in source
