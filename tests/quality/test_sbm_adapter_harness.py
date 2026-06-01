from __future__ import annotations

import importlib.util
import math
import sys
import tracemalloc
from pathlib import Path
from types import ModuleType

import pytest


def _load_harness() -> ModuleType:
    module_name = "sbm_adapter_harness_for_test"
    module_path = Path(__file__).parents[2] / "benchmarks" / "sbm_adapter_harness.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_traced_peak_bytes_stops_tracing_on_exception() -> None:
    harness = _load_harness()

    def fail() -> None:
        raise RuntimeError("boom")

    was_tracing = tracemalloc.is_tracing()
    with pytest.raises(RuntimeError, match="boom"):
        harness._traced_peak_bytes(fail)

    if not was_tracing:
        assert not tracemalloc.is_tracing()


@pytest.mark.parametrize(
    ("row_total", "batch_total"),
    ((math.nan, 1.0), (1.0, math.nan), (math.inf, 1.0), (1.0, -math.inf)),
)
def test_matching_capital_delta_rejects_non_finite_totals(
    row_total: float,
    batch_total: float,
) -> None:
    harness = _load_harness()

    with pytest.raises(RuntimeError, match="must be finite"):
        harness._matching_capital_delta(
            label="case",
            row_total=row_total,
            batch_total=batch_total,
        )


def test_matching_capital_delta_rejects_divergent_finite_totals() -> None:
    harness = _load_harness()

    assert harness._matching_capital_delta(
        label="case",
        row_total=10.0,
        batch_total=10.0 + 5e-10,
    ) == pytest.approx(5e-10)
    with pytest.raises(RuntimeError, match="diverged"):
        harness._matching_capital_delta(
            label="case",
            row_total=10.0,
            batch_total=10.0 + 2e-9,
        )
