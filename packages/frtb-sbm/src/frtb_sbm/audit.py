"""
Deterministic SBM audit serialization and reconciliation.

Regulatory traceability:
    Basel MAR21 component traceability by formula.
    SBM-AUDIT-001, SBM-FUNC-021, SBM-FUNC-022.
"""

from __future__ import annotations

from frtb_sbm.assembly.hashes import (
    input_hash_for_validated_sensitivities as _input_hash_for_validated_sensitivities,
)
from frtb_sbm.data_models import (
    BucketCapital,
    CurvatureBranchRecord,
    CurvatureBucketBranchRecord,
    IntraBucketScenarioRecord,
    PairwiseCorrelationSummary,
    RiskClassCapital,
    RiskClassScenarioDetail,
    SbmBranchMetadata,
    SbmCapitalResult,
    SbmReconciliationMetadata,
    SbmRunContextSummary,
    SbmScenarioLabel,
    WeightedSensitivity,
)
from frtb_sbm.numeric import is_reconciled
from frtb_sbm.org_scope import scope_payload
from frtb_sbm.validation import SbmInputError, validate_sbm_sensitivities

_HASH_HEX_LENGTH = 64


def input_hash_for_sensitivities(sensitivities: object) -> str:
    """Return a deterministic hash of canonical SBM input sensitivities."""

    validated = validate_sbm_sensitivities(sensitivities)
    return _input_hash_for_validated_sensitivities(validated)


def serialize_sbm_result(result: SbmCapitalResult) -> dict[str, object]:
    """Return a JSON-serialisable audit payload for an SBM result."""

    payload: dict[str, object] = {
        "total_capital": result.total_capital,
        "profile_id": result.profile_id,
        "profile_hash": result.profile_hash,
        "input_hash": result.input_hash,
        "input_hash_algorithm": result.input_hash_algorithm,
        "warnings": list(result.warnings),
        "unsupported_flags": list(result.unsupported_flags),
        "risk_classes": [_risk_class_payload(risk_class) for risk_class in result.risk_classes],
        "reconciliation": _reconciliation_payload(result.reconciliation),
    }
    if result.run_context is not None:
        payload["run_context"] = _run_context_payload(result.run_context)
    if result.portfolio_scenario_totals is not None:
        payload["portfolio_scenario_totals"] = {
            label.value: total for label, total in sorted(result.portfolio_scenario_totals.items())
        }
    if result.selected_portfolio_scenario is not None:
        payload["selected_portfolio_scenario"] = result.selected_portfolio_scenario.value
    if result.portfolio_scenario_selection is not None:
        payload["portfolio_scenario_selection"] = _branch_metadata_payload(
            result.portfolio_scenario_selection
        )
    return payload


def validate_sbm_result_reconciliation(result: SbmCapitalResult) -> None:
    """Raise when a public SBM result does not reconcile to its capital records."""

    _validate_hash("profile_hash", result.profile_hash)
    _validate_hash("input_hash", result.input_hash)

    expected_total = sum(risk_class.selected_capital for risk_class in result.risk_classes)
    if not is_reconciled(result.total_capital, expected_total):
        raise SbmInputError(
            "total capital does not reconcile to risk-class selected capital",
            field="total_capital",
        )

    if result.portfolio_scenario_totals is not None:
        if result.selected_portfolio_scenario is None:
            raise SbmInputError(
                "portfolio scenario totals require selected_portfolio_scenario",
                field="selected_portfolio_scenario",
            )
        portfolio_total_value = result.portfolio_scenario_totals.get(
            result.selected_portfolio_scenario
        )
        if portfolio_total_value is None:
            raise SbmInputError(
                "selected portfolio scenario is missing from portfolio scenario totals",
                field="selected_portfolio_scenario",
            )
        portfolio_total = float(portfolio_total_value)
        if not is_reconciled(result.total_capital, portfolio_total):
            raise SbmInputError(
                "total capital does not reconcile to selected portfolio scenario total",
                field="total_capital",
            )

    for risk_class in result.risk_classes:
        _validate_risk_class_reconciliation(risk_class, result.selected_portfolio_scenario)


def _validate_risk_class_reconciliation(
    risk_class: RiskClassCapital,
    selected_portfolio_scenario: SbmScenarioLabel | None = None,
) -> None:
    if risk_class.scenario_totals is None or risk_class.selected_scenario is None:
        raise SbmInputError(
            "risk-class capital must include scenario totals and selected scenario",
            field="risk_classes",
        )

    selected_total = float(risk_class.scenario_totals[risk_class.selected_scenario])
    if not is_reconciled(risk_class.selected_capital, selected_total):
        raise SbmInputError(
            "selected risk-class capital does not reconcile to selected scenario total",
            field="selected_capital",
        )

    if selected_portfolio_scenario is not None:
        if risk_class.selected_scenario is not selected_portfolio_scenario:
            raise SbmInputError(
                "risk-class selected scenario must match portfolio scenario selection",
                field="selected_scenario",
            )


def _validate_hash(field: str, value: str) -> None:
    if not isinstance(value, str) or len(value) != _HASH_HEX_LENGTH:
        raise SbmInputError("hash must be a sha256 hex digest", field=field)
    try:
        int(value, 16)
    except ValueError as exc:
        raise SbmInputError("hash must be a sha256 hex digest", field=field) from exc


def _risk_class_payload(risk_class: RiskClassCapital) -> dict[str, object]:
    payload: dict[str, object] = {
        "risk_class": risk_class.risk_class.value,
        "selected_capital": risk_class.selected_capital,
        "citation_ids": list(risk_class.citation_ids),
        "buckets": [_bucket_payload(bucket) for bucket in risk_class.buckets],
    }
    if risk_class.risk_measure is not None:
        payload["risk_measure"] = risk_class.risk_measure.value
    if risk_class.scenario_totals is not None:
        payload["scenario_totals"] = {
            label.value: total for label, total in sorted(risk_class.scenario_totals.items())
        }
    if risk_class.selected_scenario is not None:
        payload["selected_scenario"] = risk_class.selected_scenario.value
    if risk_class.scenario_details:
        payload["scenario_details"] = [
            _scenario_detail_payload(detail) for detail in risk_class.scenario_details
        ]
    if risk_class.scenario_selection is not None:
        payload["scenario_selection"] = _branch_metadata_payload(risk_class.scenario_selection)
    if risk_class.curvature_branches:
        payload["curvature_branches"] = [
            _curvature_branch_payload(branch) for branch in risk_class.curvature_branches
        ]
    if risk_class.curvature_bucket_branches:
        payload["curvature_bucket_branches"] = [
            _curvature_bucket_branch_payload(branch)
            for branch in risk_class.curvature_bucket_branches
        ]
    return payload


def _scenario_detail_payload(detail: RiskClassScenarioDetail) -> dict[str, object]:
    return {
        "scenario": detail.scenario.value,
        "capital": detail.capital,
        "alternative_sb_used": detail.alternative_sb_used,
        "inter_bucket_correlations": [
            {"bucket_a": bucket_a, "bucket_b": bucket_b, "correlation": correlation}
            for bucket_a, bucket_b, correlation in detail.inter_bucket_correlations
        ],
        "intra_buckets": [
            _intra_bucket_scenario_payload(bucket) for bucket in detail.intra_buckets
        ],
        "citation_ids": list(detail.citation_ids),
    }


def _intra_bucket_scenario_payload(bucket: IntraBucketScenarioRecord) -> dict[str, object]:
    payload: dict[str, object] = {
        "bucket_id": bucket.bucket_id,
        "kb": bucket.kb,
        "sb": bucket.sb,
        "floor_applied": bucket.floor_applied,
        "citation_ids": list(bucket.citation_ids),
        "pairwise_correlations": [
            {
                "sensitivity_a": pair.sensitivity_a,
                "sensitivity_b": pair.sensitivity_b,
                "correlation": pair.correlation,
            }
            for pair in bucket.pairwise_correlations
        ],
    }
    if bucket.pairwise_correlation_summary is not None:
        payload["pairwise_correlation_summary"] = _pairwise_correlation_summary_payload(
            bucket.pairwise_correlation_summary
        )
    return payload


def _pairwise_correlation_summary_payload(
    summary: PairwiseCorrelationSummary | None,
) -> dict[str, object] | None:
    if summary is None:
        return None
    return {
        "evidence_mode": summary.evidence_mode.value,
        "total_count": summary.total_count,
        "materialized_count": summary.materialized_count,
        "omitted_count": summary.omitted_count,
        "factor_ids": list(summary.factor_ids),
    }


def _branch_metadata_payload(branch: SbmBranchMetadata) -> dict[str, object]:
    return {
        "branch_id": branch.branch_id,
        "branch_type": branch.branch_type.value,
        "source_id": branch.source_id,
        "selected": branch.selected,
        "reason": branch.reason,
        "citation_ids": list(branch.citation_ids),
    }


def _curvature_branch_payload(branch: CurvatureBranchRecord) -> dict[str, object]:
    return {
        "sensitivity_id": branch.sensitivity_id,
        "selected_branch": branch.selected_branch,
        "up_shock_amount": branch.up_shock_amount,
        "down_shock_amount": branch.down_shock_amount,
        "citation_ids": list(branch.citation_ids),
    }


def _curvature_bucket_branch_payload(
    branch: CurvatureBucketBranchRecord,
) -> dict[str, object]:
    return {
        "bucket_id": branch.bucket_id,
        "scenario": branch.scenario.value,
        "selected_branch": branch.selected_branch,
        "rejected_branch": branch.rejected_branch,
        "selected_bucket_capital": branch.selected_bucket_capital,
        "rejected_bucket_capital": branch.rejected_bucket_capital,
        "up_bucket_capital": branch.up_bucket_capital,
        "down_bucket_capital": branch.down_bucket_capital,
        "selected_sum": branch.selected_sum,
        "up_sum": branch.up_sum,
        "down_sum": branch.down_sum,
        "selected_psi_zero_count": branch.selected_psi_zero_count,
        "up_psi_zero_count": branch.up_psi_zero_count,
        "down_psi_zero_count": branch.down_psi_zero_count,
        "floor_applied": branch.floor_applied,
        "citation_ids": list(branch.citation_ids),
    }


def _run_context_payload(context: SbmRunContextSummary) -> dict[str, object]:
    payload: dict[str, object] = {
        "run_id": context.run_id,
        "calculation_date": context.calculation_date.isoformat(),
        "base_currency": context.base_currency,
        "reporting_currency": context.reporting_currency,
    }
    calculation_scope = scope_payload(context.calculation_scope)
    if calculation_scope is not None:
        payload["calculation_scope"] = calculation_scope
    return payload


def _bucket_payload(bucket: BucketCapital) -> dict[str, object]:
    payload: dict[str, object] = {
        "bucket_id": bucket.bucket_id,
        "risk_class": bucket.risk_class.value,
        "risk_measure": bucket.risk_measure.value,
        "kb": bucket.kb,
        "citation_ids": list(bucket.citation_ids),
        "weighted_sensitivities": [
            _weighted_sensitivity_payload(item) for item in bucket.weighted_sensitivities
        ],
        "floor_applied": bucket.floor_applied,
    }
    if bucket.sb is not None:
        payload["sb"] = bucket.sb
    if bucket.scenario is not None:
        payload["scenario"] = bucket.scenario.value
    return payload


def _weighted_sensitivity_payload(item: WeightedSensitivity) -> dict[str, object]:
    payload: dict[str, object] = {
        "sensitivity_id": item.sensitivity_id,
        "risk_class": item.risk_class.value,
        "risk_measure": item.risk_measure.value,
        "bucket": item.bucket,
        "raw_amount": item.raw_amount,
        "risk_weight": item.risk_weight,
        "scaled_amount": item.scaled_amount,
        "citation_ids": list(item.citation_ids),
    }
    if item.qualifier is not None:
        payload["qualifier"] = item.qualifier
    if item.factor_key:
        payload["factor_key"] = list(item.factor_key)
    if item.contributing_sensitivity_ids:
        payload["contributing_sensitivity_ids"] = list(item.contributing_sensitivity_ids)
    if item.contributing_source_row_ids:
        payload["contributing_source_row_ids"] = list(item.contributing_source_row_ids)
    org_scope = scope_payload(item.org_scope)
    if org_scope is not None:
        payload["org_scope"] = org_scope
    if item.contributing_org_scopes:
        contributing_scopes: list[dict[str, object]] = []
        for scope in item.contributing_org_scopes:
            scope_record = scope_payload(scope)
            if scope_record is not None:
                contributing_scopes.append(scope_record)
        payload["contributing_org_scopes"] = contributing_scopes
    if item.risk_factor_id is not None:
        payload["risk_factor_id"] = item.risk_factor_id
    if item.risk_factor_mapping_version is not None:
        payload["risk_factor_mapping_version"] = item.risk_factor_mapping_version
    if item.bucket_label is not None:
        payload["bucket_label"] = item.bucket_label
    if item.source_system is not None:
        payload["source_system"] = item.source_system
    if item.source_row_id is not None:
        payload["source_row_id"] = item.source_row_id
    return payload


def _reconciliation_payload(
    reconciliation: SbmReconciliationMetadata | None,
) -> dict[str, object] | None:
    if reconciliation is None:
        return None
    return {
        "input_count": reconciliation.input_count,
        "rejected_input_count": reconciliation.rejected_input_count,
        "requirement_ids": list(reconciliation.requirement_ids),
        "citation_ids": list(reconciliation.citation_ids),
    }


__all__ = [
    "input_hash_for_sensitivities",
    "serialize_sbm_result",
    "validate_sbm_result_reconciliation",
]
