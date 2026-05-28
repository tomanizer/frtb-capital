"""Sensitivity sweeps over the committed capital_run_v1 fixture.

Generates the evidence tables for `docs/modules/frtb-ima/model_documentation/
04_sensitivity_analysis.md`. The script perturbs one policy parameter at a
time, holding the fixture inputs fixed, and reports the resulting capital and
intermediate metrics. Results are written as JSON for transcription.

Run:
    PYTHONPATH=packages/frtb-ima/src python packages/frtb-ima/scripts/sensitivity_sweep.py \
        --output sensitivity_sweep_results.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

from frtb_ima._version import __version__
from frtb_ima.audit_inputs import compute_inputs_hash
from frtb_ima.capital import (
    models_based_capital,
    supervisory_multiplier_for_policy,
)
from frtb_ima.capital_run_fixture import (
    _filtered_cube,
    as_of_date_from_fixture,
    classifications_from_fixture,
    load_capital_run_v1_fixture,
    nmrf_artifacts_from_fixture,
    nmrf_direct_shocks_from_fixture,
    nmrf_full_revaluations_from_fixture,
    nmrf_method_evidence_from_fixture,
    policy_from_fixture,
)
from frtb_ima.expected_shortfall import ESEstimator
from frtb_ima.imcc import imcc_breakdown_for_policy
from frtb_ima.lha_builder import imcc_nested_lh_vectors_from_cube
from frtb_ima.nmrf import route_nmrf_classifications_for_capital
from frtb_ima.nmrf_method_selection import (
    select_nmrf_methods,
    selection_input_from_method_evidence,
)
from frtb_ima.nmrf_stress_spec import build_nmrf_valuation_specs
from frtb_ima.nmrf_valuation_run import (
    build_nmrf_valuation_run_request,
    calculate_nmrf_capital_from_valuation_run,
    complete_nmrf_valuation_run,
)
from frtb_ima.stress_periods import (
    select_stress_periods_for_policy,
    stress_period_specs_for_nmrf,
    validate_selected_stress_periods,
)

DEFAULT_OUTPUT_PATH = Path("sensitivity_sweep_results.json")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic sensitivity sweeps over capital_run_v1."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="JSON output path. Defaults to ./sensitivity_sweep_results.json.",
    )
    return parser.parse_args()


def _fixture_inputs_hash(fixture: Any) -> str:
    return compute_inputs_hash(
        params=fixture.params,
        risk_factors=fixture.risk_factors,
        rfet_evidence=fixture.rfet_evidence,
        scenario_cube=fixture.scenario_cube,
        stress_histories=fixture.stress_histories,
        nmrf_evidence=fixture.nmrf_evidence,
        nmrf_artifacts=fixture.nmrf_artifacts,
        pla_bt_vectors=fixture.pla_bt_vectors,
    )


def _build_nmrf_capital(fixture: Any, policy: Any) -> Any:
    """Re-run the NMRF pipeline under a perturbed policy."""
    risk_factors_by_name = {rf.name: rf for rf in fixture.risk_factors}
    classifications = classifications_from_fixture(fixture, policy)
    routing = route_nmrf_classifications_for_capital(classifications, policy)
    as_of_date = as_of_date_from_fixture(fixture)
    stress_selection = select_stress_periods_for_policy(
        fixture.stress_histories, policy, as_of_date=as_of_date
    )
    validate_selected_stress_periods(
        stress_selection,
        tuple(risk_factors_by_name[name].risk_class for name in routing.ses_risk_factors),
    )
    method_evidence = nmrf_method_evidence_from_fixture(fixture)
    selection_inputs = tuple(
        selection_input_from_method_evidence(
            method_evidence[name],
            classifications[name],
            risk_factors_by_name[name].liquidity_horizon,
        )
        for name in routing.ses_risk_factors
    )
    decisions = select_nmrf_methods(selection_inputs, policy)
    specs = build_nmrf_valuation_specs(
        tuple(d.to_valuation_instruction() for d in decisions),
        {rf.name: rf.risk_class for rf in fixture.risk_factors},
        stress_period_specs_for_nmrf(stress_selection),
        policy,
        direct_shocks=nmrf_direct_shocks_from_fixture(fixture),
        full_revaluations=nmrf_full_revaluations_from_fixture(fixture),
        source="sensitivity sweep",
    )
    artifacts = nmrf_artifacts_from_fixture(fixture, specs)
    valuation_request = build_nmrf_valuation_run_request(
        specs,
        policy,
        run_id="sensitivity-sweep",
        desk_id="sensitivity-desk",
        as_of_date=as_of_date,
    )
    valuation_run = complete_nmrf_valuation_run(valuation_request, artifacts)
    return calculate_nmrf_capital_from_valuation_run(classifications, valuation_run, policy)


def _build_imcc(fixture: Any, policy: Any) -> Any:
    risk_factors_by_name = {rf.name: rf for rf in fixture.risk_factors}
    classifications = classifications_from_fixture(fixture, policy)
    routing = route_nmrf_classifications_for_capital(classifications, policy)
    imcc_cube = _filtered_cube(fixture.scenario_cube, list(routing.imcc_risk_factors))
    imcc_risk_factors = tuple(risk_factors_by_name[name] for name in imcc_cube.risk_factor_names)
    nested_vectors = imcc_nested_lh_vectors_from_cube(imcc_cube, imcc_risk_factors)
    return imcc_breakdown_for_policy(
        nested_vectors.all_risk_class_vectors,
        nested_vectors.per_risk_class_vectors,
        policy,
    )


def sweep_es_alpha(fixture: Any, base_policy: Any) -> list[dict[str, Any]]:
    """Vary ES confidence level."""
    rows = []
    for alpha in [0.95, 0.96, 0.97, 0.975, 0.98, 0.99]:
        policy = dataclasses.replace(base_policy, es_confidence_level=alpha)
        imcc = _build_imcc(fixture, policy)
        rows.append(
            {
                "alpha": alpha,
                "imcc": round(imcc.imcc, 6),
                "unconstrained_lha_es": round(imcc.unconstrained_lha_es, 6),
                "constrained_lha_es": round(imcc.constrained_lha_es, 6),
            }
        )
    return rows


def sweep_es_estimator(fixture: Any, base_policy: Any) -> list[dict[str, Any]]:
    """Compare ES estimators."""
    rows = []
    for est in [ESEstimator.WEIGHTED_INTERPOLATED, ESEstimator.DISCRETE_CEIL]:
        policy = dataclasses.replace(base_policy, es_estimator=est)
        imcc = _build_imcc(fixture, policy)
        rows.append(
            {
                "estimator": est.value,
                "imcc": round(imcc.imcc, 6),
                "unconstrained_lha_es": round(imcc.unconstrained_lha_es, 6),
                "constrained_lha_es": round(imcc.constrained_lha_es, 6),
            }
        )
    return rows


def sweep_imcc_blend(fixture: Any, base_policy: Any) -> list[dict[str, Any]]:
    """Vary IMCC unconstrained weight."""
    rows = []
    for weight in [0.0, 0.25, 0.5, 0.75, 1.0]:
        policy = dataclasses.replace(base_policy, imcc_unconstrained_weight=weight)
        imcc = _build_imcc(fixture, policy)
        rows.append(
            {
                "unconstrained_weight": weight,
                "imcc": round(imcc.imcc, 6),
                "unconstrained_lha_es": round(imcc.unconstrained_lha_es, 6),
                "constrained_lha_es": round(imcc.constrained_lha_es, 6),
            }
        )
    return rows


def sweep_type_b_rho(fixture: Any, base_policy: Any) -> list[dict[str, Any]]:
    """Vary Type B SES correlation."""
    rows = []
    for rho in [0.0, 0.18, 0.36, 0.54, 0.72, 0.99]:
        policy = dataclasses.replace(base_policy, type_b_ses_rho=rho)
        nmrf = _build_nmrf_capital(fixture, policy)
        rows.append(
            {
                "type_b_rho": rho,
                "total_ses": round(nmrf.total_ses, 6),
            }
        )
    return rows


def sweep_type_b_rho_synthetic(base_policy: Any) -> list[dict[str, Any]]:
    """Demonstrate Type B SES rho-sensitivity using synthetic SES vectors.

    The committed fixture has only 1 Type B NMRF, so total_ses is rho-insensitive
    by construction (no off-diagonal correlation terms). This synthetic sweep
    isolates the aggregation formula across N = 2, 3, 5 with identical
    per-factor SES so that rho directly drives the aggregate.
    """
    from frtb_ima.nmrf import aggregate_ses_breakdown_for_policy

    rows = []
    per_factor_ses = 100.0
    for n_factors in [2, 3, 5]:
        for rho in [0.0, 0.18, 0.36, 0.54, 0.72, 0.99]:
            policy = dataclasses.replace(base_policy, type_b_ses_rho=rho)
            ses_values = tuple([per_factor_ses] * n_factors)
            result = aggregate_ses_breakdown_for_policy(
                type_a_values=(),
                type_b_values=ses_values,
                policy=policy,
            )
            rows.append(
                {
                    "n_type_b_factors": n_factors,
                    "type_b_rho": rho,
                    "per_factor_ses": per_factor_ses,
                    "type_b_correlated_term": round(result.type_b_correlated_term, 6),
                    "total_ses": round(result.total_ses, 6),
                }
            )
    return rows


def sweep_supervisory_multiplier(base_policy: Any) -> list[dict[str, Any]]:
    """Map exception count to multiplier per policy schedule."""
    rows = []
    for count in range(0, 13):
        m = supervisory_multiplier_for_policy(count, base_policy)
        rows.append({"exception_count": count, "multiplier": m})
    return rows


def sweep_capital_with_multiplier(fixture: Any, base_policy: Any) -> list[dict[str, Any]]:
    """Capital response as multiplier changes (holding IMCC and SES fixed)."""
    imcc = _build_imcc(fixture, base_policy)
    nmrf = _build_nmrf_capital(fixture, base_policy)
    rows = []
    for count in [0, 4, 5, 8, 9, 10]:
        m = supervisory_multiplier_for_policy(count, base_policy)
        capital = models_based_capital(
            imcc_t_minus_1=imcc.imcc,
            ses_t_minus_1=nmrf.total_ses,
            imcc_60d_avg=imcc.imcc * 1.03,
            ses_60d_avg=nmrf.total_ses * 1.02,
            multiplier=m,
            pla_addon=0.0,
        )
        rows.append(
            {
                "exception_count": count,
                "multiplier": m,
                "models_based_capital": round(capital.models_based_capital, 6),
                "binding_term": capital.binding_term,
            }
        )
    return rows


def baseline_summary(fixture: Any, base_policy: Any) -> dict[str, Any]:
    imcc = _build_imcc(fixture, base_policy)
    nmrf = _build_nmrf_capital(fixture, base_policy)
    return {
        "es_confidence_level": base_policy.es_confidence_level,
        "es_estimator": base_policy.es_estimator.value,
        "imcc_unconstrained_weight": base_policy.imcc_unconstrained_weight,
        "type_b_ses_rho": base_policy.type_b_ses_rho,
        "imcc": round(imcc.imcc, 6),
        "unconstrained_lha_es": round(imcc.unconstrained_lha_es, 6),
        "constrained_lha_es": round(imcc.constrained_lha_es, 6),
        "total_ses": round(nmrf.total_ses, 6),
    }


def build_results(fixture: Any, base_policy: Any) -> dict[str, Any]:
    return {
        "metadata": {
            "fixture_root": str(fixture.root),
            "inputs_hash": _fixture_inputs_hash(fixture),
            "policy_profile": base_policy.regime.value,
            "policy_hash": base_policy.policy_hash,
            "code_version": __version__,
            "python_minor": f"{sys.version_info.major}.{sys.version_info.minor}",
        },
        "baseline": baseline_summary(fixture, base_policy),
        "es_alpha": sweep_es_alpha(fixture, base_policy),
        "es_estimator": sweep_es_estimator(fixture, base_policy),
        "imcc_blend": sweep_imcc_blend(fixture, base_policy),
        "type_b_rho_fixture": sweep_type_b_rho(fixture, base_policy),
        "type_b_rho_synthetic": sweep_type_b_rho_synthetic(base_policy),
        "supervisory_multiplier": sweep_supervisory_multiplier(base_policy),
        "capital_vs_multiplier": sweep_capital_with_multiplier(fixture, base_policy),
    }


def main() -> None:
    args = _parse_args()
    fixture = load_capital_run_v1_fixture()
    base_policy = policy_from_fixture(fixture)
    results = build_results(fixture, base_policy)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
