#!/usr/bin/env python3
"""Run a deterministic FRTB-IMA target-scale performance benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
import tracemalloc
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
from frtb_ima.audit import DeskAuditRecord, audit_records_to_ndjson
from frtb_ima.backtesting import trading_desk_backtest_for_policy
from frtb_ima.capital import (
    desk_eligibility_from_results,
    models_based_capital_for_policy,
    pla_addon,
)
from frtb_ima.data_contracts import RiskFactorDefinition, ScenarioCube
from frtb_ima.data_models import LiquidityHorizon, RiskClass
from frtb_ima.imcc import imcc_breakdown_for_policy
from frtb_ima.lha_builder import imcc_nested_lh_vectors_from_cube
from frtb_ima.liquidity_horizon import lha_es_breakdown_from_vectors
from frtb_ima.nmrf import aggregate_ses_breakdown_for_policy
from frtb_ima.pla import pla_assessment_for_policy_with_diagnostics
from frtb_ima.regimes import RegulatoryRegime, get_policy
from frtb_ima.scenario import ScenarioMetadata, ScenarioSetType, make_scenario_metadata

TARGET_SCENARIOS = 10_000
TARGET_DESKS = 100
TARGET_POSITIONS = 1
TARGET_PLA_OBSERVATIONS = 250
TARGET_NMRF_PER_TYPE = 25
DEFAULT_OUTPUT = Path("dist/benchmarks/frtb-ima-target-scale.json")
RISK_CLASSES: tuple[RiskClass, ...] = (
    RiskClass.GIRR,
    RiskClass.CSR,
    RiskClass.EQUITY,
    RiskClass.FX,
    RiskClass.COMMODITY,
)
LIQUIDITY_HORIZONS: tuple[LiquidityHorizon, ...] = (
    LiquidityHorizon.LH10,
    LiquidityHorizon.LH20,
    LiquidityHorizon.LH40,
    LiquidityHorizon.LH60,
    LiquidityHorizon.LH120,
)


@dataclass
class PhaseStats:
    """Cumulative timing for one benchmark phase."""

    seconds: float = 0.0
    count: int = 0

    def add(self, elapsed_seconds: float) -> None:
        self.seconds += elapsed_seconds
        self.count += 1

    def as_dict(self) -> dict[str, object]:
        mean_seconds = self.seconds / self.count if self.count else 0.0
        return {
            "seconds": self.seconds,
            "count": self.count,
            "mean_seconds": mean_seconds,
        }


@dataclass
class BenchmarkTimer:
    """Named phase timer used to aggregate repeated desk-level measurements."""

    phases: dict[str, PhaseStats] = field(default_factory=dict)

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - started
            self.phases.setdefault(name, PhaseStats()).add(elapsed)

    def as_dict(self) -> dict[str, object]:
        return {
            phase_name: stats.as_dict()
            for phase_name, stats in sorted(self.phases.items(), key=lambda item: item[0])
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", type=int, default=TARGET_SCENARIOS)
    parser.add_argument("--desks", type=int, default=TARGET_DESKS)
    parser.add_argument("--positions", type=int, default=TARGET_POSITIONS)
    parser.add_argument("--pla-observations", type=int, default=TARGET_PLA_OBSERVATIONS)
    parser.add_argument("--nmrf-per-type", type=int, default=TARGET_NMRF_PER_TYPE)
    parser.add_argument("--seed", type=int, default=20260528)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    for name in ("scenarios", "desks", "positions", "pla_observations", "nmrf_per_type"):
        value = getattr(args, name)
        if value <= 0:
            raise ValueError(f"{name.replace('_', '-')} must be positive, got {value}")


def build_risk_factors() -> tuple[RiskFactorDefinition, ...]:
    return tuple(
        RiskFactorDefinition(
            name=f"{risk_class.value}_{liquidity_horizon.name}",
            risk_class=risk_class,
            liquidity_horizon=liquidity_horizon,
        )
        for risk_class in RISK_CLASSES
        for liquidity_horizon in LIQUIDITY_HORIZONS
    )


def build_scenario_metadata(scenarios: int) -> tuple[ScenarioMetadata, ...]:
    start = date(1990, 1, 1)
    dates = tuple(start + timedelta(days=offset) for offset in range(scenarios))
    return make_scenario_metadata(
        dates,
        prefix="target-scale",
        scenario_set=ScenarioSetType.CURRENT,
        calibration_window="target-scale-benchmark",
        source="synthetic-deterministic",
    )


def build_cube(
    *,
    desk_index: int,
    scenarios: int,
    positions: int,
    risk_factors: tuple[RiskFactorDefinition, ...],
    metadata: tuple[ScenarioMetadata, ...],
    seed: int,
) -> ScenarioCube:
    rng = np.random.default_rng(seed + desk_index)
    values = rng.standard_normal(
        size=(scenarios, positions, len(risk_factors)),
        dtype=np.float64,
    )
    risk_class_scale = np.linspace(0.8, 1.2, len(risk_factors), dtype=np.float64)
    values *= risk_class_scale.reshape(1, 1, len(risk_factors))
    values += 0.01 * (desk_index + 1)
    return ScenarioCube(
        values=values,
        scenario_metadata=metadata,
        position_ids=tuple(f"desk-{desk_index:03d}-position-{idx:02d}" for idx in range(positions)),
        risk_factor_names=tuple(risk_factor.name for risk_factor in risk_factors),
        name=f"desk-{desk_index:03d}-target-scale",
    )


def build_pl_vectors(observations: int, desk_index: int) -> tuple[np.ndarray, np.ndarray]:
    idx = np.arange(observations, dtype=np.float64)
    hpl = 1.5 * np.sin(idx / 17.0 + desk_index * 0.01)
    rtpl = hpl * 0.995 + 0.003 * np.cos(idx / 13.0)
    return hpl, rtpl


def build_var_vectors(observations: int) -> dict[float, np.ndarray]:
    return {
        0.975: np.full(observations, 5.0, dtype=np.float64),
        0.99: np.full(observations, 6.5, dtype=np.float64),
    }


def build_nmrf_values(count: int, desk_index: int) -> tuple[np.ndarray, np.ndarray]:
    idx = np.arange(1, count + 1, dtype=np.float64)
    type_a = 100.0 + np.abs(np.sin(idx + desk_index)) * 30.0
    type_b = 80.0 + np.abs(np.cos(idx * 0.7 + desk_index)) * 25.0
    return type_a, type_b


def cube_digest(cube: ScenarioCube) -> str:
    """
    Return a raw numeric hash of scenario-cube values for drift detection.

    This intentionally hashes the float64 bytes rather than rounded values.
    Reproducibility remains bounded by NumPy, platform, architecture, and BLAS
    behavior documented in the determinism and performance notes.
    """
    return hashlib.sha256(np.ascontiguousarray(cube.values).tobytes()).hexdigest()


def run_benchmark(args: argparse.Namespace) -> dict[str, object]:
    validate_args(args)
    timer = BenchmarkTimer()
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    risk_factors = build_risk_factors()
    metadata = build_scenario_metadata(args.scenarios)
    var_vectors = build_var_vectors(args.pla_observations)
    records: list[DeskAuditRecord] = []
    sample_results: dict[str, object] = {}

    tracemalloc.start()
    wall_started = time.perf_counter()

    for desk_index in range(args.desks):
        desk_started = time.perf_counter()
        desk_id = f"desk-{desk_index:03d}"
        with timer.phase("synthetic_input_generation"):
            cube = build_cube(
                desk_index=desk_index,
                scenarios=args.scenarios,
                positions=args.positions,
                risk_factors=risk_factors,
                metadata=metadata,
                seed=args.seed,
            )
            inputs_hash = hashlib.sha256(
                bytes(
                    f"{desk_id}:{cube_digest(cube)}:{policy.policy_hash}:{args.seed}",
                    "utf-8",
                )
            ).hexdigest()

        with timer.phase("nested_lh_vector_construction"):
            nested_vectors = imcc_nested_lh_vectors_from_cube(
                cube,
                risk_factors,
                lha_weights=policy.lha_weights,
            )

        with timer.phase("lha_es"):
            lha_result = lha_es_breakdown_from_vectors(
                nested_vectors.all_risk_class_vectors,
                alpha=policy.es_confidence_level,
                estimator=policy.es_estimator,
                lha_weights=policy.lha_weights,
            )

        with timer.phase("imcc_decomposition"):
            imcc_result = imcc_breakdown_for_policy(
                nested_vectors.all_risk_class_vectors,
                nested_vectors.per_risk_class_vectors,
                policy,
                run_id="target-scale-benchmark",
                desk_id=desk_id,
            )

        with timer.phase("nmrf_ses_aggregation"):
            type_a_values, type_b_values = build_nmrf_values(args.nmrf_per_type, desk_index)
            ses_result = aggregate_ses_breakdown_for_policy(
                type_a_values,
                type_b_values,
                policy,
            )

        with timer.phase("pla_backtesting_checks"):
            hpl, rtpl = build_pl_vectors(args.pla_observations, desk_index)
            pla_result = pla_assessment_for_policy_with_diagnostics(
                hpl,
                rtpl,
                policy,
                run_id="target-scale-benchmark",
                desk_id=desk_id,
            )
            backtest_result = trading_desk_backtest_for_policy(
                apl=hpl,
                hpl=hpl,
                var_estimates_by_confidence=var_vectors,
                policy=policy,
                run_id="target-scale-benchmark",
                desk_id=desk_id,
            )

        with timer.phase("capital_assembly"):
            eligibility = desk_eligibility_from_results(
                backtest_result,
                pla_result.zone,
                pla_zone_labels=policy.pla_zone_labels,
            )
            max_exceptions = max(
                (
                    max(level.apl_exceptions, level.hpl_exceptions)
                    for level in backtest_result.levels
                ),
                default=0,
            )
            addon = pla_addon(
                standardized_green_amber=imcc_result.imcc * 1.25 + ses_result.total_ses,
                standardized_amber=0.0,
                ima_green_amber=imcc_result.imcc + ses_result.total_ses,
            )
            capital_result = models_based_capital_for_policy(
                desk_eligibility=eligibility,
                imcc_t_minus_1=imcc_result.imcc,
                ses_t_minus_1=ses_result.total_ses,
                imcc_60d_avg=imcc_result.imcc * 1.01,
                ses_60d_avg=ses_result.total_ses * 1.02,
                pla_addon=addon.pla_addon,
                policy=policy,
                exception_count=max_exceptions,
            )

        with timer.phase("audit_record_construction"):
            records.append(
                DeskAuditRecord(
                    run_id="target-scale-benchmark",
                    desk_id=desk_id,
                    regime=policy.regime.value,
                    desk_eligibility=eligibility.value,
                    policy_hash=policy.policy_hash,
                    inputs_hash=inputs_hash,
                    imcc=imcc_result.as_dict(),
                    ses=ses_result.as_dict(),
                    pla=pla_result.as_dict(),
                    backtesting=backtest_result.as_dict(),
                    capital=capital_result.as_dict(),
                    elapsed_seconds=time.perf_counter() - desk_started,
                    metadata={
                        "benchmark": "target-scale",
                        "lha_es": lha_result.lha_es,
                    },
                )
            )

        if desk_index == args.desks - 1:
            sample_results = {
                "desk_id": desk_id,
                "lha_es": lha_result.lha_es,
                "imcc": imcc_result.imcc,
                "ses": ses_result.total_ses,
                "pla_zone": pla_result.zone,
                "backtesting_model_eligible": backtest_result.model_eligible,
                "models_based_capital": capital_result.models_based_capital,
            }

    with timer.phase("audit_ndjson_serialization"):
        ndjson = audit_records_to_ndjson(records)

    wall_seconds = time.perf_counter() - wall_started
    current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "schema_version": "frtb_ima_target_scale_benchmark_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor() or platform.machine(),
        },
        "fixture_dimensions": {
            "scenarios": args.scenarios,
            "liquidity_horizon_subsets": len(LIQUIDITY_HORIZONS),
            "risk_classes": len(RISK_CLASSES),
            "desks": args.desks,
            "positions_per_desk": args.positions,
            "risk_factors_per_desk": len(risk_factors),
            "pla_backtesting_observations": args.pla_observations,
            "nmrf_type_a_values_per_desk": args.nmrf_per_type,
            "nmrf_type_b_values_per_desk": args.nmrf_per_type,
            "seed": args.seed,
        },
        "totals": {
            "wall_clock_seconds": wall_seconds,
            "tracemalloc_current_bytes": current_bytes,
            "tracemalloc_peak_bytes": peak_bytes,
            "tracemalloc_scope": (
                "Python allocations; NumPy native buffers may not be fully counted"
            ),
            "desk_records": len(records),
            "ndjson_bytes": len(bytes(ndjson, "utf-8")),
        },
        "phase_timings": timer.as_dict(),
        "sample_results": sample_results,
    }


def print_summary(report: dict[str, object], output: Path) -> None:
    dimensions = report["fixture_dimensions"]
    totals = report["totals"]
    phases = report["phase_timings"]
    assert isinstance(dimensions, dict)
    assert isinstance(totals, dict)
    assert isinstance(phases, dict)
    print("FRTB-IMA target-scale benchmark")
    print(
        "Dimensions: "
        f"{dimensions['scenarios']} scenarios x "
        f"{dimensions['liquidity_horizon_subsets']} LH subsets x "
        f"{dimensions['risk_classes']} risk classes x "
        f"{dimensions['desks']} desks"
    )
    print(f"Wall clock: {float(totals['wall_clock_seconds']):.3f}s")
    print(f"Peak memory (tracemalloc): {int(totals['tracemalloc_peak_bytes']) / 1_000_000:.1f} MB")
    print(f"NDJSON bytes: {totals['ndjson_bytes']}")
    print("")
    print("Phase timings:")
    for phase_name, stats in phases.items():
        assert isinstance(stats, dict)
        print(
            f"  {phase_name}: "
            f"{float(stats['seconds']):.3f}s total, "
            f"{float(stats['mean_seconds']):.6f}s mean over {stats['count']}"
        )
    print("")
    print(f"JSON report: {output}")


def main() -> None:
    args = parse_args()
    report = run_benchmark(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print_summary(report, args.output)


if __name__ == "__main__":
    main()
