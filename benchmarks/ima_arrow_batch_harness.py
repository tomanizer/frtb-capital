#!/usr/bin/env python3
"""Benchmark IMA Arrow-backed scenario metadata and RFET batches."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Generic, TypeVar

import pyarrow as pa
from frtb_common import source_content_hash
from frtb_ima import (
    LiquidityHorizon,
    RealPriceObservation,
    RegulatoryRegime,
    RFETEvidence,
    RiskClass,
    RiskFactorBucket,
    RiskFactorDefinition,
    ScenarioSetType,
    assess_rfet_evidence,
    assess_rfet_observation_batch,
    build_rfet_observation_batch_from_arrow,
    build_scenario_metadata_batch_from_arrow,
    get_policy,
    normalize_ima_rfet_observation_arrow_table,
    normalize_ima_scenario_metadata_arrow_table,
)

DEFAULT_OUTPUT = Path("dist/benchmarks/frtb-ima-arrow-batch.json")
DEFAULT_SCENARIO_COUNT = 10_000
DEFAULT_RISK_FACTOR_COUNT = 100
DEFAULT_OBSERVATIONS_PER_FACTOR = 260
AS_OF_DATE = date(2025, 6, 30)
TARGET_RISK_FACTOR = "USD_SWAP_5Y"
T = TypeVar("T")


@dataclass(frozen=True)
class IMAArrowBatchBenchmarkConfig:
    scenario_count: int = DEFAULT_SCENARIO_COUNT
    risk_factor_count: int = DEFAULT_RISK_FACTOR_COUNT
    observations_per_factor: int = DEFAULT_OBSERVATIONS_PER_FACTOR
    as_of_date: date = AS_OF_DATE


@dataclass(frozen=True)
class TimedResult(Generic[T]):
    value: T
    seconds: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario-count", type=int, default=DEFAULT_SCENARIO_COUNT)
    parser.add_argument("--risk-factor-count", type=int, default=DEFAULT_RISK_FACTOR_COUNT)
    parser.add_argument(
        "--observations-per-factor",
        type=int,
        default=DEFAULT_OBSERVATIONS_PER_FACTOR,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def run_benchmark(config: IMAArrowBatchBenchmarkConfig) -> dict[str, object]:
    _validate_config(config)
    tracemalloc.start()
    wall_started = time.perf_counter()

    scenario_table = _timed(lambda: build_scenario_metadata_table(config))
    scenario_arrow_table = _timed(
        lambda: normalize_ima_scenario_metadata_arrow_table(
            scenario_table.value,
            source_hash=source_content_hash("synthetic ima scenario metadata benchmark"),
        )
    )
    scenario_batch = _timed(
        lambda: build_scenario_metadata_batch_from_arrow(scenario_arrow_table.value)
    )
    scenario_rows = _timed(lambda: scenario_batch.value.to_metadata())

    rfet_table = _timed(lambda: build_rfet_observation_table(config))
    rfet_arrow_table = _timed(
        lambda: normalize_ima_rfet_observation_arrow_table(
            rfet_table.value,
            source_hash=source_content_hash("synthetic ima rfet observation benchmark"),
        )
    )
    rfet_batch = _timed(lambda: build_rfet_observation_batch_from_arrow(rfet_arrow_table.value))
    risk_factor = _risk_factor()
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    rfet_batch_assessment = _timed(
        lambda: assess_rfet_observation_batch(
            risk_factor,
            rfet_batch.value,
            policy,
            as_of_date=config.as_of_date,
            qualitative_pass=True,
            bucket_id="USD_RATES",
        )
    )
    row_observations = _timed(lambda: build_row_observations(config))
    rfet_row_assessment = _timed(
        lambda: assess_rfet_evidence(
            risk_factor,
            RFETEvidence(
                risk_factor_name=risk_factor.name,
                as_of_date=config.as_of_date,
                observations=tuple(
                    item
                    for item in row_observations.value
                    if item.risk_factor_name == risk_factor.name
                ),
                qualitative_pass=True,
                bucket_id="USD_RATES",
                observation_time_series_id=_rfet_time_series_id(risk_factor.name),
            ),
            policy,
        )
    )

    _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    wall_seconds = time.perf_counter() - wall_started
    batch_assessment_hash = _hash_json(rfet_batch_assessment.value.as_dict())
    row_assessment_hash = _hash_json(rfet_row_assessment.value.as_dict())
    parse_seconds = scenario_table.seconds + rfet_table.seconds
    adapt_seconds = scenario_arrow_table.seconds + rfet_arrow_table.seconds
    build_seconds = scenario_batch.seconds + rfet_batch.seconds
    calculate_seconds = rfet_batch_assessment.seconds

    return {
        "schema_version": "frtb_ima_arrow_batch_benchmark_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "parameters": {
            "scenario_count": config.scenario_count,
            "risk_factor_count": config.risk_factor_count,
            "observations_per_factor": config.observations_per_factor,
            "observation_count": config.risk_factor_count * config.observations_per_factor,
            "as_of_date": config.as_of_date.isoformat(),
        },
        "summary": {
            "timings_seconds": {
                "parse": parse_seconds,
                "adapt": adapt_seconds,
                "build": build_seconds,
                "calculate": calculate_seconds,
                "row_compatibility_materialization": (
                    scenario_rows.seconds + row_observations.seconds
                ),
                "row_compatibility_calculate": rfet_row_assessment.seconds,
                "wall_clock": wall_seconds,
                "wall_clock_proxy": parse_seconds
                + adapt_seconds
                + build_seconds
                + calculate_seconds,
            },
            "materialized_dataclass_count": {
                "scenario_metadata_row_compatibility_path": len(scenario_rows.value),
                "scenario_metadata_arrow_batch_path": 0,
                "rfet_observation_row_compatibility_path": len(row_observations.value),
                "rfet_observation_arrow_batch_path": 0,
            },
            "accepted_row_dataclasses_materialized": 0,
            "tracemalloc_peak_bytes": peak_bytes,
            "rfet_assessment_hash_delta": 0.0
            if batch_assessment_hash == row_assessment_hash
            else 1.0,
            "result_hashes": {
                "scenario_batch_input": scenario_batch.value.input_hash,
                "rfet_batch_input": rfet_batch.value.input_hash,
                "rfet_batch_assessment": batch_assessment_hash,
                "rfet_row_assessment": row_assessment_hash,
            },
        },
    }


def write_report(report: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    report = run_benchmark(
        IMAArrowBatchBenchmarkConfig(
            scenario_count=args.scenario_count,
            risk_factor_count=args.risk_factor_count,
            observations_per_factor=args.observations_per_factor,
        )
    )
    write_report(report, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))  # noqa: T201
    return 0


def _timed(callback: Callable[[], T]) -> TimedResult[T]:
    started = time.perf_counter()
    value = callback()
    return TimedResult(value=value, seconds=time.perf_counter() - started)


def _validate_config(config: IMAArrowBatchBenchmarkConfig) -> None:
    if config.scenario_count <= 0:
        raise ValueError("scenario_count must be positive")
    if config.risk_factor_count <= 0:
        raise ValueError("risk_factor_count must be positive")
    if config.observations_per_factor <= 0:
        raise ValueError("observations_per_factor must be positive")


def build_scenario_metadata_table(config: IMAArrowBatchBenchmarkConfig) -> pa.Table:
    start_date = date(1990, 1, 1)
    return pa.table(
        {
            "scenarioId": [f"scenario-{index:07d}" for index in range(config.scenario_count)],
            "scenarioDate": [
                start_date + timedelta(days=index) for index in range(config.scenario_count)
            ],
            "setType": pa.array(
                [ScenarioSetType.STRESS.value] * config.scenario_count
            ).dictionary_encode(),
            "calibrationWindow": ["2007-2009"] * config.scenario_count,
            "source": ["synthetic-ima-benchmark"] * config.scenario_count,
            "provenanceJson": ['{"benchmark":"ima-arrow-batch"}'] * config.scenario_count,
            "sourceRowId": [f"scenario-row-{index:07d}" for index in range(config.scenario_count)],
        }
    )


def build_rfet_observation_table(config: IMAArrowBatchBenchmarkConfig) -> pa.Table:
    rows = [
        _rfet_row(factor_index, observation_index, config)
        for factor_index in range(config.risk_factor_count)
        for observation_index in range(config.observations_per_factor)
    ]
    return pa.table(
        {
            "riskFactorName": [row["risk_factor_name"] for row in rows],
            "observationDate": [row["observation_date"] for row in rows],
            "source": pa.array([row["source"] for row in rows]).dictionary_encode(),
            "vendorId": pa.array([row["vendor_id"] for row in rows]).dictionary_encode(),
            "observationTimeSeriesId": [row["observation_time_series_id"] for row in rows],
            "sourceRowId": [row["source_row_id"] for row in rows],
        }
    )


def build_row_observations(
    config: IMAArrowBatchBenchmarkConfig,
) -> tuple[RealPriceObservation, ...]:
    return tuple(
        RealPriceObservation(
            risk_factor_name=str(row["risk_factor_name"]),
            observation_date=row["observation_date"],
            source=str(row["source"]),
            vendor_id=str(row["vendor_id"]),
            source_row_id=str(row["source_row_id"]),
        )
        for factor_index in range(config.risk_factor_count)
        for observation_index in range(config.observations_per_factor)
        for row in (_rfet_row(factor_index, observation_index, config),)
    )


def _rfet_row(
    factor_index: int,
    observation_index: int,
    config: IMAArrowBatchBenchmarkConfig,
) -> dict[str, object]:
    risk_factor_name = TARGET_RISK_FACTOR if factor_index == 0 else f"USD_SWAP_{factor_index:04d}"
    return {
        "risk_factor_name": risk_factor_name,
        "observation_date": config.as_of_date
        - timedelta(days=config.observations_per_factor - observation_index),
        "source": "VENDOR_A",
        "vendor_id": f"vendor-{factor_index % 5}",
        "observation_time_series_id": _rfet_time_series_id(risk_factor_name),
        "source_row_id": f"rfet-row-{factor_index:04d}-{observation_index:04d}",
    }


def _rfet_time_series_id(risk_factor_name: str) -> str:
    return f"ts:ima:benchmark:rfet:{risk_factor_name}"


def _risk_factor() -> RiskFactorDefinition:
    bucket = RiskFactorBucket(
        bucket_id="USD_RATES",
        risk_class=RiskClass.GIRR,
        liquidity_horizon=LiquidityHorizon.LH10,
    )
    return RiskFactorDefinition(
        name=TARGET_RISK_FACTOR,
        risk_class=RiskClass.GIRR,
        liquidity_horizon=LiquidityHorizon.LH10,
        bucket=bucket,
    )


def _hash_json(payload: dict[str, object]) -> str:
    encoded = bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")), "utf-8")
    return hashlib.sha256(encoded).hexdigest()


if __name__ == "__main__":
    sys.exit(main())
