"""Net-JTD array kernels for DRC batch calculation."""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import count
from typing import TYPE_CHECKING, cast

import frtb_common.batch_arrays as _batch_arrays

from frtb_drc._batch_columns import FloatArray, ObjectArray
from frtb_drc._batch_order import sorted_position_indices as _sorted_indices
from frtb_drc._identifiers import slug_path as _slug
from frtb_drc._netting_helpers import (
    bounded_rejected_group_offsets as _bounded_rejected_group_offsets,
)
from frtb_drc._validation_utils import optional_text as _optional_text
from frtb_drc._validation_utils import require_text as _required_text
from frtb_drc.data_models import (
    BranchMetadata,
    BranchType,
    DefaultDirection,
    DrcCalculationContext,
    DrcRiskClass,
    DrcSeniority,
    NetJtd,
    RejectedOffset,
)
from frtb_drc.validation import DrcInputError

if TYPE_CHECKING:
    from frtb_drc.batch import DrcPositionBatch

_SENIORITY_RANK: dict[DrcSeniority, int] = {
    DrcSeniority.COVERED_BOND: 0,
    DrcSeniority.GSE_GUARANTEED: 0,
    DrcSeniority.SENIOR_DEBT: 1,
    DrcSeniority.GSE_ISSUED_NOT_GUARANTEED: 1,
    DrcSeniority.PSE: 1,
    DrcSeniority.NON_SENIOR_DEBT: 2,
    DrcSeniority.EQUITY: 3,
    # ADR 0047 treats the zero-LGD recovery-unlinked category as below equity
    # for same-obligor netting, grounded in US_NPR_210_B_1_IV / BASEL_MAR22_12.
    DrcSeniority.NOT_RECOVERY_LINKED: 4,
}


def calculate_nonsec_net_jtds_from_arrays(
    batch: DrcPositionBatch,
    gross_jtd: FloatArray,
    scaled_jtd: FloatArray,
    *,
    netting_citation: str,
) -> tuple[NetJtd, ...]:
    """Calculate non-securitisation net JTD records from batch arrays.

    Parameters
    ----------
    batch : DrcPositionBatch
        Validated non-securitisation DRC batch.
    gross_jtd : FloatArray
        Gross JTD amounts aligned to the batch rows.
    scaled_jtd : FloatArray
        Maturity-scaled JTD amounts aligned to the batch rows.
    netting_citation : str
        Paragraph-level citation for the active non-securitisation netting rule.

    Returns
    -------
    tuple[NetJtd, ...]
        Deterministically ordered net JTD records with rejected-offset audit metadata.
    """

    grouped: dict[tuple[str, str], list[int]] = {}
    for index in _sorted_indices(batch):
        key = (
            cast(str, batch.bucket_keys[index]),
            cast(str, batch.issuer_ids[index]),
        )
        grouped.setdefault(key, []).append(index)

    net_records: list[NetJtd] = []
    for key in sorted(grouped):
        net_records.extend(
            _net_group(
                batch,
                grouped[key],
                gross_jtd,
                scaled_jtd,
                key=key,
                netting_citation=netting_citation,
            )
        )
    return tuple(net_records)


def calculate_securitisation_non_ctp_net_jtds_from_arrays(
    batch: DrcPositionBatch,
    gross_jtd: FloatArray,
    scaled_jtd: FloatArray,
    *,
    context: DrcCalculationContext,
    netting_citations: tuple[str, ...],
) -> tuple[NetJtd, ...]:
    """Calculate securitisation non-CTP net JTD records from batch arrays.

    Parameters
    ----------
    batch : DrcPositionBatch
        Validated securitisation non-CTP DRC batch.
    gross_jtd : FloatArray
        Gross JTD amounts aligned to the batch rows.
    scaled_jtd : FloatArray
        Maturity-scaled JTD amounts aligned to the batch rows.
    context : DrcCalculationContext
        Run context containing optional replication-group evidence.
    netting_citations : tuple[str, ...]
        Paragraph-level citations for the active securitisation non-CTP netting rules.

    Returns
    -------
    tuple[NetJtd, ...]
        Deterministically ordered net JTD records with rejected-offset audit metadata.
    """

    offset_groups = _securitisation_non_ctp_offset_groups(batch, context=context)
    return _calculate_exact_group_net_jtds_from_arrays(
        batch,
        gross_jtd,
        scaled_jtd,
        offset_groups=offset_groups,
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        seniority_layer="SECURITISATION_TRANCHE",
        net_prefix="sec-non-ctp",
        normal_reason=(
            "securitisation non-CTP netting used same-pool/same-tranche identity "
            "or explicit replication-group evidence"
        ),
        zero_net_reason=(
            "securitisation non-CTP same-pool/same-tranche group fully offset to zero net JTD"
        ),
        emit_zero_net_records=True,
        rejected_reason_code="SEC_NON_CTP_OFFSET_REQUIRES_SAME_POOL_TRANCHE_OR_REPLICATION",
        netting_citations=netting_citations,
    )


def calculate_ctp_net_jtds_from_arrays(
    batch: DrcPositionBatch,
    gross_jtd: FloatArray,
    scaled_jtd: FloatArray,
    *,
    context: DrcCalculationContext,
    netting_citations: tuple[str, ...],
) -> tuple[NetJtd, ...]:
    """Calculate CTP net JTD records from batch arrays.

    Parameters
    ----------
    batch : DrcPositionBatch
        Validated correlation trading portfolio DRC batch.
    gross_jtd : FloatArray
        Gross JTD amounts aligned to the batch rows.
    scaled_jtd : FloatArray
        Maturity-scaled JTD amounts aligned to the batch rows.
    context : DrcCalculationContext
        Run context containing optional replication-group evidence.
    netting_citations : tuple[str, ...]
        Paragraph-level citations for the active CTP netting rules.

    Returns
    -------
    tuple[NetJtd, ...]
        Deterministically ordered net JTD records with rejected-offset audit metadata.
    """

    offset_groups = _ctp_offset_groups(batch, context=context)
    return _calculate_exact_group_net_jtds_from_arrays(
        batch,
        gross_jtd,
        scaled_jtd,
        offset_groups=offset_groups,
        risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        seniority_layer="CTP",
        net_prefix="ctp",
        normal_reason=(
            "CTP netting used exact exposure identity or explicit replication group evidence"
        ),
        zero_net_reason="",
        emit_zero_net_records=False,
        rejected_reason_code="CTP_OFFSET_REQUIRES_EXACT_MATCH_OR_EXPLICIT_REPLICATION",
        netting_citations=netting_citations,
    )


def _calculate_exact_group_net_jtds_from_arrays(
    batch: DrcPositionBatch,
    gross_jtd: FloatArray,
    scaled_jtd: FloatArray,
    *,
    offset_groups: ObjectArray,
    risk_class: DrcRiskClass,
    seniority_layer: str,
    net_prefix: str,
    normal_reason: str,
    zero_net_reason: str,
    emit_zero_net_records: bool,
    rejected_reason_code: str,
    netting_citations: tuple[str, ...],
) -> tuple[NetJtd, ...]:
    grouped: dict[tuple[str, str], list[int]] = {}
    for index in _sorted_indices(batch):
        key = (cast(str, batch.bucket_keys[index]), cast(str, offset_groups[index]))
        grouped.setdefault(key, []).append(index)

    rejected_by_bucket = _rejected_exact_group_offsets(
        batch,
        offset_groups=offset_groups,
        net_prefix=net_prefix,
        rejected_reason_code=rejected_reason_code,
        netting_citations=netting_citations,
    )
    records: list[NetJtd] = []
    for key in sorted(grouped):
        bucket_key, group_key = key
        indices = grouped[key]
        long_indices = [
            index
            for index in indices
            if batch.default_directions[index] == DefaultDirection.LONG.value
        ]
        short_indices = [
            index
            for index in indices
            if batch.default_directions[index] == DefaultDirection.SHORT.value
        ]
        gross_long = math.fsum(float(gross_jtd[index]) for index in long_indices)
        gross_short = math.fsum(float(gross_jtd[index]) for index in short_indices)
        scaled_long = math.fsum(float(scaled_jtd[index]) for index in long_indices)
        scaled_short = math.fsum(float(scaled_jtd[index]) for index in short_indices)
        signed_net = scaled_long - scaled_short
        if signed_net == 0.0:
            if not emit_zero_net_records:
                continue
            reason = zero_net_reason
            direction = DefaultDirection.LONG
        else:
            reason = normal_reason
            direction = DefaultDirection.LONG if signed_net > 0.0 else DefaultDirection.SHORT
        records.append(
            NetJtd(
                net_jtd_id=(
                    f"net-{net_prefix}-{_slug(bucket_key)}-{_slug(group_key)}-"
                    f"{direction.value.lower()}"
                ),
                netting_group_id=f"ng-{net_prefix}-{_slug(bucket_key)}-{_slug(group_key)}",
                risk_class=risk_class,
                bucket_key=bucket_key,
                obligor_or_tranche_key=group_key,
                seniority_layer=seniority_layer,
                gross_long=gross_long,
                gross_short=gross_short,
                scaled_long=scaled_long,
                scaled_short=scaled_short,
                net_amount=abs(signed_net),
                net_direction=direction,
                position_ids=tuple(cast(str, batch.position_ids[index]) for index in indices),
                scaled_jtd_ids=tuple(f"scaled-{batch.position_ids[index]}" for index in indices),
                rejected_offsets=rejected_by_bucket.get(bucket_key, ()),
                branch_metadata=(
                    BranchMetadata(
                        branch_id=f"net-{net_prefix}-{_slug(bucket_key)}-{_slug(group_key)}",
                        branch_type=BranchType.NORMAL,
                        source_id=group_key,
                        selected=True,
                        reason=reason,
                        citations=netting_citations,
                    ),
                ),
            )
        )
    return tuple(records)


def _rejected_exact_group_offsets(
    batch: DrcPositionBatch,
    *,
    offset_groups: ObjectArray,
    net_prefix: str,
    rejected_reason_code: str,
    netting_citations: tuple[str, ...],
) -> dict[str, tuple[RejectedOffset, ...]]:
    grouped: dict[str, list[int]] = {}
    for index in _sorted_indices(batch):
        grouped.setdefault(cast(str, batch.bucket_keys[index]), []).append(index)

    rejected_by_bucket: dict[str, tuple[RejectedOffset, ...]] = {}
    sequence = count(1)
    for bucket_key in sorted(grouped):
        indices = grouped[bucket_key]
        long_groups = _direction_groups(batch, indices, offset_groups, DefaultDirection.LONG)
        short_groups = _direction_groups(batch, indices, offset_groups, DefaultDirection.SHORT)
        rejected = _bounded_rejected_group_offsets(
            bucket_key=bucket_key,
            long_groups=long_groups,
            short_groups=short_groups,
            rejection_id_prefix=f"rej-{net_prefix}",
            sequence=sequence,
            representative=lambda item: _representative_scaled_id(batch, item),
            reason_code=rejected_reason_code,
            citations=netting_citations,
        )
        if rejected:
            rejected_by_bucket[bucket_key] = tuple(rejected)
    return rejected_by_bucket


def _direction_groups(
    batch: DrcPositionBatch,
    indices: Sequence[int],
    offset_groups: ObjectArray,
    direction: DefaultDirection,
) -> dict[str, list[int]]:
    grouped: dict[str, list[int]] = {}
    for index in indices:
        if batch.default_directions[index] == direction.value:
            grouped.setdefault(cast(str, offset_groups[index]), []).append(index)
    return grouped


def _representative_scaled_id(batch: DrcPositionBatch, indices: Sequence[int]) -> str:
    return sorted(f"scaled-{batch.position_ids[index]}" for index in indices)[0]


def _securitisation_non_ctp_offset_groups(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
) -> ObjectArray:
    groups: list[str] = []
    for index in range(batch.row_count):
        position_id = cast(str, batch.position_ids[index])
        explicit = context.securitisation_non_ctp_offset_groups.get(position_id)
        if explicit is not None:
            groups.append(
                _required_text(
                    explicit,
                    f"securitisation_non_ctp_offset_groups[{position_id!r}]",
                )
            )
            continue
        pool_id = _optional_text(batch.issuer_ids[index])
        tranche_id = _optional_text(batch.tranche_ids[index])
        if pool_id is None:
            raise DrcInputError(
                "securitisation non-CTP offsetting requires issuer_id to carry the "
                f"underlying pool id for position {position_id}, unless an explicit "
                "securitisation_non_ctp_offset_group is supplied"
            )
        if tranche_id is None:
            raise DrcInputError(f"securitisation non-CTP position {position_id} has no tranche_id")
        groups.append(f"exact:pool:{pool_id}:tranche:{tranche_id}")
    return _batch_arrays.object_array(groups, copy=True)


def _ctp_offset_groups(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
) -> ObjectArray:
    groups: list[str] = []
    for index in range(batch.row_count):
        position_id = cast(str, batch.position_ids[index])
        explicit = context.ctp_offset_groups.get(position_id)
        if explicit is not None:
            groups.append(_required_text(explicit, f"ctp_offset_groups[{position_id!r}]"))
            continue
        index_series_id = _optional_text(batch.index_series_ids[index])
        tranche_id = _optional_text(batch.tranche_ids[index])
        issuer_id = _optional_text(batch.issuer_ids[index])
        if index_series_id is not None and tranche_id is not None:
            groups.append(f"exact:index:{index_series_id}:tranche:{tranche_id}")
        elif index_series_id is not None:
            groups.append(f"exact:index:{index_series_id}:non-tranched")
        elif issuer_id is not None:
            groups.append(f"exact:single-name:{issuer_id}")
        elif tranche_id is not None:
            groups.append(f"exact:tranche:{tranche_id}")
        else:
            raise DrcInputError(f"CTP position {position_id} has no offset identity")
    return _batch_arrays.object_array(groups, copy=True)


def _net_group(
    batch: DrcPositionBatch,
    indices: list[int],
    gross_jtd: FloatArray,
    scaled_jtd: FloatArray,
    *,
    key: tuple[str, str],
    netting_citation: str,
) -> list[NetJtd]:
    bucket_key, issuer_key = key
    longs = _by_seniority(batch, indices, DefaultDirection.LONG)
    shorts = _by_seniority(batch, indices, DefaultDirection.SHORT)
    short_states = {
        seniority: [
            {
                "index": index,
                "remaining_gross": float(gross_jtd[index]),
                "remaining_scaled": float(scaled_jtd[index]),
            }
            for index in items
        ]
        for seniority, items in shorts.items()
    }
    rejected = _rejected_seniority_offsets(
        batch,
        bucket_key,
        issuer_key,
        longs,
        shorts,
        netting_citation=netting_citation,
    )
    records: list[NetJtd] = []

    for seniority in sorted(longs, key=_seniority_rank):
        long_items = longs[seniority]
        scaled_long = float(sum(float(scaled_jtd[index]) for index in long_items))
        gross_long = float(sum(float(gross_jtd[index]) for index in long_items))
        used_short_scaled = 0.0
        used_short_gross = 0.0
        used_short_items: list[int] = []
        for short_seniority in sorted(shorts, key=_seniority_rank):
            if not _short_can_offset(long_seniority=seniority, short_seniority=short_seniority):
                continue
            remaining_long = scaled_long - used_short_scaled
            if remaining_long <= 0:
                break
            for short_state in short_states.get(short_seniority, ()):
                if remaining_long <= 0:
                    break
                consumed_scaled, consumed_gross = _consume_short_state(short_state, remaining_long)
                if consumed_scaled <= 0:
                    continue
                used_short_scaled += consumed_scaled
                used_short_gross += consumed_gross
                remaining_long -= consumed_scaled
                used_short_items.append(cast(int, short_state["index"]))

        net_amount = scaled_long - used_short_scaled
        if net_amount > 0:
            records.append(
                _net_record(
                    batch,
                    bucket_key=bucket_key,
                    issuer_key=issuer_key,
                    seniority=seniority,
                    direction=DefaultDirection.LONG,
                    gross_long=gross_long,
                    gross_short=used_short_gross,
                    scaled_long=scaled_long,
                    scaled_short=used_short_scaled,
                    net_amount=net_amount,
                    source_indices=(*long_items, *used_short_items),
                    rejected_offsets=rejected,
                )
            )

    for seniority in sorted(shorts, key=_seniority_rank):
        remaining_states = [
            short_state
            for short_state in short_states.get(seniority, ())
            if short_state["remaining_scaled"] > 0
        ]
        if not remaining_states:
            continue
        source_indices = tuple(cast(int, short_state["index"]) for short_state in remaining_states)
        remaining_gross = math.fsum(
            float(short_state["remaining_gross"]) for short_state in remaining_states
        )
        remaining_scaled = math.fsum(
            float(short_state["remaining_scaled"]) for short_state in remaining_states
        )
        records.append(
            _net_record(
                batch,
                bucket_key=bucket_key,
                issuer_key=issuer_key,
                seniority=seniority,
                direction=DefaultDirection.SHORT,
                gross_long=0.0,
                gross_short=remaining_gross,
                scaled_long=0.0,
                scaled_short=remaining_scaled,
                net_amount=remaining_scaled,
                source_indices=source_indices,
                rejected_offsets=rejected,
            )
        )

    return records


def _by_seniority(
    batch: DrcPositionBatch,
    indices: Sequence[int],
    direction: DefaultDirection,
) -> dict[DrcSeniority, list[int]]:
    grouped: dict[DrcSeniority, list[int]] = {}
    for index in indices:
        if DefaultDirection(cast(str, batch.default_directions[index])) == direction:
            grouped.setdefault(DrcSeniority(cast(str, batch.seniorities[index])), []).append(index)
    return grouped


def _consume_short_state(
    short_state: dict[str, float | int],
    requested_scaled: float,
) -> tuple[float, float]:
    remaining_scaled = cast(float, short_state["remaining_scaled"])
    if remaining_scaled <= 0:
        return 0.0, 0.0

    consumed_scaled = min(requested_scaled, remaining_scaled)
    if consumed_scaled <= 0:
        return 0.0, 0.0

    consumed_ratio = consumed_scaled / remaining_scaled
    consumed_gross = cast(float, short_state["remaining_gross"]) * consumed_ratio
    short_state["remaining_scaled"] = remaining_scaled - consumed_scaled
    short_state["remaining_gross"] = cast(float, short_state["remaining_gross"]) - consumed_gross
    return consumed_scaled, consumed_gross


def _net_record(
    batch: DrcPositionBatch,
    *,
    bucket_key: str,
    issuer_key: str,
    seniority: DrcSeniority,
    direction: DefaultDirection,
    gross_long: float,
    gross_short: float,
    scaled_long: float,
    scaled_short: float,
    net_amount: float,
    source_indices: tuple[int, ...],
    rejected_offsets: tuple[RejectedOffset, ...],
) -> NetJtd:
    seniority_label = seniority.value.lower()
    return NetJtd(
        net_jtd_id=f"net-{_slug(bucket_key)}-{_slug(issuer_key)}-{seniority_label}-{direction.value.lower()}",
        netting_group_id=f"ng-{_slug(bucket_key)}-{_slug(issuer_key)}-{seniority_label}",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        bucket_key=bucket_key,
        obligor_or_tranche_key=issuer_key,
        seniority_layer=seniority.value,
        gross_long=gross_long,
        gross_short=gross_short,
        scaled_long=scaled_long,
        scaled_short=scaled_short,
        net_amount=net_amount,
        net_direction=direction,
        position_ids=tuple(cast(str, batch.position_ids[index]) for index in source_indices),
        scaled_jtd_ids=tuple(f"scaled-{batch.position_ids[index]}" for index in source_indices),
        rejected_offsets=rejected_offsets,
    )


def _rejected_seniority_offsets(
    batch: DrcPositionBatch,
    bucket_key: str,
    issuer_key: str,
    longs: dict[DrcSeniority, list[int]],
    shorts: dict[DrcSeniority, list[int]],
    *,
    netting_citation: str,
) -> tuple[RejectedOffset, ...]:
    rejected: list[RejectedOffset] = []
    sequence = count(1)
    for long_seniority, long_items in sorted(
        longs.items(), key=lambda item: _seniority_rank(item[0])
    ):
        for short_seniority, short_items in sorted(
            shorts.items(),
            key=lambda item: _seniority_rank(item[0]),
        ):
            if _short_can_offset(long_seniority=long_seniority, short_seniority=short_seniority):
                continue
            for long_index in long_items:
                for short_index in short_items:
                    rejected.append(
                        RejectedOffset(
                            rejection_id=(
                                f"rej-{_slug(bucket_key)}-{_slug(issuer_key)}-{next(sequence)}"
                            ),
                            long_source_id=f"scaled-{batch.position_ids[long_index]}",
                            short_source_id=f"scaled-{batch.position_ids[short_index]}",
                            reason_code="SHORT_HIGHER_SENIORITY_THAN_LONG",
                            citations=(netting_citation,),
                        )
                    )
    return tuple(rejected)


def _short_can_offset(*, long_seniority: DrcSeniority, short_seniority: DrcSeniority) -> bool:
    return _seniority_rank(short_seniority) >= _seniority_rank(long_seniority)


def _seniority_rank(seniority: DrcSeniority) -> int:
    try:
        return _SENIORITY_RANK[seniority]
    except KeyError as exc:  # pragma: no cover - all enum values are mapped.
        raise DrcInputError(f"missing DRC seniority rank: {seniority.value}") from exc


__all__ = [
    "calculate_ctp_net_jtds_from_arrays",
    "calculate_nonsec_net_jtds_from_arrays",
    "calculate_securitisation_non_ctp_net_jtds_from_arrays",
]
