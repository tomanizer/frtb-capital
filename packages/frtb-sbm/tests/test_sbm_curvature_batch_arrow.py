from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import pyarrow as pa
import pytest
from frtb_common import NormalizedArrowTable, source_content_hash
from frtb_sbm import (
    FX_CURVATURE_SCALAR_1_5_FLAG,
    SbmCalculationContext,
    SbmCapitalResult,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSensitivityBatch,
    SbmSignConvention,
    SbmSourceLineage,
    build_sbm_batch,
    calculate_sbm_capital,
    calculate_sbm_capital_from_batch,
    input_hash_for_sensitivities,
)
from sbm_registry_helpers import (
    build_commodity_curvature_batch_from_arrow,
    build_csr_nonsec_curvature_batch_from_arrow,
    build_csr_sec_ctp_curvature_batch_from_arrow,
    build_csr_sec_nonctp_curvature_batch_from_arrow,
    build_equity_curvature_batch_from_arrow,
    build_fx_curvature_batch_from_arrow,
    build_girr_curvature_batch_from_arrow,
    calculate_sbm_capital_from_commodity_curvature_arrow,
    calculate_sbm_capital_from_csr_nonsec_curvature_arrow,
    calculate_sbm_capital_from_csr_sec_ctp_curvature_arrow,
    calculate_sbm_capital_from_csr_sec_nonctp_curvature_arrow,
    calculate_sbm_capital_from_equity_curvature_arrow,
    calculate_sbm_capital_from_fx_curvature_arrow,
    calculate_sbm_capital_from_girr_curvature_arrow,
    normalize_commodity_curvature_arrow_table,
    normalize_csr_nonsec_curvature_arrow_table,
    normalize_csr_sec_ctp_curvature_arrow_table,
    normalize_csr_sec_nonctp_curvature_arrow_table,
    normalize_equity_curvature_arrow_table,
    normalize_fx_curvature_arrow_table,
    normalize_girr_curvature_arrow_table,
    normalize_sbm_path,
)

from tests.sbm_fixture_helpers import sample_sbm_basel_context as sample_context

BatchBuilder = Callable[[tuple[SbmSensitivity, ...]], SbmSensitivityBatch]
HandoffBuilder = Callable[[NormalizedArrowTable], SbmSensitivityBatch]


class NormalizeFn(Protocol):
    def __call__(
        self,
        table: pa.Table,
        *,
        source_hash: str | None = None,
    ) -> NormalizedArrowTable: ...


class BatchCalculator(Protocol):
    def __call__(
        self,
        batch: SbmSensitivityBatch,
        *,
        context: SbmCalculationContext | None = None,
    ) -> SbmCapitalResult: ...


class HandoffCalculator(Protocol):
    def __call__(
        self,
        handoff: NormalizedArrowTable,
        *,
        context: SbmCalculationContext | None = None,
    ) -> SbmCapitalResult: ...


def build_girr_curvature_batch_from_sensitivities(sensitivities: object):
    return build_sbm_batch(sensitivities, SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE)


def build_fx_curvature_batch_from_sensitivities(sensitivities: object):
    return build_sbm_batch(sensitivities, SbmRiskClass.FX, SbmRiskMeasure.CURVATURE)


def build_equity_curvature_batch_from_sensitivities(sensitivities: object):
    return build_sbm_batch(sensitivities, SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE)


def build_commodity_curvature_batch_from_sensitivities(
    sensitivities: object,
):
    return build_sbm_batch(sensitivities, SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE)


def build_csr_nonsec_curvature_batch_from_sensitivities(
    sensitivities: object,
):
    return build_sbm_batch(sensitivities, SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE)


def build_csr_sec_nonctp_curvature_batch_from_sensitivities(
    sensitivities: object,
):
    return build_sbm_batch(sensitivities, SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.CURVATURE)


def build_csr_sec_ctp_curvature_batch_from_sensitivities(
    sensitivities: object,
):
    return build_sbm_batch(sensitivities, SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.CURVATURE)


def sample_lineage(row_id: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm-curvature.csv",
        source_row_id=row_id,
    )


def _curvature(
    *,
    sensitivity_id: str,
    source_row_id: str,
    risk_class: SbmRiskClass,
    bucket: str,
    risk_factor: str,
    up: float,
    down: float,
    qualifier: str | None = None,
    tenor: str | None = None,
    mapping_citation_ids: tuple[str, ...] = (),
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=source_row_id,
        desk_id="curvature-desk",
        legal_entity="LE-001",
        risk_class=risk_class,
        risk_measure=SbmRiskMeasure.CURVATURE,
        bucket=bucket,
        risk_factor=risk_factor,
        amount=0.0,
        amount_currency="USD",
        tenor=tenor,
        qualifier=qualifier,
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=sample_lineage(source_row_id),
        up_shock_amount=up,
        down_shock_amount=down,
        mapping_citation_ids=mapping_citation_ids,
    )


def girr_curvature_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _curvature(
            sensitivity_id="girr-curv-usd-5y",
            source_row_id="row-girr-curv-001",
            risk_class=SbmRiskClass.GIRR,
            bucket="1",
            risk_factor="USD",
            tenor="5y",
            up=12_000.0,
            down=8_000.0,
        ),
        _curvature(
            sensitivity_id="girr-curv-usd-10y",
            source_row_id="row-girr-curv-002",
            risk_class=SbmRiskClass.GIRR,
            bucket="1",
            risk_factor="USD",
            tenor="10y",
            up=4_000.0,
            down=7_000.0,
        ),
    )


def fx_curvature_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _curvature(
            sensitivity_id="fx-curv-eur",
            source_row_id="row-fx-curv-001",
            risk_class=SbmRiskClass.FX,
            bucket="EUR",
            risk_factor="EUR",
            up=100.0,
            down=40.0,
        ),
        _curvature(
            sensitivity_id="fx-curv-gbp",
            source_row_id="row-fx-curv-002",
            risk_class=SbmRiskClass.FX,
            bucket="GBP",
            risk_factor="GBP",
            up=200.0,
            down=80.0,
        ),
    )


def equity_curvature_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _curvature(
            sensitivity_id="eq-curv-a",
            source_row_id="row-eq-curv-001",
            risk_class=SbmRiskClass.EQUITY,
            bucket="5",
            risk_factor="SPOT",
            qualifier="EQ-A",
            up=90.0,
            down=30.0,
        ),
        _curvature(
            sensitivity_id="eq-curv-b",
            source_row_id="row-eq-curv-002",
            risk_class=SbmRiskClass.EQUITY,
            bucket="5",
            risk_factor="SPOT",
            qualifier="EQ-B",
            up=70.0,
            down=50.0,
        ),
    )


def commodity_curvature_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _curvature(
            sensitivity_id="cmdty-curv-wti",
            source_row_id="row-cmdty-curv-001",
            risk_class=SbmRiskClass.COMMODITY,
            bucket="2",
            risk_factor="WTI",
            qualifier="NYMEX",
            up=110.0,
            down=60.0,
        ),
        _curvature(
            sensitivity_id="cmdty-curv-brent",
            source_row_id="row-cmdty-curv-002",
            risk_class=SbmRiskClass.COMMODITY,
            bucket="2",
            risk_factor="BRENT",
            qualifier="ICE",
            up=80.0,
            down=20.0,
        ),
    )


def csr_nonsec_curvature_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _curvature(
            sensitivity_id="csr-nonsec-curv-a",
            source_row_id="row-csr-nonsec-curv-001",
            risk_class=SbmRiskClass.CSR_NONSEC,
            bucket="11",
            risk_factor="BOND",
            qualifier="issuer-a",
            up=10.0,
            down=4.0,
        ),
        _curvature(
            sensitivity_id="csr-nonsec-curv-b",
            source_row_id="row-csr-nonsec-curv-002",
            risk_class=SbmRiskClass.CSR_NONSEC,
            bucket="11",
            risk_factor="CDS",
            qualifier="issuer-b",
            up=20.0,
            down=6.0,
        ),
    )


def csr_sec_nonctp_curvature_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _curvature(
            sensitivity_id="csr-sec-nonctp-curv-a",
            source_row_id="row-csr-sec-nonctp-curv-001",
            risk_class=SbmRiskClass.CSR_SEC_NONCTP,
            bucket="1",
            risk_factor="BOND",
            qualifier="tranche-a",
            up=15.0,
            down=5.0,
        ),
        _curvature(
            sensitivity_id="csr-sec-nonctp-curv-b",
            source_row_id="row-csr-sec-nonctp-curv-002",
            risk_class=SbmRiskClass.CSR_SEC_NONCTP,
            bucket="1",
            risk_factor="CDS",
            qualifier="tranche-b",
            up=25.0,
            down=7.0,
        ),
    )


def csr_sec_ctp_curvature_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _curvature(
            sensitivity_id="csr-sec-ctp-curv-a",
            source_row_id="row-csr-sec-ctp-curv-001",
            risk_class=SbmRiskClass.CSR_SEC_CTP,
            bucket="4",
            risk_factor="BOND",
            qualifier="underlying-a",
            up=18.0,
            down=8.0,
        ),
        _curvature(
            sensitivity_id="csr-sec-ctp-curv-b",
            source_row_id="row-csr-sec-ctp-curv-002",
            risk_class=SbmRiskClass.CSR_SEC_CTP,
            bucket="4",
            risk_factor="CDS",
            qualifier="underlying-b",
            up=28.0,
            down=9.0,
        ),
    )


def arrow_table(sensitivities: tuple[SbmSensitivity, ...]) -> pa.Table:
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
        "up_shock_amount": pa.array(
            [item.up_shock_amount for item in sensitivities],
            type=pa.float64(),
        ),
        "down_shock_amount": pa.array(
            [item.down_shock_amount for item in sensitivities],
            type=pa.float64(),
        ),
        "lineage_source_system": [item.lineage.source_system for item in sensitivities],
        "lineage_source_file": [item.lineage.source_file for item in sensitivities],
    }
    if any(item.tenor is not None for item in sensitivities):
        columns["tenor"] = _dictionary([item.tenor for item in sensitivities])
    if any(item.qualifier is not None for item in sensitivities):
        columns["qualifier"] = _dictionary([item.qualifier for item in sensitivities])
    return pa.table(columns)


def _dictionary(values: list[str | None]) -> pa.Array:
    return pa.array(values).dictionary_encode()


@pytest.mark.parametrize(
    (
        "risk_class",
        "sensitivities_factory",
        "normalize",
        "build_row_batch",
        "build_handoff_batch",
        "calculate_batch",
        "calculate_handoff",
    ),
    [
        (
            SbmRiskClass.GIRR,
            girr_curvature_sensitivities,
            normalize_girr_curvature_arrow_table,
            build_girr_curvature_batch_from_sensitivities,
            build_girr_curvature_batch_from_arrow,
            calculate_sbm_capital_from_batch,
            calculate_sbm_capital_from_girr_curvature_arrow,
        ),
        (
            SbmRiskClass.FX,
            fx_curvature_sensitivities,
            normalize_fx_curvature_arrow_table,
            build_fx_curvature_batch_from_sensitivities,
            build_fx_curvature_batch_from_arrow,
            calculate_sbm_capital_from_batch,
            calculate_sbm_capital_from_fx_curvature_arrow,
        ),
        (
            SbmRiskClass.EQUITY,
            equity_curvature_sensitivities,
            normalize_equity_curvature_arrow_table,
            build_equity_curvature_batch_from_sensitivities,
            build_equity_curvature_batch_from_arrow,
            calculate_sbm_capital_from_batch,
            calculate_sbm_capital_from_equity_curvature_arrow,
        ),
        (
            SbmRiskClass.COMMODITY,
            commodity_curvature_sensitivities,
            normalize_commodity_curvature_arrow_table,
            build_commodity_curvature_batch_from_sensitivities,
            build_commodity_curvature_batch_from_arrow,
            calculate_sbm_capital_from_batch,
            calculate_sbm_capital_from_commodity_curvature_arrow,
        ),
        (
            SbmRiskClass.CSR_NONSEC,
            csr_nonsec_curvature_sensitivities,
            normalize_csr_nonsec_curvature_arrow_table,
            build_csr_nonsec_curvature_batch_from_sensitivities,
            build_csr_nonsec_curvature_batch_from_arrow,
            calculate_sbm_capital_from_batch,
            calculate_sbm_capital_from_csr_nonsec_curvature_arrow,
        ),
        (
            SbmRiskClass.CSR_SEC_NONCTP,
            csr_sec_nonctp_curvature_sensitivities,
            normalize_csr_sec_nonctp_curvature_arrow_table,
            build_csr_sec_nonctp_curvature_batch_from_sensitivities,
            build_csr_sec_nonctp_curvature_batch_from_arrow,
            calculate_sbm_capital_from_batch,
            calculate_sbm_capital_from_csr_sec_nonctp_curvature_arrow,
        ),
        (
            SbmRiskClass.CSR_SEC_CTP,
            csr_sec_ctp_curvature_sensitivities,
            normalize_csr_sec_ctp_curvature_arrow_table,
            build_csr_sec_ctp_curvature_batch_from_sensitivities,
            build_csr_sec_ctp_curvature_batch_from_arrow,
            calculate_sbm_capital_from_batch,
            calculate_sbm_capital_from_csr_sec_ctp_curvature_arrow,
        ),
    ],
)
def test_curvature_batch_and_handoff_match_row_capital(
    risk_class: SbmRiskClass,
    sensitivities_factory: Callable[[], tuple[SbmSensitivity, ...]],
    normalize: NormalizeFn,
    build_row_batch: BatchBuilder,
    build_handoff_batch: HandoffBuilder,
    calculate_batch: BatchCalculator,
    calculate_handoff: HandoffCalculator,
) -> None:
    context = sample_context(f"{risk_class.value.lower()}-curvature-batch-run")
    sensitivities = sensitivities_factory()
    handoff = normalize(
        arrow_table(sensitivities),
        source_hash=source_content_hash(f"synthetic {risk_class.value} curvature source"),
    )

    row_result = calculate_sbm_capital(sensitivities, context=context)
    row_batch = build_row_batch(sensitivities)
    arrow_batch = build_handoff_batch(handoff)
    batch_result = calculate_batch(arrow_batch, context=context)
    handoff_result = calculate_handoff(handoff, context=context)

    assert row_batch.input_hash == input_hash_for_sensitivities(sensitivities)
    assert arrow_batch.input_hash == row_batch.input_hash
    assert arrow_batch.source_hash == handoff.source_hash
    assert arrow_batch.handoff_hash is not None
    assert arrow_batch.up_shock_amounts is not None
    assert arrow_batch.down_shock_amounts is not None
    assert batch_result.input_hash == row_result.input_hash
    assert handoff_result.input_hash == row_result.input_hash
    assert batch_result.total_capital == pytest.approx(row_result.total_capital)
    assert handoff_result.total_capital == pytest.approx(row_result.total_capital)
    assert handoff_result.risk_classes[0].buckets == row_result.risk_classes[0].buckets


def test_fx_curvature_batch_preserves_scalar_mapping_evidence() -> None:
    sensitivities = (
        _curvature(
            sensitivity_id="fx-cross-curv-001",
            source_row_id="row-fx-cross-curv-001",
            risk_class=SbmRiskClass.FX,
            bucket="EUR",
            risk_factor="EUR",
            qualifier="EUR/GBP",
            up=150.0,
            down=60.0,
            mapping_citation_ids=(FX_CURVATURE_SCALAR_1_5_FLAG,),
        ),
    )
    context = sample_context("fx-curvature-scalar-batch-run")

    row_result = calculate_sbm_capital(sensitivities, context=context)
    batch = build_fx_curvature_batch_from_sensitivities(sensitivities)
    batch_result = calculate_sbm_capital_from_batch(batch, context=context)

    assert batch_result.total_capital == pytest.approx(row_result.total_capital)
    assert batch_result.risk_classes[0].buckets[0].weighted_sensitivities[0].scaled_amount == (
        pytest.approx(100.0)
    )


def test_curvature_handoff_requires_shock_columns() -> None:
    table = arrow_table(fx_curvature_sensitivities()).drop(["up_shock_amount"])

    with pytest.raises(ValueError, match="up_shock_amount"):
        normalize_sbm_path(SbmRiskClass.FX, SbmRiskMeasure.CURVATURE, table)
