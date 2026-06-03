"""Synthetic SBM notebook data and Arrow batch helpers."""

from __future__ import annotations

import importlib.util
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

import pyarrow as pa
from frtb_common import NormalizedArrowTable
from frtb_sbm import (
    SbmCalculationContext,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
)
from frtb_sbm.arrow_batch import (
    normalize_commodity_curvature_arrow_table,
    normalize_commodity_delta_arrow_table,
    normalize_commodity_vega_arrow_table,
    normalize_csr_nonsec_curvature_arrow_table,
    normalize_csr_nonsec_delta_arrow_table,
    normalize_csr_nonsec_vega_arrow_table,
    normalize_csr_sec_ctp_curvature_arrow_table,
    normalize_csr_sec_ctp_delta_arrow_table,
    normalize_csr_sec_ctp_vega_arrow_table,
    normalize_csr_sec_nonctp_curvature_arrow_table,
    normalize_csr_sec_nonctp_delta_arrow_table,
    normalize_csr_sec_nonctp_vega_arrow_table,
    normalize_equity_curvature_arrow_table,
    normalize_equity_delta_arrow_table,
    normalize_equity_vega_arrow_table,
    normalize_fx_curvature_arrow_table,
    normalize_fx_delta_arrow_table,
    normalize_fx_vega_arrow_table,
    normalize_girr_curvature_arrow_table,
    normalize_girr_delta_arrow_table,
    normalize_girr_vega_arrow_table,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = PACKAGE_ROOT / "tests" / "fixtures"


@dataclass(frozen=True)
class FixturePack:
    """Notebook-facing description of an executable validation fixture."""

    fixture_id: str
    risk_class: str
    risk_measure: str
    description: str


@dataclass(frozen=True)
class LoadedFixture:
    """Data loaded from a fixture directory."""

    fixture_id: str
    context: SbmCalculationContext
    sensitivities: tuple[SbmSensitivity, ...]
    expected_outputs: dict[str, Any]
    invalid_cases: tuple[tuple[str, str, tuple[object, ...]], ...]


NormalizeFn = Callable[..., NormalizedArrowTable]
PathKey = tuple[SbmRiskClass, SbmRiskMeasure]


FIXTURE_PACKS: tuple[FixturePack, ...] = (
    FixturePack(
        "girr_delta_v1",
        "GIRR",
        "DELTA",
        "GIRR delta weighting, bucket aggregation, scenario selection, and replay hash.",
    ),
    FixturePack(
        "fx_delta_v1",
        "FX",
        "DELTA",
        "FX delta bucket treatment and currency normalisation.",
    ),
    FixturePack(
        "equity_delta_v1",
        "EQUITY",
        "DELTA",
        "Equity delta issuer/bucket inputs and inter-bucket aggregation.",
    ),
    FixturePack(
        "commodity_delta_v1",
        "COMMODITY",
        "DELTA",
        "Commodity delta bucket, tenor, and location qualifier inputs.",
    ),
    FixturePack(
        "csr_nonsec_delta_v1",
        "CSR_NONSEC",
        "DELTA",
        "CSR non-securitisation delta issuer and tenor inputs.",
    ),
    FixturePack(
        "girr_vega_v1",
        "GIRR",
        "VEGA",
        "GIRR vega option-tenor handling and replay-stable audit output.",
    ),
    FixturePack(
        "non_girr_vega_v1",
        "FX/EQUITY/COMMODITY/CSR",
        "VEGA",
        "Non-GIRR vega paths, scenario totals, and portfolio scenario selection.",
    ),
)


SUPPORTED_PATHS: tuple[PathKey, ...] = (
    (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
    (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
    (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.FX, SbmRiskMeasure.DELTA),
    (SbmRiskClass.FX, SbmRiskMeasure.VEGA),
    (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA),
    (SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA),
    (SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA),
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA),
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA),
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.VEGA),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.VEGA),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.CURVATURE),
)


NORMALIZERS: dict[PathKey, NormalizeFn] = {
    (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA): normalize_girr_delta_arrow_table,
    (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA): normalize_girr_vega_arrow_table,
    (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE): normalize_girr_curvature_arrow_table,
    (SbmRiskClass.FX, SbmRiskMeasure.DELTA): normalize_fx_delta_arrow_table,
    (SbmRiskClass.FX, SbmRiskMeasure.VEGA): normalize_fx_vega_arrow_table,
    (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE): normalize_fx_curvature_arrow_table,
    (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA): normalize_equity_delta_arrow_table,
    (SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA): normalize_equity_vega_arrow_table,
    (SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE): normalize_equity_curvature_arrow_table,
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA): normalize_commodity_delta_arrow_table,
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA): normalize_commodity_vega_arrow_table,
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE): normalize_commodity_curvature_arrow_table,
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA): normalize_csr_nonsec_delta_arrow_table,
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA): normalize_csr_nonsec_vega_arrow_table,
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE): (
        normalize_csr_nonsec_curvature_arrow_table
    ),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA): (
        normalize_csr_sec_nonctp_delta_arrow_table
    ),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.VEGA): (normalize_csr_sec_nonctp_vega_arrow_table),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.CURVATURE): (
        normalize_csr_sec_nonctp_curvature_arrow_table
    ),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA): normalize_csr_sec_ctp_delta_arrow_table,
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.VEGA): normalize_csr_sec_ctp_vega_arrow_table,
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.CURVATURE): (
        normalize_csr_sec_ctp_curvature_arrow_table
    ),
}


def load_fixture(fixture_id: str) -> LoadedFixture:
    """Load a deterministic fixture through its package-local loader."""

    module = load_fixture_module(fixture_id)
    return LoadedFixture(
        fixture_id=fixture_id,
        context=module.load_fixture_context(),
        sensitivities=module.load_fixture_sensitivities(),
        expected_outputs=module.load_expected_outputs(),
        invalid_cases=tuple(module.load_invalid_cases()),
    )


def load_fixture_module(fixture_id: str) -> ModuleType:
    """Load the fixture loader module for a known fixture id."""

    known_ids = {fixture.fixture_id for fixture in FIXTURE_PACKS}
    if fixture_id not in known_ids:
        known = ", ".join(sorted(known_ids))
        raise ValueError(f"unknown fixture_id {fixture_id!r}; expected one of: {known}")
    loader_path = FIXTURE_ROOT / fixture_id / "loader.py"
    spec = importlib.util.spec_from_file_location(f"{fixture_id}_loader", loader_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load fixture loader at {loader_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def notebook_context(run_id: str = "sbm-notebook-demo") -> SbmCalculationContext:
    """Return a stable Basel MAR21 notebook calculation context."""

    return SbmCalculationContext(
        run_id=run_id,
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        desk_id="sbm-demo-desk",
        legal_entity="LE-DEMO",
    )


def portfolio_sample_sensitivities() -> tuple[SbmSensitivity, ...]:
    """Return one synthetic row for every supported risk-class/measure path."""

    return tuple(
        sample_sensitivity(index, risk_class=risk_class, risk_measure=risk_measure)
        for index, (risk_class, risk_measure) in enumerate(SUPPORTED_PATHS, start=1)
    )


def curvature_sample_sensitivities() -> tuple[SbmSensitivity, ...]:
    """Return a compact set of curvature rows across representative risk classes."""

    paths: tuple[PathKey, ...] = (
        (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
        (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE),
        (SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE),
        (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE),
    )
    return tuple(
        sample_sensitivity(index, risk_class=risk_class, risk_measure=risk_measure)
        for index, (risk_class, risk_measure) in enumerate(paths, start=1)
    )


def sample_sensitivity(
    index: int,
    *,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> SbmSensitivity:
    """Build one synthetic sensitivity for a supported SBM capital path."""

    bucket, risk_factor, qualifier, tenor = path_metadata(risk_class, risk_measure, index)
    is_curvature = risk_measure is SbmRiskMeasure.CURVATURE
    return SbmSensitivity(
        sensitivity_id=f"{risk_class.value.lower()}-{risk_measure.value.lower()}-{index:03d}",
        source_row_id=f"row-{index:03d}",
        desk_id="sbm-demo-desk",
        legal_entity="LE-DEMO",
        risk_class=risk_class,
        risk_measure=risk_measure,
        bucket=bucket,
        risk_factor=risk_factor,
        amount=0.0 if is_curvature else 1_000.0 + index,
        amount_currency="USD",
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=lineage(index),
        qualifier=qualifier,
        tenor=tenor,
        option_tenor="1y" if risk_measure is SbmRiskMeasure.VEGA else None,
        up_shock_amount=200.0 + index if is_curvature else None,
        down_shock_amount=80.0 + index if is_curvature else None,
    )


def path_metadata(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    index: int,
) -> tuple[str, str, str | None, str | None]:
    """Return bucket, risk factor, qualifier, and tenor for a synthetic path."""

    if risk_class is SbmRiskClass.GIRR:
        risk_factor = "USD-OIS" if risk_measure is SbmRiskMeasure.DELTA else "USD"
        return "2", risk_factor, None, "5y"
    if risk_class is SbmRiskClass.FX:
        currency = "EUR" if index % 2 else "GBP"
        return currency, currency, None, None
    if risk_class is SbmRiskClass.EQUITY:
        return "5", "SPOT", f"ISS-{index}", None
    if risk_class is SbmRiskClass.COMMODITY:
        tenor = "3m" if risk_measure is SbmRiskMeasure.DELTA else None
        return "2", "WTI", f"LOC-{index}", tenor
    if risk_class is SbmRiskClass.CSR_NONSEC:
        tenor = "5y" if risk_measure is SbmRiskMeasure.DELTA else None
        return "4", "BOND", f"ISS-{index}", tenor
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        tenor = "5y" if risk_measure is SbmRiskMeasure.DELTA else None
        return "1", "BOND", f"TR-{index}", tenor
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        tenor = "5y" if risk_measure is SbmRiskMeasure.DELTA else None
        return "3", "BOND", f"UND-{index}", tenor
    raise ValueError(f"unexpected risk class {risk_class}")


def lineage(index: int, source_file: str = "sbm-notebook.csv") -> SbmSourceLineage:
    """Return stable source lineage for a synthetic notebook row."""

    return SbmSourceLineage(
        source_system="notebook",
        source_file=source_file,
        source_row_id=f"row-{index:03d}",
    )


def arrow_table(sensitivities: Iterable[SbmSensitivity]) -> pa.Table:
    """Build an Arrow table that satisfies the SBM handoff column contracts."""

    rows = tuple(sensitivities)
    columns: dict[str, object] = {
        "sensitivity_id": [item.sensitivity_id for item in rows],
        "source_row_id": [item.source_row_id for item in rows],
        "desk_id": [item.desk_id for item in rows],
        "legal_entity": [item.legal_entity for item in rows],
        "risk_class": _dictionary([item.risk_class.value for item in rows]),
        "risk_measure": _dictionary([item.risk_measure.value for item in rows]),
        "bucket": _dictionary([item.bucket for item in rows]),
        "risk_factor": _dictionary([item.risk_factor for item in rows]),
        "amount": pa.array([item.amount for item in rows], type=pa.float64()),
        "amount_currency": _dictionary([item.amount_currency for item in rows]),
        "sign_convention": _dictionary([item.sign_convention.value for item in rows]),
        "lineage_source_system": [item.lineage.source_system for item in rows],
        "lineage_source_file": [item.lineage.source_file for item in rows],
    }
    optional_columns = {
        "qualifier": [item.qualifier for item in rows],
        "tenor": [item.tenor for item in rows],
        "option_tenor": [item.option_tenor for item in rows],
        "up_shock_amount": [item.up_shock_amount for item in rows],
        "down_shock_amount": [item.down_shock_amount for item in rows],
    }
    for column_name, values in optional_columns.items():
        if not any(value is not None for value in values):
            continue
        if column_name in {"up_shock_amount", "down_shock_amount"}:
            columns[column_name] = pa.array(values, type=pa.float64())
        else:
            columns[column_name] = _dictionary(values)
    return pa.table(columns)


def arrow_tables_for_sensitivities(
    sensitivities: Iterable[SbmSensitivity],
) -> tuple[NormalizedArrowTable, ...]:
    """Group synthetic rows by path and normalise each group to an Arrow batch."""

    grouped: dict[PathKey, list[SbmSensitivity]] = defaultdict(list)
    for sensitivity in sensitivities:
        grouped[(sensitivity.risk_class, sensitivity.risk_measure)].append(sensitivity)
    return tuple(NORMALIZERS[path](arrow_table(rows)) for path, rows in grouped.items())


def markdown_table(headers: tuple[str, ...], rows: Iterable[Iterable[object]]) -> str:
    """Return a compact GitHub-flavoured Markdown table."""

    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    body = tuple("| " + " | ".join(_format_cell(cell) for cell in row) + " |" for row in rows)
    return "\n".join((header, separator, *body))


def _dictionary(values: list[str | None]) -> pa.Array:
    return pa.array(values).dictionary_encode()


def _format_cell(value: object) -> str:
    if isinstance(value, float):
        return f"{value:,.6g}"
    return str(value)
