"""Securitisation non-CTP DRC calculation path."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import count

from frtb_drc._citations import merge_citations
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
from frtb_drc.kernel.securitisation_context import (
    securitisation_non_ctp_context_input_hash,
    validate_securitisation_non_ctp_context,
)
from frtb_drc.kernel.securitisation_context import (
    validate_securitisation_non_ctp_context_for_positions as _validate_context_for_positions,
)
from frtb_drc.kernel.securitisation_gross import (
    fair_value_capped_gross_jtd as _fair_value_capped_gross_jtd,
)
from frtb_drc.maturity import scale_gross_jtds
from frtb_drc.reference_data import get_bucket_definition
from frtb_drc.regimes import (
    BASEL_MAR22_PROFILE_ID as _BASEL_MAR22_PROFILE_ID,
)
from frtb_drc.regimes import (
    EU_CRR3_PROFILE_ID as _EU_CRR3_PROFILE_ID,
)
from frtb_drc.regimes import (
    PRA_UK_CRR_PROFILE_ID as _PRA_UK_CRR_PROFILE_ID,
)
from frtb_drc.regimes import (
    US_NPR_2_0_PROFILE_ID,
    ensure_risk_class_supported,
    get_rule_profile,
)
from frtb_drc.risk_weight_evidence import (
    effective_risk_weights,
)
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
_FAIR_VALUE_CAP_CITATIONS = ("US_NPR_210_C_3_III", "BASEL_MAR22_34")
_BASEL_GROSS_CITATIONS = ("BASEL_MAR22_27",)
_BASEL_NETTING_CITATIONS = ("BASEL_MAR22_28", "BASEL_MAR22_29", "BASEL_MAR22_30")
_BASEL_BUCKET_CITATIONS = (
    "BASEL_MAR22_31",
    "BASEL_MAR22_32",
    "BASEL_MAR22_33",
    "BASEL_MAR22_34",
)
_BASEL_HBR_CITATIONS = ("BASEL_MAR22_33",)
_BASEL_CATEGORY_CITATIONS = ("BASEL_MAR22_35",)
_BASEL_FAIR_VALUE_CAP_CITATIONS = ("BASEL_MAR22_34",)
_EU_CRR3_GROSS_CITATIONS = ("EU_CRR3_ARTICLE_325Z",)
_EU_CRR3_NETTING_CITATIONS = ("EU_CRR3_ARTICLE_325Z",)
_EU_CRR3_BUCKET_CITATIONS = ("EU_CRR3_ARTICLE_325AA",)
_EU_CRR3_HBR_CITATIONS = ("EU_CRR3_ARTICLE_325AA",)
_EU_CRR3_CATEGORY_CITATIONS = ("EU_CRR3_ARTICLE_325AA",)
_EU_CRR3_FAIR_VALUE_CAP_CITATIONS = ("EU_CRR3_ARTICLE_325AA",)
_PRA_GROSS_CITATIONS = ("PRA_DRC_ARTICLE_325Z",)
_PRA_NETTING_CITATIONS = ("PRA_DRC_ARTICLE_325Z",)
_PRA_BUCKET_CITATIONS = ("PRA_DRC_ARTICLE_325AA",)
_PRA_HBR_CITATIONS = ("PRA_DRC_ARTICLE_325AA",)
_PRA_CATEGORY_CITATIONS = ("PRA_DRC_ARTICLE_325AA",)
_PRA_FAIR_VALUE_CAP_CITATIONS = ("PRA_DRC_ARTICLE_325AA",)


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
        require_finite_non_negative(self.risk_weight, "risk_weight")


def calculate_securitisation_non_ctp_drc(
    positions: Iterable[DrcPosition],
    *,
    context: DrcCalculationContext,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> SecuritisationNonCtpCalculation:
    """Calculate supported securitisation non-CTP DRC for validated positions.
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
    SecuritisationNonCtpCalculation
        Securitisation non-CTP gross, maturity-scaled, net, and category
        records for result assembly.
    """

    profile = get_rule_profile(profile_id)
    ensure_risk_class_supported(profile, DrcRiskClass.SECURITISATION_NON_CTP)
    records = tuple(positions)
    if not records:
        return SecuritisationNonCtpCalculation(
            gross_jtds=(),
            maturity_scaled_jtds=(),
            net_jtds=(),
            category=_zero_securitisation_non_ctp_category(profile_id=profile_id),
        )
    _validate_context_for_positions(records, context=context)
    gross_jtds = tuple(
        calculate_securitisation_non_ctp_gross_jtd(
            position,
            context=context,
            profile_id=profile_id,
        )
        for position in records
    )
    scaled_jtds = scale_gross_jtds(
        (
            (gross_jtd, position.maturity_years)
            for gross_jtd, position in zip(gross_jtds, records, strict=True)
        ),
        profile_id=profile_id,
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
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
            risk_weights=effective_risk_weights(
                context,
                risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
            ),
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
    context: DrcCalculationContext | None = None,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> GrossJtd:
    """Calculate securitisation non-CTP gross default exposure from market value.
    Parameters
    ----------
    position : DrcPosition
        Position.
    context : DrcCalculationContext | None, optional
        Calculation context including profile, FX, and run metadata.
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    GrossJtd
        Securitisation non-CTP GrossJtd record using market value, cap evidence, and citations.
    """

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
    gross_jtd, branch_metadata, citations = _fair_value_capped_gross_jtd(
        position,
        market_value=abs(position.market_value),
        context=context,
        profile_id=profile_id,
        gross_citations=_gross_citations(profile_id),
        fair_value_cap_citations=_fair_value_cap_citations(profile_id),
    )

    return GrossJtd(
        gross_jtd_id=f"gross-{position.position_id}",
        position_id=position.position_id,
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        issuer_or_tranche_key=_exposure_key(position),
        bucket_key=require_text(position.bucket_key, "bucket_key"),
        default_direction=DefaultDirection(position.default_direction),
        lgd_rate=1.0,
        lgd_source=(
            "securitisation non-CTP gross default exposure equals market value; "
            "LGD is embedded in the securitisation risk weight"
        ),
        notional=abs(position.notional),
        pnl_component=0.0,
        gross_jtd=gross_jtd,
        citations=merge_citations(
            (*_gross_citations(profile_id), *citations, *position.citation_ids)
        ),
        branch_metadata=branch_metadata,
    )


def calculate_securitisation_non_ctp_net_jtds(
    exposures: Iterable[SecuritisationNonCtpNettingInput],
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> tuple[NetJtd, ...]:
    """Calculate securitisation non-CTP net default exposures in stable order.
    Parameters
    ----------
    exposures : Iterable[SecuritisationNonCtpNettingInput]
        Exposures.
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[NetJtd, ...]
        Tuple of securitisation non-CTP NetJtd records, including zero-net audit records.
    """

    profile = get_rule_profile(profile_id)
    ensure_risk_class_supported(profile, DrcRiskClass.SECURITISATION_NON_CTP)
    records = tuple(exposures)
    grouped: dict[tuple[str, str], list[SecuritisationNonCtpNettingInput]] = {}
    for exposure in records:
        _validate_securitisation_non_ctp_netting_input(exposure)
        key = (exposure.gross_jtd.bucket_key, exposure.offset_group)
        grouped.setdefault(key, []).append(exposure)

    rejected_by_bucket = _rejected_securitisation_non_ctp_offsets(
        records,
        profile_id=profile_id,
    )
    net_records: list[NetJtd] = []
    for key in sorted(grouped):
        record = _net_securitisation_non_ctp_group(
            key,
            grouped[key],
            rejected_offsets=rejected_by_bucket.get(key[0], ()),
            profile_id=profile_id,
        )
        net_records.append(record)
    return tuple(net_records)


def calculate_securitisation_non_ctp_category_drc(
    inputs: Iterable[SecuritisationNonCtpCapitalInput],
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> CategoryDrc:
    """Calculate securitisation non-CTP category capital from net JTD positions.
    Parameters
    ----------
    inputs : Iterable[SecuritisationNonCtpCapitalInput]
        Capital inputs pairing net JTD with credit quality.
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    CategoryDrc
        Securitisation non-CTP CategoryDrc with per-bucket capital and branch metadata.
    """

    profile = get_rule_profile(profile_id)
    ensure_risk_class_supported(profile, DrcRiskClass.SECURITISATION_NON_CTP)
    records = tuple(inputs)
    if not records:
        return _zero_securitisation_non_ctp_category(profile_id=profile_id)

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
                citations=_category_citations(profile_id),
            ),
        ),
    )


def _securitisation_non_ctp_capital_inputs(
    net_jtds: tuple[NetJtd, ...],
    *,
    risk_weights: Mapping[str, float],
) -> tuple[SecuritisationNonCtpCapitalInput, ...]:
    inputs: list[SecuritisationNonCtpCapitalInput] = []
    for net_jtd in net_jtds:
        weights = tuple(
            sorted(
                risk_weights_for_net_jtd(
                    net_jtd,
                    risk_weights=risk_weights,
                    field_name="context.securitisation_non_ctp_risk_weights",
                    position_label="securitisation non-CTP",
                )
            )
        )
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
    profile_id: str,
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
                branch_id=f"hbr-sec-non-ctp-zero-denominator-{slug_path(bucket_key)}",
                branch_type=BranchType.ZERO_DENOMINATOR,
                source_id=bucket_key,
                selected=True,
                reason=(
                    "securitisation non-CTP aggregate net long and net short "
                    "default exposures are both zero"
                ),
                citations=_hbr_citations(profile_id),
            ),
        )
    else:
        ratio = aggregate_long / denominator
    return HedgeBenefitRatio(
        hbr_id=f"hbr-sec-non-ctp-{slug_path(bucket_key)}",
        bucket_key=bucket_key,
        aggregate_net_long=aggregate_long,
        aggregate_net_short=aggregate_short,
        denominator=denominator,
        ratio=ratio,
        citations=_hbr_citations(profile_id),
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

    hbr = _securitisation_non_ctp_hbr(
        tuple(records),
        bucket_key=bucket_key,
        profile_id=profile_id,
    )
    unfloored_capital = weighted_long - hbr.ratio * weighted_short
    floor_applied = unfloored_capital < 0.0
    capital = max(unfloored_capital, 0.0)
    branch_metadata: tuple[BranchMetadata, ...] = ()
    if floor_applied:
        branch_metadata = (
            BranchMetadata(
                branch_id=f"bucket-sec-non-ctp-floor-{slug_path(bucket_key)}",
                branch_type=BranchType.FLOOR,
                source_id=bucket_key,
                selected=True,
                reason="securitisation non-CTP bucket DRC is floored at zero",
                citations=_hbr_citations(profile_id),
            ),
        )

    return BucketDrc(
        bucket_id=f"bucket-drc-sec-non-ctp-{slug_path(bucket_key)}",
        bucket_key=bucket_key,
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        hbr=hbr,
        weighted_long=weighted_long,
        weighted_short=weighted_short,
        capital=capital,
        floor_applied=floor_applied,
        net_jtd_ids=tuple(net_jtd_ids),
        citations=merge_citations((*_bucket_citations(profile_id), bucket_definition.citation_id)),
        branch_metadata=branch_metadata,
    )


def _net_securitisation_non_ctp_group(
    key: tuple[str, str],
    exposures: list[SecuritisationNonCtpNettingInput],
    *,
    rejected_offsets: tuple[RejectedOffset, ...],
    profile_id: str,
) -> NetJtd:
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
    direction = DefaultDirection.LONG if signed_net >= 0.0 else DefaultDirection.SHORT
    net_amount = abs(signed_net)
    reason = (
        "securitisation non-CTP netting used same-pool/same-tranche "
        "identity or explicit replication-group evidence"
    )
    if signed_net == 0.0:
        reason = "securitisation non-CTP same-pool/same-tranche group fully offset to zero net JTD"
    return NetJtd(
        net_jtd_id=(
            "net-sec-non-ctp-"
            f"{slug_path(bucket_key)}-{slug_path(group_key)}-{direction.value.lower()}"
        ),
        netting_group_id=f"ng-sec-non-ctp-{slug_path(bucket_key)}-{slug_path(group_key)}",
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
                branch_id=f"net-sec-non-ctp-{slug_path(bucket_key)}-{slug_path(group_key)}",
                branch_type=BranchType.NORMAL,
                source_id=group_key,
                selected=True,
                reason=reason,
                citations=_netting_citations(profile_id),
            ),
        ),
    )


def _rejected_securitisation_non_ctp_offsets(
    exposures: tuple[SecuritisationNonCtpNettingInput, ...],
    *,
    profile_id: str,
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
        rejected = bounded_rejected_group_offsets(
            bucket_key=bucket_key,
            long_groups=longs_by_group,
            short_groups=shorts_by_group,
            rejection_id_prefix="rej-sec-non-ctp",
            sequence=sequence,
            representative=_representative_scaled_jtd_id,
            reason_code="SEC_NON_CTP_OFFSET_REQUIRES_SAME_POOL_TRANCHE_OR_REPLICATION",
            citations=_netting_citations(profile_id),
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
    require_text(exposure.offset_group, "securitisation_non_ctp_offset_group")


def _validate_securitisation_non_ctp_net_jtd(net_jtd: NetJtd, *, bucket_key: str) -> None:
    if DrcRiskClass(net_jtd.risk_class) != DrcRiskClass.SECURITISATION_NON_CTP:
        raise DrcInputError("securitisation non-CTP bucket DRC requires securitisation net JTD")
    if net_jtd.bucket_key != bucket_key:
        raise DrcInputError(
            "securitisation non-CTP bucket DRC input bucket mismatch: "
            f"expected {bucket_key}, got {net_jtd.bucket_key}"
        )
    require_finite_non_negative(net_jtd.net_amount, f"net JTD amount {net_jtd.net_jtd_id}")


def _zero_securitisation_non_ctp_category(
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> CategoryDrc:
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
                citations=_category_citations(profile_id),
            ),
        ),
    )


def _offset_group(position: DrcPosition, *, context: DrcCalculationContext) -> str:
    explicit = context.securitisation_non_ctp_offset_groups.get(position.position_id)
    if explicit is not None:
        return require_text(
            explicit,
            f"securitisation_non_ctp_offset_groups[{position.position_id!r}]",
        )
    pool_id = optional_text(position.issuer_id)
    tranche_id = optional_text(position.tranche_id)
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
    pool_id = optional_text(position.issuer_id)
    tranche_id = optional_text(position.tranche_id)
    if pool_id is not None and tranche_id is not None:
        return f"{pool_id}/{tranche_id}"
    if tranche_id is not None:
        return tranche_id
    raise DrcInputError(f"securitisation non-CTP position {position.position_id} has no tranche_id")


def _inputs_by_offset_group(
    items: list[SecuritisationNonCtpNettingInput],
) -> dict[str, list[SecuritisationNonCtpNettingInput]]:
    grouped: dict[str, list[SecuritisationNonCtpNettingInput]] = {}
    for item in items:
        grouped.setdefault(item.offset_group, []).append(item)
    return grouped


def _representative_scaled_jtd_id(items: Sequence[SecuritisationNonCtpNettingInput]) -> str:
    return sorted(item.scaled_jtd.scaled_jtd_id for item in items)[0]


def _gross_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == _BASEL_MAR22_PROFILE_ID:
        return _BASEL_GROSS_CITATIONS
    if profile_id == _EU_CRR3_PROFILE_ID:
        return _EU_CRR3_GROSS_CITATIONS
    if profile_id == _PRA_UK_CRR_PROFILE_ID:
        return _PRA_GROSS_CITATIONS
    return _GROSS_CITATIONS


def _netting_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == _BASEL_MAR22_PROFILE_ID:
        return _BASEL_NETTING_CITATIONS
    if profile_id == _EU_CRR3_PROFILE_ID:
        return _EU_CRR3_NETTING_CITATIONS
    if profile_id == _PRA_UK_CRR_PROFILE_ID:
        return _PRA_NETTING_CITATIONS
    return _NETTING_CITATIONS


def _bucket_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == _BASEL_MAR22_PROFILE_ID:
        return _BASEL_BUCKET_CITATIONS
    if profile_id == _EU_CRR3_PROFILE_ID:
        return _EU_CRR3_BUCKET_CITATIONS
    if profile_id == _PRA_UK_CRR_PROFILE_ID:
        return _PRA_BUCKET_CITATIONS
    return _BUCKET_CITATIONS


def _hbr_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == _BASEL_MAR22_PROFILE_ID:
        return _BASEL_HBR_CITATIONS
    if profile_id == _EU_CRR3_PROFILE_ID:
        return _EU_CRR3_HBR_CITATIONS
    if profile_id == _PRA_UK_CRR_PROFILE_ID:
        return _PRA_HBR_CITATIONS
    return _HBR_CITATIONS


def _category_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == _BASEL_MAR22_PROFILE_ID:
        return _BASEL_CATEGORY_CITATIONS
    if profile_id == _EU_CRR3_PROFILE_ID:
        return _EU_CRR3_CATEGORY_CITATIONS
    if profile_id == _PRA_UK_CRR_PROFILE_ID:
        return _PRA_CATEGORY_CITATIONS
    return _CATEGORY_CITATIONS


def _fair_value_cap_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == _BASEL_MAR22_PROFILE_ID:
        return _BASEL_FAIR_VALUE_CAP_CITATIONS
    if profile_id == _EU_CRR3_PROFILE_ID:
        return _EU_CRR3_FAIR_VALUE_CAP_CITATIONS
    if profile_id == _PRA_UK_CRR_PROFILE_ID:
        return _PRA_FAIR_VALUE_CAP_CITATIONS
    return _FAIR_VALUE_CAP_CITATIONS


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
