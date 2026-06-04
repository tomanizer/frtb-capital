from __future__ import annotations

from dataclasses import replace

import pytest
from frtb_common.attribution import AttributionMethod, ReconciliationStatus
from frtb_common.contribution_bundle import ComponentContributionBundle
from test_rrao_allocation import us_fixture_result

from frtb_rrao import (
    RraoAllocationBucket,
    RraoAllocationDimension,
    RraoInputError,
    build_rrao_allocation_report,
    build_rrao_contribution_bundle,
    calculate_rrao_attribution,
    rrao_allocation_report_to_contributions,
)


def test_line_attribution_projects_additive_records_without_changing_result() -> None:
    result = us_fixture_result()
    before_payload = result.as_dict()

    records = calculate_rrao_attribution(result)

    assert result.as_dict() == before_payload
    assert sum(record.contribution or 0.0 for record in records) == result.total_rrao
    assert {record.method for record in records} == {AttributionMethod.STANDALONE}
    assert {record.reconciliation_status for record in records} == {ReconciliationStatus.RECONCILED}
    assert all(record.residual == 0.0 for record in records)
    assert all(record.input_hash == result.input_hash for record in records)
    assert all(record.profile_hash == result.profile_hash for record in records)

    excluded = next(record for record in records if record.source_id == "excluded-listed-001")
    assert excluded.contribution == 0.0
    assert excluded.category == "EXCLUDED"


@pytest.mark.parametrize(
    ("dimension", "source_level", "source_id"),
    (
        (RraoAllocationDimension.DESK, "desk", "desk-exotics"),
        (RraoAllocationDimension.LEGAL_ENTITY, "legal_entity", "LE-001"),
        (RraoAllocationDimension.EVIDENCE_TYPE, "evidence_type", "EXOTIC_UNDERLYING"),
    ),
)
def test_grouped_attribution_routes_supported_source_dimensions(
    dimension: RraoAllocationDimension,
    source_level: str,
    source_id: str,
) -> None:
    result = us_fixture_result()

    records = calculate_rrao_attribution(result, dimension)

    assert sum(record.contribution or 0.0 for record in records) == result.total_rrao
    routed = next(record for record in records if record.source_id == source_id)
    assert routed.source_level == source_level
    assert routed.bucket_key == source_id
    assert routed.method is AttributionMethod.STANDALONE


def test_allocation_report_projection_accepts_serialized_report_context() -> None:
    result = us_fixture_result()
    report = build_rrao_allocation_report(result, "evidence-type")

    records = rrao_allocation_report_to_contributions(
        report,
        profile_hash=result.profile_hash,
        citations=("manual_context",),
    )

    assert sum(record.contribution or 0.0 for record in records) == result.total_rrao
    assert all(record.profile_hash == result.profile_hash for record in records)
    assert all(record.citations == ("manual_context",) for record in records)


def test_rrao_contribution_bundle_uses_canonical_line_view() -> None:
    result = us_fixture_result()

    bundle = build_rrao_contribution_bundle(result)

    assert isinstance(bundle, ComponentContributionBundle)
    assert bundle.component == "frtb_rrao"
    assert bundle.component_total == result.total_rrao
    assert bundle.component_input_hash == result.input_hash
    assert bundle.component_profile_hash == result.profile_hash
    assert all(record.source_level == "line" for record in bundle.contributions)


def test_rrao_contribution_bundle_rejects_tampered_totals() -> None:
    result = us_fixture_result()
    tampered = replace(result, total_rrao=result.total_rrao + 1.0)

    with pytest.raises(RraoInputError, match="total RRAO does not reconcile"):
        build_rrao_contribution_bundle(tampered)


def test_rrao_attribution_rejects_unsupported_dimensions() -> None:
    result = us_fixture_result()

    with pytest.raises(RraoInputError, match="unsupported RRAO allocation dimension"):
        calculate_rrao_attribution(result, "classification")


def test_allocation_report_projection_rejects_missing_line_lookup_entries() -> None:
    result = us_fixture_result()
    report = build_rrao_allocation_report(result, "line")

    with pytest.raises(RraoInputError, match="was not found in result lines"):
        rrao_allocation_report_to_contributions(report, line_lookup={})


def test_line_projection_rejects_empty_position_ids() -> None:
    result = us_fixture_result()
    report = build_rrao_allocation_report(result, "line")
    empty_bucket = RraoAllocationBucket(
        dimension=RraoAllocationDimension.LINE,
        bucket_key="empty-line",
        gross_effective_notional=0.0,
        add_on=0.0,
        position_ids=(),
        included_position_ids=(),
        excluded_position_ids=(),
        line_count=0,
        excluded_line_count=0,
    )
    empty_report = replace(
        report,
        total_rrao=0.0,
        allocated_rrao=0.0,
        buckets=(empty_bucket,),
    )

    with pytest.raises(RraoInputError, match="has no position ids"):
        rrao_allocation_report_to_contributions(empty_report)
