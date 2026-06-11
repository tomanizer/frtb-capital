from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Protocol

import numpy as np
import pyarrow as pa
import pytest
from frtb_common import NormalizedArrowTable, source_content_hash
from frtb_sbm import (
    SbmCalculationContext,
    SbmCapitalResult,
    SbmRegulatoryProfile,
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
    weight_non_girr_vega_sensitivity_batch,
)
from frtb_sbm.csr_nonsec_reference_data import CSR_BOND_RISK_FACTOR
from frtb_sbm.equity_reference_data import EQUITY_SPOT_RISK_FACTOR
from sbm_registry_helpers import (
    build_commodity_vega_batch_from_arrow,
    build_csr_nonsec_vega_batch_from_arrow,
    build_csr_sec_ctp_vega_batch_from_arrow,
    build_csr_sec_nonctp_vega_batch_from_arrow,
    build_equity_vega_batch_from_arrow,
    build_fx_vega_batch_from_arrow,
    build_sbm_path_from_arrow,
    calculate_sbm_capital_from_commodity_vega_arrow,
    calculate_sbm_capital_from_csr_nonsec_vega_arrow,
    calculate_sbm_capital_from_csr_sec_ctp_vega_arrow,
    calculate_sbm_capital_from_csr_sec_nonctp_vega_arrow,
    calculate_sbm_capital_from_equity_vega_arrow,
    calculate_sbm_capital_from_fx_vega_arrow,
    normalize_commodity_vega_arrow_table,
    normalize_csr_nonsec_vega_arrow_table,
    normalize_csr_sec_ctp_vega_arrow_table,
    normalize_csr_sec_nonctp_vega_arrow_table,
    normalize_equity_vega_arrow_table,
    normalize_fx_vega_arrow_table,
    normalize_sbm_path,
)

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


def build_fx_vega_batch_from_sensitivities(sensitivities: object):
    return build_sbm_batch(sensitivities, SbmRiskClass.FX, SbmRiskMeasure.VEGA)


def build_equity_vega_batch_from_sensitivities(sensitivities: object):
    return build_sbm_batch(sensitivities, SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA)


def build_commodity_vega_batch_from_sensitivities(sensitivities: object):
    return build_sbm_batch(sensitivities, SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA)


def build_csr_nonsec_vega_batch_from_sensitivities(sensitivities: object):
    return build_sbm_batch(sensitivities, SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA)


def build_csr_sec_nonctp_vega_batch_from_sensitivities(
    sensitivities: object,
):
    return build_sbm_batch(sensitivities, SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.VEGA)


def build_csr_sec_ctp_vega_batch_from_sensitivities(sensitivities: object):
    return build_sbm_batch(sensitivities, SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.VEGA)


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
        source_file="sbm-non-girr-vega.csv",
        source_row_id=row_id,
    )


def fx_vega_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _sensitivity(
            sensitivity_id="fx-vega-eur-1y",
            source_row_id="row-fx-vega-001",
            risk_class=SbmRiskClass.FX,
            bucket="EUR",
            risk_factor="EUR",
            amount=500_000.0,
        ),
        _sensitivity(
            sensitivity_id="fx-vega-gbp-5y",
            source_row_id="row-fx-vega-002",
            risk_class=SbmRiskClass.FX,
            bucket="GBP",
            risk_factor="GBP",
            option_tenor="5y",
            amount=-350_000.0,
        ),
    )


def equity_vega_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _sensitivity(
            sensitivity_id="eq-vega-a-1y",
            source_row_id="row-eq-vega-001",
            risk_class=SbmRiskClass.EQUITY,
            bucket="5",
            risk_factor=EQUITY_SPOT_RISK_FACTOR,
            qualifier="ISS-A",
            amount=400_000.0,
        ),
        _sensitivity(
            sensitivity_id="eq-vega-b-5y",
            source_row_id="row-eq-vega-002",
            risk_class=SbmRiskClass.EQUITY,
            bucket="5",
            risk_factor=EQUITY_SPOT_RISK_FACTOR,
            qualifier="ISS-B",
            option_tenor="5y",
            amount=-150_000.0,
        ),
    )


def commodity_vega_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _sensitivity(
            sensitivity_id="com-vega-wti-1y",
            source_row_id="row-com-vega-001",
            risk_class=SbmRiskClass.COMMODITY,
            bucket="2",
            risk_factor="WTI",
            amount=650_000.0,
        ),
        _sensitivity(
            sensitivity_id="com-vega-brent-5y",
            source_row_id="row-com-vega-002",
            risk_class=SbmRiskClass.COMMODITY,
            bucket="2",
            risk_factor="BRENT",
            option_tenor="5y",
            amount=-275_000.0,
        ),
    )


def csr_nonsec_vega_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _sensitivity(
            sensitivity_id="csr-ns-vega-a-1y",
            source_row_id="row-csr-ns-vega-001",
            risk_class=SbmRiskClass.CSR_NONSEC,
            bucket="4",
            risk_factor=CSR_BOND_RISK_FACTOR,
            qualifier="ISS-A",
            amount=450_000.0,
        ),
        _sensitivity(
            sensitivity_id="csr-ns-vega-b-5y",
            source_row_id="row-csr-ns-vega-002",
            risk_class=SbmRiskClass.CSR_NONSEC,
            bucket="5",
            risk_factor=CSR_BOND_RISK_FACTOR,
            qualifier="ISS-B",
            option_tenor="5y",
            amount=-225_000.0,
        ),
    )


def csr_sec_nonctp_vega_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _sensitivity(
            sensitivity_id="csr-sec-nctp-vega-a-1y",
            source_row_id="row-csr-sec-nctp-vega-001",
            risk_class=SbmRiskClass.CSR_SEC_NONCTP,
            bucket="1",
            risk_factor=CSR_BOND_RISK_FACTOR,
            qualifier="TR-A",
            amount=520_000.0,
        ),
        _sensitivity(
            sensitivity_id="csr-sec-nctp-vega-b-5y",
            source_row_id="row-csr-sec-nctp-vega-002",
            risk_class=SbmRiskClass.CSR_SEC_NONCTP,
            bucket="2",
            risk_factor=CSR_BOND_RISK_FACTOR,
            qualifier="TR-B",
            option_tenor="5y",
            amount=-240_000.0,
        ),
    )


def csr_sec_ctp_vega_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _sensitivity(
            sensitivity_id="csr-sec-ctp-vega-a-1y",
            source_row_id="row-csr-sec-ctp-vega-001",
            risk_class=SbmRiskClass.CSR_SEC_CTP,
            bucket="4",
            risk_factor=CSR_BOND_RISK_FACTOR,
            qualifier="UND-A",
            amount=490_000.0,
        ),
        _sensitivity(
            sensitivity_id="csr-sec-ctp-vega-b-5y",
            source_row_id="row-csr-sec-ctp-vega-002",
            risk_class=SbmRiskClass.CSR_SEC_CTP,
            bucket="5",
            risk_factor=CSR_BOND_RISK_FACTOR,
            qualifier="UND-B",
            option_tenor="5y",
            amount=-210_000.0,
        ),
    )


def _sensitivity(
    *,
    sensitivity_id: str,
    source_row_id: str,
    risk_class: SbmRiskClass,
    bucket: str,
    risk_factor: str,
    amount: float,
    qualifier: str | None = None,
    option_tenor: str = "1y",
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=source_row_id,
        desk_id="vega-desk",
        legal_entity="LE-001",
        risk_class=risk_class,
        risk_measure=SbmRiskMeasure.VEGA,
        bucket=bucket,
        risk_factor=risk_factor,
        qualifier=qualifier,
        option_tenor=option_tenor,
        amount=amount,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=sample_lineage(source_row_id),
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
        "option_tenor": _dictionary([item.option_tenor for item in sensitivities]),
        "amount": pa.array([item.amount for item in sensitivities], type=pa.float64()),
        "amount_currency": _dictionary([item.amount_currency for item in sensitivities]),
        "sign_convention": _dictionary([item.sign_convention.value for item in sensitivities]),
        "lineage_source_system": [item.lineage.source_system for item in sensitivities],
        "lineage_source_file": [item.lineage.source_file for item in sensitivities],
    }
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
            SbmRiskClass.FX,
            fx_vega_sensitivities,
            normalize_fx_vega_arrow_table,
            build_fx_vega_batch_from_sensitivities,
            build_fx_vega_batch_from_arrow,
            calculate_sbm_capital_from_batch,
            calculate_sbm_capital_from_fx_vega_arrow,
        ),
        (
            SbmRiskClass.EQUITY,
            equity_vega_sensitivities,
            normalize_equity_vega_arrow_table,
            build_equity_vega_batch_from_sensitivities,
            build_equity_vega_batch_from_arrow,
            calculate_sbm_capital_from_batch,
            calculate_sbm_capital_from_equity_vega_arrow,
        ),
        (
            SbmRiskClass.COMMODITY,
            commodity_vega_sensitivities,
            normalize_commodity_vega_arrow_table,
            build_commodity_vega_batch_from_sensitivities,
            build_commodity_vega_batch_from_arrow,
            calculate_sbm_capital_from_batch,
            calculate_sbm_capital_from_commodity_vega_arrow,
        ),
        (
            SbmRiskClass.CSR_NONSEC,
            csr_nonsec_vega_sensitivities,
            normalize_csr_nonsec_vega_arrow_table,
            build_csr_nonsec_vega_batch_from_sensitivities,
            build_csr_nonsec_vega_batch_from_arrow,
            calculate_sbm_capital_from_batch,
            calculate_sbm_capital_from_csr_nonsec_vega_arrow,
        ),
        (
            SbmRiskClass.CSR_SEC_NONCTP,
            csr_sec_nonctp_vega_sensitivities,
            normalize_csr_sec_nonctp_vega_arrow_table,
            build_csr_sec_nonctp_vega_batch_from_sensitivities,
            build_csr_sec_nonctp_vega_batch_from_arrow,
            calculate_sbm_capital_from_batch,
            calculate_sbm_capital_from_csr_sec_nonctp_vega_arrow,
        ),
        (
            SbmRiskClass.CSR_SEC_CTP,
            csr_sec_ctp_vega_sensitivities,
            normalize_csr_sec_ctp_vega_arrow_table,
            build_csr_sec_ctp_vega_batch_from_sensitivities,
            build_csr_sec_ctp_vega_batch_from_arrow,
            calculate_sbm_capital_from_batch,
            calculate_sbm_capital_from_csr_sec_ctp_vega_arrow,
        ),
    ],
)
def test_non_girr_vega_batch_and_handoff_match_row_capital(
    risk_class: SbmRiskClass,
    sensitivities_factory: Callable[[], tuple[SbmSensitivity, ...]],
    normalize: NormalizeFn,
    build_row_batch: BatchBuilder,
    build_handoff_batch: HandoffBuilder,
    calculate_batch: BatchCalculator,
    calculate_handoff: HandoffCalculator,
) -> None:
    context = sample_context(f"{risk_class.value.lower()}-vega-batch-run")
    sensitivities = sensitivities_factory()
    handoff = normalize(
        arrow_table(sensitivities),
        source_hash=source_content_hash(f"synthetic {risk_class.value} vega source"),
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
    assert arrow_batch.option_tenors is not None
    np.testing.assert_array_equal(arrow_batch.option_tenors, row_batch.option_tenors)
    assert batch_result.input_hash == row_result.input_hash
    assert handoff_result.input_hash == row_result.input_hash
    assert batch_result.total_capital == pytest.approx(row_result.total_capital)
    assert handoff_result.risk_classes[0].buckets == row_result.risk_classes[0].buckets
    assert [
        item.sensitivity_id
        for item in weight_non_girr_vega_sensitivity_batch(
            arrow_batch,
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        )
    ] == [
        item.sensitivity_id
        for item in sorted(
            sensitivities,
            key=lambda item: (
                item.risk_class.value,
                item.risk_measure.value,
                item.bucket,
                item.risk_factor,
                item.sensitivity_id,
            ),
        )
    ]


def test_commodity_vega_batch_does_not_require_qualifier() -> None:
    batch = build_sbm_path_from_arrow(
        SbmRiskClass.COMMODITY,
        SbmRiskMeasure.VEGA,
        normalize_sbm_path(
            SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA, arrow_table(commodity_vega_sensitivities())
        ),
    )

    assert batch.qualifiers is None
    result = calculate_sbm_capital_from_batch(
        batch,
        context=sample_context("commodity-vega-no-qualifier"),
    )
    assert result.risk_classes[0].risk_class is SbmRiskClass.COMMODITY


def test_non_girr_vega_handoff_requires_option_tenor() -> None:
    table = arrow_table(fx_vega_sensitivities()).drop(["option_tenor"])

    with pytest.raises(ValueError, match="option_tenor"):
        normalize_sbm_path(SbmRiskClass.FX, SbmRiskMeasure.VEGA, table)
