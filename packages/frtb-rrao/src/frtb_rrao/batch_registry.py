"""RRAO batch ingress field registry."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from frtb_rrao.data_models import RraoPosition


@dataclass(frozen=True)
class RraoBatchPositionColumnSpec:
    """Projection rule from canonical position rows into batch-builder columns."""

    argument_name: str
    position_value: Callable[[RraoPosition], object]
    arrow_column_name: str | None = None


@dataclass(frozen=True)
class RraoBatchSpec:
    """Shared RRAO batch ingress contract for position and Arrow adapters."""

    name: str
    position_columns: tuple[RraoBatchPositionColumnSpec, ...]
    arrow_column_to_argument: Mapping[str, str]

    @property
    def builder_arguments(self) -> tuple[str, ...]:
        """Column-builder keyword names owned by this registry.

        Returns
        -------
        tuple[str, ...]
            Keyword argument names accepted by ``build_rrao_batch_from_columns``.
        """
        return tuple(spec.argument_name for spec in self.position_columns)


def rrao_position_column_kwargs(
    positions: Sequence[RraoPosition],
) -> dict[str, list[object]]:
    """Return column-builder keyword arguments for canonical positions.

    Parameters
    ----------
    positions : Sequence[RraoPosition]
        Validated canonical positions to project into batch columns.

    Returns
    -------
    dict[str, list[object]]
        Keyword arguments for ``build_rrao_batch_from_columns``.
    """

    return {
        spec.argument_name: [spec.position_value(position) for position in positions]
        for spec in RRAO_BATCH_POSITION_COLUMN_SPECS
    }


def _lineage_source_system(position: RraoPosition) -> str:
    return "" if position.lineage is None else position.lineage.source_system


def _lineage_source_file(position: RraoPosition) -> str:
    return "" if position.lineage is None else position.lineage.source_file


def _lineage_source_row_id(position: RraoPosition) -> str:
    return "" if position.lineage is None else position.lineage.source_row_id


def _source_column_map(position: RraoPosition) -> tuple[tuple[str, str], ...]:
    return () if position.lineage is None else tuple(position.lineage.source_column_map)


def _investment_fund_id(position: RraoPosition) -> str | None:
    if position.investment_fund_descriptor is None:
        return None
    return position.investment_fund_descriptor.fund_id


def _investment_fund_section_205_method(position: RraoPosition) -> str | None:
    if position.investment_fund_descriptor is None:
        return None
    return position.investment_fund_descriptor.section_205_method.value


def _investment_fund_included_exposure_type(position: RraoPosition) -> str | None:
    if position.investment_fund_descriptor is None:
        return None
    return position.investment_fund_descriptor.included_exposure_type.value


def _investment_fund_mandate_evidence_id(position: RraoPosition) -> str | None:
    if position.investment_fund_descriptor is None:
        return None
    return position.investment_fund_descriptor.mandate_evidence_id


def _investment_fund_section_205_evidence_id(position: RraoPosition) -> str | None:
    if position.investment_fund_descriptor is None:
        return None
    return position.investment_fund_descriptor.section_205_evidence_id


def _investment_fund_gross_effective_notional(position: RraoPosition) -> float | None:
    if position.investment_fund_descriptor is None:
        return None
    return position.investment_fund_descriptor.fund_gross_effective_notional


def _investment_fund_included_exposure_ratio(position: RraoPosition) -> float | None:
    if position.investment_fund_descriptor is None:
        return None
    return position.investment_fund_descriptor.included_exposure_ratio


def _investment_fund_look_through_available(position: RraoPosition) -> bool:
    if position.investment_fund_descriptor is None:
        return False
    return position.investment_fund_descriptor.look_through_available


def _investment_fund_mandate_allows_rrao_exposures(position: RraoPosition) -> bool:
    if position.investment_fund_descriptor is None:
        return True
    return position.investment_fund_descriptor.mandate_allows_rrao_exposures


def _classification_hint(position: RraoPosition) -> str | None:
    if position.classification_hint is None:
        return None
    return position.classification_hint.value


def _exclusion_reason(position: RraoPosition) -> str | None:
    if position.exclusion_reason is None:
        return None
    return position.exclusion_reason.value


def _back_to_back_match_group_id(position: RraoPosition) -> str | None:
    if position.back_to_back_match is None:
        return None
    return position.back_to_back_match.match_group_id


def _back_to_back_matched_position_id(position: RraoPosition) -> str | None:
    if position.back_to_back_match is None:
        return None
    return position.back_to_back_match.matched_position_id


RRAO_BATCH_POSITION_COLUMN_SPECS: tuple[RraoBatchPositionColumnSpec, ...] = (
    RraoBatchPositionColumnSpec(
        "position_ids", lambda position: position.position_id, "position_id"
    ),
    RraoBatchPositionColumnSpec(
        "source_row_ids",
        lambda position: position.source_row_id,
        "source_row_id",
    ),
    RraoBatchPositionColumnSpec("desk_ids", lambda position: position.desk_id, "desk_id"),
    RraoBatchPositionColumnSpec(
        "legal_entities",
        lambda position: position.legal_entity,
        "legal_entity",
    ),
    RraoBatchPositionColumnSpec(
        "gross_effective_notionals",
        lambda position: position.gross_effective_notional,
        "gross_effective_notional",
    ),
    RraoBatchPositionColumnSpec("currencies", lambda position: position.currency, "currency"),
    RraoBatchPositionColumnSpec(
        "evidence_types",
        lambda position: position.evidence_type.value,
        "evidence_type",
    ),
    RraoBatchPositionColumnSpec(
        "evidence_labels",
        lambda position: position.evidence_label,
        "evidence_label",
    ),
    RraoBatchPositionColumnSpec(
        "classification_hints", _classification_hint, "classification_hint"
    ),
    RraoBatchPositionColumnSpec("exclusion_reasons", _exclusion_reason, "exclusion_reason"),
    RraoBatchPositionColumnSpec(
        "exclusion_evidence_ids",
        lambda position: position.exclusion_evidence_id,
        "exclusion_evidence_id",
    ),
    RraoBatchPositionColumnSpec(
        "back_to_back_match_group_ids",
        _back_to_back_match_group_id,
        "back_to_back_match_group_id",
    ),
    RraoBatchPositionColumnSpec(
        "back_to_back_matched_position_ids",
        _back_to_back_matched_position_id,
        "back_to_back_matched_position_id",
    ),
    RraoBatchPositionColumnSpec(
        "supervisor_directive_ids",
        lambda position: position.supervisor_directive_id,
        "supervisor_directive_id",
    ),
    RraoBatchPositionColumnSpec(
        "underlying_counts",
        lambda position: position.underlying_count,
        "underlying_count",
    ),
    RraoBatchPositionColumnSpec(
        "is_path_dependents",
        lambda position: position.is_path_dependent,
        "is_path_dependent",
    ),
    RraoBatchPositionColumnSpec(
        "has_maturities",
        lambda position: position.has_maturity,
        "has_maturity",
    ),
    RraoBatchPositionColumnSpec(
        "has_strike_or_barriers",
        lambda position: position.has_strike_or_barrier,
        "has_strike_or_barrier",
    ),
    RraoBatchPositionColumnSpec(
        "has_multiple_strikes_or_barriers",
        lambda position: position.has_multiple_strikes_or_barriers,
        "has_multiple_strikes_or_barriers",
    ),
    RraoBatchPositionColumnSpec(
        "is_ctp_hedges", lambda position: position.is_ctp_hedge, "is_ctp_hedge"
    ),
    RraoBatchPositionColumnSpec(
        "is_investment_fund_exposures",
        lambda position: position.is_investment_fund_exposure,
        "is_investment_fund_exposure",
    ),
    RraoBatchPositionColumnSpec("investment_fund_ids", _investment_fund_id, "investment_fund_id"),
    RraoBatchPositionColumnSpec(
        "investment_fund_section_205_methods",
        _investment_fund_section_205_method,
        "investment_fund_section_205_method",
    ),
    RraoBatchPositionColumnSpec(
        "investment_fund_included_exposure_types",
        _investment_fund_included_exposure_type,
        "investment_fund_included_exposure_type",
    ),
    RraoBatchPositionColumnSpec(
        "investment_fund_mandate_evidence_ids",
        _investment_fund_mandate_evidence_id,
        "investment_fund_mandate_evidence_id",
    ),
    RraoBatchPositionColumnSpec(
        "investment_fund_section_205_evidence_ids",
        _investment_fund_section_205_evidence_id,
        "investment_fund_section_205_evidence_id",
    ),
    RraoBatchPositionColumnSpec(
        "investment_fund_gross_effective_notionals",
        _investment_fund_gross_effective_notional,
        "investment_fund_gross_effective_notional",
    ),
    RraoBatchPositionColumnSpec(
        "investment_fund_included_exposure_ratios",
        _investment_fund_included_exposure_ratio,
        "investment_fund_included_exposure_ratio",
    ),
    RraoBatchPositionColumnSpec(
        "investment_fund_look_through_availables",
        _investment_fund_look_through_available,
        "investment_fund_look_through_available",
    ),
    RraoBatchPositionColumnSpec(
        "investment_fund_mandate_allows_rrao_exposures",
        _investment_fund_mandate_allows_rrao_exposures,
        "investment_fund_mandate_allows_rrao_exposures",
    ),
    RraoBatchPositionColumnSpec(
        "notional_sources",
        lambda position: position.notional_source,
        "notional_source",
    ),
    RraoBatchPositionColumnSpec(
        "lineage_source_systems",
        _lineage_source_system,
        "lineage_source_system",
    ),
    RraoBatchPositionColumnSpec(
        "lineage_source_files",
        _lineage_source_file,
        "lineage_source_file",
    ),
    RraoBatchPositionColumnSpec(
        "lineage_source_row_ids",
        _lineage_source_row_id,
        "lineage_source_row_id",
    ),
    RraoBatchPositionColumnSpec(
        "lineage_present",
        lambda position: position.lineage is not None,
    ),
    RraoBatchPositionColumnSpec("source_column_maps", _source_column_map),
    RraoBatchPositionColumnSpec("citations", lambda position: position.citations),
)


def _arrow_column_to_argument() -> Mapping[str, str]:
    return MappingProxyType(
        {
            spec.arrow_column_name: spec.argument_name
            for spec in RRAO_BATCH_POSITION_COLUMN_SPECS
            if spec.arrow_column_name is not None
        }
    )


RRAO_BATCH_SPEC = RraoBatchSpec(
    name="rrao_position",
    position_columns=RRAO_BATCH_POSITION_COLUMN_SPECS,
    arrow_column_to_argument=_arrow_column_to_argument(),
)

__all__ = [
    "RRAO_BATCH_POSITION_COLUMN_SPECS",
    "RRAO_BATCH_SPEC",
    "RraoBatchPositionColumnSpec",
    "RraoBatchSpec",
    "rrao_position_column_kwargs",
]
