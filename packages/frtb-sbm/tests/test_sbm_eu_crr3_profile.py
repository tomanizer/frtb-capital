from __future__ import annotations

import hashlib
import importlib.util
import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import ModuleType

import pyarrow as pa
import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    SbmCalculationContext,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    build_sbm_batch,
    calculate_sbm_capital,
    calculate_sbm_capital_from_batch,
    serialize_sbm_result,
    validate_sbm_result_reconciliation,
)
from frtb_sbm.reference_citations_eu_crr3 import translate_basel_citation_ids_to_eu
from frtb_sbm.validation import phase1_capital_supported_paths
from sbm_registry_helpers import calculate_sbm_capital_from_path_arrow, normalize_sbm_path

FIXTURE_DIR = Path(__file__).parent / "fixtures"
_EU_PROFILE = "EU_CRR3"
_SUPPORTED_EU_PATHS = frozenset(
    {
        (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
        (SbmRiskClass.FX, SbmRiskMeasure.DELTA),
        (SbmRiskClass.FX, SbmRiskMeasure.VEGA),
        (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE),
        (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
    }
)


def test_eu_crr3_support_matrix_opens_only_delivered_cells() -> None:
    assert phase1_capital_supported_paths(_EU_PROFILE) == _SUPPORTED_EU_PATHS


def test_eu_crr3_basel_citation_translation_fails_for_unmapped_basel_id() -> None:
    with pytest.raises(KeyError, match="basel_mar21_missing"):
        translate_basel_citation_ids_to_eu(("basel_mar21_missing",))


@pytest.mark.parametrize(
    ("case_id", "risk_class", "risk_measure"),
    [
        ("girr_delta_eu_crr3_v1", SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
        ("girr_vega_eu_crr3_v1", SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
        ("girr_curvature_eu_crr3_v1", SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
        ("fx_delta_eu_crr3_v1", SbmRiskClass.FX, SbmRiskMeasure.DELTA),
        ("fx_vega_eu_crr3_v1", SbmRiskClass.FX, SbmRiskMeasure.VEGA),
        ("fx_curvature_eu_crr3_v1", SbmRiskClass.FX, SbmRiskMeasure.CURVATURE),
        ("equity_delta_eu_crr3_v1", SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA),
        ("commodity_delta_eu_crr3_v1", SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
    ],
)
def test_eu_crr3_supported_fixture_packs_match_expected_outputs(
    case_id: str,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> None:
    loader = _load_fixture_module(case_id)
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()
    expected = loader.load_expected_outputs()

    row_result = calculate_sbm_capital(sensitivities, context=context)
    validate_sbm_result_reconciliation(row_result)
    batch_result = calculate_sbm_capital_from_batch(
        build_sbm_batch(sensitivities, risk_class, risk_measure),
        context=context,
    )
    handoff = normalize_sbm_path(risk_class, risk_measure, _arrow_table(sensitivities))
    arrow_result = calculate_sbm_capital_from_path_arrow(
        risk_class,
        risk_measure,
        handoff,
        context=context,
    )

    row_payload = serialize_sbm_result(row_result)
    assert row_payload == expected
    assert serialize_sbm_result(batch_result) == row_payload
    assert serialize_sbm_result(arrow_result)["risk_classes"] == row_payload["risk_classes"]
    assert row_payload["profile_id"] == _EU_PROFILE
    assert row_payload["total_capital"] > 0.0
    assert not _contains_basel_citation(row_payload)
    assert _contains_eu_citation(row_payload)
    assert not _contains_basel_citation(_fixture_manifest(case_id))


@pytest.mark.parametrize(
    "case_id",
    [
        "girr_delta_eu_crr3_v1",
        "girr_vega_eu_crr3_v1",
        "girr_curvature_eu_crr3_v1",
        "fx_delta_eu_crr3_v1",
        "fx_vega_eu_crr3_v1",
        "fx_curvature_eu_crr3_v1",
        "equity_delta_eu_crr3_v1",
        "commodity_delta_eu_crr3_v1",
    ],
)
def test_eu_crr3_fixture_manifest_hashes_match_files(case_id: str) -> None:
    manifest = _fixture_manifest(case_id)
    assert manifest["profile"] == _EU_PROFILE
    fixture_dir = FIXTURE_DIR / case_id

    for filename, metadata in manifest["files"].items():
        assert _sha256(fixture_dir / filename) == metadata["sha256"]


@pytest.mark.parametrize(
    ("risk_class", "risk_measure"),
    [
        (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA),
        (SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE),
    ],
)
def test_eu_crr3_unsupported_cells_remain_fail_closed(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> None:
    sensitivity = _unsupported_cell_sensitivity(risk_class, risk_measure)
    with pytest.raises(UnsupportedRegulatoryFeatureError):
        calculate_sbm_capital((sensitivity,), context=_context("unsupported-eu-cell"))


def _load_fixture_sensitivities(name: str) -> tuple[SbmSensitivity, ...]:
    module = _load_fixture_module(name)
    return module.load_fixture_sensitivities()


def _unsupported_cell_sensitivity(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> SbmSensitivity:
    if risk_class is SbmRiskClass.CSR_NONSEC:
        return _load_fixture_sensitivities("csr_nonsec_delta_v1")[0]
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return replace(
            _load_fixture_sensitivities("csr_nonsec_delta_v1")[0],
            risk_class=SbmRiskClass.CSR_SEC_NONCTP,
            bucket="1",
            risk_factor="senior_investment_grade",
            qualifier="tranche-a",
        )
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        return replace(
            _load_fixture_sensitivities("csr_nonsec_delta_v1")[0],
            risk_class=SbmRiskClass.CSR_SEC_CTP,
            bucket="1",
            risk_factor="senior_investment_grade",
            qualifier="issuer-a",
        )
    if risk_class is SbmRiskClass.EQUITY and risk_measure is SbmRiskMeasure.VEGA:
        return next(
            item
            for item in _load_fixture_sensitivities("non_girr_vega_v1")
            if item.risk_class is SbmRiskClass.EQUITY
        )
    return _curvature_sensitivity(
        SbmRiskClass.COMMODITY,
        "2",
        "WTI",
        qualifier="NYMEX",
        tenor="3m",
    )


def _load_fixture_module(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"{name}_loader", FIXTURE_DIR / name / "loader.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture_manifest(name: str) -> dict[str, object]:
    with (FIXTURE_DIR / name / "manifest.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _context(run_id: str) -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id=run_id,
        calculation_date=date(2026, 1, 1),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=_EU_PROFILE,
    )


def _curvature_sensitivity(
    risk_class: SbmRiskClass,
    bucket: str,
    risk_factor: str,
    *,
    qualifier: str | None = None,
    tenor: str | None = None,
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=f"{risk_class.value.lower()}-curvature-eu",
        source_row_id="row-eu-curvature",
        desk_id="desk-eu",
        legal_entity="entity-eu",
        risk_class=risk_class,
        risk_measure=SbmRiskMeasure.CURVATURE,
        bucket=bucket,
        risk_factor=risk_factor,
        amount=0.0,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=SbmSourceLineage(
            source_system="synthetic",
            source_file="eu_crr3_curvature_v1",
            source_row_id="row-eu-curvature",
        ),
        qualifier=qualifier,
        tenor=tenor,
        up_shock_amount=100.0,
        down_shock_amount=40.0,
    )


def _arrow_table(sensitivities: tuple[SbmSensitivity, ...]) -> pa.Table:
    return pa.table(
        {
            "sensitivity_id": [item.sensitivity_id for item in sensitivities],
            "source_row_id": [item.source_row_id for item in sensitivities],
            "desk_id": [item.desk_id for item in sensitivities],
            "legal_entity": [item.legal_entity for item in sensitivities],
            "risk_class": [item.risk_class.value for item in sensitivities],
            "risk_measure": [item.risk_measure.value for item in sensitivities],
            "bucket": [item.bucket for item in sensitivities],
            "risk_factor": [item.risk_factor for item in sensitivities],
            "amount": [item.amount for item in sensitivities],
            "amount_currency": [item.amount_currency for item in sensitivities],
            "sign_convention": [item.sign_convention.value for item in sensitivities],
            "qualifier": [item.qualifier for item in sensitivities],
            "tenor": [item.tenor for item in sensitivities],
            "option_tenor": [item.option_tenor for item in sensitivities],
            "liquidity_horizon_days": [item.liquidity_horizon_days for item in sensitivities],
            "maturity": [item.maturity for item in sensitivities],
            "up_shock_amount": [item.up_shock_amount for item in sensitivities],
            "down_shock_amount": [item.down_shock_amount for item in sensitivities],
            "mapping_citation_ids": [list(item.mapping_citation_ids) for item in sensitivities],
            "lineage_source_system": [item.lineage.source_system for item in sensitivities],
            "lineage_source_file": [item.lineage.source_file for item in sensitivities],
        }
    )


def _contains_basel_citation(payload: object) -> bool:
    if isinstance(payload, dict):
        return any(_contains_basel_citation(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_basel_citation(value) for value in payload)
    return isinstance(payload, str) and payload.startswith("basel_")


def _contains_eu_citation(payload: object) -> bool:
    if isinstance(payload, dict):
        return any(_contains_eu_citation(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_eu_citation(value) for value in payload)
    return isinstance(payload, str) and payload.startswith("eu_crr3_")
