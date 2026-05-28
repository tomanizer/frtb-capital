"""Generate the deterministic capital-run v1 integration fixture."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from frtb_ima.backtesting import trading_desk_backtest_trace_for_policy
from frtb_ima.capital import models_based_capital, supervisory_multiplier_for_policy
from frtb_ima.data_contracts import (
    RFETEvidence,
    RiskFactorBucket,
    RiskFactorDefinition,
    ScenarioCube,
)
from frtb_ima.data_models import (
    LiquidityHorizon,
    RealPriceObservation,
    RiskClass,
    RiskFactor,
)
from frtb_ima.demo_data import DEMO_RISK_FACTORS, make_observations
from frtb_ima.imcc import imcc_breakdown_for_policy
from frtb_ima.lha_builder import imcc_nested_lh_vectors_from_cube
from frtb_ima.nmrf import (
    NMRFStressArtifact,
    route_nmrf_classifications_for_capital,
)
from frtb_ima.nmrf_method_selection import (
    NMRFMethodEvidence,
    assess_direct_loss_robustness,
    select_nmrf_methods,
    selection_input_from_method_evidence,
)
from frtb_ima.nmrf_stress_spec import (
    NMRFDirectShockSpec,
    NMRFFullRevaluationSpec,
    NMRFShockDirection,
    NMRFValuationSpec,
    build_nmrf_valuation_specs,
)
from frtb_ima.nmrf_valuation_run import (
    build_nmrf_valuation_run_request,
    calculate_nmrf_capital_from_valuation_run,
    complete_nmrf_valuation_run,
)
from frtb_ima.pla import pla_assessment_for_policy_with_diagnostics
from frtb_ima.regimes import RegulatoryPolicy, RegulatoryRegime, get_policy
from frtb_ima.rfet_evidence import assess_rfet_evidence
from frtb_ima.scenario import ScenarioMetadata, ScenarioSetType
from frtb_ima.stress_periods import (
    HistoricalStressSeries,
    select_stress_periods_for_policy,
    stress_period_specs_for_nmrf,
    validate_selected_stress_periods,
)

AS_OF_DATE = date(2025, 6, 30)
RUN_ID = "capital-run-v1"
DESK_ID = "rates-credit-demo"
REGIME = RegulatoryRegime.FED_NPR_2_0
GENERATOR_VERSION = "1"
SCHEMA_VERSION = "capital_run_fixture_v1"
POSITION_IDS = (
    "POS_RATE_SWAP",
    "POS_CREDIT_BOND",
    "POS_EQUITY_OPTION",
    "POS_FX_FORWARD",
    "POS_CMDTY_SWAP",
)
NMRF_NAMES = frozenset({"HY_CREDIT_SPD", "EXOTIC_RF"})
ARTIFACT_SOURCE = "fixture upstream valuation artifact"
FIXED_ZIP_DATE = (2026, 1, 1, 0, 0, 0)


def _fixture_risk_factors() -> tuple[RiskFactor, ...]:
    return (
        *DEMO_RISK_FACTORS,
        RiskFactor("COMM_BASIS_RF", RiskClass.COMMODITY, LiquidityHorizon.LH60),
    )


RISK_FACTORS = _fixture_risk_factors()
BUCKETS: Mapping[str, str] = {
    "USD_LIBOR_3M": "GIRR_USD_RATES",
    "EUR_SWAP_10Y": "GIRR_EUR_RATES",
    "IG_CREDIT_SPD": "CSR_IG",
    "HY_CREDIT_SPD": "CSR_HY",
    "SPX_EQUITY": "EQUITY_INDEX_US",
    "EM_EQUITY": "EQUITY_EM",
    "EURUSD_FX": "FX_MAJOR",
    "WTI_CRUDE": "COMMODITY_ENERGY",
    "EXOTIC_RF": "EQUITY_EXOTIC",
    "COMM_BASIS_RF": "COMMODITY_BASIS",
}
CURRENCIES: Mapping[str, str] = {
    "USD_LIBOR_3M": "USD",
    "EUR_SWAP_10Y": "EUR",
    "IG_CREDIT_SPD": "USD",
    "HY_CREDIT_SPD": "USD",
    "SPX_EQUITY": "USD",
    "EM_EQUITY": "USD",
    "EURUSD_FX": "USD",
    "WTI_CRUDE": "USD",
    "EXOTIC_RF": "USD",
    "COMM_BASIS_RF": "USD",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/fixtures/capital_run_v1"),
    )
    args = parser.parse_args()

    generate_fixture(output=args.output, seed=args.seed)
    return 0


def generate_fixture(*, output: Path, seed: int) -> None:
    output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    policy = get_policy(REGIME)

    risk_factor_definitions = _risk_factor_definitions()
    rfet_evidence = _rfet_evidence(risk_factor_definitions)
    scenario_cube = _scenario_cube(rng)
    stress_histories = _stress_histories(rng)
    nmrf_evidence = _nmrf_evidence(policy.es_confidence_level)
    nmrf_artifacts = _nmrf_artifact_arrays()
    pla_bt_vectors = _pla_backtesting_vectors(rng)

    _write_risk_factors(output / "risk_factors.csv", risk_factor_definitions)
    _write_rfet_observations(output / "rfet_observations.csv", rfet_evidence)
    _write_scenario_metadata(output / "scenario_metadata.csv", scenario_cube.scenario_metadata)
    _write_npz(
        output / "scenario_cube.npz",
        {
            "cube": scenario_cube.values,
            "position_ids": np.asarray(scenario_cube.position_ids),
            "risk_factor_names": np.asarray(scenario_cube.risk_factor_names),
        },
    )
    _write_stress_history_metadata(output / "stress_history_metadata.csv", stress_histories)
    _write_npz(output / "stress_histories.npz", _stress_history_arrays(stress_histories))
    _write_json(output / "nmrf_evidence.json", nmrf_evidence)
    _write_npz(output / "nmrf_artifacts.npz", nmrf_artifacts)
    _write_npz(output / "pla_bt_vectors.npz", pla_bt_vectors)

    params = _params(policy, seed)
    _write_json(output / "params.json", params)
    expected_outputs = _expected_outputs(
        policy=policy,
        risk_factors=risk_factor_definitions,
        rfet_evidence=rfet_evidence,
        scenario_cube=scenario_cube,
        stress_histories=stress_histories,
        nmrf_evidence=nmrf_evidence,
        nmrf_artifacts=nmrf_artifacts,
        pla_bt_vectors=pla_bt_vectors,
    )
    _write_json(output / "expected_outputs.json", expected_outputs)
    _write_json(output / "manifest.json", _manifest(output, seed))


def _risk_factor_definitions() -> tuple[RiskFactorDefinition, ...]:
    definitions: list[RiskFactorDefinition] = []
    for risk_factor in RISK_FACTORS:
        bucket = RiskFactorBucket(
            bucket_id=BUCKETS[risk_factor.name],
            risk_class=risk_factor.risk_class,
            liquidity_horizon=risk_factor.liquidity_horizon,
            description="Synthetic fixture bucket",
        )
        definitions.append(
            RiskFactorDefinition(
                name=risk_factor.name,
                risk_class=risk_factor.risk_class,
                liquidity_horizon=risk_factor.liquidity_horizon,
                bucket=bucket,
                currency=CURRENCIES[risk_factor.name],
                metadata={"fixture": "capital_run_v1"},
            )
        )
    return tuple(definitions)


def _rfet_evidence(
    risk_factor_definitions: Sequence[RiskFactorDefinition],
) -> Mapping[str, RFETEvidence]:
    well_observed = [
        risk_factor.name
        for risk_factor in risk_factor_definitions
        if risk_factor.name not in NMRF_NAMES
    ]
    poorly_observed = sorted(NMRF_NAMES)
    observations = make_observations(
        AS_OF_DATE,
        well_observed_names=well_observed,
        poorly_observed_names=poorly_observed,
    )
    by_name: dict[str, list[RealPriceObservation]] = {
        risk_factor.name: [] for risk_factor in risk_factor_definitions
    }
    for observation in observations:
        by_name[observation.risk_factor_name].append(observation)

    definitions_by_name = {risk_factor.name: risk_factor for risk_factor in risk_factor_definitions}
    evidence: dict[str, RFETEvidence] = {}
    for risk_factor_name, risk_factor_observations in by_name.items():
        risk_factor = definitions_by_name[risk_factor_name]
        qualitative_pass = risk_factor_name != "EXOTIC_RF"
        evidence[risk_factor_name] = RFETEvidence(
            risk_factor_name=risk_factor_name,
            as_of_date=AS_OF_DATE,
            observations=tuple(
                sorted(
                    risk_factor_observations,
                    key=lambda item: item.observation_date,
                )
            ),
            qualitative_pass=qualitative_pass,
            bucket_id=risk_factor.bucket.bucket_id if risk_factor.bucket is not None else "",
            metadata={"fixture": "capital_run_v1"},
        )
    return evidence


def _scenario_cube(rng: np.random.Generator) -> ScenarioCube:
    scenario_dates = _business_dates_ending(AS_OF_DATE, 250)
    metadata = tuple(
        ScenarioMetadata(
            scenario_id=f"current-{idx:05d}",
            scenario_date=scenario_date,
            scenario_set=ScenarioSetType.CURRENT,
            source="synthetic fixture current scenario cube",
        )
        for idx, scenario_date in enumerate(scenario_dates)
    )
    n_scenarios = len(metadata)
    n_positions = len(POSITION_IDS)
    n_factors = len(RISK_FACTORS)
    exposures = rng.uniform(0.45, 1.35, size=(n_positions, n_factors))
    position_signs = np.where(
        rng.uniform(size=(n_positions, n_factors)) > 0.25,
        1.0,
        -1.0,
    )
    values = np.zeros((n_scenarios, n_positions, n_factors), dtype=np.float64)
    class_scale = {
        RiskClass.GIRR: 390.0,
        RiskClass.CSR: 640.0,
        RiskClass.EQUITY: 780.0,
        RiskClass.FX: 430.0,
        RiskClass.COMMODITY: 570.0,
    }
    lh_scale = {
        LiquidityHorizon.LH10: 0.85,
        LiquidityHorizon.LH20: 1.00,
        LiquidityHorizon.LH40: 1.25,
        LiquidityHorizon.LH60: 1.55,
        LiquidityHorizon.LH120: 2.10,
    }
    tail_profile = np.linspace(0.0, 1.0, n_scenarios, dtype=np.float64) ** 8
    for factor_index, risk_factor in enumerate(RISK_FACTORS):
        scale = class_scale[risk_factor.risk_class] * lh_scale[risk_factor.liquidity_horizon]
        common = rng.normal(0.0, scale, size=n_scenarios)
        idiosyncratic = rng.normal(0.0, scale * 0.35, size=(n_scenarios, n_positions))
        tail = tail_profile[:, None] * exposures[:, factor_index] * scale * 0.9
        values[:, :, factor_index] = (
            common[:, None] * exposures[:, factor_index] * position_signs[:, factor_index]
            + idiosyncratic
            + tail
        )

    values.flags.writeable = False
    return ScenarioCube(
        values=values,
        scenario_metadata=metadata,
        position_ids=POSITION_IDS,
        risk_factor_names=tuple(risk_factor.name for risk_factor in RISK_FACTORS),
        name="capital_run_v1_current",
    )


def _stress_histories(rng: np.random.Generator) -> tuple[HistoricalStressSeries, ...]:
    histories: list[HistoricalStressSeries] = []
    dates = _business_dates_ending(AS_OF_DATE, 520)
    for index, risk_class in enumerate(sorted(RiskClass, key=lambda item: item.value)):
        base = rng.normal(220.0 + index * 35.0, 90.0 + index * 12.0, size=len(dates))
        losses = np.maximum(base, 0.0)
        start = 90 + index * 23
        severe_window = slice(start, start + 250)
        losses[severe_window] += 1_550.0 + index * 260.0
        losses[start + 210 : start + 250] += np.linspace(100.0, 780.0 + index * 70.0, 40)
        losses.flags.writeable = False
        scenario_ids = tuple(
            f"{risk_class.value.lower()}-stress-{idx:05d}" for idx in range(len(dates))
        )
        histories.append(
            HistoricalStressSeries(
                risk_class=risk_class,
                losses=losses,
                dates=dates,
                source="synthetic fixture stress history",
                scenario_ids=scenario_ids,
                name=f"{risk_class.value} fixture stress history",
            )
        )
    return tuple(histories)


def _nmrf_evidence(confidence_level: float) -> dict[str, object]:
    full_reval_ids = tuple(f"stress-ms-{idx:05d}" for idx in range(250))
    return {
        "HY_CREDIT_SPD": {
            "source": "fixture NMRF method evidence",
            "nonlinear": False,
            "full_revaluation_available": False,
            "direct_method_available": True,
            "direct_shock_well_defined": True,
            "stepwise_available": False,
            "stepwise_required": False,
            "max_loss_fallback_allowed": False,
            "pricing_attempt_count": 6,
            "pricing_failure_count": 0,
            "proxy_or_basis_risk": False,
            "direct_robustness_check": {
                "direct_losses": [95.0, 205.0, 322.0, 451.0],
                "benchmark_losses": [100.0, 200.0, 310.0, 440.0],
                "max_relative_error_threshold": 0.10,
                "source": "fixture checkpoint revaluation",
            },
            "direct_shock": {
                "shock_size": 350.0,
                "shock_unit": "spread_bps",
                "direction": NMRFShockDirection.UP.value,
                "calibration_source": "synthetic stress-period calibration",
                "confidence_level": confidence_level,
                "notes": "Fixture direct shock only; upstream engine supplies losses.",
            },
        },
        "EXOTIC_RF": {
            "source": "fixture NMRF method evidence",
            "nonlinear": True,
            "full_revaluation_available": True,
            "direct_method_available": False,
            "direct_shock_well_defined": False,
            "stepwise_available": False,
            "stepwise_required": False,
            "max_loss_fallback_allowed": False,
            "pricing_attempt_count": 8,
            "pricing_failure_count": 0,
            "proxy_or_basis_risk": False,
            "full_revaluation": {
                "scenario_set_id": "fixture-full-revaluation",
                "market_state_ids": list(full_reval_ids),
                "calibration_source": "synthetic market-state replay",
                "require_full_trade_repricing": True,
                "notes": "Fixture full-revaluation contract; upstream engine supplies losses.",
            },
        },
    }


def _nmrf_artifact_arrays() -> dict[str, npt.NDArray[Any]]:
    scenario_count = 250
    direct_ids = np.asarray(tuple(f"direct-stress-{idx:05d}" for idx in range(scenario_count)))
    full_reval_ids = np.asarray(tuple(f"stress-ms-{idx:05d}" for idx in range(scenario_count)))
    tail = np.linspace(0.0, 1.0, scenario_count, dtype=np.float64) ** 3
    hy_losses = np.linspace(-420.0, 980.0, scenario_count, dtype=np.float64) + tail * 2_350.0
    exotic_losses = np.linspace(-760.0, 1_480.0, scenario_count, dtype=np.float64) + tail * 3_250.0
    return {
        "HY_CREDIT_SPD_losses": hy_losses,
        "HY_CREDIT_SPD_scenario_ids": direct_ids,
        "EXOTIC_RF_losses": exotic_losses,
        "EXOTIC_RF_scenario_ids": full_reval_ids,
    }


def _pla_backtesting_vectors(rng: np.random.Generator) -> dict[str, npt.NDArray[Any]]:
    dates = _business_dates_ending(AS_OF_DATE, 250)
    common = rng.normal(0.0, 820.0, size=len(dates))
    apl = 45.0 + common + rng.normal(0.0, 360.0, size=len(dates))
    hpl = 40.0 + common * 0.94 + rng.normal(0.0, 260.0, size=len(dates))
    rtpl = hpl + rng.normal(0.0, 70.0, size=len(dates))
    var_975 = np.full(len(dates), 2_350.0, dtype=np.float64)
    var_99 = np.full(len(dates), 3_100.0, dtype=np.float64)
    return {
        "observation_dates": np.asarray(tuple(item.isoformat() for item in dates)),
        "apl": apl.astype(np.float64),
        "hpl": hpl.astype(np.float64),
        "rtpl": rtpl.astype(np.float64),
        "var_975": var_975,
        "var_99": var_99,
    }


def _params(policy: RegulatoryPolicy, seed: int) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "run_id": RUN_ID,
        "desk_id": DESK_ID,
        "as_of_date": AS_OF_DATE.isoformat(),
        "regime": policy.regime.value,
        "es_confidence_level": policy.es_confidence_level,
        "es_estimator": policy.es_estimator.value,
        "lha_weights": [
            {"liquidity_horizon": liquidity_horizon.value, "weight": weight}
            for liquidity_horizon, weight in policy.lha_weights
        ],
        "imcc_unconstrained_weight": policy.imcc_unconstrained_weight,
        "rfet_lookback_days": policy.rfet_lookback_days,
        "rfet_short_lh_threshold": policy.rfet_short_lh_threshold,
        "rfet_long_lh_threshold": policy.rfet_long_lh_threshold,
        "stress_period_window_observations": policy.stress_period_window_observations,
        "stress_period_minimum_observations": policy.stress_period_minimum_observations,
        "pla_window_days": policy.pla_window_days,
        "backtesting_window_days": policy.backtesting_window_days,
    }


def _expected_outputs(
    *,
    policy: RegulatoryPolicy,
    risk_factors: Sequence[RiskFactorDefinition],
    rfet_evidence: Mapping[str, RFETEvidence],
    scenario_cube: ScenarioCube,
    stress_histories: Sequence[HistoricalStressSeries],
    nmrf_evidence: Mapping[str, object],
    nmrf_artifacts: Mapping[str, npt.NDArray[Any]],
    pla_bt_vectors: Mapping[str, npt.NDArray[Any]],
) -> dict[str, object]:
    assessments = {
        risk_factor.name: assess_rfet_evidence(
            risk_factor,
            rfet_evidence[risk_factor.name],
            policy,
        )
        for risk_factor in risk_factors
    }
    classifications = {
        risk_factor_name: assessment.modellability_status
        for risk_factor_name, assessment in assessments.items()
    }
    routing = route_nmrf_classifications_for_capital(classifications, policy)
    imcc_cube = _filtered_cube(scenario_cube, routing.imcc_risk_factors)
    risk_factors_by_name = {risk_factor.name: risk_factor for risk_factor in risk_factors}
    imcc_risk_factors = tuple(risk_factors_by_name[name] for name in imcc_cube.risk_factor_names)
    nested_vectors = imcc_nested_lh_vectors_from_cube(imcc_cube, imcc_risk_factors)
    imcc_result = imcc_breakdown_for_policy(
        nested_vectors.all_risk_class_vectors,
        nested_vectors.per_risk_class_vectors,
        policy,
        run_id=RUN_ID,
        desk_id=DESK_ID,
    )

    selection = select_stress_periods_for_policy(
        stress_histories,
        policy,
        as_of_date=AS_OF_DATE,
        run_id=RUN_ID,
        desk_id=DESK_ID,
    )
    nmrf_risk_classes = tuple(
        risk_factors_by_name[name].risk_class for name in routing.ses_risk_factors
    )
    validate_selected_stress_periods(selection, nmrf_risk_classes)
    stress_periods = stress_period_specs_for_nmrf(selection)

    evidence_by_name = _method_evidence_from_json(nmrf_evidence)
    selection_inputs = tuple(
        selection_input_from_method_evidence(
            evidence_by_name[name],
            classifications[name],
            risk_factors_by_name[name].liquidity_horizon,
        )
        for name in routing.ses_risk_factors
    )
    decisions = select_nmrf_methods(selection_inputs, policy)
    specs = build_nmrf_valuation_specs(
        tuple(decision.to_valuation_instruction() for decision in decisions),
        {risk_factor.name: risk_factor.risk_class for risk_factor in risk_factors},
        stress_periods,
        policy,
        direct_shocks=_direct_shocks_from_json(nmrf_evidence),
        full_revaluations=_full_revaluations_from_json(nmrf_evidence),
        source="fixture NMRF valuation spec builder",
    )
    artifacts = _artifacts_from_arrays(specs, nmrf_artifacts)
    request = build_nmrf_valuation_run_request(
        specs,
        policy,
        run_id=RUN_ID,
        desk_id=DESK_ID,
        as_of_date=AS_OF_DATE,
    )
    valuation_run = complete_nmrf_valuation_run(request, artifacts)
    nmrf_capital = calculate_nmrf_capital_from_valuation_run(
        classifications,
        valuation_run,
        policy,
    )

    observation_dates = tuple(
        date.fromisoformat(str(value)) for value in pla_bt_vectors["observation_dates"].tolist()
    )
    pla_result = pla_assessment_for_policy_with_diagnostics(
        pla_bt_vectors["hpl"],
        pla_bt_vectors["rtpl"],
        policy,
        observation_dates=observation_dates,
        run_id=RUN_ID,
        desk_id=DESK_ID,
    )
    backtest_result = trading_desk_backtest_trace_for_policy(
        pla_bt_vectors["apl"],
        pla_bt_vectors["hpl"],
        {0.975: pla_bt_vectors["var_975"], 0.99: pla_bt_vectors["var_99"]},
        policy,
        observation_dates=observation_dates,
        run_id=RUN_ID,
        desk_id=DESK_ID,
    )
    level_99 = backtest_result.result.level(0.99)
    multiplier = supervisory_multiplier_for_policy(level_99.apl_exceptions, policy)
    capital = models_based_capital(
        imcc_t_minus_1=imcc_result.imcc,
        ses_t_minus_1=nmrf_capital.total_ses,
        imcc_60d_avg=imcc_result.imcc * 1.03,
        ses_60d_avg=nmrf_capital.total_ses * 1.02,
        multiplier=multiplier,
        pla_addon=0.0,
    )

    return {
        "scalars": {
            "imcc": _golden(imcc_result.imcc),
            "unconstrained_lha_es": _golden(imcc_result.unconstrained_lha_es),
            "constrained_lha_es": _golden(imcc_result.constrained_lha_es),
            "total_ses": _golden(nmrf_capital.total_ses),
            "pla_ks_statistic": _golden(pla_result.ks_statistic),
            "models_based_capital": _golden(capital.models_based_capital),
            "supervisory_multiplier": _golden(multiplier),
        },
        "classifications": {name: classifications[name].value for name in sorted(classifications)},
        "nmrf_methods": {
            decision.risk_factor_name: decision.method.value for decision in decisions
        },
        "selected_stress_periods": {
            risk_class.value: selection.selected_by_risk_class[risk_class].period_id
            for risk_class in sorted(selection.selected_by_risk_class, key=lambda item: item.value)
        },
        "reconciliation": {
            "passed": valuation_run.passed,
            "failed_item_count": valuation_run.reconciliation.failed_item_count,
            "artifact_count": valuation_run.reconciliation.artifact_count,
        },
        "pla": {
            "zone": pla_result.zone,
            "window_size": pla_result.diagnostics.window_size,
        },
        "backtesting": {
            "model_eligible": backtest_result.model_eligible,
            "window_size": backtest_result.window_size,
            "levels": {
                str(level.confidence_level): {
                    "apl_exceptions": level.apl_exceptions,
                    "hpl_exceptions": level.hpl_exceptions,
                    "level_passed": level.level_passed,
                }
                for level in backtest_result.result.levels
            },
        },
        "capital": {
            "binding_term": capital.binding_term,
        },
    }


def _method_evidence_from_json(raw_evidence: Mapping[str, object]) -> dict[str, NMRFMethodEvidence]:
    evidence_by_name: dict[str, NMRFMethodEvidence] = {}
    for risk_factor_name, raw in raw_evidence.items():
        if not isinstance(raw, Mapping):
            raise TypeError(f"NMRF evidence for {risk_factor_name} must be a mapping")
        robustness = None
        check = raw.get("direct_robustness_check")
        if isinstance(check, Mapping):
            robustness = assess_direct_loss_robustness(
                check["direct_losses"],
                check["benchmark_losses"],
                max_relative_error_threshold=float(check["max_relative_error_threshold"]),
                source=str(check["source"]),
            )
        evidence_by_name[risk_factor_name] = NMRFMethodEvidence(
            risk_factor_name=risk_factor_name,
            nonlinear=bool(raw.get("nonlinear", False)),
            full_revaluation_available=bool(raw.get("full_revaluation_available", False)),
            direct_method_available=bool(raw.get("direct_method_available", False)),
            direct_shock_well_defined=bool(raw.get("direct_shock_well_defined", False)),
            direct_robustness=robustness,
            stepwise_available=bool(raw.get("stepwise_available", False)),
            stepwise_required=bool(raw.get("stepwise_required", False)),
            max_loss_fallback_allowed=bool(raw.get("max_loss_fallback_allowed", False)),
            pricing_attempt_count=int(raw.get("pricing_attempt_count", 0)),
            pricing_failure_count=int(raw.get("pricing_failure_count", 0)),
            proxy_or_basis_risk=bool(raw.get("proxy_or_basis_risk", False)),
            source=str(raw.get("source", "")),
        )
    return evidence_by_name


def _direct_shocks_from_json(raw_evidence: Mapping[str, object]) -> dict[str, NMRFDirectShockSpec]:
    result: dict[str, NMRFDirectShockSpec] = {}
    for risk_factor_name, raw in raw_evidence.items():
        if not isinstance(raw, Mapping):
            raise TypeError(f"NMRF evidence for {risk_factor_name} must be a mapping")
        shock = raw.get("direct_shock")
        if not isinstance(shock, Mapping):
            continue
        result[risk_factor_name] = NMRFDirectShockSpec(
            shock_size=float(shock["shock_size"]),
            shock_unit=str(shock["shock_unit"]),
            direction=NMRFShockDirection(str(shock["direction"])),
            calibration_source=str(shock["calibration_source"]),
            confidence_level=float(shock["confidence_level"]),
            notes=str(shock.get("notes", "")),
        )
    return result


def _full_revaluations_from_json(
    raw_evidence: Mapping[str, object],
) -> dict[str, NMRFFullRevaluationSpec]:
    result: dict[str, NMRFFullRevaluationSpec] = {}
    for risk_factor_name, raw in raw_evidence.items():
        if not isinstance(raw, Mapping):
            raise TypeError(f"NMRF evidence for {risk_factor_name} must be a mapping")
        revaluation = raw.get("full_revaluation")
        if not isinstance(revaluation, Mapping):
            continue
        result[risk_factor_name] = NMRFFullRevaluationSpec(
            scenario_set_id=str(revaluation["scenario_set_id"]),
            market_state_ids=tuple(str(item) for item in revaluation["market_state_ids"]),
            calibration_source=str(revaluation["calibration_source"]),
            require_full_trade_repricing=bool(
                revaluation.get("require_full_trade_repricing", True)
            ),
            notes=str(revaluation.get("notes", "")),
        )
    return result


def _artifacts_from_arrays(
    specs: Sequence[NMRFValuationSpec],
    arrays: Mapping[str, npt.NDArray[Any]],
) -> tuple[NMRFStressArtifact, ...]:
    artifacts: list[NMRFStressArtifact] = []
    for spec in specs:
        risk_factor_name = spec.risk_factor_name
        artifacts.append(
            NMRFStressArtifact(
                risk_factor_name=risk_factor_name,
                method=spec.method,
                losses=arrays[f"{risk_factor_name}_losses"],
                liquidity_horizon=spec.required_liquidity_horizon,
                stress_period=spec.stress_period.stress_period_id,
                source=ARTIFACT_SOURCE,
                scenario_ids=tuple(
                    str(item) for item in arrays[f"{risk_factor_name}_scenario_ids"].tolist()
                ),
                generated_by_prototype=False,
            )
        )
    return tuple(artifacts)


def _filtered_cube(cube: ScenarioCube, risk_factor_names: Sequence[str]) -> ScenarioCube:
    allowed = set(risk_factor_names)
    selected = tuple(name for name in cube.risk_factor_names if name in allowed)
    indices = [cube.risk_factor_index[name] for name in selected]
    values = cube.values[:, :, indices].copy()
    values.flags.writeable = False
    return ScenarioCube(
        values=values,
        scenario_metadata=cube.scenario_metadata,
        position_ids=cube.position_ids,
        risk_factor_names=selected,
        name=f"{cube.name}_filtered_imcc",
    )


def _write_risk_factors(
    path: Path,
    risk_factors: Sequence[RiskFactorDefinition],
) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("name", "risk_class", "liquidity_horizon", "bucket_id", "currency"),
        )
        writer.writeheader()
        for risk_factor in sorted(risk_factors, key=lambda item: item.name):
            writer.writerow(
                {
                    "name": risk_factor.name,
                    "risk_class": risk_factor.risk_class.value,
                    "liquidity_horizon": risk_factor.liquidity_horizon.value,
                    "bucket_id": risk_factor.bucket.bucket_id
                    if risk_factor.bucket is not None
                    else "",
                    "currency": risk_factor.currency,
                }
            )


def _write_rfet_observations(
    path: Path,
    evidence: Mapping[str, RFETEvidence],
) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "risk_factor_name",
                "observation_date",
                "source",
                "qualitative_pass",
                "bucket_id",
            ),
        )
        writer.writeheader()
        rows = [
            {
                "risk_factor_name": package.risk_factor_name,
                "observation_date": observation.observation_date.isoformat(),
                "source": observation.source,
                "qualitative_pass": str(package.qualitative_pass).lower(),
                "bucket_id": package.bucket_id,
            }
            for package in evidence.values()
            for observation in package.observations
        ]
        for row in sorted(
            rows, key=lambda item: (item["risk_factor_name"], item["observation_date"])
        ):
            writer.writerow(row)


def _write_scenario_metadata(
    path: Path,
    metadata: Sequence[ScenarioMetadata],
) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("scenario_id", "scenario_date", "set_type"),
        )
        writer.writeheader()
        for item in metadata:
            writer.writerow(
                {
                    "scenario_id": item.scenario_id,
                    "scenario_date": item.scenario_date.isoformat(),
                    "set_type": item.scenario_set.value,
                }
            )


def _write_stress_history_metadata(
    path: Path,
    histories: Sequence[HistoricalStressSeries],
) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("risk_class", "source"))
        writer.writeheader()
        for history in sorted(histories, key=lambda item: item.risk_class.value):
            writer.writerow(
                {
                    "risk_class": history.risk_class.value,
                    "source": history.source,
                }
            )


def _stress_history_arrays(
    histories: Sequence[HistoricalStressSeries],
) -> dict[str, npt.NDArray[Any]]:
    arrays: dict[str, npt.NDArray[Any]] = {}
    for history in histories:
        prefix = history.risk_class.value
        arrays[f"{prefix}_losses"] = np.asarray(history.losses, dtype=np.float64)
        arrays[f"{prefix}_dates"] = np.asarray(tuple(item.isoformat() for item in history.dates))
        arrays[f"{prefix}_scenario_ids"] = np.asarray(history.scenario_ids)
    return arrays


def _write_npz(path: Path, arrays: Mapping[str, npt.NDArray[Any]]) -> None:
    with zipfile.ZipFile(path, mode="w") as archive:
        for name in sorted(arrays):
            buffer = io.BytesIO()
            np.lib.format.write_array(buffer, np.asarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=FIXED_ZIP_DATE)
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, buffer.getvalue())


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _manifest(output: Path, seed: int) -> dict[str, object]:
    files = sorted(
        path.name for path in output.iterdir() if path.is_file() and path.name != "manifest.json"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "generator": "scripts/generate_fixture.py",
        "generator_command": (
            f"python scripts/generate_fixture.py --seed {seed} --output {output.as_posix()}"
        ),
        "seed": seed,
        "files": {name: {"sha256": _sha256(output / name)} for name in files},
        "sign_conventions": {
            "scenario_cube.npz": {
                "cube": "positive_loss",
            },
            "stress_histories.npz": {
                "*_losses": "positive_loss",
                "*_dates": "not_applicable",
                "*_scenario_ids": "not_applicable",
            },
            "nmrf_artifacts.npz": {
                "*_losses": "positive_loss",
                "*_scenario_ids": "not_applicable",
            },
            "pla_bt_vectors.npz": {
                "apl": "positive_profit",
                "hpl": "positive_profit",
                "rtpl": "positive_profit",
                "var_975": "positive_magnitude",
                "var_99": "positive_magnitude",
                "observation_dates": "not_applicable",
            },
        },
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _business_dates_ending(end_date: date, count: int) -> tuple[date, ...]:
    if count <= 0:
        raise ValueError("count must be positive")
    dates: list[date] = []
    current = end_date
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current)
        current -= timedelta(days=1)
    return tuple(reversed(dates))


def _golden(value: float) -> dict[str, float]:
    return {"value": float(value), "rtol": 1e-9, "atol": 1e-9}


if __name__ == "__main__":
    raise SystemExit(main())
