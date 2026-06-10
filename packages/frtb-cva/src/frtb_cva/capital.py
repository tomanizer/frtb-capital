"""
Public CVA capital calculation entry point.
"""

from __future__ import annotations

from collections.abc import Iterable

from frtb_cva._citations import merge_citations as _merge_citations
from frtb_cva._profile_warnings import profile_warnings as _profile_warnings
from frtb_cva.audit import _input_hash_from_validated, validate_cva_result_reconciliation
from frtb_cva.ba_cva import calculate_full_portfolio, calculate_reduced_portfolio
from frtb_cva.data_models import (
    BaCvaCounterpartyCapital,
    BaCvaFullPortfolioResult,
    BaCvaReducedPortfolioResult,
    BaCvaStandAloneLine,
    CvaCalculationContext,
    CvaCapitalResult,
    CvaCounterparty,
    CvaHedge,
    CvaMethod,
    CvaMethodComponentTotal,
    CvaNettingSet,
    SaCvaRiskClassCapital,
    SaCvaSensitivity,
)
from frtb_cva.regimes import get_cva_rule_profile
from frtb_cva.sa_cva import calculate_sa_cva_capital
from frtb_cva.scope import (
    partition_mixed_method_inputs,
    require_mixed_sensitivity_scope_evidence,
    validate_method_selection,
)
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
    """Calculate supported BA-CVA, SA-CVA, or mixed carve-out CVA capital.

    Parameters
    ----------
    context : CvaCalculationContext
        Calculation context carrying profile, currency, and method metadata.
    counterparties : Iterable[CvaCounterparty]
        Counterparty records referenced by netting sets and BA-CVA weights.
    netting_sets : Iterable[CvaNettingSet]
        Netting sets supplying EAD, maturity, and discount inputs for BA-CVA.
    hedges : Iterable[CvaHedge], optional
        Declared BA-CVA or SA-CVA hedge records assessed for eligibility.
    sensitivities : Iterable[SaCvaSensitivity], optional
        Raw SA-CVA sensitivities prior to weighting.

    Returns
    -------
    CvaCapitalResult
        Frozen CVA capital result with method components, citations, and audit hashes.
    """

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

    ba_cva_reduced: BaCvaReducedPortfolioResult | None = None
    ba_cva_full: BaCvaFullPortfolioResult | None = None
    ba_cva_counterparty_capitals: tuple[BaCvaCounterpartyCapital, ...] = ()
    ba_cva_netting_set_lines: tuple[BaCvaStandAloneLine, ...] = ()
    sa_cva_risk_class_capitals: tuple[SaCvaRiskClassCapital, ...] = ()
    method_components: list[CvaMethodComponentTotal] = []
    total_cva_capital = 0.0

    if scope.method is CvaMethod.MIXED_CARVE_OUT:
        (
            ba_counterparties,
            ba_netting_sets,
            _ba_hedges,
            _,
            _,
            sa_hedges,
        ) = partition_mixed_method_inputs(
            validated_counterparties,
            validated_netting_sets,
            validated_hedges,
            carve_out_netting_set_ids=scope.carve_out_netting_set_ids,
        )
        if not validated_sensitivities:
            raise CvaInputError(
                "mixed carve-out requires SA-CVA sensitivities",
                field="sensitivities",
            )
        require_mixed_sensitivity_scope_evidence(validated_context)
        sa_cva_risk_class_capitals = calculate_sa_cva_capital(
            validated_sensitivities,
            hedges=sa_hedges,
            profile=rule_profile.profile,
            reporting_currency=validated_context.base_currency,
        )
        sa_total = sum(item.post_multiplier_capital for item in sa_cva_risk_class_capitals)
        method_components.append(
            CvaMethodComponentTotal(
                method=CvaMethod.SA_CVA,
                total_capital=sa_total,
                citations=tuple(
                    citation for item in sa_cva_risk_class_capitals for citation in item.citations
                ),
            )
        )
        ba_cva_reduced = calculate_reduced_portfolio(
            ba_counterparties,
            ba_netting_sets,
            profile=rule_profile.profile,
        )
        method_components.append(
            CvaMethodComponentTotal(
                method=CvaMethod.BA_CVA_REDUCED,
                total_capital=ba_cva_reduced.k_reduced,
                citations=ba_cva_reduced.citations,
            )
        )
        ba_cva_counterparty_capitals = ba_cva_reduced.counterparty_capitals
        ba_cva_netting_set_lines = ba_cva_reduced.netting_set_lines
        total_cva_capital = sa_total + ba_cva_reduced.k_reduced
    elif scope.method is CvaMethod.BA_CVA_FULL:
        ba_cva_full = calculate_full_portfolio(
            validated_counterparties,
            validated_netting_sets,
            validated_hedges,
            profile=rule_profile.profile,
        )
        ba_cva_reduced = ba_cva_full.reduced
        ba_cva_counterparty_capitals = ba_cva_reduced.counterparty_capitals
        ba_cva_netting_set_lines = ba_cva_reduced.netting_set_lines
        total_cva_capital = ba_cva_full.k_full
    elif scope.method is CvaMethod.BA_CVA_REDUCED:
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
                "pass them only when method is BA_CVA_REDUCED or MIXED_CARVE_OUT",
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
    if ba_cva_full is not None:
        citations = _merge_citations(citations, ba_cva_full.citations)
    if ba_cva_reduced is not None:
        citations = _merge_citations(
            citations,
            _collect_citations(ba_cva_reduced.citations, ba_cva_netting_set_lines),
        )
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
        ba_cva_full=ba_cva_full,
        ba_cva_counterparty_capitals=ba_cva_counterparty_capitals,
        ba_cva_netting_set_lines=ba_cva_netting_set_lines,
        sa_cva_risk_class_capitals=sa_cva_risk_class_capitals,
        method_components=tuple(method_components),
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


__all__ = ["calculate_cva_capital"]
