"""NMRF capital routing and SES assembly."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence

from frtb_ima.data_models import LiquidityHorizon, ModellabilityStatus
from frtb_ima.logging import calculation_log_extra
from frtb_ima.nmrf_aggregation import (
    aggregate_ses_breakdown_for_policy,
    ses_values_from_stress_results,
)
from frtb_ima.nmrf_stress import calculate_nmrf_ses_from_revaluation
from frtb_ima.nmrf_types import (
    NMRFCapitalResult,
    NMRFCapitalRouting,
    NMRFStressArtifact,
    NMRFStressMethod,
    NMRFStressScenarioResult,
)
from frtb_ima.regimes import RegulatoryPolicy

logger = logging.getLogger(__name__)


def _validate_classification_mapping(
    classifications: Mapping[str, ModellabilityStatus],
) -> None:
    if not classifications:
        raise ValueError("classifications must be non-empty")
    for risk_factor_name, status in classifications.items():
        if not risk_factor_name:
            raise ValueError("classification risk-factor names must be non-empty")
        if not isinstance(status, ModellabilityStatus):
            raise TypeError("classification values must be ModellabilityStatus")


def route_nmrf_classifications_for_capital(
    classifications: Mapping[str, ModellabilityStatus],
    policy: RegulatoryPolicy,
) -> NMRFCapitalRouting:
    """Route RFET classifications into IMCC and SES populations.

    Under the Fed NPR 2.0 profile, Type A NMRFs remain in IMCC and also
    require SES. Type B NMRFs require SES only. Under UK CRR / EU comparison
    profiles, modellable factors stay in IMCC and all NMRF statuses feed SES only.
    Parameters
    ----------
    classifications : Mapping[str, ModellabilityStatus]
        Classifications.
    policy : RegulatoryPolicy
        Policy.

    Returns
    -------
    NMRFCapitalRouting
        Result of the operation.
    """
    policy.require_capital_runtime_supported()
    _validate_classification_mapping(classifications)

    modellable: list[str] = []
    type_a: list[str] = []
    type_b: list[str] = []
    for risk_factor_name, status in classifications.items():
        if status == ModellabilityStatus.MODELLABLE:
            modellable.append(risk_factor_name)
        elif status == ModellabilityStatus.TYPE_A_NMRF:
            type_a.append(risk_factor_name)
        elif status == ModellabilityStatus.TYPE_B_NMRF:
            type_b.append(risk_factor_name)

    modellable = sorted(modellable)
    type_a = sorted(type_a)
    type_b = sorted(type_b)

    if policy.uses_type_a_type_b_taxonomy:
        policy.require_type_a_type_b_taxonomy()
        imcc_risk_factors = tuple(modellable + type_a)
    else:
        imcc_risk_factors = tuple(modellable)

    return NMRFCapitalRouting(
        modellable_risk_factors=tuple(modellable),
        type_a_nmrf_risk_factors=tuple(type_a),
        type_b_nmrf_risk_factors=tuple(type_b),
        imcc_risk_factors=imcc_risk_factors,
        ses_risk_factors=tuple(type_a + type_b),
    )


def _artifact_by_risk_factor(
    artifacts: Sequence[NMRFStressArtifact],
) -> dict[str, NMRFStressArtifact]:
    result: dict[str, NMRFStressArtifact] = {}
    for artifact in artifacts:
        if artifact.risk_factor_name in result:
            raise ValueError(f"duplicate NMRF stress artifact for {artifact.risk_factor_name}")
        result[artifact.risk_factor_name] = artifact
    return result


def _validate_required_artifacts(
    routing: NMRFCapitalRouting,
    classifications: Mapping[str, ModellabilityStatus],
    artifacts_by_name: Mapping[str, NMRFStressArtifact],
    required_methods: Mapping[str, NMRFStressMethod] | None,
    required_liquidity_horizons: Mapping[str, LiquidityHorizon] | None,
) -> None:
    classification_names = set(classifications)
    unknown = [
        risk_factor_name
        for risk_factor_name in artifacts_by_name
        if risk_factor_name not in classification_names
    ]
    if unknown:
        raise ValueError(f"NMRF stress artifacts reference unknown risk factors: {unknown}")

    modellable_artifacts = [
        risk_factor_name
        for risk_factor_name in artifacts_by_name
        if classifications[risk_factor_name] == ModellabilityStatus.MODELLABLE
    ]
    if modellable_artifacts:
        raise ValueError(
            "NMRF stress artifacts were supplied for modellable risk factors: "
            f"{modellable_artifacts}"
        )

    missing = [
        risk_factor_name
        for risk_factor_name in routing.ses_risk_factors
        if risk_factor_name not in artifacts_by_name
    ]
    if missing:
        raise ValueError(f"Missing NMRF stress artifacts for: {missing}")

    if required_methods is not None:
        for risk_factor_name in routing.ses_risk_factors:
            expected_method = required_methods.get(risk_factor_name)
            if expected_method is not None:
                actual_method = artifacts_by_name[risk_factor_name].method
                if actual_method != expected_method:
                    raise ValueError(
                        f"NMRF artifact method mismatch for {risk_factor_name}: "
                        f"expected {expected_method.value}, got {actual_method.value}"
                    )

    if required_liquidity_horizons is not None:
        for risk_factor_name in routing.ses_risk_factors:
            required_lh = required_liquidity_horizons.get(risk_factor_name)
            if required_lh is not None:
                actual_lh = artifacts_by_name[risk_factor_name].liquidity_horizon
                if actual_lh.value < required_lh.value:
                    raise ValueError(
                        f"NMRF artifact liquidity horizon too short for {risk_factor_name}: "
                        f"required at least {required_lh.value}, got {actual_lh.value}"
                    )


def _stress_results_for_risk_factors(
    risk_factor_names: Sequence[str],
    artifacts_by_name: Mapping[str, NMRFStressArtifact],
    policy: RegulatoryPolicy,
    *,
    required_methods: Mapping[str, NMRFStressMethod] | None,
    allow_linear_approximation: bool,
    allow_max_loss_fallback: bool,
) -> tuple[NMRFStressScenarioResult, ...]:
    for risk_factor_name in risk_factor_names:
        artifact = artifacts_by_name[risk_factor_name]
        expected_method = (
            None if required_methods is None else required_methods.get(risk_factor_name)
        )
        if (
            artifact.method == NMRFStressMethod.MAX_LOSS_FALLBACK
            and not allow_max_loss_fallback
            and expected_method != NMRFStressMethod.MAX_LOSS_FALLBACK
        ):
            raise ValueError(
                f"MAX_LOSS_FALLBACK artifact for {risk_factor_name} requires "
                "allow_max_loss_fallback=True at the capital assembly layer or an "
                "explicit required_methods entry selecting MAX_LOSS_FALLBACK."
            )
    return tuple(
        calculate_nmrf_ses_from_revaluation(
            artifacts_by_name[risk_factor_name],
            policy,
            allow_linear_approximation=allow_linear_approximation,
        )
        for risk_factor_name in risk_factor_names
    )


def _log_nmrf_capital_complete(
    result: NMRFCapitalResult,
    policy: RegulatoryPolicy,
    *,
    run_id: str | None,
    desk_id: str | None,
) -> None:
    aggregation = result.aggregation
    routing = result.routing
    logger.info(
        "nmrf_capital_complete",
        extra=calculation_log_extra(
            run_id=run_id,
            desk_id=desk_id,
            regime=policy.regime.value,
            total_ses=result.total_ses,
            type_a_count=aggregation.type_a_count,
            type_b_count=aggregation.type_b_count,
            ses_risk_factor_count=len(routing.ses_risk_factors),
            imcc_risk_factor_count=len(routing.imcc_risk_factors),
        ),
    )


def calculate_nmrf_capital_for_policy(
    classifications: Mapping[str, ModellabilityStatus],
    artifacts: Sequence[NMRFStressArtifact],
    policy: RegulatoryPolicy,
    *,
    required_methods: Mapping[str, NMRFStressMethod] | None = None,
    required_liquidity_horizons: Mapping[str, LiquidityHorizon] | None = None,
    allow_linear_approximation: bool = False,
    allow_max_loss_fallback: bool = False,
    run_id: str | None = None,
    desk_id: str | None = None,
) -> NMRFCapitalResult:
    """Validate NMRF stress artifacts, extract SES, and aggregate Type A / Type B.

    Missing Type A or Type B stress artifacts are hard errors. This prevents the
    capital layer from silently falling back to the linear approximation helper.

    Parameters
    ----------
    classifications : Mapping[str, ModellabilityStatus]
        RFET classifications keyed by risk-factor name.
    artifacts : Sequence[NMRFStressArtifact]
        Upstream valuation artifacts for non-modellable risk factors.
    policy : RegulatoryPolicy
        Active regulatory policy.
    required_methods : Mapping[str, NMRFStressMethod] | None, optional
        Expected upstream method by risk-factor name.
    required_liquidity_horizons : Mapping[str, LiquidityHorizon] | None, optional
        Minimum required liquidity horizon by risk-factor name.
    allow_linear_approximation : bool, optional
        Whether labelled linear artifacts may feed SES.
    allow_max_loss_fallback : bool, optional
        Whether MAX_LOSS_FALLBACK artifacts may feed SES without a matching
        ``required_methods`` entry. This preserves the approval boundary from
        method selection to capital assembly.
    run_id : str | None, optional
        Optional run identifier for structured logs.
    desk_id : str | None, optional
        Optional desk identifier for structured logs.

    Returns
    -------
    NMRFCapitalResult
        Routed NMRF SES result and aggregation audit detail.
    """
    policy.require_capital_runtime_supported()
    routing = route_nmrf_classifications_for_capital(classifications, policy)
    artifacts_by_name = _artifact_by_risk_factor(tuple(artifacts))
    _validate_required_artifacts(
        routing,
        classifications,
        artifacts_by_name,
        required_methods,
        required_liquidity_horizons,
    )

    type_a_results = _stress_results_for_risk_factors(
        routing.type_a_nmrf_risk_factors,
        artifacts_by_name,
        policy,
        required_methods=required_methods,
        allow_linear_approximation=allow_linear_approximation,
        allow_max_loss_fallback=allow_max_loss_fallback,
    )
    type_b_results = _stress_results_for_risk_factors(
        routing.type_b_nmrf_risk_factors,
        artifacts_by_name,
        policy,
        required_methods=required_methods,
        allow_linear_approximation=allow_linear_approximation,
        allow_max_loss_fallback=allow_max_loss_fallback,
    )
    aggregation = aggregate_ses_breakdown_for_policy(
        ses_values_from_stress_results(type_a_results),
        ses_values_from_stress_results(type_b_results),
        policy,
    )
    result = NMRFCapitalResult(
        routing=routing,
        type_a_results=type_a_results,
        type_b_results=type_b_results,
        aggregation=aggregation,
    )
    _log_nmrf_capital_complete(result, policy, run_id=run_id, desk_id=desk_id)
    return result


__all__ = [
    "calculate_nmrf_capital_for_policy",
    "route_nmrf_classifications_for_capital",
]
