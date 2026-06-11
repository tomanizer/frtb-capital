from __future__ import annotations

from collections.abc import Callable

import pyarrow as pa
from frtb_common import AdapterDiagnostic, NormalizedArrowTable
from frtb_sbm import SbmCalculationContext, SbmCapitalResult, SbmRiskClass, SbmRiskMeasure
from frtb_sbm.arrow_batch import (
    build_sbm_batch_from_arrow,
    calculate_sbm_capital_from_arrow,
    normalize_sbm_arrow_table,
)
from frtb_sbm.batch import SbmSensitivityBatch


def normalize_sbm_path(
    risk_class: SbmRiskClass,
    measure: SbmRiskMeasure,
    table: pa.Table,
    *,
    diagnostics: tuple[AdapterDiagnostic, ...] = (),
    metadata: dict[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    return normalize_sbm_arrow_table(
        table,
        risk_class,
        measure,
        diagnostics=diagnostics,
        metadata=metadata,
        rejected=rejected,
        source_hash=source_hash,
    )


def build_sbm_path_from_arrow(
    risk_class: SbmRiskClass,
    measure: SbmRiskMeasure,
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    return build_sbm_batch_from_arrow(handoff, risk_class, measure)


def calculate_sbm_capital_from_path_arrow(
    risk_class: SbmRiskClass,
    measure: SbmRiskMeasure,
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    return calculate_sbm_capital_from_arrow(handoff, risk_class, measure, context=context)


def _normalizer(
    risk_class: SbmRiskClass,
    measure: SbmRiskMeasure,
) -> Callable[..., NormalizedArrowTable]:
    def normalize(table: pa.Table, **kwargs: object) -> NormalizedArrowTable:
        return normalize_sbm_path(risk_class, measure, table, **kwargs)

    return normalize


def _builder(
    risk_class: SbmRiskClass,
    measure: SbmRiskMeasure,
) -> Callable[[NormalizedArrowTable], SbmSensitivityBatch]:
    def build(handoff: NormalizedArrowTable) -> SbmSensitivityBatch:
        return build_sbm_path_from_arrow(risk_class, measure, handoff)

    return build


def _arrow_calculator(
    risk_class: SbmRiskClass,
    measure: SbmRiskMeasure,
) -> Callable[..., SbmCapitalResult]:
    def calculate(
        handoff: NormalizedArrowTable,
        *,
        context: SbmCalculationContext | None = None,
    ) -> SbmCapitalResult:
        return calculate_sbm_capital_from_path_arrow(
            risk_class,
            measure,
            handoff,
            context=context,
        )

    return calculate


_PATHS = {
    "girr_delta": (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
    "girr_vega": (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
    "girr_curvature": (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
    "fx_delta": (SbmRiskClass.FX, SbmRiskMeasure.DELTA),
    "fx_vega": (SbmRiskClass.FX, SbmRiskMeasure.VEGA),
    "fx_curvature": (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE),
    "equity_delta": (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA),
    "equity_vega": (SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA),
    "equity_curvature": (SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE),
    "commodity_delta": (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
    "commodity_vega": (SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA),
    "commodity_curvature": (SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE),
    "csr_nonsec_delta": (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA),
    "csr_nonsec_vega": (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA),
    "csr_nonsec_curvature": (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE),
    "csr_sec_nonctp_delta": (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA),
    "csr_sec_nonctp_vega": (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.VEGA),
    "csr_sec_nonctp_curvature": (
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskMeasure.CURVATURE,
    ),
    "csr_sec_ctp_delta": (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA),
    "csr_sec_ctp_vega": (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.VEGA),
    "csr_sec_ctp_curvature": (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.CURVATURE),
}

for _path_name, (_risk_class, _measure) in _PATHS.items():
    globals()[f"normalize_{_path_name}_arrow_table"] = _normalizer(_risk_class, _measure)
    globals()[f"build_{_path_name}_batch_from_arrow"] = _builder(_risk_class, _measure)
    globals()[f"calculate_sbm_capital_from_{_path_name}_arrow"] = _arrow_calculator(
        _risk_class,
        _measure,
    )
