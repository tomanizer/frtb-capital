from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_harness() -> ModuleType:
    module_name = "ima_arrow_batch_harness_for_test"
    module_path = Path(__file__).parents[2] / "benchmarks" / "ima_arrow_batch_harness.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_ima_arrow_batch_harness_reports_zero_fast_path_dataclasses() -> None:
    harness = _load_harness()
    config = harness.IMAArrowBatchBenchmarkConfig(
        scenario_count=20,
        risk_factor_count=4,
        observations_per_factor=30,
    )

    report = harness.run_benchmark(config)

    summary = report["summary"]
    assert summary["accepted_row_dataclasses_materialized"] == 0
    assert summary["materialized_dataclass_count"]["scenario_metadata_arrow_batch_path"] == 0
    assert summary["materialized_dataclass_count"]["rfet_observation_arrow_batch_path"] == 0
    assert summary["materialized_dataclass_count"]["scenario_metadata_row_compatibility_path"] == 20
    assert summary["materialized_dataclass_count"]["rfet_observation_row_compatibility_path"] == 120
    assert summary["rfet_assessment_hash_delta"] == 0.0
    assert (
        summary["result_hashes"]["rfet_batch_assessment"]
        == summary["result_hashes"]["rfet_row_assessment"]
    )
    assert summary["timings_seconds"]["parse"] >= 0.0
    assert summary["timings_seconds"]["adapt"] >= 0.0
    assert summary["timings_seconds"]["build"] >= 0.0
    assert summary["timings_seconds"]["calculate"] >= 0.0
