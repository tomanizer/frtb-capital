"""Shared DRC-local helpers for netting-adjacent package paths."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import TypeVar

from frtb_drc._identifiers import slug_path
from frtb_drc._validation_utils import require_finite_non_negative
from frtb_drc.data_models import NetJtd, RejectedOffset
from frtb_drc.validation import DrcInputError

T = TypeVar("T")


def bounded_rejected_group_offsets(
    *,
    bucket_key: str,
    long_groups: Mapping[str, Sequence[T]],
    short_groups: Mapping[str, Sequence[T]],
    rejection_id_prefix: str,
    sequence: Iterator[int],
    representative: Callable[[Sequence[T]], str],
    reason_code: str,
    citations: tuple[str, ...],
) -> tuple[RejectedOffset, ...]:
    """Build rejected offsets for non-exact long/short group pairings."""

    rejected: list[RejectedOffset] = []
    sorted_short_groups = sorted(short_groups)
    for long_group, long_items in sorted(long_groups.items()):
        candidate_short_group = next(
            (item for item in sorted_short_groups if item != long_group), None
        )
        if candidate_short_group is None:
            continue
        rejected.append(
            RejectedOffset(
                rejection_id=f"{rejection_id_prefix}-{slug_path(bucket_key)}-{next(sequence)}",
                long_source_id=representative(long_items),
                short_source_id=representative(short_groups[candidate_short_group]),
                reason_code=reason_code,
                citations=citations,
            )
        )
    covered_short_source_ids = {record.short_source_id for record in rejected}
    sorted_long_groups = sorted(long_groups)
    for short_group, short_items in sorted(short_groups.items()):
        short_source_id = representative(short_items)
        if short_source_id in covered_short_source_ids:
            continue
        candidate_long_group = next(
            (item for item in sorted_long_groups if item != short_group), None
        )
        if candidate_long_group is None:
            continue
        rejected.append(
            RejectedOffset(
                rejection_id=f"{rejection_id_prefix}-{slug_path(bucket_key)}-{next(sequence)}",
                long_source_id=representative(long_groups[candidate_long_group]),
                short_source_id=short_source_id,
                reason_code=reason_code,
                citations=citations,
            )
        )
    return tuple(rejected)


def risk_weights_for_net_jtd(
    net_jtd: NetJtd,
    *,
    risk_weights: Mapping[str, object],
    field_name: str,
    position_label: str = "",
) -> set[float]:
    """Return the distinct supplied risk weights needed by a net JTD record."""

    weights: set[float] = set()
    for position_id in net_jtd.position_ids:
        try:
            raw_risk_weight = risk_weights[position_id]
        except KeyError as exc:
            label = f"{position_label} " if position_label else ""
            raise DrcInputError(
                f"{field_name} is required for {label}position {position_id}"
            ) from exc
        weights.add(
            require_finite_non_negative(
                raw_risk_weight,
                f"{field_name}[{position_id!r}]",
            )
        )
    return weights


__all__ = ["bounded_rejected_group_offsets", "risk_weights_for_net_jtd"]
