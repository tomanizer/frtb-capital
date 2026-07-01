"""Correlation trading portfolio DRC calculation path."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import count

from frtb_drc._citations import merge_citations
from frtb_drc._hashing import hash_payload
from frtb_drc._identifiers import slug_path
from frtb_drc._netting_helpers import (
    bounded_rejected_group_offsets,
    risk_weights_for_net_jtd,
)
from frtb_drc._validation_utils import optional_text, require_finite_non_negative, require_text
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
from frtb_drc.org_scope import single_scope_metadata, unique_scope_metadata
from frtb_drc.regimes import (
    BASEL_MAR22_PROFILE_ID,
    EU_CRR3_PROFILE_ID,
    PRA_UK_CRR_PROFILE_ID,
    US_NPR_2_0_PROFILE_ID,
    ensure_risk_class_supported,
    get_rule_profile,
)
from frtb_drc.risk_weight_evidence import (
    effective_risk_weights,
    risk_weight_evidence_hash_payload,
)
from frtb_drc.validation import DrcInputError, validate_position

_US_NPR_GROSS_CITATIONS = ("US_NPR_210_D_1",)
_BASEL_GROSS_CITATIONS = ("BASEL_MAR22_36", "BASEL_MAR22_37")
_US_NPR_NETTING_CITATIONS = ("US_NPR_210_D_2",)
_BASEL_NETTING_CITATIONS = ("BASEL_MAR22_39",)
_US_NPR_BUCKET_CITATIONS = (
    "US_NPR_210_D_3_I_III",
    "US_NPR_210_D_3_IV",
    "US_NPR_210_D_3_IV_D",
)
_BASEL_BUCKET_CITATIONS = (
    "BASEL_MAR22_40",
    "BASEL_MAR22_41",
    "BASEL_MAR22_42",
    "BASEL_MAR22_44",
)
_US_NPR_HBR_CITATIONS = ("US_NPR_210_D_3_IV",)
_BASEL_HBR_CITATIONS = ("BASEL_MAR22_44",)
_US_NPR_CATEGORY_CITATIONS = ("US_NPR_210_D_3_V",)
_BASEL_CATEGORY_CITATIONS = ("BASEL_MAR22_45",)
_EU_CRR3_GROSS_CITATIONS = ("EU_CRR3_ARTICLE_325AB",)
_EU_CRR3_NETTING_CITATIONS = ("EU_CRR3_ARTICLE_325AC",)
_EU_CRR3_BUCKET_CITATIONS = ("EU_CRR3_ARTICLE_325AD",)
_EU_CRR3_HBR_CITATIONS = ("EU_CRR3_ARTICLE_325AD",)
_EU_CRR3_CATEGORY_CITATIONS = ("EU_CRR3_ARTICLE_325AD",)
_PRA_GROSS_CITATIONS = ("PRA_DRC_ARTICLE_325AB",)
_PRA_NETTING_CITATIONS = ("PRA_DRC_ARTICLE_325AC",)
_PRA_BUCKET_CITATIONS = ("PRA_DRC_ARTICLE_325AD",)
_PRA_HBR_CITATIONS = ("PRA_DRC_ARTICLE_325AD",)
_PRA_CATEGORY_CITATIONS = ("PRA_DRC_ARTICLE_325AD",)


@dataclass(frozen=True)
class CtpCalculation:
    """CTP calculation records for integration into the public DRC result."""

    gross_jtds: tuple[GrossJtd, ...]
    maturity_scaled_jtds: tuple[MaturityScaledJtd, ...]
    net_jtds: tuple[NetJtd, ...]
    category: CategoryDrc


@dataclass(frozen=True)
class CtpNettingInput:
    """Input needed for CTP offsetting after maturity scaling."""

    position: DrcPosition
    gross_jtd: GrossJtd
    scaled_jtd: MaturityScaledJtd
    offset_group: str


@dataclass(frozen=True)
class CtpCapitalInput:
    """CTP net JTD with the run-supplied risk weight used for capital."""

    net_jtd: NetJtd
    risk_weight: float

    def __post_init__(self) -> None:
        require_finite_non_negative(self.risk_weight, "risk_weight")


def calculate_ctp_drc(
    positions: Iterable[DrcPosition],
    *,
    context: DrcCalculationContext,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> CtpCalculation:
    """Calculate the supported CTP DRC path for validated positions.
    Parameters
    ----------
    positions : Iterable[DrcPosition]
        Canonical DRC position records.
    context : DrcCalculationContext
        Calculation context including profile, FX, and run metadata.
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    CtpCalculation
        CTP gross, maturity-scaled, net, and category records for result assembly.
    """

    profile = get_rule_profile(profile_id)
    ensure_risk_class_supported(profile, DrcRiskClass.CORRELATION_TRADING_PORTFOLIO)
    records = tuple(positions)
    if not records:
        return CtpCalculation(
            gross_jtds=(),
            maturity_scaled_jtds=(),
            net_jtds=(),
            category=_zero_ctp_category(profile_id=profile_id),
        )
    _validate_ctp_context(records, context=context)
    gross_jtds = tuple(
        calculate_ctp_gross_jtd(position, profile_id=profile_id) for position in records
    )
    scaled_jtds = scale_gross_jtds(
        (
            (gross_jtd, position.maturity_years)
            for gross_jtd, position in zip(gross_jtds, records, strict=True)
        ),
        profile_id=profile_id,
        risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
    )
    net_jtds = calculate_ctp_net_jtds(
        (
            CtpNettingInput(
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
    category = calculate_ctp_category_drc(
        _ctp_capital_inputs(
            net_jtds,
            risk_weights=effective_risk_weights(
                context,
                risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
            ),
        ),
        profile_id=profile_id,
    )
    return CtpCalculation(
        gross_jtds=gross_jtds,
        maturity_scaled_jtds=scaled_jtds,
        net_jtds=net_jtds,
        category=category,
    )


def calculate_ctp_gross_jtd(
    position: DrcPosition,
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> GrossJtd:
    """Calculate CTP gross default exposure from market value.
    Parameters
    ----------
    position : DrcPosition
        Position.
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    GrossJtd
        CTP GrossJtd record using market-value default exposure and profile citations.
    """

    validate_position(position)
    profile = get_rule_profile(profile_id)
    ensure_risk_class_supported(profile, DrcRiskClass.CORRELATION_TRADING_PORTFOLIO)
    if DrcRiskClass(position.risk_class) != DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        raise DrcInputError("CTP gross JTD requires CTP risk_class")
    if position.market_value is None:
        raise DrcInputError(f"CTP position {position.position_id} requires market_value")
    if position.lgd_override is not None:
        raise DrcInputError("CTP gross JTD uses market value; lgd_override is not supported")

    return GrossJtd(
        gross_jtd_id=f"gross-{position.position_id}",
        position_id=position.position_id,
        risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        issuer_or_tranche_key=_exposure_key(position),
        bucket_key=require_text(position.bucket_key, "bucket_key"),
        default_direction=DefaultDirection(position.default_direction),
        lgd_rate=1.0,
        lgd_source="CTP gross default exposure equals market value; no separate LGD is applied",
        notional=abs(position.notional),
        pnl_component=0.0,
        gross_jtd=abs(position.market_value),
        citations=merge_citations((*_ctp_gross_citations(profile_id), *position.citation_ids)),
        org_scope=position.org_scope,
    )


def calculate_ctp_net_jtds(
    exposures: Iterable[CtpNettingInput],
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> tuple[NetJtd, ...]:
    """Calculate CTP net default exposures in stable bucket/group order.
    Parameters
    ----------
    exposures : Iterable[CtpNettingInput]
        Exposures.
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[NetJtd, ...]
        Tuple of CTP NetJtd records in stable bucket and offset-group order.
    """

    profile = get_rule_profile(profile_id)
    ensure_risk_class_supported(profile, DrcRiskClass.CORRELATION_TRADING_PORTFOLIO)
    records = tuple(exposures)
    grouped: dict[tuple[str, str], list[CtpNettingInput]] = {}
    for exposure in records:
        _validate_ctp_netting_input(exposure)
        key = (exposure.gross_jtd.bucket_key, exposure.offset_group)
        grouped.setdefault(key, []).append(exposure)

    rejected_by_bucket = _rejected_ctp_offsets(records, profile_id=profile_id)
    net_records: list[NetJtd] = []
    for key in sorted(grouped):
        record = _net_ctp_group(
            key,
            grouped[key],
            rejected_offsets=rejected_by_bucket.get(key[0], ()),
            profile_id=profile_id,
        )
        if record is not None:
            net_records.append(record)
    return tuple(net_records)


def calculate_ctp_category_drc(
    inputs: Iterable[CtpCapitalInput],
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> CategoryDrc:
    """Calculate CTP category capital from CTP net JTD risk positions.
    Parameters
    ----------
    inputs : Iterable[CtpCapitalInput]
        Capital inputs pairing net JTD with credit quality.
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    CategoryDrc
        CTP CategoryDrc with bucket capital, cross-index aggregation, and branch metadata.
    """

    profile = get_rule_profile(profile_id)
    ensure_risk_class_supported(profile, DrcRiskClass.CORRELATION_TRADING_PORTFOLIO)
    records = tuple(inputs)
    if not records:
        return _zero_ctp_category(profile_id=profile_id)

    hbr = _ctp_hbr(records, profile_id=profile_id)
    grouped: dict[str, list[CtpCapitalInput]] = {}
    for record in records:
        grouped.setdefault(record.net_jtd.bucket_key, []).append(record)

    bucket_results = tuple(
        _ctp_bucket_drc(
            bucket_key=bucket_key,
            records=grouped[bucket_key],
            hbr=hbr,
            profile_id=profile_id,
        )
        for bucket_key in sorted(grouped)
    )
    aggregated = sum(
        max(bucket.capital, 0.0) + 0.5 * min(bucket.capital, 0.0) for bucket in bucket_results
    )
    floor_applied = aggregated < 0.0
    capital = max(aggregated, 0.0)
    branch_metadata: tuple[BranchMetadata, ...] = (
        BranchMetadata(
            branch_id="category-ctp-cross-index-aggregation",
            branch_type=BranchType.NORMAL,
            source_id=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO.value,
            selected=True,
            reason=(
                "CTP category aggregates positive bucket DRC at 100 percent and "
                "negative bucket DRC at 50 percent"
            ),
            citations=_ctp_category_citations(profile_id),
        ),
    )
    if floor_applied:
        branch_metadata = (
            *branch_metadata,
            BranchMetadata(
                branch_id="category-ctp-floor",
                branch_type=BranchType.FLOOR,
                source_id=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO.value,
                selected=True,
                reason="CTP category DRC is floored at zero after cross-index aggregation",
                citations=_ctp_category_citations(profile_id),
            ),
        )

    return CategoryDrc(
        category_id="category-drc-ctp",
        risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        bucket_results=bucket_results,
        capital=capital,
        branch_metadata=branch_metadata,
    )


def ctp_context_input_hash(
    input_hash: str,
    *,
    positions: Iterable[DrcPosition],
    context: DrcCalculationContext,
) -> str:
    """Include CTP risk-weight and offset evidence in the input hash when CTP is present.
    Parameters
    ----------
    input_hash : str
        Precomputed input digest before FX lineage.
    positions : Iterable[DrcPosition]
        Canonical DRC position records.
    context : DrcCalculationContext
        Calculation context including profile, FX, and run metadata.

    Returns
    -------
    str
        Stable string identifier for audit or hashing.
    """

    records = tuple(
        position
        for position in positions
        if DrcRiskClass(position.risk_class) == DrcRiskClass.CORRELATION_TRADING_PORTFOLIO
    )
    if not records:
        return input_hash
    position_ids = tuple(sorted(position.position_id for position in records))
    weights = effective_risk_weights(
        context,
        risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
    )
    payload = {
        "input_hash": input_hash,
        "ctp_risk_weights": {position_id: weights[position_id] for position_id in position_ids},
        "ctp_risk_weight_evidence": risk_weight_evidence_hash_payload(
            position_ids,
            context,
            risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        ),
        "ctp_offset_groups": {
            position_id: context.ctp_offset_groups[position_id]
            for position_id in position_ids
            if position_id in context.ctp_offset_groups
        },
    }
    return hash_payload(payload)


def validate_ctp_context(context: DrcCalculationContext) -> None:
    """Validate CTP context maps without requiring that CTP positions are present.
    Parameters
    ----------
    context : DrcCalculationContext
        Calculation context including profile, FX, and run metadata.
    """

    effective_risk_weights(context, risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO)
    for position_id, offset_group in context.ctp_offset_groups.items():
        require_text(position_id, "ctp_offset_groups position_id")
        require_text(offset_group, f"ctp_offset_groups[{position_id!r}]")


def _validate_ctp_context(
    positions: tuple[DrcPosition, ...],
    *,
    context: DrcCalculationContext,
) -> None:
    validate_ctp_context(context)
    risk_weights = effective_risk_weights(
        context,
        risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
    )
    position_ids = {position.position_id for position in positions}
    missing_risk_weights = sorted(position_ids - set(risk_weights))
    if missing_risk_weights:
        raise DrcInputError(
            "context.ctp_risk_weights is required for CTP positions: "
            + ", ".join(missing_risk_weights)
        )
    unused_risk_weights = sorted(set(risk_weights) - position_ids)
    if unused_risk_weights:
        raise DrcInputError(
            "context.ctp_risk_weights contains unused CTP position ids: "
            + ", ".join(unused_risk_weights)
        )
    unused_offset_groups = sorted(set(context.ctp_offset_groups) - position_ids)
    if unused_offset_groups:
        raise DrcInputError(
            "context.ctp_offset_groups contains unused CTP position ids: "
            + ", ".join(unused_offset_groups)
        )
    if context.profile_id in {EU_CRR3_PROFILE_ID, PRA_UK_CRR_PROFILE_ID}:
        missing_offset_groups = sorted(position_ids - set(context.ctp_offset_groups))
        if missing_offset_groups:
            raise DrcInputError(
                f"context.ctp_offset_groups is required for {context.profile_id} CTP positions: "
                + ", ".join(missing_offset_groups)
            )


def _ctp_capital_inputs(
    net_jtds: tuple[NetJtd, ...],
    *,
    risk_weights: Mapping[str, float],
) -> tuple[CtpCapitalInput, ...]:
    inputs: list[CtpCapitalInput] = []
    for net_jtd in net_jtds:
        weights = tuple(
            sorted(
                risk_weights_for_net_jtd(
                    net_jtd,
                    risk_weights=risk_weights,
                    field_name="context.ctp_risk_weights",
                    position_label="CTP",
                )
            )
        )
        if len(weights) != 1:
            raise DrcInputError(
                f"CTP net JTD must map to exactly one risk weight: {net_jtd.net_jtd_id}"
            )
        inputs.append(CtpCapitalInput(net_jtd=net_jtd, risk_weight=weights[0]))
    return tuple(inputs)


def _ctp_hbr(records: tuple[CtpCapitalInput, ...], *, profile_id: str) -> HedgeBenefitRatio:
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
                branch_id="hbr-ctp-zero-denominator",
                branch_type=BranchType.ZERO_DENOMINATOR,
                source_id=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO.value,
                selected=True,
                reason="CTP aggregate net long and net short default exposures are both zero",
                citations=_ctp_hbr_citations(profile_id),
            ),
        )
    else:
        ratio = aggregate_long / denominator
    return HedgeBenefitRatio(
        hbr_id="hbr-ctp",
        bucket_key=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO.value,
        aggregate_net_long=aggregate_long,
        aggregate_net_short=aggregate_short,
        denominator=denominator,
        ratio=ratio,
        citations=_ctp_hbr_citations(profile_id),
        branch_metadata=branch_metadata,
    )


def _ctp_bucket_drc(
    *,
    bucket_key: str,
    records: list[CtpCapitalInput],
    hbr: HedgeBenefitRatio,
    profile_id: str,
) -> BucketDrc:
    weighted_long = 0.0
    weighted_short = 0.0
    net_jtd_ids: list[str] = []
    for record in records:
        net_jtd = record.net_jtd
        _validate_ctp_net_jtd(net_jtd, bucket_key=bucket_key)
        weighted_amount = net_jtd.net_amount * record.risk_weight
        if DefaultDirection(net_jtd.net_direction) == DefaultDirection.LONG:
            weighted_long += weighted_amount
        else:
            weighted_short += weighted_amount
        net_jtd_ids.append(net_jtd.net_jtd_id)

    bucket_capital = weighted_long - hbr.ratio * weighted_short
    return BucketDrc(
        bucket_id=f"bucket-drc-ctp-{slug_path(bucket_key)}",
        bucket_key=bucket_key,
        risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        hbr=HedgeBenefitRatio(
            hbr_id=f"hbr-ctp-{slug_path(bucket_key)}",
            bucket_key=bucket_key,
            aggregate_net_long=hbr.aggregate_net_long,
            aggregate_net_short=hbr.aggregate_net_short,
            denominator=hbr.denominator,
            ratio=hbr.ratio,
            citations=hbr.citations,
            branch_metadata=hbr.branch_metadata,
        ),
        weighted_long=weighted_long,
        weighted_short=weighted_short,
        capital=bucket_capital,
        floor_applied=False,
        net_jtd_ids=tuple(net_jtd_ids),
        citations=_ctp_bucket_citations(profile_id),
        branch_metadata=(
            BranchMetadata(
                branch_id=f"bucket-ctp-no-floor-{slug_path(bucket_key)}",
                branch_type=BranchType.NORMAL,
                source_id=bucket_key,
                selected=True,
                reason="CTP bucket DRC is not floored at zero",
                citations=_ctp_hbr_citations(profile_id),
            ),
        ),
    )


def _net_ctp_group(
    key: tuple[str, str],
    exposures: list[CtpNettingInput],
    *,
    rejected_offsets: tuple[RejectedOffset, ...],
    profile_id: str,
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
        net_jtd_id=(
            f"net-ctp-{slug_path(bucket_key)}-{slug_path(group_key)}-{direction.value.lower()}"
        ),
        netting_group_id=f"ng-ctp-{slug_path(bucket_key)}-{slug_path(group_key)}",
        risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        bucket_key=bucket_key,
        obligor_or_tranche_key=group_key,
        seniority_layer="CTP",
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
                branch_id=f"net-ctp-{slug_path(bucket_key)}-{slug_path(group_key)}",
                branch_type=BranchType.NORMAL,
                source_id=group_key,
                selected=True,
                reason=(
                    "CTP netting used exact exposure identity or explicit replication "
                    "group evidence"
                ),
                citations=_ctp_netting_citations(profile_id),
            ),
        ),
        org_scope=single_scope_metadata(item.gross_jtd.org_scope for item in exposures),
        contributing_org_scopes=unique_scope_metadata(
            item.gross_jtd.org_scope for item in exposures
        ),
    )


def _rejected_ctp_offsets(
    exposures: tuple[CtpNettingInput, ...],
    *,
    profile_id: str,
) -> dict[str, tuple[RejectedOffset, ...]]:
    grouped: dict[str, list[CtpNettingInput]] = {}
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
        rejected = bounded_rejected_group_offsets(
            bucket_key=bucket_key,
            long_groups=longs_by_group,
            short_groups=shorts_by_group,
            rejection_id_prefix="rej-ctp",
            sequence=sequence,
            representative=_representative_scaled_jtd_id,
            reason_code="CTP_OFFSET_REQUIRES_EXACT_MATCH_OR_EXPLICIT_REPLICATION",
            citations=_ctp_netting_citations(profile_id),
        )
        if rejected:
            rejected_by_bucket[bucket_key] = tuple(rejected)
    return rejected_by_bucket


def _validate_ctp_netting_input(exposure: CtpNettingInput) -> None:
    gross = exposure.gross_jtd
    scaled = exposure.scaled_jtd
    if DrcRiskClass(gross.risk_class) != DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        raise DrcInputError("CTP netting requires CTP gross JTD")
    if gross.gross_jtd_id != scaled.gross_jtd_id:
        raise DrcInputError("gross_jtd_id mismatch between gross and scaled JTD")
    if gross.position_id != scaled.position_id:
        raise DrcInputError("position_id mismatch between gross and scaled JTD")
    if gross.gross_jtd != scaled.gross_jtd:
        raise DrcInputError("gross_jtd amount mismatch between gross and scaled JTD")
    require_text(exposure.offset_group, "ctp_offset_group")


def _validate_ctp_net_jtd(net_jtd: NetJtd, *, bucket_key: str) -> None:
    if DrcRiskClass(net_jtd.risk_class) != DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        raise DrcInputError("CTP bucket DRC requires CTP net JTD")
    if net_jtd.bucket_key != bucket_key:
        raise DrcInputError(
            f"CTP bucket DRC input bucket mismatch: expected {bucket_key}, got {net_jtd.bucket_key}"
        )
    require_finite_non_negative(net_jtd.net_amount, f"net JTD amount {net_jtd.net_jtd_id}")


def _zero_ctp_category(*, profile_id: str = US_NPR_2_0_PROFILE_ID) -> CategoryDrc:
    return CategoryDrc(
        category_id="category-drc-ctp",
        risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        bucket_results=(),
        capital=0.0,
        branch_metadata=(
            BranchMetadata(
                branch_id="category-ctp-zero",
                branch_type=BranchType.ZERO_DENOMINATOR,
                source_id=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO.value,
                selected=True,
                reason="all supported CTP net JTD records are zero",
                citations=_ctp_category_citations(profile_id),
            ),
        ),
    )


def _ctp_gross_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_GROSS_CITATIONS
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_GROSS_CITATIONS
    if profile_id == PRA_UK_CRR_PROFILE_ID:
        return _PRA_GROSS_CITATIONS
    return _US_NPR_GROSS_CITATIONS


def _ctp_netting_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_NETTING_CITATIONS
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_NETTING_CITATIONS
    if profile_id == PRA_UK_CRR_PROFILE_ID:
        return _PRA_NETTING_CITATIONS
    return _US_NPR_NETTING_CITATIONS


def _ctp_bucket_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_BUCKET_CITATIONS
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_BUCKET_CITATIONS
    if profile_id == PRA_UK_CRR_PROFILE_ID:
        return _PRA_BUCKET_CITATIONS
    return _US_NPR_BUCKET_CITATIONS


def _ctp_hbr_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_HBR_CITATIONS
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_HBR_CITATIONS
    if profile_id == PRA_UK_CRR_PROFILE_ID:
        return _PRA_HBR_CITATIONS
    return _US_NPR_HBR_CITATIONS


def _ctp_category_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_CATEGORY_CITATIONS
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_CATEGORY_CITATIONS
    if profile_id == PRA_UK_CRR_PROFILE_ID:
        return _PRA_CATEGORY_CITATIONS
    return _US_NPR_CATEGORY_CITATIONS


def _offset_group(position: DrcPosition, *, context: DrcCalculationContext) -> str:
    explicit = context.ctp_offset_groups.get(position.position_id)
    if explicit is not None:
        return require_text(explicit, f"ctp_offset_groups[{position.position_id!r}]")
    index_series_id = optional_text(position.index_series_id)
    tranche_id = optional_text(position.tranche_id)
    issuer_id = optional_text(position.issuer_id)
    if index_series_id is not None and tranche_id is not None:
        return f"exact:index:{index_series_id}:tranche:{tranche_id}"
    if index_series_id is not None:
        return f"exact:index:{index_series_id}:non-tranched"
    if issuer_id is not None:
        return f"exact:single-name:{issuer_id}"
    if tranche_id is not None:
        return f"exact:tranche:{tranche_id}"
    raise DrcInputError(f"CTP position {position.position_id} has no offset identity")


def _exposure_key(position: DrcPosition) -> str:
    index_series_id = optional_text(position.index_series_id)
    tranche_id = optional_text(position.tranche_id)
    issuer_id = optional_text(position.issuer_id)
    if index_series_id is not None and tranche_id is not None:
        return f"{index_series_id}/{tranche_id}"
    if index_series_id is not None:
        return index_series_id
    if issuer_id is not None:
        return issuer_id
    if tranche_id is not None:
        return tranche_id
    raise DrcInputError(f"CTP position {position.position_id} has no exposure identity")


def _inputs_by_offset_group(
    items: list[CtpNettingInput],
) -> dict[str, list[CtpNettingInput]]:
    grouped: dict[str, list[CtpNettingInput]] = {}
    for item in items:
        grouped.setdefault(item.offset_group, []).append(item)
    return grouped


def _representative_scaled_jtd_id(items: Sequence[CtpNettingInput]) -> str:
    return sorted(item.scaled_jtd.scaled_jtd_id for item in items)[0]


__all__ = [
    "CtpCalculation",
    "CtpCapitalInput",
    "CtpNettingInput",
    "calculate_ctp_category_drc",
    "calculate_ctp_drc",
    "calculate_ctp_gross_jtd",
    "calculate_ctp_net_jtds",
    "ctp_context_input_hash",
    "validate_ctp_context",
]
