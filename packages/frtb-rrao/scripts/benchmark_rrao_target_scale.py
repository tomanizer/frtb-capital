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

from frtb_rrao import (
    RraoCalculationContext,
    RraoCapitalResult,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    calculate_rrao_capital,
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


def run_benchmark(config: RraoBenchmarkConfig) -> dict[str, object]:
    validate_config(config)
    tracemalloc.start()
    wall_started = time.perf_counter()

    build_started = time.perf_counter()
    positions = build_positions(config)
    build_seconds = time.perf_counter() - build_started

    calculate_started = time.perf_counter()
    result = calculate_rrao_capital(positions, context=build_context(config))
    calculate_seconds = time.perf_counter() - calculate_started

    serialize_started = time.perf_counter()
    payload = serialize_rrao_result(result)
    serialize_seconds = time.perf_counter() - serialize_started

    _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    wall_seconds = time.perf_counter() - wall_started

    return {
        "benchmark_id": "frtb-rrao-target-scale-v1",
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
            "build_positions_seconds": build_seconds,
            "calculate_seconds": calculate_seconds,
            "serialize_seconds": serialize_seconds,
            "wall_seconds": wall_seconds,
            "positions_per_second": config.positions / calculate_seconds
            if calculate_seconds
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
            "payload_hash": audit_payload_hash(payload),
            "ordering_hash": ordering_hash(result),
            "citation_count": len(result.citations),
            "warning_count": len(result.warnings),
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
