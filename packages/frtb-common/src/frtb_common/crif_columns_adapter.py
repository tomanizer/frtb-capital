"""CRIF source-column discovery and mapping validation helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

import pyarrow as pa  # type: ignore[import-untyped]

from frtb_common.arrow_table import NormalizedTableError, TabularLogicalType
from frtb_common.crif_types import (
    CRIF_RISK_TYPE_COLUMN,
    CrifColumnSpec,
    CrifRiskTypeMapping,
    _column_key,
)


def resolve_crif_column_name(table: pa.Table, aliases: Sequence[str]) -> str | None:
    """Resolve a source column by CRIF aliases using case/spacing-insensitive matching.

    Parameters
    ----------
    table : pyarrow.Table
        Source CRIF-like Arrow table.
    aliases : sequence of str
        Candidate header aliases to match.

    Returns
    -------
    str or None
        Matching input column name, or ``None`` when no alias matches.
    """

    if not isinstance(table, pa.Table):
        raise TypeError("table must be a pyarrow.Table")
    if not aliases:
        raise NormalizedTableError("at least one CRIF alias is required")
    by_key: dict[str, list[str]] = {}
    for column_name in table.column_names:
        by_key.setdefault(_column_key(column_name), []).append(column_name)
    matches: list[str] = []
    for alias in aliases:
        matches.extend(by_key.get(_column_key(alias), ()))
    unique_matches = tuple(dict.fromkeys(matches))
    if len(unique_matches) > 1:
        raise NormalizedTableError(
            f"CRIF aliases {tuple(aliases)!r} match multiple input columns: {unique_matches!r}"
        )
    return unique_matches[0] if unique_matches else None


def _validate_crif_column_specs(
    column_specs: Sequence[CrifColumnSpec],
) -> tuple[CrifColumnSpec, ...]:
    specs = tuple(column_specs)
    seen_targets: set[str] = set()
    for spec in specs:
        if spec.name in seen_targets:
            raise NormalizedTableError(f"Duplicate CRIF target column {spec.name!r}")
        seen_targets.add(spec.name)
    return specs


def _risk_mapping_by_type(
    risk_type_mappings: Sequence[CrifRiskTypeMapping],
) -> Mapping[str, Mapping[str, object]]:
    by_type: dict[str, Mapping[str, object]] = {}
    for mapping in risk_type_mappings:
        for source_value in mapping.source_values:
            if source_value in by_type:
                raise NormalizedTableError(
                    f"CRIF RiskType {source_value!r} appears in multiple mappings"
                )
            by_type[source_value] = mapping.output_values
    return MappingProxyType(by_type)


def _resolve_crif_columns(
    table: pa.Table,
    specs: tuple[CrifColumnSpec, ...],
) -> Mapping[str, str]:
    return MappingProxyType(
        {
            spec.name: source_name
            for spec in specs
            if (source_name := resolve_crif_column_name(table, (spec.name, *spec.aliases)))
            is not None
        }
    )


def _can_use_vectorized_static_mapping(specs: tuple[CrifColumnSpec, ...]) -> bool:
    if not any(spec.name == CRIF_RISK_TYPE_COLUMN for spec in specs):
        return False
    supported_types = {
        TabularLogicalType.BOOLEAN,
        TabularLogicalType.FLOAT,
        TabularLogicalType.INTEGER,
        TabularLogicalType.STRING,
    }
    return all(spec.logical_type in supported_types for spec in specs)
