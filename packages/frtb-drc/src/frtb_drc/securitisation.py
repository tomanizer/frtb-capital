"""Securitisation non-CTP DRC calculation path."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import count

from frtb_common import jsonable

from frtb_drc.data_models import (
    BranchMetadata,
    BranchType,
    BucketDrc,
    CategoryDrc,
    DefaultDirection,
    DrcCalculationContext,
    DrcPosition,
    DrcRiskClass,
    GrossJtd,
    HedgeBenefitRatio,
    MaturityScaledJtd,
    NetJtd,
    RejectedOffset,
)
from frtb_drc.maturity import scale_gross_jtds
from frtb_drc.reference_data import get_bucket_definition
from frtb_drc.regimes import US_NPR_2_0_PROFILE_ID, ensure_risk_class_supported, get_rule_profile
from frtb_drc.validation import DrcInputError, validate_position

_GROSS_CITATIONS = ("US_NPR_210_C_1", "BASEL_MAR22_27")
_NETTING_CITATIONS = (
    "US_NPR_210_C_2",
    "BASEL_MAR22_28",
    "BASEL_MAR22_29",
    "BASEL_MAR22_30",
)
_BUCKET_CITATIONS = (
    "US_NPR_210_C_3_I_II",
    "US_NPR_210_C_3_III",
    "BASEL_MAR22_31",
    "BASEL_MAR22_32",
    "BASEL_MAR22_33",
    "BASEL_MAR22_34",
)
_HBR_CITATIONS = ("US_NPR_210_A_2_IV_A", "US_NPR_210_C_3_III", "BASEL_MAR22_33")
_CATEGORY_CITATIONS = ("US_NPR_210_C_3_IV", "BASEL_MAR22_35")


@dataclass(frozen=True)
class SecuritisationNonCtpCalculation:
    """Securitisation non-CTP records for integration into the public DRC result."""

    gross_jtds: tuple[GrossJtd, ...]
    maturity_scaled_jtds: tuple[MaturityScaledJtd, ...]
    net_jtds: tuple[NetJtd, ...]
    category: CategoryDrc


@dataclass(frozen=True)
class SecuritisationNonCtpNettingInput:
    """Input needed for securitisation non-CTP offsetting after maturity scaling."""

    position: DrcPosition
    gross_jtd: GrossJtd
    scaled_jtd: MaturityScaledJtd
    offset_group: str


@dataclass(frozen=True)
class SecuritisationNonCtpCapitalInput:
    """Securitisation non-CTP net JTD with the run-supplied risk weight."""

    net_jtd: NetJtd
    risk_weight: float

    def __post_init__(self) -> None:
        _require_finite_non_negative(self.risk_weight, "risk_weight")


def calculate_securitisation_non_ctp_drc(
    positions: Iterable[DrcPosition],
    *,
    context: DrcCalculationContext,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> SecuritisationNonCtpCalculation:
    """Calculate supported securitisation non-CTP DRC for validated positions."""

    profile = get_rule_profile(profile_id)
    ensure_risk_class_supported(profile, DrcRiskClass.SECURITISATION_NON_CTP)
    records = tuple(positions)
    if not records:
        return SecuritisationNonCtpCalculation(
            gross_jtds=(),
            maturity_scaled_jtds=(),
            net_jtds=(),
            category=_zero_securitisation_non_ctp_category(),
        )
    _validate_securitisation_non_ctp_context(records, context=context)
    gross_jtds = tuple(
        calculate_securitisation_non_ctp_gross_jtd(position, profile_id=profile_id)
        for position in records
    )
    scaled_jtds = scale_gross_jtds(
        (
            (gross_jtd, position.maturity_years)
            for gross_jtd, position in zip(gross_jtds, records, strict=True)
        ),
        profile_id=profile_id,
    )
    net_jtds = calculate_securitisation_non_ctp_net_jtds(
        (
            SecuritisationNonCtpNettingInput(
                position=position,
                gross_jtd=gross_jtd,
                scaled_jtd=scaled_jtd,
                offset_group=_offset_group(position, context=context),
            )
            for position, gross_jtd, scaled_jtd in zip(
                records,
                gross_jtds,
                scaled_jtds,
                strict=True,
            )
        ),
        profile_id=profile_id,
    )
    category = calculate_securitisation_non_ctp_category_drc(
        _securitisation_non_ctp_capital_inputs(
            net_jtds,
            risk_weights=context.securitisation_non_ctp_risk_weights,
        ),
        profile_id=profile_id,
    )
    return SecuritisationNonCtpCalculation(
        gross_jtds=gross_jtds,
        maturity_scaled_jtds=scaled_jtds,
        net_jtds=net_jtds,
        category=category,
    )


def calculate_securitisation_non_ctp_gross_jtd(
    position: DrcPosition,
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> GrossJtd:
    """Calculate securitisation non-CTP gross default exposure from market value."""

    validate_position(position)
    profile = get_rule_profile(profile_id)
    ensure_risk_class_supported(profile, DrcRiskClass.SECURITISATION_NON_CTP)
    if DrcRiskClass(position.risk_class) != DrcRiskClass.SECURITISATION_NON_CTP:
        raise DrcInputError("securitisation non-CTP gross JTD requires SECURITISATION_NON_CTP")
    if position.market_value is None:
        raise DrcInputError(
            f"securitisation non-CTP position {position.position_id} requires market_value"
        )
    if position.lgd_override is not None:
        raise DrcInputError(
            "securitisation non-CTP gross JTD uses market value; lgd_override is not supported"
        )

    return GrossJtd(
        gross_jtd_id=f"gross-{position.position_id}",
        position_id=position.position_id,
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        issuer_or_tranche_key=_exposure_key(position),
        bucket_key=_require_text(position.bucket_key, "bucket_key"),
        default_direction=DefaultDirection(position.default_direction),
        lgd_rate=1.0,
        lgd_source=(
            "securitisation non-CTP gross default exposure equals market value; "
            "LGD is embedded in the securitisation risk weight"
        ),
        notional=abs(position.notional),
        pnl_component=0.0,
        gross_jtd=abs(position.market_value),
        citations=_merge_citations((*_GROSS_CITATIONS, *position.citation_ids)),
    )


def calculate_securitisation_non_ctp_net_jtds(
    exposures: Iterable[SecuritisationNonCtpNettingInput],
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> tuple[NetJtd, ...]:
    """Calculate securitisation non-CTP net default exposures in stable order."""

    profile = get_rule_profile(profile_id)
    ensure_risk_class_supported(profile, DrcRiskClass.SECURITISATION_NON_CTP)
    records = tuple(exposures)
    grouped: dict[tuple[str, str], list[SecuritisationNonCtpNettingInput]] = {}
    for exposure in records:
        _validate_securitisation_non_ctp_netting_input(exposure)
        key = (exposure.gross_jtd.bucket_key, exposure.offset_group)
        grouped.setdefault(key, []).append(exposure)

    rejected_by_bucket = _rejected_securitisation_non_ctp_offsets(records)
    net_records: list[NetJtd] = []
    for key in sorted(grouped):
        record = _net_securitisation_non_ctp_group(
            key,
            grouped[key],
            rejected_offsets=rejected_by_bucket.get(key[0], ()),
        )
        if record is not None:
            net_records.append(record)
    return tuple(net_records)


def calculate_securitisation_non_ctp_category_drc(
    inputs: Iterable[SecuritisationNonCtpCapitalInput],
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> CategoryDrc:
    """Calculate securitisation non-CTP category capital from net JTD positions."""

    profile = get_rule_profile(profile_id)
    ensure_risk_class_supported(profile, DrcRiskClass.SECURITISATION_NON_CTP)
    records = tuple(inputs)
    if not records:
        return _zero_securitisation_non_ctp_category()

    grouped: dict[str, list[SecuritisationNonCtpCapitalInput]] = {}
    for record in records:
        grouped.setdefault(record.net_jtd.bucket_key, []).append(record)

    bucket_results = tuple(
        _securitisation_non_ctp_bucket_drc(
            bucket_key=bucket_key,
            records=grouped[bucket_key],
            profile_id=profile_id,
        )
        for bucket_key in sorted(grouped)
    )
    return CategoryDrc(
        category_id="category-drc-securitisation-non-ctp",
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        bucket_results=bucket_results,
        capital=sum(bucket.capital for bucket in bucket_results),
        branch_metadata=(
            BranchMetadata(
                branch_id="category-securitisation-non-ctp-sum",
                branch_type=BranchType.NORMAL,
                source_id=DrcRiskClass.SECURITISATION_NON_CTP.value,
                selected=True,
                reason=(
                    "securitisation non-CTP category DRC is the simple sum of "
                    "bucket-level requirements"
                ),
                citations=_CATEGORY_CITATIONS,
            ),
        ),
    )


def securitisation_non_ctp_context_input_hash(
    input_hash: str,
    *,
    positions: Iterable[DrcPosition],
    context: DrcCalculationContext,
) -> str:
    """Include securitisation non-CTP risk-weight and offset evidence in the input hash."""

    records = tuple(
        position
        for position in positions
        if DrcRiskClass(position.risk_class) == DrcRiskClass.SECURITISATION_NON_CTP
    )
    if not records:
        return input_hash
    position_ids = tuple(sorted(position.position_id for position in records))
    payload = {
        "input_hash": input_hash,
        "securitisation_non_ctp_risk_weights": {
            position_id: context.securitisation_non_ctp_risk_weights[position_id]
            for position_id in position_ids
        },
        "securitisation_non_ctp_offset_groups": {
            position_id: context.securitisation_non_ctp_offset_groups[position_id]
            for position_id in position_ids
            if position_id in context.securitisation_non_ctp_offset_groups
        },
    }
    encoded = bytes(
        json.dumps(jsonable(payload), sort_keys=True, separators=(",", ":")),
        "utf-8",
    )
    return hashlib.sha256(encoded).hexdigest()


def validate_securitisation_non_ctp_context(context: DrcCalculationContext) -> None:
    """Validate securitisation non-CTP context maps without requiring positions."""

    for position_id, risk_weight in context.securitisation_non_ctp_risk_weights.items():
        _require_text(position_id, "securitisation_non_ctp_risk_weights position_id")
        _require_finite_non_negative(
            risk_weight,
            f"securitisation_non_ctp_risk_weights[{position_id!r}]",
        )
    for position_id, offset_group in context.securitisation_non_ctp_offset_groups.items():
        _require_text(position_id, "securitisation_non_ctp_offset_groups position_id")
        _require_text(
            offset_group,
            f"securitisation_non_ctp_offset_groups[{position_id!r}]",
        )


def _validate_securitisation_non_ctp_context(
    positions: tuple[DrcPosition, ...],
    *,
    context: DrcCalculationContext,
) -> None:
    validate_securitisation_non_ctp_context(context)
    position_ids = {position.position_id for position in positions}
    missing_risk_weights = sorted(position_ids - set(context.securitisation_non_ctp_risk_weights))
    if missing_risk_weights:
        raise DrcInputError(
            "context.securitisation_non_ctp_risk_weights is required for "
            "securitisation non-CTP positions: " + ", ".join(missing_risk_weights)
        )
    unused_risk_weights = sorted(set(context.securitisation_non_ctp_risk_weights) - position_ids)
    if unused_risk_weights:
        raise DrcInputError(
            "context.securitisation_non_ctp_risk_weights contains unused "
            "securitisation non-CTP position ids: " + ", ".join(unused_risk_weights)
        )
    unused_offset_groups = sorted(set(context.securitisation_non_ctp_offset_groups) - position_ids)
    if unused_offset_groups:
        raise DrcInputError(
            "context.securitisation_non_ctp_offset_groups contains unused "
            "securitisation non-CTP position ids: " + ", ".join(unused_offset_groups)
        )


def _securitisation_non_ctp_capital_inputs(
    net_jtds: tuple[NetJtd, ...],
    *,
    risk_weights: Mapping[str, float],
) -> tuple[SecuritisationNonCtpCapitalInput, ...]:
    inputs: list[SecuritisationNonCtpCapitalInput] = []
    for net_jtd in net_jtds:
        weights = tuple(sorted(_risk_weights_for_net_jtd(net_jtd, risk_weights=risk_weights)))
        if len(weights) != 1:
            raise DrcInputError(
                "securitisation non-CTP net JTD must map to exactly one risk weight: "
                f"{net_jtd.net_jtd_id}"
            )
        inputs.append(SecuritisationNonCtpCapitalInput(net_jtd=net_jtd, risk_weight=weights[0]))
    return tuple(inputs)


def _securitisation_non_ctp_hbr(
    records: tuple[SecuritisationNonCtpCapitalInput, ...],
    *,
    bucket_key: str,
) -> HedgeBenefitRatio:
    net_jtds = tuple(record.net_jtd for record in records)
    aggregate_long = sum(
        record.net_amount
        for record in net_jtds
        if DefaultDirection(record.net_direction) == DefaultDirection.LONG
    )
    aggregate_short = sum(
        record.net_amount
        for record in net_jtds
        if DefaultDirection(record.net_direction) == DefaultDirection.SHORT
    )
    denominator = aggregate_long + aggregate_short
    branch_metadata: tuple[BranchMetadata, ...] = ()
    if denominator == 0.0:
        ratio = 0.0
        branch_metadata = (
            BranchMetadata(
                branch_id=f"hbr-sec-non-ctp-zero-denominator-{_slug(bucket_key)}",
                branch_type=BranchType.ZERO_DENOMINATOR,
                source_id=bucket_key,
                selected=True,
                reason=(
                    "securitisation non-CTP aggregate net long and net short "
                    "default exposures are both zero"
                ),
                citations=_HBR_CITATIONS,
            ),
        )
    else:
        ratio = aggregate_long / denominator
    return HedgeBenefitRatio(
        hbr_id=f"hbr-sec-non-ctp-{_slug(bucket_key)}",
        bucket_key=bucket_key,
        aggregate_net_long=aggregate_long,
        aggregate_net_short=aggregate_short,
        denominator=denominator,
        ratio=ratio,
        citations=_HBR_CITATIONS,
        branch_metadata=branch_metadata,
    )


def _securitisation_non_ctp_bucket_drc(
    *,
    bucket_key: str,
    records: list[SecuritisationNonCtpCapitalInput],
    profile_id: str,
) -> BucketDrc:
    if not records:
        raise DrcInputError("securitisation non-CTP bucket DRC requires inputs")
    bucket_definition = get_bucket_definition(bucket_key, profile_id=profile_id)
    if DrcRiskClass(bucket_definition.risk_class) != DrcRiskClass.SECURITISATION_NON_CTP:
        raise DrcInputError(f"bucket is not securitisation non-CTP: {bucket_key}")

    weighted_long = 0.0
    weighted_short = 0.0
    net_jtd_ids: list[str] = []
    for record in records:
        net_jtd = record.net_jtd
        _validate_securitisation_non_ctp_net_jtd(net_jtd, bucket_key=bucket_key)
        weighted_amount = net_jtd.net_amount * record.risk_weight
        if DefaultDirection(net_jtd.net_direction) == DefaultDirection.LONG:
            weighted_long += weighted_amount
        else:
            weighted_short += weighted_amount
        net_jtd_ids.append(net_jtd.net_jtd_id)

    hbr = _securitisation_non_ctp_hbr(tuple(records), bucket_key=bucket_key)
    unfloored_capital = weighted_long - hbr.ratio * weighted_short
    floor_applied = unfloored_capital < 0.0
    capital = max(unfloored_capital, 0.0)
    branch_metadata: tuple[BranchMetadata, ...] = ()
    if floor_applied:
        branch_metadata = (
            BranchMetadata(
                branch_id=f"bucket-sec-non-ctp-floor-{_slug(bucket_key)}",
                branch_type=BranchType.FLOOR,
                source_id=bucket_key,
                selected=True,
                reason="securitisation non-CTP bucket DRC is floored at zero",
                citations=("US_NPR_210_C_3_III", "BASEL_MAR22_33"),
            ),
        )

    return BucketDrc(
        bucket_id=f"bucket-drc-sec-non-ctp-{_slug(bucket_key)}",
        bucket_key=bucket_key,
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        hbr=hbr,
        weighted_long=weighted_long,
        weighted_short=weighted_short,
        capital=capital,
        floor_applied=floor_applied,
        net_jtd_ids=tuple(net_jtd_ids),
        citations=_merge_citations((*_BUCKET_CITATIONS, bucket_definition.citation_id)),
        branch_metadata=branch_metadata,
    )


def _net_securitisation_non_ctp_group(
    key: tuple[str, str],
    exposures: list[SecuritisationNonCtpNettingInput],
    *,
    rejected_offsets: tuple[RejectedOffset, ...],
) -> NetJtd | None:
    bucket_key, group_key = key
    gross_long = sum(
        item.gross_jtd.gross_jtd
        for item in exposures
        if DefaultDirection(item.gross_jtd.default_direction) == DefaultDirection.LONG
    )
    gross_short = sum(
        item.gross_jtd.gross_jtd
        for item in exposures
        if DefaultDirection(item.gross_jtd.default_direction) == DefaultDirection.SHORT
    )
    scaled_long = sum(
        item.scaled_jtd.scaled_jtd
        for item in exposures
        if DefaultDirection(item.gross_jtd.default_direction) == DefaultDirection.LONG
    )
    scaled_short = sum(
        item.scaled_jtd.scaled_jtd
        for item in exposures
        if DefaultDirection(item.gross_jtd.default_direction) == DefaultDirection.SHORT
    )
    signed_net = scaled_long - scaled_short
    if signed_net == 0.0:
        return None
    direction = DefaultDirection.LONG if signed_net > 0.0 else DefaultDirection.SHORT
    net_amount = abs(signed_net)
    return NetJtd(
        net_jtd_id=f"net-sec-non-ctp-{_slug(bucket_key)}-{_slug(group_key)}-{direction.value.lower()}",
        netting_group_id=f"ng-sec-non-ctp-{_slug(bucket_key)}-{_slug(group_key)}",
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        bucket_key=bucket_key,
        obligor_or_tranche_key=group_key,
        seniority_layer="SECURITISATION_TRANCHE",
        gross_long=gross_long,
        gross_short=gross_short,
        scaled_long=scaled_long,
        scaled_short=scaled_short,
        net_amount=net_amount,
        net_direction=direction,
        position_ids=tuple(item.position.position_id for item in exposures),
        scaled_jtd_ids=tuple(item.scaled_jtd.scaled_jtd_id for item in exposures),
        rejected_offsets=rejected_offsets,
        branch_metadata=(
            BranchMetadata(
                branch_id=f"net-sec-non-ctp-{_slug(bucket_key)}-{_slug(group_key)}",
                branch_type=BranchType.NORMAL,
                source_id=group_key,
                selected=True,
                reason=(
                    "securitisation non-CTP netting used same-pool/same-tranche "
                    "identity or explicit replication-group evidence"
                ),
                citations=_NETTING_CITATIONS,
            ),
        ),
    )


def _rejected_securitisation_non_ctp_offsets(
    exposures: tuple[SecuritisationNonCtpNettingInput, ...],
) -> dict[str, tuple[RejectedOffset, ...]]:
    grouped: dict[str, list[SecuritisationNonCtpNettingInput]] = {}
    for exposure in exposures:
        grouped.setdefault(exposure.gross_jtd.bucket_key, []).append(exposure)

    rejected_by_bucket: dict[str, tuple[RejectedOffset, ...]] = {}
    sequence = count(1)
    for bucket_key in sorted(grouped):
        bucket_exposures = grouped[bucket_key]
        longs = [
            item
            for item in bucket_exposures
            if DefaultDirection(item.gross_jtd.default_direction) == DefaultDirection.LONG
        ]
        shorts = [
            item
            for item in bucket_exposures
            if DefaultDirection(item.gross_jtd.default_direction) == DefaultDirection.SHORT
        ]
        longs_by_group = _inputs_by_offset_group(longs)
        shorts_by_group = _inputs_by_offset_group(shorts)
        rejected: list[RejectedOffset] = []
        for long_group, long_items in sorted(longs_by_group.items()):
            for short_group, short_items in sorted(shorts_by_group.items()):
                if long_group == short_group:
                    continue
                rejected.append(
                    RejectedOffset(
                        rejection_id=f"rej-sec-non-ctp-{_slug(bucket_key)}-{next(sequence)}",
                        long_source_id=_representative_scaled_jtd_id(long_items),
                        short_source_id=_representative_scaled_jtd_id(short_items),
                        reason_code=(
                            "SEC_NON_CTP_OFFSET_REQUIRES_SAME_POOL_TRANCHE_OR_REPLICATION"
                        ),
                        citations=_NETTING_CITATIONS,
                    )
                )
        if rejected:
            rejected_by_bucket[bucket_key] = tuple(rejected)
    return rejected_by_bucket


def _validate_securitisation_non_ctp_netting_input(
    exposure: SecuritisationNonCtpNettingInput,
) -> None:
    gross = exposure.gross_jtd
    scaled = exposure.scaled_jtd
    if DrcRiskClass(gross.risk_class) != DrcRiskClass.SECURITISATION_NON_CTP:
        raise DrcInputError("securitisation non-CTP netting requires securitisation gross JTD")
    if gross.gross_jtd_id != scaled.gross_jtd_id:
        raise DrcInputError("gross_jtd_id mismatch between gross and scaled JTD")
    if gross.position_id != scaled.position_id:
        raise DrcInputError("position_id mismatch between gross and scaled JTD")
    if gross.gross_jtd != scaled.gross_jtd:
        raise DrcInputError("gross_jtd amount mismatch between gross and scaled JTD")
    _require_text(exposure.offset_group, "securitisation_non_ctp_offset_group")


def _validate_securitisation_non_ctp_net_jtd(net_jtd: NetJtd, *, bucket_key: str) -> None:
    if DrcRiskClass(net_jtd.risk_class) != DrcRiskClass.SECURITISATION_NON_CTP:
        raise DrcInputError("securitisation non-CTP bucket DRC requires securitisation net JTD")
    if net_jtd.bucket_key != bucket_key:
        raise DrcInputError(
            "securitisation non-CTP bucket DRC input bucket mismatch: "
            f"expected {bucket_key}, got {net_jtd.bucket_key}"
        )
    _require_finite_non_negative(net_jtd.net_amount, f"net JTD amount {net_jtd.net_jtd_id}")


def _zero_securitisation_non_ctp_category() -> CategoryDrc:
    return CategoryDrc(
        category_id="category-drc-securitisation-non-ctp",
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        bucket_results=(),
        capital=0.0,
        branch_metadata=(
            BranchMetadata(
                branch_id="category-securitisation-non-ctp-zero",
                branch_type=BranchType.ZERO_DENOMINATOR,
                source_id=DrcRiskClass.SECURITISATION_NON_CTP.value,
                selected=True,
                reason="all supported securitisation non-CTP net JTD records are zero",
                citations=_CATEGORY_CITATIONS,
            ),
        ),
    )


def _offset_group(position: DrcPosition, *, context: DrcCalculationContext) -> str:
    explicit = context.securitisation_non_ctp_offset_groups.get(position.position_id)
    if explicit is not None:
        return _require_text(
            explicit,
            f"securitisation_non_ctp_offset_groups[{position.position_id!r}]",
        )
    pool_id = _optional_text(position.issuer_id)
    tranche_id = _optional_text(position.tranche_id)
    if pool_id is None:
        raise DrcInputError(
            "securitisation non-CTP offsetting requires issuer_id to carry the "
            f"underlying pool id for position {position.position_id}, unless an explicit "
            "securitisation_non_ctp_offset_group is supplied"
        )
    if tranche_id is None:
        raise DrcInputError(
            f"securitisation non-CTP position {position.position_id} has no tranche_id"
        )
    return f"exact:pool:{pool_id}:tranche:{tranche_id}"


def _exposure_key(position: DrcPosition) -> str:
    pool_id = _optional_text(position.issuer_id)
    tranche_id = _optional_text(position.tranche_id)
    if pool_id is not None and tranche_id is not None:
        return f"{pool_id}/{tranche_id}"
    if tranche_id is not None:
        return tranche_id
    raise DrcInputError(f"securitisation non-CTP position {position.position_id} has no tranche_id")


def _risk_weights_for_net_jtd(
    net_jtd: NetJtd,
    *,
    risk_weights: Mapping[str, float],
) -> set[float]:
    weights: set[float] = set()
    for position_id in net_jtd.position_ids:
        try:
            risk_weight = risk_weights[position_id]
        except KeyError as exc:
            raise DrcInputError(
                "context.securitisation_non_ctp_risk_weights is required for "
                f"securitisation non-CTP position {position_id}"
            ) from exc
        _require_finite_non_negative(
            risk_weight,
            f"securitisation_non_ctp_risk_weights[{position_id!r}]",
        )
        weights.add(risk_weight)
    return weights


def _inputs_by_offset_group(
    items: list[SecuritisationNonCtpNettingInput],
) -> dict[str, list[SecuritisationNonCtpNettingInput]]:
    grouped: dict[str, list[SecuritisationNonCtpNettingInput]] = {}
    for item in items:
        grouped.setdefault(item.offset_group, []).append(item)
    return grouped


def _representative_scaled_jtd_id(items: list[SecuritisationNonCtpNettingInput]) -> str:
    return sorted(item.scaled_jtd.scaled_jtd_id for item in items)[0]


def _require_finite_non_negative(value: float, field_name: str) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise DrcInputError(f"{field_name} must be finite and non-negative")


def _require_text(value: str | None, field_name: str) -> str:
    if value is None:
        raise DrcInputError(f"{field_name} must be non-empty")
    text = str(value).strip()
    if not text:
        raise DrcInputError(f"{field_name} must be non-empty")
    return text


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text == "" else text


def _merge_citations(citations: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(citations))


def _slug(value: str) -> str:
    return value.lower().replace(" ", "-").replace("_", "-").replace(":", "-").replace("/", "-")


__all__ = [
    "SecuritisationNonCtpCalculation",
    "SecuritisationNonCtpCapitalInput",
    "SecuritisationNonCtpNettingInput",
    "calculate_securitisation_non_ctp_category_drc",
    "calculate_securitisation_non_ctp_drc",
    "calculate_securitisation_non_ctp_gross_jtd",
    "calculate_securitisation_non_ctp_net_jtds",
    "securitisation_non_ctp_context_input_hash",
    "validate_securitisation_non_ctp_context",
]
