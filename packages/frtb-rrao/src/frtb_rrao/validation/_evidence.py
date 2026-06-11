"""Evidence and investment-fund validation for RRAO position rows."""

from __future__ import annotations

from frtb_rrao._investment_fund_validation import (
    InvestmentFundRuleFailure,
    InvestmentFundRuleValues,
    validate_investment_fund_rule_values,
)
from frtb_rrao._validation_rules import (
    BACK_TO_BACK_ONLY_FOR_EXACT_EXCLUSION_MESSAGE,
    EXACT_BACK_TO_BACK_REQUIRES_MATCH_MESSAGE,
    EXCLUDED_CLASSIFICATION_REQUIRES_REASON_MESSAGE,
    EXCLUSION_REASON_REQUIRES_EXPLICIT_EVIDENCE_MESSAGE,
    EXPLICIT_EXCLUSION_REQUIRES_REASON_MESSAGE,
    UNDERLYING_COUNT_INTEGER_MESSAGE,
    UNDERLYING_COUNT_NON_NEGATIVE_MESSAGE,
    back_to_back_match_requires_exact_exclusion,
    exact_back_to_back_requires_match,
    excluded_classification_requires_reason,
    exclusion_reason_requires_explicit_evidence,
    explicit_exclusion_requires_reason,
    investment_fund_path_required,
    is_valid_underlying_count,
    supervisor_directive_required,
)
from frtb_rrao.data_models import (
    RraoEvidenceType,
    RraoInvestmentFundDescriptor,
    RraoInvestmentFundExposureType,
    RraoInvestmentFundMethod,
    RraoPosition,
)
from frtb_rrao.validation._common import _finite_float, _require_text
from frtb_rrao.validation._errors import RraoInputError


def _validate_optional_fields(position: RraoPosition) -> None:
    if position.underlying_count is not None:
        if not isinstance(position.underlying_count, int) or isinstance(
            position.underlying_count,
            bool,
        ):
            raise RraoInputError(
                UNDERLYING_COUNT_INTEGER_MESSAGE,
                field="underlying_count",
                position_id=position.position_id,
            )
        if not is_valid_underlying_count(position.underlying_count):
            raise RraoInputError(
                UNDERLYING_COUNT_NON_NEGATIVE_MESSAGE,
                field="underlying_count",
                position_id=position.position_id,
            )

    for field_name in (
        "is_path_dependent",
        "has_maturity",
        "has_strike_or_barrier",
        "has_multiple_strikes_or_barriers",
    ):
        value = getattr(position, field_name)
        if value is not None and not isinstance(value, bool):
            raise RraoInputError(
                f"{field_name} must be a bool when provided",
                field=field_name,
                position_id=position.position_id,
            )

    for field_name in ("is_ctp_hedge", "is_investment_fund_exposure"):
        if not isinstance(getattr(position, field_name), bool):
            raise RraoInputError(
                f"{field_name} must be a bool",
                field=field_name,
                position_id=position.position_id,
            )
    _validate_investment_fund_fields(position)
    for citation in position.citations:
        _require_text(citation, "citations", position.position_id)


def _validate_evidence_requirements(position: RraoPosition) -> None:
    if supervisor_directive_required(position.evidence_type, position.classification_hint):
        _require_text(
            position.supervisor_directive_id,
            "supervisor_directive_id",
            position.position_id,
        )
    if excluded_classification_requires_reason(
        position.classification_hint,
        position.exclusion_reason,
    ):
        raise RraoInputError(
            EXCLUDED_CLASSIFICATION_REQUIRES_REASON_MESSAGE,
            field="exclusion_reason",
            position_id=position.position_id,
        )
    if position.exclusion_reason is not None:
        if exclusion_reason_requires_explicit_evidence(
            position.exclusion_reason,
            position.evidence_type,
        ):
            raise RraoInputError(
                EXCLUSION_REASON_REQUIRES_EXPLICIT_EVIDENCE_MESSAGE,
                field="evidence_type",
                position_id=position.position_id,
            )
        _require_text(position.exclusion_evidence_id, "exclusion_evidence_id", position.position_id)
    if exact_back_to_back_requires_match(
        position.exclusion_reason,
        position.back_to_back_match is not None,
    ):
        raise RraoInputError(
            EXACT_BACK_TO_BACK_REQUIRES_MATCH_MESSAGE,
            field="back_to_back_match",
            position_id=position.position_id,
        )
    if back_to_back_match_requires_exact_exclusion(
        position.exclusion_reason,
        position.back_to_back_match is not None,
    ):
        raise RraoInputError(
            BACK_TO_BACK_ONLY_FOR_EXACT_EXCLUSION_MESSAGE,
            field="back_to_back_match",
            position_id=position.position_id,
        )
    if explicit_exclusion_requires_reason(position.evidence_type, position.exclusion_reason):
        raise RraoInputError(
            EXPLICIT_EXCLUSION_REQUIRES_REASON_MESSAGE,
            field="exclusion_reason",
            position_id=position.position_id,
        )
    if position.evidence_type is RraoEvidenceType.EXPLICIT_EXCLUSION:
        _require_text(position.exclusion_evidence_id, "exclusion_evidence_id", position.position_id)


def _validate_investment_fund_fields(position: RraoPosition) -> None:
    is_fund_path = investment_fund_path_required(
        is_investment_fund_exposure=position.is_investment_fund_exposure,
        evidence_type=position.evidence_type,
        descriptor_present=position.investment_fund_descriptor is not None,
    )
    if not is_fund_path:
        return

    _validate_investment_fund_linkage(position)
    descriptor = position.investment_fund_descriptor
    if descriptor is None:
        return
    _validate_investment_fund_descriptor(position, descriptor)
    _validate_investment_fund_notional_rule(position, descriptor)


def _validate_investment_fund_linkage(position: RraoPosition) -> None:
    _raise_investment_fund_failure(
        validate_investment_fund_rule_values(
            InvestmentFundRuleValues(
                position_id=position.position_id,
                gross_effective_notional=position.gross_effective_notional,
                is_investment_fund_exposure=position.is_investment_fund_exposure,
                evidence_type=position.evidence_type,
                descriptor_present=position.investment_fund_descriptor is not None,
                section_205_method_value=None,
                fund_gross_effective_notional=None,
                included_exposure_ratio=None,
                look_through_available=None,
                mandate_allows_rrao_exposures=None,
            ),
            check_descriptor_values=False,
        )
    )


def _validate_investment_fund_descriptor(
    position: RraoPosition,
    descriptor: object,
) -> None:
    if not isinstance(descriptor, RraoInvestmentFundDescriptor):
        raise RraoInputError(
            "invalid investment fund descriptor",
            field="investment_fund_descriptor",
            position_id=position.position_id,
        )
    _require_text(descriptor.fund_id, "investment_fund_descriptor.fund_id", position.position_id)
    _require_text(
        descriptor.mandate_evidence_id,
        "investment_fund_descriptor.mandate_evidence_id",
        position.position_id,
    )
    _require_text(
        descriptor.section_205_evidence_id,
        "investment_fund_descriptor.section_205_evidence_id",
        position.position_id,
    )
    if not isinstance(descriptor.section_205_method, RraoInvestmentFundMethod):
        raise RraoInputError(
            "invalid investment fund method",
            field="investment_fund_descriptor.section_205_method",
            position_id=position.position_id,
        )
    if not isinstance(descriptor.included_exposure_type, RraoInvestmentFundExposureType):
        raise RraoInputError(
            "invalid investment fund exposure type",
            field="investment_fund_descriptor.included_exposure_type",
            position_id=position.position_id,
        )
    _validate_fund_boolean_descriptor_fields(position, descriptor)


def _validate_fund_boolean_descriptor_fields(
    position: RraoPosition,
    descriptor: RraoInvestmentFundDescriptor,
) -> None:
    if not isinstance(descriptor.look_through_available, bool):
        raise RraoInputError(
            "look-through availability must be a bool",
            field="investment_fund_descriptor.look_through_available",
            position_id=position.position_id,
        )
    if not isinstance(descriptor.mandate_allows_rrao_exposures, bool):
        raise RraoInputError(
            "mandate RRAO exposure flag must be a bool",
            field="investment_fund_descriptor.mandate_allows_rrao_exposures",
            position_id=position.position_id,
        )


def _validate_investment_fund_notional_rule(
    position: RraoPosition,
    descriptor: RraoInvestmentFundDescriptor,
) -> None:
    fund_notional = _finite_float(
        descriptor.fund_gross_effective_notional,
        field="investment_fund_descriptor.fund_gross_effective_notional",
    )
    ratio = _finite_float(
        descriptor.included_exposure_ratio,
        field="investment_fund_descriptor.included_exposure_ratio",
    )
    _raise_investment_fund_failure(
        validate_investment_fund_rule_values(
            InvestmentFundRuleValues(
                position_id=position.position_id,
                gross_effective_notional=position.gross_effective_notional,
                is_investment_fund_exposure=position.is_investment_fund_exposure,
                evidence_type=position.evidence_type,
                descriptor_present=True,
                section_205_method_value=descriptor.section_205_method.value,
                fund_gross_effective_notional=fund_notional,
                included_exposure_ratio=ratio,
                look_through_available=descriptor.look_through_available,
                mandate_allows_rrao_exposures=descriptor.mandate_allows_rrao_exposures,
            )
        )
    )


def _raise_investment_fund_failure(failure: InvestmentFundRuleFailure | None) -> None:
    if failure is not None:
        raise RraoInputError(
            failure.message,
            field=failure.field,
            position_id=failure.position_id,
        )
