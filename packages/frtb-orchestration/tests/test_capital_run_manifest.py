from __future__ import annotations

from datetime import date
from pathlib import Path

import frtb_drc
import frtb_rrao
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from frtb_common import StandardisedComponent
from frtb_orchestration import (
    DRC_NONSEC_INPUT_TABLE,
    RRAO_POSITIONS_INPUT_TABLE,
    CapitalRunManifest,
    ManifestInputTableRoute,
    OrchestrationInputError,
    run_standardised_approach_from_manifest,
    standardised_jurisdiction_family,
    validate_capital_run_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_manifest_validation_accepts_drc_and_rrao_input_tables_with_stable_hashes() -> None:
    manifest = _manifest()
    required = (DRC_NONSEC_INPUT_TABLE, RRAO_POSITIONS_INPUT_TABLE)

    first = validate_capital_run_manifest(
        manifest,
        routes=_routes(),
        required_input_table_keys=required,
    )
    second = validate_capital_run_manifest(
        manifest, routes=_routes(), required_input_table_keys=required
    )

    assert first.valid
    assert first.jurisdiction_family == "US_NPR"
    assert first.missing_required_input_tables == ()
    assert [input_table.logical_name for input_table in first.input_tables] == [
        DRC_NONSEC_INPUT_TABLE,
        RRAO_POSITIONS_INPUT_TABLE,
    ]
    assert [input_table.accepted_row_count for input_table in first.input_tables] == [1, 1]
    assert first.as_dict()["valid"] is True
    assert [input_table.input_table_hash for input_table in first.input_tables] == [
        input_table.input_table_hash for input_table in second.input_tables
    ]
    assert [input_table.source_hash for input_table in first.input_tables] == [
        input_table.source_hash for input_table in second.input_tables
    ]


def test_manifest_validation_reports_missing_required_input_tables() -> None:
    manifest = _manifest(input_tables={DRC_NONSEC_INPUT_TABLE: _drc_nonsec_table()})

    result = validate_capital_run_manifest(
        manifest,
        routes=_routes(),
        required_input_table_keys=(DRC_NONSEC_INPUT_TABLE, RRAO_POSITIONS_INPUT_TABLE),
    )

    assert not result.valid
    assert result.missing_required_input_tables == (RRAO_POSITIONS_INPUT_TABLE,)
    assert result.errors == ()


def test_manifest_validation_reports_profile_family_mismatch() -> None:
    manifest = CapitalRunManifest(
        run_id="client-sa-run-001",
        calculation_date=date(2026, 5, 29),
        profile_id="EU_CRR3",
        base_currency="USD",
        input_tables={RRAO_POSITIONS_INPUT_TABLE: _rrao_positions_table()},
        rrao_context=_rrao_context(),
    )

    result = validate_capital_run_manifest(
        manifest,
        routes=_routes(),
        required_input_table_keys=(RRAO_POSITIONS_INPUT_TABLE,),
    )

    assert not result.valid
    assert result.jurisdiction_family == "EU_CRR3"
    assert result.errors == (
        "rrao.positions context profile_id 'US_NPR_2_0' is in US_NPR, "
        "but manifest profile_id 'EU_CRR3' is in EU_CRR3",
    )


def test_standardised_manifest_run_records_fail_closed_missing_sbm_status() -> None:
    result = run_standardised_approach_from_manifest(
        _manifest(),
        routes=_routes(),
        required_input_table_keys=(DRC_NONSEC_INPUT_TABLE, RRAO_POSITIONS_INPUT_TABLE),
    )

    assert result.validation.valid
    assert result.standardised_result is None
    assert result.orchestration_error is not None
    assert "missing required component outputs: SBM" in result.orchestration_error
    assert [input_table.component for input_table in result.component_summaries] == [
        StandardisedComponent.DRC,
        StandardisedComponent.RRAO,
    ]
    assert result.as_dict()["orchestration_error"] == result.orchestration_error


def test_standardised_manifest_run_reports_missing_route_context_cleanly() -> None:
    manifest = CapitalRunManifest(
        run_id="client-sa-run-001",
        calculation_date=date(2026, 5, 29),
        profile_id="US_NPR_2_0",
        base_currency="USD",
        input_tables={RRAO_POSITIONS_INPUT_TABLE: _rrao_positions_table()},
    )

    result = run_standardised_approach_from_manifest(
        manifest,
        routes=_routes(),
        required_input_table_keys=(RRAO_POSITIONS_INPUT_TABLE,),
    )

    assert not result.validation.valid
    assert result.validation.errors == ("rrao.positions requires manifest.rrao_context",)
    assert result.orchestration_error == (
        "rrao.positions: Required context 'rrao_context' is missing from the manifest"
    )
    assert result.component_summaries == ()


def test_manifest_rejects_empty_mapping_keys_with_clear_error() -> None:
    with pytest.raises(OrchestrationInputError, match="input_tables keys must be non-empty text"):
        CapitalRunManifest(
            run_id="client-sa-run-001",
            calculation_date=date(2026, 5, 29),
            profile_id="US_NPR_2_0",
            base_currency="USD",
            input_tables={"": _rrao_positions_table()},
        )


def test_manifest_route_rejects_calculation_route_without_context_attr() -> None:
    try:
        ManifestInputTableRoute(
            logical_name=RRAO_POSITIONS_INPUT_TABLE,
            component=StandardisedComponent.RRAO,
            normalize=frtb_rrao.normalize_rrao_arrow_table,
            calculate_batch=frtb_rrao.calculate_rrao_capital_from_batch,
        )
    except OrchestrationInputError as exc:
        assert exc.field == "context_attr"
    else:  # pragma: no cover - failure branch keeps assertion message clear
        raise AssertionError("ManifestInputTableRoute accepted a calculation route without context")


def test_standardised_jurisdiction_family_is_public_guard() -> None:
    assert standardised_jurisdiction_family("BASEL_MAR21") == "BASEL"
    assert standardised_jurisdiction_family("BASEL_MAR22") == "BASEL"
    assert standardised_jurisdiction_family("BASEL_MAR23") == "BASEL"


def _manifest(
    *,
    input_tables: dict[str, pa.Table] | None = None,
) -> CapitalRunManifest:
    return CapitalRunManifest(
        run_id="client-sa-run-001",
        calculation_date=date(2026, 5, 29),
        profile_id="US_NPR_2_0",
        base_currency="USD",
        input_tables=_default_input_tables() if input_tables is None else input_tables,
        drc_context=_drc_context(),
        rrao_context=_rrao_context(),
        metadata={"source": "client-onboarding"},
    )


def _default_input_tables() -> dict[str, pa.Table]:
    return {
        DRC_NONSEC_INPUT_TABLE: _drc_nonsec_table(),
        RRAO_POSITIONS_INPUT_TABLE: _rrao_positions_table(),
    }


def _routes() -> dict[str, ManifestInputTableRoute]:
    return {
        DRC_NONSEC_INPUT_TABLE: ManifestInputTableRoute(
            logical_name=DRC_NONSEC_INPUT_TABLE,
            component=StandardisedComponent.DRC,
            normalize=frtb_drc.normalize_drc_nonsec_arrow_table,
            build_batch=frtb_drc.build_drc_nonsec_batch_from_arrow,
            calculate_batch=frtb_drc.calculate_drc_capital_from_batch,
            to_component_summary=frtb_drc.to_component_summary,
            context_attr="drc_context",
        ),
        RRAO_POSITIONS_INPUT_TABLE: ManifestInputTableRoute(
            logical_name=RRAO_POSITIONS_INPUT_TABLE,
            component=StandardisedComponent.RRAO,
            normalize=frtb_rrao.normalize_rrao_arrow_table,
            build_batch=frtb_rrao.build_rrao_batch_from_arrow,
            calculate_batch=frtb_rrao.calculate_rrao_capital_from_batch,
            to_component_summary=frtb_rrao.to_component_summary,
            context_attr="rrao_context",
        ),
    }


def _drc_context() -> frtb_drc.DrcCalculationContext:
    return frtb_drc.DrcCalculationContext(
        run_id="client-sa-run-001",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id=frtb_drc.US_NPR_2_0_PROFILE_ID,
    )


def _rrao_context() -> frtb_rrao.RraoCalculationContext:
    return frtb_rrao.RraoCalculationContext(
        run_id="client-sa-run-001",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile=frtb_rrao.RraoRegulatoryProfile.US_NPR_2_0,
    )


def _drc_nonsec_table() -> pa.Table:
    return pq.read_table(
        REPO_ROOT / "packages/frtb-drc/tests/fixtures/handoff/drc_nonsec_minimal.parquet"
    )


def _rrao_positions_table() -> pa.Table:
    return pa.table(
        {
            "position_id": ["rrao-pos-001"],
            "source_row_id": ["row-001"],
            "desk_id": ["structured-credit"],
            "legal_entity": ["bank-na"],
            "gross_effective_notional": [2_500_000.0],
            "currency": ["USD"],
            "evidence_type": ["GAP_RISK"],
            "evidence_label": ["synthetic gap-risk onboarding row"],
            "classification_hint": ["OTHER_RESIDUAL_RISK"],
            "lineage_source_system": ["client-risk-engine"],
            "lineage_source_file": ["rrao_positions.csv"],
            "citations": ["us_npr_211_a_1"],
        }
    )
