"""Bucket and category capital for non-securitisation DRC."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite

from frtb_drc._identifiers import slug as _slug
from frtb_drc.data_models import (
    BranchMetadata,
    BranchType,
    BucketDrc,
    CategoryDrc,
    CreditQuality,
    DefaultDirection,
    DrcRiskClass,
    HedgeBenefitRatio,
    NetJtd,
)
from frtb_drc.reference_data import get_bucket_definition, get_risk_weight_rule
from frtb_drc.regimes import (
    BASEL_MAR22_PROFILE_ID,
    EU_CRR3_PROFILE_ID,
    US_NPR_2_0_PROFILE_ID,
    ensure_risk_class_supported,
    get_rule_profile,
)
from frtb_drc.validation import DrcInputError

_US_NPR_HBR_CITATION = "US_NPR_210_A_2_IV_A"
_US_NPR_BUCKET_CAPITAL_CITATION = "US_NPR_210_A_2_IV_C"
_US_NPR_CATEGORY_CITATION = "US_NPR_210_B_3_III"
_BASEL_HBR_CITATION = "BASEL_MAR22_23"
_BASEL_BUCKET_CAPITAL_CITATION = "BASEL_MAR22_25"
_BASEL_CATEGORY_CITATION = "BASEL_MAR22_26"
_EU_CRR3_HBR_CITATION = "EU_CRR3_ARTICLE_325Y_3_5"
_EU_CRR3_BUCKET_CAPITAL_CITATION = "EU_CRR3_ARTICLE_325Y_3_5"
_EU_CRR3_CATEGORY_CITATION = "EU_CRR3_ARTICLE_325Y_3_5"


@dataclass(frozen=True)
class CapitalInput:
    """Net JTD with credit-quality metadata needed for risk-weight lookup."""

    net_jtd: NetJtd
    credit_quality: CreditQuality | str

    def __post_init__(self) -> None:
        if not isinstance(self.credit_quality, CreditQuality):
            object.__setattr__(
                self,
                "credit_quality",
                CreditQuality(self.credit_quality),
            )


def calculate_hedge_benefit_ratio(
    net_jtds: Iterable[NetJtd],
    *,
    bucket_key: str,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> HedgeBenefitRatio:
    """Calculate the bucket HBR from aggregate long and short net JTD.
    Parameters
    ----------
    net_jtds : Iterable[NetJtd]
        Net JTD records within one bucket or category.
    bucket_key : str
        DRC bucket key for the calculation scope.
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    HedgeBenefitRatio
        Result of the operation.
    """

    records = tuple(net_jtds)
    for record in records:
        _validate_net_jtd(record, bucket_key=bucket_key)
    aggregate_long = sum(
        record.net_amount
        for record in records
        if DefaultDirection(record.net_direction) == DefaultDirection.LONG
    )
    aggregate_short = sum(
        record.net_amount
        for record in records
        if DefaultDirection(record.net_direction) == DefaultDirection.SHORT
    )
    denominator = aggregate_long + aggregate_short
    hbr_citation = _hbr_citation(profile_id)
    branch_metadata: tuple[BranchMetadata, ...] = ()
    if denominator == 0.0:
        ratio = 0.0
        branch_metadata = (
            BranchMetadata(
                branch_id=f"hbr-zero-denominator-{_slug(bucket_key)}",
                branch_type=BranchType.ZERO_DENOMINATOR,
                source_id=bucket_key,
                selected=True,
                reason="aggregate net long and net short default exposures are both zero",
                citations=(hbr_citation,),
            ),
        )
    else:
        ratio = aggregate_long / denominator

    return HedgeBenefitRatio(
        hbr_id=f"hbr-{_slug(bucket_key)}",
        bucket_key=bucket_key,
        aggregate_net_long=aggregate_long,
        aggregate_net_short=aggregate_short,
        denominator=denominator,
        ratio=ratio,
        citations=(hbr_citation,),
        branch_metadata=branch_metadata,
    )


def calculate_bucket_drc(
    inputs: Iterable[CapitalInput],
    *,
    bucket_key: str | None = None,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> BucketDrc:
    """Calculate non-securitisation DRC capital for one bucket.
    Parameters
    ----------
    inputs : Iterable[CapitalInput]
        Capital inputs pairing net JTD with credit quality.
    bucket_key : str | None, optional
        DRC bucket key for the calculation scope.
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    BucketDrc
        Result of the operation.
    """

    profile = get_rule_profile(profile_id)
    ensure_risk_class_supported(profile, DrcRiskClass.NON_SECURITISATION)
    records = tuple(inputs)
    if not records:
        raise DrcInputError("bucket DRC requires at least one net JTD input")

    resolved_bucket = records[0].net_jtd.bucket_key if bucket_key is None else bucket_key
    if not resolved_bucket.strip():
        raise DrcInputError("bucket_key must be non-empty")
    bucket_definition = get_bucket_definition(resolved_bucket, profile_id=profile_id)
    if DrcRiskClass(bucket_definition.risk_class) != DrcRiskClass.NON_SECURITISATION:
        raise DrcInputError(f"bucket is not non-securitisation: {resolved_bucket}")

    weighted_long = 0.0
    weighted_short = 0.0
    bucket_capital_citation = _bucket_capital_citation(profile.profile_id)
    citation_ids = {bucket_capital_citation, bucket_definition.citation_id}
    net_records: list[NetJtd] = []
    for capital_input in records:
        net_jtd = capital_input.net_jtd
        _validate_net_jtd(net_jtd, bucket_key=resolved_bucket)
        credit_quality = CreditQuality(capital_input.credit_quality)
        risk_weight = get_risk_weight_rule(
            resolved_bucket,
            credit_quality,
            profile_id=profile_id,
        )
        citation_ids.add(risk_weight.citation_id)
        weighted_amount = net_jtd.net_amount * risk_weight.risk_weight
        if DefaultDirection(net_jtd.net_direction) == DefaultDirection.LONG:
            weighted_long += weighted_amount
        else:
            weighted_short += weighted_amount
        net_records.append(net_jtd)

    hbr = calculate_hedge_benefit_ratio(
        net_records,
        bucket_key=resolved_bucket,
        profile_id=profile.profile_id,
    )
    unfloored_capital = weighted_long - hbr.ratio * weighted_short
    floor_applied = unfloored_capital < 0.0
    capital = max(unfloored_capital, 0.0)
    branch_metadata: tuple[BranchMetadata, ...] = ()
    if floor_applied:
        branch_metadata = (
            BranchMetadata(
                branch_id=f"bucket-floor-{_slug(resolved_bucket)}",
                branch_type=BranchType.FLOOR,
                source_id=resolved_bucket,
                selected=True,
                reason="non-securitisation bucket DRC is floored at zero",
                citations=(bucket_capital_citation,),
            ),
        )

    return BucketDrc(
        bucket_id=f"bucket-drc-{_slug(resolved_bucket)}",
        bucket_key=resolved_bucket,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        hbr=hbr,
        weighted_long=weighted_long,
        weighted_short=weighted_short,
        capital=capital,
        floor_applied=floor_applied,
        net_jtd_ids=tuple(record.net_jtd_id for record in net_records),
        citations=tuple(sorted(citation_ids)),
        branch_metadata=branch_metadata,
    )


def calculate_category_drc(
    inputs: Iterable[CapitalInput],
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> CategoryDrc:
    """Calculate the non-securitisation category total from bucket DRC results.
    Parameters
    ----------
    inputs : Iterable[CapitalInput]
        Capital inputs pairing net JTD with credit quality.
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    CategoryDrc
        Result of the operation.
    """

    profile = get_rule_profile(profile_id)
    ensure_risk_class_supported(profile, DrcRiskClass.NON_SECURITISATION)
    grouped: dict[str, list[CapitalInput]] = {}
    for capital_input in inputs:
        bucket_key = capital_input.net_jtd.bucket_key
        grouped.setdefault(bucket_key, []).append(capital_input)
    if not grouped:
        raise DrcInputError("category DRC requires at least one net JTD input")

    bucket_results = tuple(
        calculate_bucket_drc(grouped[bucket_key], bucket_key=bucket_key, profile_id=profile_id)
        for bucket_key in sorted(grouped)
    )
    return CategoryDrc(
        category_id="category-drc-non-securitisation",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        bucket_results=bucket_results,
        capital=sum(bucket.capital for bucket in bucket_results),
        branch_metadata=(
            BranchMetadata(
                branch_id="category-non-securitisation-sum",
                branch_type=BranchType.NORMAL,
                source_id=DrcRiskClass.NON_SECURITISATION.value,
                selected=True,
                reason="non-securitisation category DRC is the sum of bucket requirements",
                citations=(_category_citation(profile.profile_id),),
            ),
        ),
    )


def _hbr_citation(profile_id: str) -> str:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_HBR_CITATION
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_HBR_CITATION
    return _US_NPR_HBR_CITATION


def _bucket_capital_citation(profile_id: str) -> str:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_BUCKET_CAPITAL_CITATION
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_BUCKET_CAPITAL_CITATION
    return _US_NPR_BUCKET_CAPITAL_CITATION


def _category_citation(profile_id: str) -> str:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_CATEGORY_CITATION
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_CATEGORY_CITATION
    return _US_NPR_CATEGORY_CITATION


def _validate_net_jtd(net_jtd: NetJtd, *, bucket_key: str) -> None:
    if DrcRiskClass(net_jtd.risk_class) != DrcRiskClass.NON_SECURITISATION:
        raise DrcInputError("bucket DRC requires non-securitisation net JTD")
    if net_jtd.bucket_key != bucket_key:
        raise DrcInputError(
            f"bucket DRC input bucket mismatch: expected {bucket_key}, got {net_jtd.bucket_key}"
        )
    if not isfinite(net_jtd.net_amount):
        raise DrcInputError(f"net JTD amount must be finite: {net_jtd.net_jtd_id}")
    if net_jtd.net_amount < 0.0:
        raise DrcInputError(f"net JTD amount must be non-negative: {net_jtd.net_jtd_id}")
