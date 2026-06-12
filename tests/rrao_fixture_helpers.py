"""Shared test-only helpers for RRAO fixtures and data models."""

from __future__ import annotations

from frtb_rrao import RraoSourceLineage

RRAO_SOURCE_COLUMN_MAP = (
    ("RiskType", "evidence_type"),
    ("AmountUSD", "gross_effective_notional"),
)


def sample_rrao_lineage(
    row_id: str = "row-001",
    *,
    source_file: str = "rrao.csv",
    source_column_map: tuple[tuple[str, str], ...] = RRAO_SOURCE_COLUMN_MAP,
) -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="synthetic-risk",
        source_file=source_file,
        source_row_id=row_id,
        source_column_map=source_column_map,
    )
