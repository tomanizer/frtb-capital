"""RRAO batch ingress field registry."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from frtb_rrao import _batch_row_projection as row
from frtb_rrao.data_models import (
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInvestmentFundExposureType,
    RraoInvestmentFundMethod,
    RraoPosition,
)
from frtb_rrao.validation._errors import RraoInputError


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

    columns: dict[str, list[object]] = {
        spec.argument_name: [] for spec in RRAO_BATCH_POSITION_COLUMN_SPECS
    }
    for position in positions:
        for spec in RRAO_BATCH_POSITION_COLUMN_SPECS:
            columns[spec.argument_name].append(spec.position_value(position))
    return columns


def materialize_rrao_positions(positions: object) -> tuple[RraoPosition, ...]:
    """Return canonical row dataclasses after lightweight container/type checks.

    Parameters
    ----------
    positions:
        Candidate iterable of canonical RRAO position dataclasses.

    Returns
    -------
    tuple[RraoPosition, ...]
        Materialized RRAO positions in input order.
    """

    if isinstance(positions, RraoPosition):
        raise RraoInputError("positions must be an iterable of RraoPosition objects")
    try:
        candidates: tuple[object, ...] = tuple(positions)  # type: ignore[arg-type]
    except TypeError as exc:
        raise RraoInputError("positions must be an iterable of RraoPosition objects") from exc
    for candidate in candidates:
        if not isinstance(candidate, RraoPosition):
            raise RraoInputError("positions must contain only RraoPosition objects")
    return candidates  # type: ignore[return-value]


def _investment_fund_section_205_method(position: RraoPosition) -> str | None:
    descriptor = row._investment_fund_descriptor(position)
    if descriptor is None:
        return None
    return row._enum_value(
        descriptor.section_205_method,
        RraoInvestmentFundMethod,
        field="investment_fund_descriptor.section_205_method",
        position=position,
    )


def _investment_fund_included_exposure_type(position: RraoPosition) -> str | None:
    descriptor = row._investment_fund_descriptor(position)
    if descriptor is None:
        return None
    return row._enum_value(
        descriptor.included_exposure_type,
        RraoInvestmentFundExposureType,
        field="investment_fund_descriptor.included_exposure_type",
        position=position,
    )


def _classification_hint(position: RraoPosition) -> str | None:
    if position.classification_hint is None:
        return None
    return row._enum_value(
        position.classification_hint,
        RraoClassification,
        field="classification_hint",
        position=position,
    )


def _exclusion_reason(position: RraoPosition) -> str | None:
    if position.exclusion_reason is None:
        return None
    return row._enum_value(
        position.exclusion_reason,
        RraoExclusionReason,
        field="exclusion_reason",
        position=position,
    )


RRAO_BATCH_POSITION_COLUMN_SPECS: tuple[RraoBatchPositionColumnSpec, ...] = (
    RraoBatchPositionColumnSpec(
        "position_ids",
        lambda position: row._required_row_text(position.position_id, "position_id", position),
        "position_id",
    ),
    RraoBatchPositionColumnSpec(
        "source_row_ids",
        lambda position: row._required_row_text(
            position.source_row_id,
            "source_row_id",
            position,
        ),
        "source_row_id",
    ),
    RraoBatchPositionColumnSpec(
        "desk_ids",
        lambda position: row._required_row_text(position.desk_id, "desk_id", position),
        "desk_id",
    ),
    RraoBatchPositionColumnSpec(
        "legal_entities",
        lambda position: row._required_row_text(
            position.legal_entity,
            "legal_entity",
            position,
        ),
        "legal_entity",
    ),
    RraoBatchPositionColumnSpec(
        "gross_effective_notionals",
        lambda position: position.gross_effective_notional,
        "gross_effective_notional",
    ),
    RraoBatchPositionColumnSpec(
        "currencies",
        lambda position: row._required_row_text(position.currency, "currency", position),
        "currency",
    ),
    RraoBatchPositionColumnSpec(
        "evidence_types",
        lambda position: row._enum_value(
            position.evidence_type,
            RraoEvidenceType,
            field="evidence_type",
            position=position,
        ),
        "evidence_type",
    ),
    RraoBatchPositionColumnSpec(
        "evidence_labels",
        lambda position: row._required_row_text(
            position.evidence_label,
            "evidence_label",
            position,
        ),
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
        row._back_to_back_match_group_id,
        "back_to_back_match_group_id",
    ),
    RraoBatchPositionColumnSpec(
        "back_to_back_matched_position_ids",
        row._back_to_back_matched_position_id,
        "back_to_back_matched_position_id",
    ),
    RraoBatchPositionColumnSpec(
        "supervisor_directive_ids",
        lambda position: position.supervisor_directive_id,
        "supervisor_directive_id",
    ),
    RraoBatchPositionColumnSpec(
        "underlying_counts",
        lambda position: row._optional_row_int(
            position.underlying_count,
            "underlying_count",
            position,
        ),
        "underlying_count",
    ),
    RraoBatchPositionColumnSpec(
        "is_path_dependents",
        lambda position: row._optional_row_bool(
            position.is_path_dependent,
            "is_path_dependent",
            position,
        ),
        "is_path_dependent",
    ),
    RraoBatchPositionColumnSpec(
        "has_maturities",
        lambda position: row._optional_row_bool(position.has_maturity, "has_maturity", position),
        "has_maturity",
    ),
    RraoBatchPositionColumnSpec(
        "has_strike_or_barriers",
        lambda position: row._optional_row_bool(
            position.has_strike_or_barrier,
            "has_strike_or_barrier",
            position,
        ),
        "has_strike_or_barrier",
    ),
    RraoBatchPositionColumnSpec(
        "has_multiple_strikes_or_barriers",
        lambda position: row._optional_row_bool(
            position.has_multiple_strikes_or_barriers,
            "has_multiple_strikes_or_barriers",
            position,
        ),
        "has_multiple_strikes_or_barriers",
    ),
    RraoBatchPositionColumnSpec(
        "is_ctp_hedges",
        lambda position: row._require_row_bool(position.is_ctp_hedge, "is_ctp_hedge", position),
        "is_ctp_hedge",
    ),
    RraoBatchPositionColumnSpec(
        "is_investment_fund_exposures",
        lambda position: row._require_row_bool(
            position.is_investment_fund_exposure,
            "is_investment_fund_exposure",
            position,
        ),
        "is_investment_fund_exposure",
    ),
    RraoBatchPositionColumnSpec(
        "investment_fund_ids",
        row._investment_fund_id,
        "investment_fund_id",
    ),
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
        row._investment_fund_mandate_evidence_id,
        "investment_fund_mandate_evidence_id",
    ),
    RraoBatchPositionColumnSpec(
        "investment_fund_section_205_evidence_ids",
        row._investment_fund_section_205_evidence_id,
        "investment_fund_section_205_evidence_id",
    ),
    RraoBatchPositionColumnSpec(
        "investment_fund_gross_effective_notionals",
        row._investment_fund_gross_effective_notional,
        "investment_fund_gross_effective_notional",
    ),
    RraoBatchPositionColumnSpec(
        "investment_fund_included_exposure_ratios",
        row._investment_fund_included_exposure_ratio,
        "investment_fund_included_exposure_ratio",
    ),
    RraoBatchPositionColumnSpec(
        "investment_fund_look_through_availables",
        row._investment_fund_look_through_available,
        "investment_fund_look_through_available",
    ),
    RraoBatchPositionColumnSpec(
        "investment_fund_mandate_allows_rrao_exposures",
        row._investment_fund_mandate_allows_rrao_exposures,
        "investment_fund_mandate_allows_rrao_exposures",
    ),
    RraoBatchPositionColumnSpec(
        "notional_sources",
        lambda position: row._required_row_text(
            position.notional_source,
            "notional_source",
            position,
        ),
        "notional_source",
    ),
    RraoBatchPositionColumnSpec(
        "lineage_source_systems",
        row._lineage_source_system,
        "lineage_source_system",
    ),
    RraoBatchPositionColumnSpec(
        "lineage_source_files",
        row._lineage_source_file,
        "lineage_source_file",
    ),
    RraoBatchPositionColumnSpec(
        "lineage_source_row_ids",
        row._lineage_source_row_id,
        "lineage_source_row_id",
    ),
    RraoBatchPositionColumnSpec(
        "lineage_present",
        lambda position: position.lineage is not None,
    ),
    RraoBatchPositionColumnSpec("source_column_maps", row._source_column_map),
    RraoBatchPositionColumnSpec("citations", row._citations),
    RraoBatchPositionColumnSpec("org_scopes", lambda position: position.org_scope),
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
    "materialize_rrao_positions",
    "rrao_position_column_kwargs",
]
