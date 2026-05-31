"""
Public CVA capital calculation entry point.
"""

from __future__ import annotations

from collections.abc import Iterable

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_cva.audit import _input_hash_from_validated, validate_cva_result_reconciliation
from frtb_cva.ba_cva import calculate_reduced_portfolio
from frtb_cva.data_models import (
    BaCvaCounterpartyCapital,
    BaCvaStandAloneLine,
    CvaCalculationContext,
    CvaCapitalResult,
    CvaCounterparty,
    CvaHedge,
    CvaMethod,
    CvaNettingSet,
    SaCvaRiskClassCapital,
    SaCvaSensitivity,
)
from frtb_cva.regimes import get_cva_rule_profile
from frtb_cva.sa_cva import calculate_sa_cva_capital
from frtb_cva.scope import validate_method_selection
from frtb_cva.validation import (
    CvaInputError,
    validate_calculation_context,
    validate_cva_counterparties,
    validate_cva_hedges,
    validate_cva_netting_sets,
    validate_sa_cva_sensitivities,
)


def calculate_cva_capital(
    context: CvaCalculationContext,
    counterparties: Iterable[CvaCounterparty],
    netting_sets: Iterable[CvaNettingSet],
    *,
    hedges: Iterable[CvaHedge] = (),
    sensitivities: Iterable[SaCvaSensitivity] = (),
) -> CvaCapitalResult:
    """Calculate supported reduced BA-CVA or SA-CVA GIRR delta capital."""

    validated_context = validate_calculation_context(context)
    validated_counterparties = validate_cva_counterparties(counterparties)
    validated_netting_sets = validate_cva_netting_sets(
        netting_sets,
        counterparties=validated_counterparties,
    )
    validated_hedges = validate_cva_hedges(hedges)
    validated_sensitivities = validate_sa_cva_sensitivities(sensitivities)

    rule_profile = get_cva_rule_profile(validated_context.profile)
    scope = validate_method_selection(
        validated_context,
        netting_sets=validated_netting_sets,
    )

    if scope.method is CvaMethod.BA_CVA_FULL or scope.method is CvaMethod.MIXED_CARVE_OUT:
        raise UnsupportedRegulatoryFeatureError(
            f"CVA method {scope.method.value} is unsupported in this package slice"
        )

    ba_cva_reduced = None
    ba_cva_counterparty_capitals: tuple[BaCvaCounterpartyCapital, ...] = ()
    ba_cva_netting_set_lines: tuple[BaCvaStandAloneLine, ...] = ()
    sa_cva_risk_class_capitals: tuple[SaCvaRiskClassCapital, ...] = ()
    total_cva_capital = 0.0

    if scope.method is CvaMethod.BA_CVA_REDUCED:
        ba_cva_reduced = calculate_reduced_portfolio(
            validated_counterparties,
            validated_netting_sets,
            profile=rule_profile.profile,
        )
        ba_cva_counterparty_capitals = ba_cva_reduced.counterparty_capitals
        ba_cva_netting_set_lines = ba_cva_reduced.netting_set_lines
        total_cva_capital = ba_cva_reduced.k_reduced
    elif scope.method is CvaMethod.SA_CVA:
        if validated_counterparties or validated_netting_sets:
            raise CvaInputError(
                "SA-CVA does not accept counterparty or netting-set inputs; "
                "pass them only when method is BA_CVA_REDUCED",
                field="counterparties_or_netting_sets",
            )
        sa_cva_risk_class_capitals = calculate_sa_cva_capital(
            validated_sensitivities,
            hedges=validated_hedges,
            profile=rule_profile.profile,
            reporting_currency=validated_context.base_currency,
        )
        total_cva_capital = sum(
            risk_class_capital.post_multiplier_capital
            for risk_class_capital in sa_cva_risk_class_capitals
        )

    citations: tuple[str, ...] = ()
    if ba_cva_reduced is not None:
        citations = _collect_citations(ba_cva_reduced.citations, ba_cva_netting_set_lines)
    if sa_cva_risk_class_capitals:
        sa_citations = [
            citation
            for risk_class_capital in sa_cva_risk_class_capitals
            for citation in risk_class_capital.citations
        ]
        citations = _merge_citations(citations, tuple(sa_citations))

    result = CvaCapitalResult(
        run_id=validated_context.run_id,
        calculation_date=validated_context.calculation_date,
        base_currency=validated_context.base_currency,
        profile_id=rule_profile.profile.value,
        profile_hash=rule_profile.content_hash,
        input_hash=_input_hash_from_validated(
            validated_context,
            validated_counterparties,
            validated_netting_sets,
            hedges=validated_hedges,
            sensitivities=validated_sensitivities,
        ),
        method=scope.method,
        total_cva_capital=total_cva_capital,
        ba_cva_reduced=ba_cva_reduced,
        ba_cva_counterparty_capitals=ba_cva_counterparty_capitals,
        ba_cva_netting_set_lines=ba_cva_netting_set_lines,
        sa_cva_risk_class_capitals=sa_cva_risk_class_capitals,
        citations=citations,
        warnings=_profile_warnings(rule_profile.profile.value, scope.method),
        unsupported_flags=scope.unsupported_flags,
        audit_metadata=scope.audit_metadata,
    )
    validate_cva_result_reconciliation(result)
    return result


def _collect_citations(
    reduced_citations: tuple[str, ...],
    netting_set_lines: tuple[BaCvaStandAloneLine, ...],
) -> tuple[str, ...]:
    return _merge_citations(
        reduced_citations,
        tuple(citation for line in netting_set_lines for citation in line.citations),
    )


def _merge_citations(*groups: tuple[str, ...]) -> tuple[str, ...]:
    citation_ids: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for citation_id in group:
            if citation_id not in seen:
                citation_ids.append(citation_id)
                seen.add(citation_id)
    return tuple(citation_ids)


def _profile_warnings(profile_id: str, method: CvaMethod) -> tuple[str, ...]:
    if profile_id != "BASEL_MAR50_2020":
        return ()
    if method is CvaMethod.SA_CVA:
        return ()
    return (
        "BASEL_MAR50_2020 currently supports reduced BA-CVA only; "
        "full BA-CVA and mixed carve-out remain unsupported at the public API.",
    )


__all__ = ["calculate_cva_capital"]
