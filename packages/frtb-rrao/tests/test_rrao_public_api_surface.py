from __future__ import annotations

import frtb_rrao
import frtb_rrao._payloads as payload_compat
import frtb_rrao._result_assembly as result_compat
import frtb_rrao.assembly.hashes as hash_assembly
import frtb_rrao.assembly.payloads as payload_assembly
import frtb_rrao.assembly.results as result_assembly
import frtb_rrao.batch as batch
import frtb_rrao.validation as validation
from frtb_rrao.validation import position as position_validation

EXPECTED_PUBLIC_API = (
    "PACKAGE_METADATA",
    "RRAO_ARROW_COLUMN_SPECS",
    "SUPPORTED_RRAO_ALLOCATION_DIMENSIONS",
    "RraoAdapterResult",
    "RraoAdapterWarning",
    "RraoAllocationBucket",
    "RraoAllocationDimension",
    "RraoAllocationReport",
    "RraoBackToBackMatch",
    "RraoBatchCapitalCalculation",
    "RraoCalculationContext",
    "RraoCapitalLine",
    "RraoCapitalResult",
    "RraoCitation",
    "RraoClassification",
    "RraoClassificationDecision",
    "RraoEvidenceType",
    "RraoExclusionReason",
    "RraoInputError",
    "RraoInvestmentFundDescriptor",
    "RraoInvestmentFundExposureType",
    "RraoInvestmentFundMethod",
    "RraoPosition",
    "RraoPositionBatch",
    "RraoRegulatoryProfile",
    "RraoRejectedRow",
    "RraoRuleProfile",
    "RraoSourceLineage",
    "RraoSubtotal",
    "__version__",
    "adapt_crif_records",
    "adapt_fnet_records",
    "adapt_rrao_records",
    "build_rrao_allocation_report",
    "build_rrao_allocation_reports",
    "build_rrao_batch_from_arrow",
    "build_rrao_batch_from_columns",
    "build_rrao_batch_from_positions",
    "build_rrao_contribution_bundle",
    "calculate_rrao_attribution",
    "calculate_rrao_capital",
    "calculate_rrao_capital_from_batch",
    "classify_rrao_position",
    "classify_rrao_positions",
    "get_rrao_rule_profile",
    "input_hash_for_positions",
    "input_hash_for_rrao_batch",
    "normalize_rrao_arrow_table",
    "resolve_rrao_allocation_dimension",
    "rrao_allocation_report_to_contributions",
    "serialize_rrao_allocation_report",
    "serialize_rrao_result",
    "to_component_summary",
    "validate_rrao_allocation_report",
    "validate_rrao_positions",
    "validate_rrao_result_reconciliation",
)


def test_top_level_public_api_surface_is_explicit_and_narrow() -> None:
    assert frtb_rrao.__all__ == list(EXPECTED_PUBLIC_API)
    assert len(frtb_rrao.__all__) < 60


def test_validation_package_preserves_public_compatibility_path() -> None:
    assert validation.RraoInputError is position_validation.RraoInputError
    assert (
        validation.normalise_gross_effective_notional
        is position_validation.normalise_gross_effective_notional
    )
    assert validation.validate_rrao_positions is position_validation.validate_rrao_positions


def test_payload_assembly_preserves_private_compatibility_path() -> None:
    assert payload_compat.batch_position_payload is payload_assembly.batch_position_payload
    assert payload_compat.hash_payload is payload_assembly.hash_payload
    assert payload_compat.hash_position_payloads is payload_assembly.hash_position_payloads
    assert payload_compat.position_payload is payload_assembly.position_payload


def test_result_assembly_preserves_private_compatibility_path() -> None:
    assert result_compat.collect_line_citations is result_assembly.collect_line_citations
    assert result_compat.partition_lines is result_assembly.partition_lines
    assert result_compat.profile_warnings is result_assembly.profile_warnings
    assert result_compat.validate_context is result_assembly.validate_context


def test_batch_hash_assembly_preserves_public_compatibility_path() -> None:
    assert batch.input_hash_for_rrao_batch is hash_assembly.input_hash_for_rrao_batch
    assert frtb_rrao.input_hash_for_rrao_batch is hash_assembly.input_hash_for_rrao_batch
