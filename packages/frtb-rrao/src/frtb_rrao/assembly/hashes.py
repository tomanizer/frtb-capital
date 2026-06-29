"""RRAO batch input hash assembly stage."""

from __future__ import annotations

from typing import Any

from frtb_rrao.assembly.payloads import batch_position_payload, hash_position_payloads

INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2 = "arrow-columnar-v2"
INPUT_HASH_ALGORITHM_JSON_ROW_V1 = "json-row-v1"


def input_hash_for_rrao_batch(batch: Any) -> str:
    """Hash canonical RRAO batch inputs in deterministic input order.

    Parameters
    ----------
    batch : RraoPositionBatch
        Canonical RRAO position batch.

    Returns
    -------
    str
        Deterministic aggregate input hash.
    """

    return hash_position_payloads(
        _position_payload_for_hash(batch, index) for index in range(batch.row_count)
    )


def _position_payload_for_hash(batch: Any, index: int) -> dict[str, object]:
    return batch_position_payload(
        position_id=batch.position_ids[index],
        source_row_id=batch.source_row_ids[index],
        desk_id=batch.desk_ids[index],
        legal_entity=batch.legal_entities[index],
        gross_effective_notional=batch.gross_effective_notionals[index],
        currency=batch.currencies[index],
        evidence_type=batch.evidence_types[index],
        evidence_label=batch.evidence_labels[index],
        lineage_source_system=batch.lineage_source_systems[index],
        lineage_source_file=batch.lineage_source_files[index],
        lineage_source_row_id=batch.lineage_source_row_ids[index],
        source_column_map=batch.source_column_maps[index],
        classification_hint=batch.classification_hints[index],
        exclusion_reason=batch.exclusion_reasons[index],
        exclusion_evidence_id=batch.exclusion_evidence_ids[index],
        supervisor_directive_id=batch.supervisor_directive_ids[index],
        underlying_count=batch.underlying_counts[index],
        is_path_dependent=batch.is_path_dependents[index],
        has_maturity=batch.has_maturities[index],
        has_strike_or_barrier=batch.has_strike_or_barriers[index],
        has_multiple_strikes_or_barriers=batch.has_multiple_strikes_or_barriers[index],
        is_ctp_hedge=batch.is_ctp_hedges[index],
        is_investment_fund_exposure=batch.is_investment_fund_exposures[index],
        investment_fund_id=batch.investment_fund_ids[index],
        investment_fund_section_205_method=batch.investment_fund_section_205_methods[index],
        investment_fund_included_exposure_type=batch.investment_fund_included_exposure_types[index],
        investment_fund_mandate_evidence_id=batch.investment_fund_mandate_evidence_ids[index],
        investment_fund_section_205_evidence_id=(
            batch.investment_fund_section_205_evidence_ids[index]
        ),
        investment_fund_gross_effective_notional=(
            batch.investment_fund_gross_effective_notionals[index]
        ),
        investment_fund_included_exposure_ratio=(
            batch.investment_fund_included_exposure_ratios[index]
        ),
        investment_fund_look_through_available=(
            batch.investment_fund_look_through_availables[index]
        ),
        investment_fund_mandate_allows_rrao_exposures=(
            batch.investment_fund_mandate_allows_rrao_exposures[index]
        ),
        notional_source=batch.notional_sources[index],
        citations=batch.citations[index],
        back_to_back_match_group_id=batch.back_to_back_match_group_ids[index],
        back_to_back_matched_position_id=batch.back_to_back_matched_position_ids[index],
    )


__all__ = [
    "INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2",
    "INPUT_HASH_ALGORITHM_JSON_ROW_V1",
    "input_hash_for_rrao_batch",
]
