"""Same-obligor DRC netting."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import count

from frtb_drc.data_models import (
    DefaultDirection,
    DrcRiskClass,
    DrcSeniority,
    GrossJtd,
    MaturityScaledJtd,
    NetJtd,
    RejectedOffset,
)
from frtb_drc.regimes import US_NPR_2_0_PROFILE_ID, ensure_risk_class_supported, get_rule_profile
from frtb_drc.validation import DrcInputError

_NETTING_CITATION = "US_NPR_210_B_2"

_SENIORITY_RANK: dict[DrcSeniority, int] = {
    DrcSeniority.COVERED_BOND: 0,
    DrcSeniority.GSE_GUARANTEED: 0,
    DrcSeniority.SENIOR_DEBT: 1,
    DrcSeniority.GSE_ISSUED_NOT_GUARANTEED: 1,
    DrcSeniority.PSE: 1,
    DrcSeniority.NON_SENIOR_DEBT: 2,
    DrcSeniority.EQUITY: 3,
    DrcSeniority.NOT_RECOVERY_LINKED: 4,
}


@dataclass(frozen=True)
class NettingInput:
    """Input to non-securitisation netting."""

    gross_jtd: GrossJtd
    scaled_jtd: MaturityScaledJtd
    seniority: DrcSeniority


def calculate_net_jtds(
    exposures: Iterable[NettingInput],
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> tuple[NetJtd, ...]:
    """Calculate non-securitisation net JTD records in stable group order."""

    profile = get_rule_profile(profile_id)
    ensure_risk_class_supported(profile, DrcRiskClass.NON_SECURITISATION)
    grouped: dict[tuple[str, str], list[NettingInput]] = {}
    for exposure in exposures:
        _validate_netting_input(exposure)
        key = (exposure.gross_jtd.bucket_key, exposure.gross_jtd.issuer_or_tranche_key)
        grouped.setdefault(key, []).append(exposure)

    net_records: list[NetJtd] = []
    for key in sorted(grouped):
        net_records.extend(_net_group(key, grouped[key]))
    return tuple(net_records)


def _validate_netting_input(exposure: NettingInput) -> None:
    gross = exposure.gross_jtd
    scaled = exposure.scaled_jtd
    if gross.risk_class is not DrcRiskClass.NON_SECURITISATION:
        raise DrcInputError("non-securitisation netting requires non-securitisation gross JTD")
    if gross.gross_jtd_id != scaled.gross_jtd_id:
        raise DrcInputError("gross_jtd_id mismatch between gross and scaled JTD")
    if gross.position_id != scaled.position_id:
        raise DrcInputError("position_id mismatch between gross and scaled JTD")


def _net_group(key: tuple[str, str], exposures: list[NettingInput]) -> list[NetJtd]:
    bucket_key, issuer_key = key
    longs = _by_seniority(exposures, DefaultDirection.LONG)
    shorts = _by_seniority(exposures, DefaultDirection.SHORT)
    available_shorts = {
        seniority: sum(item.scaled_jtd.scaled_jtd for item in items)
        for seniority, items in shorts.items()
    }
    rejected = _rejected_seniority_offsets(bucket_key, issuer_key, longs, shorts)
    records: list[NetJtd] = []

    for seniority in sorted(longs, key=_seniority_rank):
        long_items = longs[seniority]
        scaled_long = sum(item.scaled_jtd.scaled_jtd for item in long_items)
        gross_long = sum(item.gross_jtd.gross_jtd for item in long_items)
        used_short = 0.0
        used_short_items: list[NettingInput] = []
        for short_seniority in sorted(shorts, key=_seniority_rank):
            if not _short_can_offset(long_seniority=seniority, short_seniority=short_seniority):
                continue
            remaining_long = scaled_long - used_short
            if remaining_long <= 0:
                break
            available = available_shorts.get(short_seniority, 0.0)
            if available <= 0:
                continue
            consumed = min(remaining_long, available)
            used_short += consumed
            available_shorts[short_seniority] = available - consumed
            used_short_items.extend(shorts[short_seniority])

        net_amount = scaled_long - used_short
        if net_amount > 0:
            records.append(
                _net_record(
                    bucket_key=bucket_key,
                    issuer_key=issuer_key,
                    seniority=seniority,
                    direction=DefaultDirection.LONG,
                    gross_long=gross_long,
                    gross_short=used_short,
                    scaled_long=scaled_long,
                    scaled_short=used_short,
                    net_amount=net_amount,
                    source_items=(*long_items, *used_short_items),
                    rejected_offsets=tuple(rejected),
                )
            )

    for seniority in sorted(shorts, key=_seniority_rank):
        remaining_short = available_shorts.get(seniority, 0.0)
        if remaining_short <= 0:
            continue
        short_items = shorts[seniority]
        records.append(
            _net_record(
                bucket_key=bucket_key,
                issuer_key=issuer_key,
                seniority=seniority,
                direction=DefaultDirection.SHORT,
                gross_long=0.0,
                gross_short=sum(item.gross_jtd.gross_jtd for item in short_items),
                scaled_long=0.0,
                scaled_short=remaining_short,
                net_amount=remaining_short,
                source_items=tuple(short_items),
                rejected_offsets=tuple(rejected),
            )
        )

    return records


def _by_seniority(
    exposures: list[NettingInput],
    direction: DefaultDirection,
) -> dict[DrcSeniority, list[NettingInput]]:
    grouped: dict[DrcSeniority, list[NettingInput]] = {}
    for exposure in exposures:
        if exposure.gross_jtd.default_direction is direction:
            grouped.setdefault(exposure.seniority, []).append(exposure)
    return grouped


def _net_record(
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
    source_items: tuple[NettingInput, ...],
    rejected_offsets: tuple[RejectedOffset, ...],
) -> NetJtd:
    seniority_label = seniority.value.lower()
    netting_group_id = f"ng-{_slug(bucket_key)}-{_slug(issuer_key)}-{seniority_label}"
    return NetJtd(
        net_jtd_id=f"net-{_slug(bucket_key)}-{_slug(issuer_key)}-{seniority_label}-{direction.value.lower()}",
        netting_group_id=netting_group_id,
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
        position_ids=tuple(item.gross_jtd.position_id for item in source_items),
        scaled_jtd_ids=tuple(item.scaled_jtd.scaled_jtd_id for item in source_items),
        rejected_offsets=rejected_offsets,
    )


def _rejected_seniority_offsets(
    bucket_key: str,
    issuer_key: str,
    longs: dict[DrcSeniority, list[NettingInput]],
    shorts: dict[DrcSeniority, list[NettingInput]],
) -> tuple[RejectedOffset, ...]:
    rejected: list[RejectedOffset] = []
    sequence = count(1)
    sorted_longs = sorted(longs.items(), key=lambda item: _seniority_rank(item[0]))
    sorted_shorts = sorted(shorts.items(), key=lambda item: _seniority_rank(item[0]))
    for long_seniority, long_items in sorted_longs:
        for short_seniority, short_items in sorted_shorts:
            if _short_can_offset(long_seniority=long_seniority, short_seniority=short_seniority):
                continue
            for long_item in long_items:
                for short_item in short_items:
                    rejected.append(
                        RejectedOffset(
                            rejection_id=(
                                f"rej-{_slug(bucket_key)}-{_slug(issuer_key)}-{next(sequence)}"
                            ),
                            long_source_id=long_item.scaled_jtd.scaled_jtd_id,
                            short_source_id=short_item.scaled_jtd.scaled_jtd_id,
                            reason_code="SHORT_HIGHER_SENIORITY_THAN_LONG",
                            citations=(_NETTING_CITATION,),
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


def _slug(value: str) -> str:
    return value.lower().replace(" ", "-").replace("_", "-")
