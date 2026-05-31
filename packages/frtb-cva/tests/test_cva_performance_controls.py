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
    config = module.CvaBenchmarkConfig(netting_sets=200)
    first = module.run_benchmark(config)
    second = module.run_benchmark(config)
    assert first["result"]["payload_hash"] == second["result"]["payload_hash"]
    assert first["timings"]["netting_sets_per_second"] > 0.0


def test_benchmark_source_has_no_dataframe_dependency() -> None:
    source = BENCHMARK_SCRIPT.read_text(encoding="utf-8")
    assert "import pandas" not in source
