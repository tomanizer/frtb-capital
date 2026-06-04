"""CRIF and vendor-row ingress helpers for DRC.

This adapter is an input boundary: it maps CRIF- or vendor-shaped default-risk
rows into canonical ``DrcPosition`` records and class-specific Arrow tables.
It is deliberately separate from the capital kernels.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from frtb_drc._crif_arrow_adapter import drc_crif_result_to_arrow_tables
from frtb_drc._crif_models import (
    DrcCrifAdapterResult,
    DrcCrifDirectionStrategy,
    DrcRejectedCrifRow,
)
from frtb_drc._crif_position import (
    _accepted_position_from_row,
    _coerce_direction_strategy,
    _require_non_empty,
    _source_hash,
)
from frtb_drc._crif_row import (
    _NormalizedRow,
    _RejectedRowError,
    _rejection_from_error,
)
from frtb_drc._crif_values import _text_or_none
from frtb_drc.data_models import DrcPosition
from frtb_drc.validation import DrcInputError


def adapt_drc_crif_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    source_system: str = "crif",
    source_file: str = "drc-crif.csv",
    direction_strategy: DrcCrifDirectionStrategy | str = DrcCrifDirectionStrategy.EXPLICIT_FIELD,
) -> DrcCrifAdapterResult:
    """Map CRIF/vendor-shaped default-risk rows into canonical DRC positions.

    Parameters
    ----------
    rows:
        Source rows represented as mappings. Field matching is case, separator,
        and whitespace insensitive over the package-owned alias set.
    source_system, source_file:
        Lineage values attached to accepted positions and Arrow tables.
    direction_strategy:
        Explicit source sign convention. ``EXPLICIT_FIELD`` reads a long/short
        field. ``SIGNED_NOTIONAL`` and ``SIGNED_MARKET_VALUE`` derive direction
        from the sign of that numeric field and store magnitudes in canonical
        rows.

    Returns
    -------
    DrcCrifAdapterResult
        Accepted canonical positions, rejected rows, diagnostics, and source
        metadata. Row-level defects are reported in the result rather than
        raising.
    """

    _require_non_empty(source_system, "source_system")
    _require_non_empty(source_file, "source_file")
    strategy = _coerce_direction_strategy(direction_strategy)
    accepted: list[DrcPosition] = []
    rejected: list[DrcRejectedCrifRow] = []
    diagnostics = []
    seen_position_ids: set[str] = set()

    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise DrcInputError(f"CRIF row at index {index} must be a mapping")
        normalized = _NormalizedRow(row)
        source_row_id = _text_or_none(normalized.value("source_row_id")) or f"row-{index + 1}"
        try:
            position = _accepted_position_from_row(
                normalized,
                source_system=source_system,
                source_file=source_file,
                direction_strategy=strategy,
                seen_position_ids=seen_position_ids,
            )
            accepted.append(position)
        except _RejectedRowError as exc:
            rejected_row, diagnostic = _rejection_from_error(
                exc,
                normalized,
                source_row_id=source_row_id,
            )
            rejected.append(rejected_row)
            diagnostics.append(diagnostic)

    return DrcCrifAdapterResult(
        positions=tuple(accepted),
        rejected_rows=tuple(rejected),
        diagnostics=tuple(diagnostics),
        source_hash=_source_hash(
            rows,
            strategy,
            source_system=source_system,
            source_file=source_file,
        ),
        source_system=source_system,
        source_file=source_file,
        direction_strategy=strategy,
    )


__all__ = [
    "DrcCrifAdapterResult",
    "DrcCrifDirectionStrategy",
    "DrcRejectedCrifRow",
    "adapt_drc_crif_rows",
    "drc_crif_result_to_arrow_tables",
]
