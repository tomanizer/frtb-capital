from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest
from frtb_rrao import (
    RraoAllocationDimension,
    RraoCalculationContext,
    RraoCapitalResult,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInputError,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    build_rrao_allocation_report,
    build_rrao_allocation_reports,
    calculate_rrao_capital,
    resolve_rrao_allocation_dimension,
    serialize_rrao_allocation_report,
    serialize_rrao_result,
    validate_rrao_allocation_report,
)

US_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "rrao_v1"
EU_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "rrao_eu"


def load_us_fixture_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rrao_v1_loader", US_FIXTURE_DIR / "loader.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def us_fixture_result() -> RraoCapitalResult:
    loader = load_us_fixture_module()
    return calculate_rrao_capital(
        loader.load_fixture_positions(),
        context=loader.load_fixture_context(),
    )


def eu_fixture_result() -> RraoCapitalResult:
    payload = json.loads((EU_FIXTURE_DIR / "positions.json").read_text(encoding="utf-8"))
    context = payload["context"]
    return calculate_rrao_capital(
        tuple(_eu_position_from_payload(position) for position in payload["positions"]),
        context=RraoCalculationContext(
            run_id=str(context["run_id"]),
            calculation_date=date.fromisoformat(str(context["calculation_date"])),
            base_currency=str(context["base_currency"]),
            profile=RraoRegulatoryProfile(str(context["profile"])),
        ),
    )


def test_line_allocation_report_reconciles_and_preserves_result_payload() -> None:
    result = us_fixture_result()
    before_payload = serialize_rrao_result(result)

    report = build_rrao_allocation_report(result, RraoAllocationDimension.LINE)

    assert serialize_rrao_result(result) == before_payload
    assert report.total_rrao == 53_000.0
    assert report.allocated_rrao == report.total_rrao
    assert [bucket.bucket_key for bucket in report.buckets] == [
        *(line.position_id for line in result.lines),
        *(line.position_id for line in result.excluded_lines),
    ]
    assert report.buckets[0].included_position_ids == ("exotic-longevity-001",)

    excluded_bucket = next(
        bucket for bucket in report.buckets if bucket.bucket_key == "excluded-listed-001"
    )
    assert excluded_bucket.add_on == 0.0
    assert excluded_bucket.excluded_position_ids == ("excluded-listed-001",)
    validate_rrao_allocation_report(report)


@pytest.mark.parametrize(
    ("dimension", "expected_add_ons"),
    (
        (
            RraoAllocationDimension.DESK,
            {
                "desk-exclusions": 0.0,
                "desk-exotics": 42_500.0,
                "desk-structured": 7_500.0,
                "desk-supervisory": 3_000.0,
            },
        ),
        (
            RraoAllocationDimension.LEGAL_ENTITY,
            {
                "LE-001": 42_500.0,
                "LE-002": 7_500.0,
                "LE-003": 3_000.0,
                "LE-004": 0.0,
            },
        ),
        (
            RraoAllocationDimension.EVIDENCE_TYPE,
            {
                "BEHAVIOURAL_RISK": 2_000.0,
                "CORRELATION_RISK": 1_500.0,
                "EXOTIC_UNDERLYING": 42_500.0,
                "EXPLICIT_EXCLUSION": 0.0,
                "GAP_RISK": 4_000.0,
                "SUPERVISOR_DIRECTIVE": 3_000.0,
            },
        ),
    ),
)
def test_grouped_allocation_reports_reconcile_v1_fixture(
    dimension: RraoAllocationDimension,
    expected_add_ons: dict[str, float],
) -> None:
    result = us_fixture_result()

    report = build_rrao_allocation_report(result, dimension)

    assert {bucket.bucket_key: bucket.add_on for bucket in report.buckets} == expected_add_ons
    assert sum(bucket.add_on for bucket in report.buckets) == result.total_rrao
    assert report.allocated_rrao == result.total_rrao


@pytest.mark.parametrize(
    "dimension",
    (
        RraoAllocationDimension.LINE,
        RraoAllocationDimension.DESK,
        RraoAllocationDimension.LEGAL_ENTITY,
        RraoAllocationDimension.EVIDENCE_TYPE,
    ),
)
def test_allocation_reports_reconcile_eu_fixture(dimension: RraoAllocationDimension) -> None:
    result = eu_fixture_result()

    report = build_rrao_allocation_report(result, dimension)

    assert report.profile_id == "EU_CRR3"
    assert report.allocated_rrao == 12_000.0
    assert report.allocated_rrao == result.total_rrao


def test_build_allocation_reports_defaults_to_supported_dimensions() -> None:
    result = us_fixture_result()

    reports = build_rrao_allocation_reports(result)

    assert [report.dimension for report in reports] == [
        RraoAllocationDimension.LINE,
        RraoAllocationDimension.DESK,
        RraoAllocationDimension.LEGAL_ENTITY,
        RraoAllocationDimension.EVIDENCE_TYPE,
    ]


def test_allocation_report_serialization_is_deterministic() -> None:
    result = us_fixture_result()
    report = build_rrao_allocation_report(result, "desk")

    payload = serialize_rrao_allocation_report(report)

    assert payload["dimension"] == "desk_id"
    assert payload["allocated_rrao"] == 53_000.0
    assert json.dumps(payload, sort_keys=True)


def test_unsupported_allocation_dimension_fails_explicitly() -> None:
    result = us_fixture_result()

    assert resolve_rrao_allocation_dimension("legal-entity") is RraoAllocationDimension.LEGAL_ENTITY
    with pytest.raises(RraoInputError, match="unsupported RRAO allocation dimension"):
        build_rrao_allocation_report(result, "classification")


def _eu_position_from_payload(payload: object) -> RraoPosition:
    assert isinstance(payload, dict)
    exclusion_reason = payload.get("exclusion_reason")
    row_id = str(payload["source_row_id"])
    return RraoPosition(
        position_id=str(payload["position_id"]),
        source_row_id=row_id,
        desk_id=str(payload["desk_id"]),
        legal_entity=str(payload["legal_entity"]),
        gross_effective_notional=float(payload["gross_effective_notional"]),
        currency=str(payload["currency"]),
        evidence_type=RraoEvidenceType(str(payload["evidence_type"])),
        evidence_label=str(payload["evidence_label"]),
        classification_hint=RraoClassification(str(payload["classification_hint"])),
        exclusion_reason=(
            RraoExclusionReason(str(exclusion_reason)) if exclusion_reason is not None else None
        ),
        exclusion_evidence_id=_optional_str(payload.get("exclusion_evidence_id")),
        lineage=RraoSourceLineage(
            source_system="synthetic-eu-rrao-fixture",
            source_file="positions.json",
            source_row_id=row_id,
            source_column_map=(
                ("evidence_type", "evidence_type"),
                ("gross_effective_notional", "gross_effective_notional"),
            ),
        ),
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
