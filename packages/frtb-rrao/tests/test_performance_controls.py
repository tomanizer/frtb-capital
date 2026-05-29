from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import ModuleType

from frtb_rrao import (
    RraoCalculationContext,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    calculate_rrao_capital,
    serialize_rrao_result,
)

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_SCRIPT = ROOT / "scripts" / "benchmark_rrao_target_scale.py"


def load_benchmark_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("benchmark_rrao_target_scale", BENCHMARK_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_target_scale_benchmark_smoke_is_deterministic() -> None:
    module = load_benchmark_module()
    config = module.RraoBenchmarkConfig(positions=500, desks=10, legal_entities=5)

    first = module.run_benchmark(config)
    second = module.run_benchmark(config)

    assert first["parameters"] == second["parameters"]
    assert first["result"]["included_count"] == 400
    assert first["result"]["excluded_count"] == 100
    assert first["result"]["payload_hash"] == second["result"]["payload_hash"]
    assert first["result"]["ordering_hash"] == second["result"]["ordering_hash"]
    assert first["timings"]["positions_per_second"] > 0.0


def test_benchmark_source_uses_no_dataframe_runtime_dependency() -> None:
    source = BENCHMARK_SCRIPT.read_text(encoding="utf-8")

    assert "import pandas" not in source
    assert "import polars" not in source
    assert "import numpy" not in source


def test_replay_hash_detects_output_ordering_drift() -> None:
    module = load_benchmark_module()
    result = calculate_rrao_capital(replay_positions(), context=replay_context())
    reordered = replace(
        result,
        lines=tuple(reversed(result.lines)),
        excluded_lines=tuple(reversed(result.excluded_lines)),
    )

    assert module.audit_payload_hash(serialize_rrao_result(result)) != module.audit_payload_hash(
        serialize_rrao_result(reordered)
    )


def test_replay_hash_detects_numeric_drift() -> None:
    module = load_benchmark_module()
    result = calculate_rrao_capital(replay_positions(), context=replay_context())
    drifted_line = replace(result.lines[0], add_on=result.lines[0].add_on + 1.0)
    drifted = replace(result, lines=(drifted_line, *result.lines[1:]))

    assert module.audit_payload_hash(serialize_rrao_result(result)) != module.audit_payload_hash(
        serialize_rrao_result(drifted)
    )


def test_benchmark_report_can_be_written(tmp_path: Path) -> None:
    module = load_benchmark_module()
    output = tmp_path / "rrao-benchmark.json"
    report = module.run_benchmark(
        module.RraoBenchmarkConfig(positions=500, desks=10, legal_entities=5)
    )

    module.write_report(report, output)

    assert json.loads(output.read_text(encoding="utf-8"))["result"]["included_count"] == 400


def replay_context() -> RraoCalculationContext:
    return RraoCalculationContext(
        run_id="rrao-performance-replay",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile=RraoRegulatoryProfile.US_NPR_2_0,
    )


def replay_positions() -> tuple[RraoPosition, ...]:
    return (
        RraoPosition(
            position_id="replay-exotic-001",
            source_row_id="row-001",
            desk_id="desk-a",
            legal_entity="LE-001",
            gross_effective_notional=1_000_000.0,
            currency="USD",
            evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
            evidence_label="weather derivative",
            classification_hint=RraoClassification.EXOTIC,
            lineage=sample_lineage("row-001"),
        ),
        RraoPosition(
            position_id="replay-gap-001",
            source_row_id="row-002",
            desk_id="desk-a",
            legal_entity="LE-001",
            gross_effective_notional=2_000_000.0,
            currency="USD",
            evidence_type=RraoEvidenceType.GAP_RISK,
            evidence_label="gap risk",
            classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
            lineage=sample_lineage("row-002"),
        ),
        RraoPosition(
            position_id="replay-listed-001",
            source_row_id="row-003",
            desk_id="desk-b",
            legal_entity="LE-001",
            gross_effective_notional=3_000_000.0,
            currency="USD",
            evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
            evidence_label="listed option",
            classification_hint=RraoClassification.EXCLUDED,
            exclusion_reason=RraoExclusionReason.LISTED,
            exclusion_evidence_id="exchange-listing-001",
            lineage=sample_lineage("row-003"),
        ),
    )


def sample_lineage(row_id: str) -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="synthetic-performance-test",
        source_file="rrao.csv",
        source_row_id=row_id,
        source_column_map=(("AmountUSD", "gross_effective_notional"),),
    )
