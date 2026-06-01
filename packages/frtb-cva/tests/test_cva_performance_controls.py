from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_SCRIPT = ROOT / "scripts" / "benchmark_cva_target_scale.py"


def load_benchmark_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("benchmark_cva_target_scale", BENCHMARK_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_benchmark_smoke_is_deterministic() -> None:
    module = load_benchmark_module()
    config = module.CvaBenchmarkConfig(counterparties=20, netting_sets=200, sensitivities=500)
    first = module.run_benchmark(config)
    second = module.run_benchmark(config)
    assert first["result"]["ba_row_payload_hash"] == second["result"]["ba_row_payload_hash"]
    assert first["result"]["ba_column_payload_hash"] == first["result"]["ba_row_payload_hash"]
    assert first["result"]["ba_arrow_payload_hash"] == first["result"]["ba_row_payload_hash"]
    assert first["result"]["ba_column_capital_delta"] == 0.0
    assert first["result"]["ba_arrow_capital_delta"] == 0.0
    assert first["result"]["sa_column_payload_hash"] == first["result"]["sa_row_payload_hash"]
    assert first["result"]["sa_arrow_payload_hash"] == first["result"]["sa_row_payload_hash"]
    assert first["result"]["sa_column_capital_delta"] == 0.0
    assert first["result"]["sa_arrow_capital_delta"] == 0.0
    assert first["dataclasses_materialized"]["ba_column_counterparties"] == 0
    assert first["dataclasses_materialized"]["ba_column_netting_sets"] == 0
    assert first["dataclasses_materialized"]["ba_arrow_counterparties"] == 0
    assert first["dataclasses_materialized"]["ba_arrow_netting_sets"] == 0
    assert first["dataclasses_materialized"]["sa_column_sensitivities"] == 0
    assert first["dataclasses_materialized"]["sa_arrow_sensitivities"] == 0
    assert first["summary"]["materialized_dataclass_count"]["arrow_batch_path"] == 0
    assert first["summary"]["capital_delta_abs_max"] == 0.0
    assert first["summary"]["timings_seconds"]["parse"] >= 0.0
    assert first["summary"]["timings_seconds"]["adapt"] >= 0.0
    assert first["summary"]["timings_seconds"]["build"] >= 0.0
    assert first["summary"]["timings_seconds"]["calculate"] > 0.0
    assert first["timings"]["ba_column_calculate_seconds"] > 0.0
    assert first["timings"]["sa_column_calculate_seconds"] > 0.0
    assert first["timings"]["sa_arrow_calculate_seconds"] > 0.0


def test_benchmark_source_has_no_dataframe_dependency() -> None:
    source = BENCHMARK_SCRIPT.read_text(encoding="utf-8")
    assert "import pandas" not in source
    assert "import polars" not in source
