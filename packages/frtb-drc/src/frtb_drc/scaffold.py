"""Public DRC calculation entry point."""

from __future__ import annotations

from collections.abc import Iterable

from frtb_common import CapitalComponentMetadata, ImplementationStatus, ValidationStatus

from frtb_drc._version import __version__
from frtb_drc.audit import input_snapshot_hash, rule_profile_hash, validate_reconciliation
from frtb_drc.capital import CapitalInput, calculate_category_drc
from frtb_drc.ctp import calculate_ctp_drc, ctp_context_input_hash, validate_ctp_context
from frtb_drc.data_models import (
    BranchMetadata,
    BranchType,
    CategoryDrc,
    CreditQuality,
    DrcCalculationContext,
    DrcCapitalResult,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    GrossJtd,
    MaturityScaledJtd,
    NetJtd,
)
from frtb_drc.fx import (
    convert_positions_to_base_currency,
    fx_branch_metadata,
    input_hash_with_fx,
    validate_fx_rates,
)
from frtb_drc.gross_jtd import calculate_gross_jtds
from frtb_drc.maturity import scale_gross_jtds
from frtb_drc.netting import NettingInput, calculate_net_jtds
from frtb_drc.regimes import DrcRuleProfile, ensure_risk_class_supported, get_rule_profile
from frtb_drc.securitisation import (
    calculate_securitisation_non_ctp_drc,
    securitisation_non_ctp_context_input_hash,
    validate_securitisation_non_ctp_context,
)
from frtb_drc.validation import DrcInputError, validate_positions

PACKAGE_METADATA = CapitalComponentMetadata(
    package_name="frtb-drc",
    import_name="frtb_drc",
    component_name="Standardised Approach default risk charge",
    implementation_status=ImplementationStatus.PARTIAL,
    validation_status=ValidationStatus.PENDING,
)

_ZERO_CATEGORY_CITATION = "US_NPR_210_B_3_III"


def calculate_drc_capital(
    positions: Iterable[DrcPosition],
    *,
    context: DrcCalculationContext,
) -> DrcCapitalResult:
    """Calculate supported non-securitisation DRC capital."""

    _validate_context(context)
    profile = get_rule_profile(context.profile_id)
    validated = _sorted_positions(
        validate_positions(
            positions,
            citation_policy=context.citation_policy,
            profile_id=profile.profile_id,
        )
    )
    if not validated:
        raise DrcInputError("DRC capital requires at least one position")
    _validate_supported_run(validated, context=context, profile=profile)

    calculation_positions, fx_conversions = convert_positions_to_base_currency(
        validated,
        context=context,
    )
    nonsec_positions = _positions_for_risk_class(
        calculation_positions,
        DrcRiskClass.NON_SECURITISATION,
    )
    securitisation_non_ctp_positions = _positions_for_risk_class(
        calculation_positions,
        DrcRiskClass.SECURITISATION_NON_CTP,
    )
    ctp_positions = _positions_for_risk_class(
        calculation_positions,
        DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
    )

    categories: list[CategoryDrc] = []
    gross_jtd_records: list[GrossJtd] = []
    scaled_jtd_records: list[MaturityScaledJtd] = []
    net_jtd_records: list[NetJtd] = []

    if nonsec_positions:
        nonsec_category, gross_jtds, scaled_jtds, net_jtds = _calculate_nonsec_category(
            nonsec_positions,
            profile=profile,
        )
        categories.append(nonsec_category)
        gross_jtd_records.extend(gross_jtds)
        scaled_jtd_records.extend(scaled_jtds)
        net_jtd_records.extend(net_jtds)

    if securitisation_non_ctp_positions:
        securitisation_calculation = calculate_securitisation_non_ctp_drc(
            securitisation_non_ctp_positions,
            context=context,
            profile_id=profile.profile_id,
        )
        categories.append(securitisation_calculation.category)
        gross_jtd_records.extend(securitisation_calculation.gross_jtds)
        scaled_jtd_records.extend(securitisation_calculation.maturity_scaled_jtds)
        net_jtd_records.extend(securitisation_calculation.net_jtds)

    if ctp_positions:
        ctp_calculation = calculate_ctp_drc(
            ctp_positions,
            context=context,
            profile_id=profile.profile_id,
        )
        categories.append(ctp_calculation.category)
        gross_jtd_records.extend(ctp_calculation.gross_jtds)
        scaled_jtd_records.extend(ctp_calculation.maturity_scaled_jtds)
        net_jtd_records.extend(ctp_calculation.net_jtds)

    gross_jtds = tuple(gross_jtd_records)
    scaled_jtds = tuple(scaled_jtd_records)
    net_jtds = tuple(net_jtd_records)
    category_results = tuple(categories)
    total_drc = sum(category.capital for category in category_results)
    input_hash = securitisation_non_ctp_context_input_hash(
        input_hash_with_fx(input_snapshot_hash(validated), fx_conversions),
        positions=calculation_positions,
        context=context,
    )
    input_hash = ctp_context_input_hash(
        input_hash,
        positions=calculation_positions,
        context=context,
    )
    result = DrcCapitalResult(
        result_id=f"drc-{_slug(context.run_id)}-{input_hash[:12]}",
        run_id=context.run_id,
        calculation_date=context.calculation_date,
        base_currency=context.base_currency,
        profile_id=profile.profile_id,
        profile_hash=rule_profile_hash(profile.profile_id),
        input_hash=input_hash,
        categories=category_results,
        total_drc=total_drc,
        citations=_collect_citations(
            gross_jtds=gross_jtds,
            scaled_jtds=scaled_jtds,
            net_jtds=net_jtds,
            categories=category_results,
        ),
        warnings=(),
        branch_metadata=(
            *_run_branch_metadata(category_results, profile_id=profile.profile_id),
            *fx_branch_metadata(fx_conversions),
        ),
        package_name=PACKAGE_METADATA.package_name,
        package_version=__version__,
        input_count=len(validated),
        rejected_input_count=0,
        input_positions=validated,
        gross_jtds=gross_jtds,
        maturity_scaled_jtds=scaled_jtds,
        net_jtds=net_jtds,
        fx_conversions=fx_conversions,
    )
    validate_reconciliation(result)
    return result


def _validate_context(context: DrcCalculationContext) -> None:
    if context.run_id.strip() == "":
        raise DrcInputError("run_id must be non-empty")
    if context.base_currency.strip() == "":
        raise DrcInputError("base_currency must be non-empty")
    if context.profile_id.strip() == "":
        raise DrcInputError("profile_id must be non-empty")
    if context.citation_policy.strip() == "":
        raise DrcInputError("citation_policy must be non-empty")
    validate_fx_rates(context)
    validate_securitisation_non_ctp_context(context)
    validate_ctp_context(context)


def _validate_supported_run(
    positions: tuple[DrcPosition, ...],
    *,
    context: DrcCalculationContext,
    profile: DrcRuleProfile,
) -> None:
    scoped_desk_id = context.desk_id.strip()
    scoped_legal_entity = context.legal_entity.strip()
    for position in positions:
        risk_class = DrcRiskClass(position.risk_class)
        ensure_risk_class_supported(profile, risk_class)
        if scoped_desk_id and position.desk_id != scoped_desk_id:
            raise DrcInputError(
                f"position {position.position_id} desk_id {position.desk_id} does not match "
                f"context desk_id {scoped_desk_id}"
            )
        if scoped_legal_entity and position.legal_entity != scoped_legal_entity:
            raise DrcInputError(
                f"position {position.position_id} legal_entity "
                f"{position.legal_entity} does not match "
                f"context legal_entity {scoped_legal_entity}"
            )


def _calculate_nonsec_category(
    positions: tuple[DrcPosition, ...],
    *,
    profile: DrcRuleProfile,
) -> tuple[CategoryDrc, tuple[GrossJtd, ...], tuple[MaturityScaledJtd, ...], tuple[NetJtd, ...]]:
    gross_jtds = calculate_gross_jtds(positions, profile_id=profile.profile_id)
    scaled_jtds = scale_gross_jtds(
        (
            (gross_jtd, position.maturity_years)
            for gross_jtd, position in zip(gross_jtds, positions, strict=True)
        ),
        profile_id=profile.profile_id,
    )
    gross_by_position = {gross.position_id: gross for gross in gross_jtds}
    scaled_by_position = {scaled.position_id: scaled for scaled in scaled_jtds}
    net_jtds = calculate_net_jtds(
        _netting_inputs(positions, gross_by_position, scaled_by_position),
        profile_id=profile.profile_id,
    )
    capital_inputs = _capital_inputs(net_jtds, positions)
    category = (
        calculate_category_drc(capital_inputs, profile_id=profile.profile_id)
        if capital_inputs
        else _zero_nonsec_category()
    )
    return category, gross_jtds, scaled_jtds, net_jtds


def _netting_inputs(
    positions: tuple[DrcPosition, ...],
    gross_by_position: dict[str, GrossJtd],
    scaled_by_position: dict[str, MaturityScaledJtd],
) -> tuple[NettingInput, ...]:
    inputs: list[NettingInput] = []
    for position in positions:
        if position.seniority is None:  # pragma: no cover - validate_positions enforces this.
            raise DrcInputError("seniority is required for non-securitisation positions")
        inputs.append(
            NettingInput(
                gross_jtd=gross_by_position[position.position_id],
                scaled_jtd=scaled_by_position[position.position_id],
                seniority=DrcSeniority(position.seniority),
            )
        )
    return tuple(inputs)


def _capital_inputs(
    net_jtds: tuple[NetJtd, ...],
    positions: tuple[DrcPosition, ...],
) -> tuple[CapitalInput, ...]:
    positions_by_id = {position.position_id: position for position in positions}
    return tuple(
        CapitalInput(
            net_jtd=net_jtd,
            credit_quality=_credit_quality_for_net_jtd(net_jtd, positions_by_id),
        )
        for net_jtd in net_jtds
    )


def _credit_quality_for_net_jtd(
    net_jtd: NetJtd,
    positions_by_id: dict[str, DrcPosition],
) -> CreditQuality:
    credit_qualities: set[CreditQuality] = set()
    for position_id in net_jtd.position_ids:
        credit_quality = positions_by_id[position_id].credit_quality
        if credit_quality is not None:
            credit_qualities.add(CreditQuality(credit_quality))
    if len(credit_qualities) != 1:
        raise DrcInputError(f"net JTD must map to exactly one credit quality: {net_jtd.net_jtd_id}")
    return next(iter(credit_qualities))


def _zero_nonsec_category() -> CategoryDrc:
    return CategoryDrc(
        category_id="category-drc-non-securitisation",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        bucket_results=(),
        capital=0.0,
        branch_metadata=(
            BranchMetadata(
                branch_id="category-non-securitisation-zero",
                branch_type=BranchType.ZERO_DENOMINATOR,
                source_id=DrcRiskClass.NON_SECURITISATION.value,
                selected=True,
                reason="all supported net JTD records are zero",
                citations=(_ZERO_CATEGORY_CITATION,),
            ),
        ),
    )


def _collect_citations(
    *,
    gross_jtds: tuple[GrossJtd, ...],
    scaled_jtds: tuple[MaturityScaledJtd, ...],
    net_jtds: tuple[NetJtd, ...],
    categories: tuple[CategoryDrc, ...],
) -> tuple[str, ...]:
    citation_ids = {"US_NPR_210_SCOPE"}
    if any(
        DrcRiskClass(record.risk_class) == DrcRiskClass.NON_SECURITISATION for record in net_jtds
    ):
        citation_ids.add("US_NPR_210_B_2")
    if any(
        DrcRiskClass(record.risk_class) == DrcRiskClass.SECURITISATION_NON_CTP
        for record in net_jtds
    ):
        citation_ids.add("US_NPR_210_C_2")
    if any(
        DrcRiskClass(record.risk_class) == DrcRiskClass.CORRELATION_TRADING_PORTFOLIO
        for record in net_jtds
    ):
        citation_ids.add("US_NPR_210_D_2")
    for gross_jtd in gross_jtds:
        citation_ids.update(gross_jtd.citations)
        citation_ids.update(_branch_citations(gross_jtd.branch_metadata))
    for scaled_jtd in scaled_jtds:
        citation_ids.update(scaled_jtd.citations)
        citation_ids.update(_branch_citations(scaled_jtd.branch_metadata))
    for net_jtd in net_jtds:
        citation_ids.update(_branch_citations(net_jtd.branch_metadata))
        for rejected_offset in net_jtd.rejected_offsets:
            citation_ids.update(rejected_offset.citations)
    for category in categories:
        citation_ids.update(_branch_citations(category.branch_metadata))
        for bucket in category.bucket_results:
            citation_ids.update(bucket.citations)
            citation_ids.update(bucket.hbr.citations)
            citation_ids.update(_branch_citations(bucket.branch_metadata))
            citation_ids.update(_branch_citations(bucket.hbr.branch_metadata))
    return tuple(sorted(citation_ids))


def _branch_citations(branches: tuple[BranchMetadata, ...]) -> set[str]:
    citation_ids: set[str] = set()
    for branch in branches:
        citation_ids.update(branch.citations)
    return citation_ids


def _sorted_positions(positions: tuple[DrcPosition, ...]) -> tuple[DrcPosition, ...]:
    return tuple(
        sorted(
            positions,
            key=lambda position: (position.position_id, position.source_row_id),
        )
    )


def _positions_for_risk_class(
    positions: tuple[DrcPosition, ...],
    risk_class: DrcRiskClass,
) -> tuple[DrcPosition, ...]:
    return tuple(
        position for position in positions if DrcRiskClass(position.risk_class) == risk_class
    )


def _run_branch_metadata(
    categories: tuple[CategoryDrc, ...],
    *,
    profile_id: str,
) -> tuple[BranchMetadata, ...]:
    branches: list[BranchMetadata] = []
    risk_classes = {DrcRiskClass(category.risk_class) for category in categories}
    if DrcRiskClass.NON_SECURITISATION in risk_classes:
        branches.append(
            BranchMetadata(
                branch_id="drc-non-securitisation-public-api",
                branch_type=BranchType.NORMAL,
                source_id=profile_id,
                selected=True,
                reason=(
                    "public API executed supported non-securitisation path; "
                    "Euler attribution is not calculated"
                ),
                citations=("US_NPR_210_SCOPE", "US_NPR_210_B_3_III"),
            )
        )
    if DrcRiskClass.SECURITISATION_NON_CTP in risk_classes:
        branches.append(
            BranchMetadata(
                branch_id="drc-securitisation-non-ctp-public-api",
                branch_type=BranchType.NORMAL,
                source_id=profile_id,
                selected=True,
                reason=(
                    "public API executed supported securitisation non-CTP path "
                    "using run-scoped banking-book securitisation risk-weight "
                    "evidence; Euler attribution is not calculated"
                ),
                citations=("US_NPR_210_C_1", "US_NPR_210_C_2", "US_NPR_210_C_3_IV"),
            )
        )
    if DrcRiskClass.CORRELATION_TRADING_PORTFOLIO in risk_classes:
        branches.append(
            BranchMetadata(
                branch_id="drc-ctp-public-api",
                branch_type=BranchType.NORMAL,
                source_id=profile_id,
                selected=True,
                reason=(
                    "public API executed supported CTP path using run-scoped "
                    "risk weights and offset-group evidence; Euler attribution "
                    "is not calculated"
                ),
                citations=("US_NPR_210_D_1", "US_NPR_210_D_2", "US_NPR_210_D_3_V"),
            )
        )
    return tuple(branches)


def _slug(value: str) -> str:
    return value.lower().replace(" ", "-").replace("_", "-")
