#!/usr/bin/env python3
"""Run a deterministic frtb-rrao target-scale performance benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
import tracemalloc
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pyarrow as pa

from frtb_rrao import (
    RraoCalculationContext,
    RraoCapitalResult,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    build_rrao_batch_from_arrow,
    build_rrao_batch_from_columns,
    calculate_rrao_capital,
    calculate_rrao_capital_from_batch,
    normalize_rrao_arrow_table,
    serialize_rrao_result,
)

TARGET_POSITIONS = 100_000
TARGET_DESKS = 50
TARGET_LEGAL_ENTITIES = 10
DEFAULT_OUTPUT = Path("dist/benchmarks/frtb-rrao-target-scale.json")


@dataclass(frozen=True)
class RraoBenchmarkConfig:
    """Configuration for a deterministic RRAO target-scale run."""

    positions: int = TARGET_POSITIONS
    desks: int = TARGET_DESKS
    legal_entities: int = TARGET_LEGAL_ENTITIES
    run_id: str = "frtb-rrao-target-scale"
    calculation_date: date = date(2026, 3, 31)
    base_currency: str = "USD"
    profile: RraoRegulatoryProfile = RraoRegulatoryProfile.US_NPR_2_0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--positions", type=int, default=TARGET_POSITIONS)
    parser.add_argument("--desks", type=int, default=TARGET_DESKS)
    parser.add_argument("--legal-entities", type=int, default=TARGET_LEGAL_ENTITIES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def validate_config(config: RraoBenchmarkConfig) -> None:
    if config.positions <= 0:
        raise ValueError(f"positions must be positive, got {config.positions}")
    if config.desks <= 0:
        raise ValueError(f"desks must be positive, got {config.desks}")
    if config.legal_entities <= 0:
        raise ValueError(f"legal_entities must be positive, got {config.legal_entities}")


def build_context(config: RraoBenchmarkConfig) -> RraoCalculationContext:
    return RraoCalculationContext(
        run_id=config.run_id,
        calculation_date=config.calculation_date,
        base_currency=config.base_currency,
        profile=config.profile,
    )


def build_positions(config: RraoBenchmarkConfig) -> tuple[RraoPosition, ...]:
    validate_config(config)
    return tuple(_position_for_index(index, config) for index in range(config.positions))


def build_column_payload(config: RraoBenchmarkConfig) -> dict[str, object]:
    validate_config(config)
    treatments = [index % 5 for index in range(config.positions)]
    return {
        "position_ids": [f"rrao-target-{index:06d}" for index in range(config.positions)],
        "source_row_ids": [f"row-{index:06d}" for index in range(config.positions)],
        "desk_ids": [f"desk-{index % config.desks:03d}" for index in range(config.positions)],
        "legal_entities": [
            f"LE-{index % config.legal_entities:03d}" for index in range(config.positions)
        ],
        "gross_effective_notionals": [
            100_000.0 + float(index % 1_000) * 1_000.0 for index in range(config.positions)
        ],
        "currencies": [config.base_currency] * config.positions,
        "evidence_types": [
            _evidence_type_for_treatment(treatment).value for treatment in treatments
        ],
        "evidence_labels": [
            _evidence_type_for_treatment(treatment).value.lower() for treatment in treatments
        ],
        "classification_hints": [
            _classification_for_treatment(treatment).value for treatment in treatments
        ],
        "exclusion_reasons": [
            RraoExclusionReason.LISTED.value if treatment == 4 else None for treatment in treatments
        ],
        "exclusion_evidence_ids": [
            f"listed-evidence-{index:06d}" if treatment == 4 else None
            for index, treatment in enumerate(treatments)
        ],
        "lineage_source_systems": ["synthetic-rrao-target-scale"] * config.positions,
        "lineage_source_files": ["generated"] * config.positions,
        "lineage_source_row_ids": [f"row-{index:06d}" for index in range(config.positions)],
        "source_column_maps": [
            (
                ("evidence_type", "evidence_type"),
                ("gross_effective_notional", "gross_effective_notional"),
            )
            for _ in range(config.positions)
        ],
    }


def run_benchmark(config: RraoBenchmarkConfig) -> dict[str, object]:
    validate_config(config)
    tracemalloc.start()
    wall_started = time.perf_counter()

    row_build_started = time.perf_counter()
    positions = build_positions(config)
    row_build_seconds = time.perf_counter() - row_build_started

    row_calculate_started = time.perf_counter()
    result = calculate_rrao_capital(positions, context=build_context(config))
    row_calculate_seconds = time.perf_counter() - row_calculate_started

    row_serialize_started = time.perf_counter()
    payload = serialize_rrao_result(result)
    row_serialize_seconds = time.perf_counter() - row_serialize_started

    columns_build_started = time.perf_counter()
    columns = build_column_payload(config)
    columns_build_seconds = time.perf_counter() - columns_build_started

    batch_build_started = time.perf_counter()
    batch = build_rrao_batch_from_columns(**columns)
    batch_build_seconds = time.perf_counter() - batch_build_started

    batch_calculate_started = time.perf_counter()
    batch_calculation = calculate_rrao_capital_from_batch(batch, context=build_context(config))
    batch_calculate_seconds = time.perf_counter() - batch_calculate_started

    batch_serialize_started = time.perf_counter()
    batch_payload = serialize_rrao_result(batch_calculation.result)
    batch_serialize_seconds = time.perf_counter() - batch_serialize_started

    arrow_table_started = time.perf_counter()
    arrow_table = pa.table(_arrow_columns_from_payload(columns))
    arrow_table_seconds = time.perf_counter() - arrow_table_started

    arrow_handoff_started = time.perf_counter()
    arrow_batch = build_rrao_batch_from_arrow(normalize_rrao_arrow_table(arrow_table))
    arrow_handoff_seconds = time.perf_counter() - arrow_handoff_started

    arrow_calculate_started = time.perf_counter()
    arrow_calculation = calculate_rrao_capital_from_batch(
        arrow_batch,
        context=build_context(config),
    )
    arrow_calculate_seconds = time.perf_counter() - arrow_calculate_started

    _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    wall_seconds = time.perf_counter() - wall_started
    batch_result = batch_calculation.result
    arrow_result = arrow_calculation.result
    batch_payload_hash = audit_payload_hash(batch_payload)
    row_payload_hash = audit_payload_hash(payload)

    return {
        "benchmark_id": "frtb-rrao-target-scale-v2",
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "parameters": {
            "positions": config.positions,
            "desks": config.desks,
            "legal_entities": config.legal_entities,
            "profile": config.profile.value,
            "calculation_date": config.calculation_date.isoformat(),
        },
        "timings": {
            "build_positions_seconds": row_build_seconds,
            "calculate_seconds": row_calculate_seconds,
            "serialize_seconds": row_serialize_seconds,
            "wall_seconds": wall_seconds,
            "positions_per_second": config.positions / row_calculate_seconds
            if row_calculate_seconds
            else 0.0,
            "batch_build_columns_seconds": columns_build_seconds,
            "batch_build_seconds": batch_build_seconds,
            "batch_calculate_seconds": batch_calculate_seconds,
            "batch_serialize_seconds": batch_serialize_seconds,
            "batch_positions_per_second": config.positions / batch_calculate_seconds
            if batch_calculate_seconds
            else 0.0,
            "arrow_table_seconds": arrow_table_seconds,
            "arrow_handoff_seconds": arrow_handoff_seconds,
            "arrow_calculate_seconds": arrow_calculate_seconds,
            "arrow_positions_per_second": config.positions / arrow_calculate_seconds
            if arrow_calculate_seconds
            else 0.0,
        },
        "memory": {
            "peak_traced_bytes": peak_bytes,
        },
        "result": {
            "total_rrao": result.total_rrao,
            "included_count": len(result.lines),
            "excluded_count": len(result.excluded_lines),
            "subtotal_count": len(result.subtotals),
            "profile_hash": result.profile_hash,
            "input_hash": result.input_hash,
            "payload_hash": row_payload_hash,
            "ordering_hash": ordering_hash(result),
            "citation_count": len(result.citations),
            "warning_count": len(result.warnings),
            "batch_input_hash": batch_result.input_hash,
            "batch_ordering_hash": ordering_hash(batch_result),
            "batch_total_rrao": batch_result.total_rrao,
            "arrow_input_hash": arrow_result.input_hash,
            "arrow_ordering_hash": ordering_hash(arrow_result),
            "arrow_total_rrao": arrow_result.total_rrao,
            "batch_payload_hash": batch_payload_hash,
            "arrow_payload_hash": audit_payload_hash(serialize_rrao_result(arrow_result)),
            "batch_absolute_delta": abs(result.total_rrao - batch_result.total_rrao),
            "arrow_absolute_delta": abs(result.total_rrao - arrow_result.total_rrao),
            "batch_accepted_row_dataclasses_materialized": (
                batch_calculation.accepted_row_dataclasses_materialized
            ),
            "arrow_accepted_row_dataclasses_materialized": (
                arrow_calculation.accepted_row_dataclasses_materialized
            ),
        },
    }


def audit_payload_hash(payload: dict[str, object]) -> str:
    """Return a stable replay hash for a serialized RRAO audit payload."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def ordering_hash(result: RraoCapitalResult) -> str:
    """Return a stable hash of line ordering for drift detection."""

    line_ids = [line.position_id for line in result.lines]
    line_ids.extend(line.position_id for line in result.excluded_lines)
    return hashlib.sha256("|".join(line_ids).encode("utf-8")).hexdigest()


def write_report(report: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    config = RraoBenchmarkConfig(
        positions=args.positions,
        desks=args.desks,
        legal_entities=args.legal_entities,
    )
    report = run_benchmark(config)
    write_report(report, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _arrow_columns_from_payload(columns: dict[str, object]) -> dict[str, object]:
    return {
        "position_id": columns["position_ids"],
        "source_row_id": columns["source_row_ids"],
        "desk_id": columns["desk_ids"],
        "legal_entity": columns["legal_entities"],
        "gross_effective_notional": columns["gross_effective_notionals"],
        "currency": columns["currencies"],
        "evidence_type": columns["evidence_types"],
        "evidence_label": columns["evidence_labels"],
        "classification_hint": columns["classification_hints"],
        "exclusion_reason": columns["exclusion_reasons"],
        "exclusion_evidence_id": columns["exclusion_evidence_ids"],
        "lineage_source_system": columns["lineage_source_systems"],
        "lineage_source_file": columns["lineage_source_files"],
        "lineage_source_row_id": columns["lineage_source_row_ids"],
    }


def _position_for_index(index: int, config: RraoBenchmarkConfig) -> RraoPosition:
    treatment = index % 5
    evidence_type = _evidence_type_for_treatment(treatment)
    classification = _classification_for_treatment(treatment)
    exclusion_reason = RraoExclusionReason.LISTED if treatment == 4 else None
    position_id = f"rrao-target-{index:06d}"
    row_id = f"row-{index:06d}"
    return RraoPosition(
        position_id=position_id,
        source_row_id=row_id,
        desk_id=f"desk-{index % config.desks:03d}",
        legal_entity=f"LE-{index % config.legal_entities:03d}",
        gross_effective_notional=100_000.0 + float(index % 1_000) * 1_000.0,
        currency=config.base_currency,
        evidence_type=evidence_type,
        evidence_label=evidence_type.value.lower(),
        classification_hint=classification,
        exclusion_reason=exclusion_reason,
        exclusion_evidence_id=f"listed-evidence-{index:06d}" if exclusion_reason else None,
        lineage=RraoSourceLineage(
            source_system="synthetic-rrao-target-scale",
            source_file="generated",
            source_row_id=row_id,
            source_column_map=(
                ("evidence_type", "evidence_type"),
                ("gross_effective_notional", "gross_effective_notional"),
            ),
        ),
    )


def _evidence_type_for_treatment(index: int) -> RraoEvidenceType:
    if index == 0:
        return RraoEvidenceType.EXOTIC_UNDERLYING
    if index == 1:
        return RraoEvidenceType.GAP_RISK
    if index == 2:
        return RraoEvidenceType.CORRELATION_RISK
    if index == 3:
        return RraoEvidenceType.BEHAVIOURAL_RISK
    return RraoEvidenceType.EXPLICIT_EXCLUSION


def _classification_for_treatment(index: int) -> RraoClassification:
    if index == 0:
        return RraoClassification.EXOTIC
    if index == 4:
        return RraoClassification.EXCLUDED
    return RraoClassification.OTHER_RESIDUAL_RISK


if __name__ == "__main__":
    sys.exit(main())
