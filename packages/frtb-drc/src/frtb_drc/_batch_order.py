"""Deterministic ordering helpers for DRC package-owned batches."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from frtb_drc.batch import DrcPositionBatch


def sorted_position_indices(batch: DrcPositionBatch) -> tuple[int, ...]:
    """Return row indices sorted by stable DRC position identity.

    Parameters
    ----------
    batch : DrcPositionBatch
        Package-owned DRC batch with position and source row identifiers.

    Returns
    -------
    tuple[int, ...]
        Row indices ordered by ``position_id`` and ``source_row_id``.
    """

    return tuple(
        sorted(
            range(batch.row_count),
            key=lambda index: (
                cast(str, batch.position_ids[index]),
                cast(str, batch.source_row_ids[index]),
            ),
        )
    )


__all__ = ["sorted_position_indices"]
