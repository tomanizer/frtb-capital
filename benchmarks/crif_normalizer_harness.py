"""Benchmark common CRIF row and vectorized static-mapping normalizers."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
import tracemalloc
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
from frtb_common import (
    CRIF_SOURCE_ROW_ID_COLUMN,
    CrifColumnSpec,
    CrifRiskTypeMapping,
    NormalizedArrowTable,
    TabularLogicalType,
    normalize_crif_arrow_table,
)
from frtb_sbm.arrow_handoff import build_girr_delta_batch_from_arrow
from frtb_sbm.crif import normalize_girr_delta_crif_arrow_table

DEFAULT_OUTPUT = Path("dist/benchmarks/frtb-common-crif-normalizer.json")
DEFAULT_ROW_COUNT = 20_000


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"JSON output path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--row-count",
        type=int,
        default=DEFAULT_ROW_COUNT,
        help=f"Synthetic rows. Default: {DEFAULT_ROW_COUNT}",
    )
    args = parser.parse_args()
    if args.row_count <= 0:
        parser.error("--row-count must be positive")

    report = build_report(row_count=args.row_count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    sys.stdout.write(f"wrote {args.output}\n")


def build_report(*, row_count: int) -> dict[str, object]:
    table = _synthetic_girr_delta_crif_table(row_count)
    row_handoff, row_seconds, row_peak = _measure(
        lambda: normalize_crif_arrow_table(
            table,
            column_specs=_girr_delta_common_column_specs(),
            risk_type_mappings=_girr_delta_risk_type_mappings(),
            source_file="synthetic-girr-delta.crif.csv",
            use_vectorized_static_mapping=False,
        )
    )
    vector_handoff, vector_seconds, vector_peak = _measure(
        lambda: normalize_crif_arrow_table(
            table,
            column_specs=_girr_delta_common_column_specs(),
            risk_type_mappings=_girr_delta_risk_type_mappings(),
            source_file="synthetic-girr-delta.crif.csv",
        )
    )
    _assert_handoffs_match(row_handoff, vector_handoff)

    sbm_batch, sbm_seconds, sbm_peak = _measure(
        lambda: build_girr_delta_batch_from_arrow(
            normalize_girr_delta_crif_arrow_table(
                table,
                source_file="synthetic-girr-delta.crif.csv",
            )
        )
    )

    speedup = row_seconds / vector_seconds if vector_seconds else None
    peak_ratio = row_peak / vector_peak if vector_peak else None
    return {
        "schema_version": "frtb_common_crif_normalizer_benchmark_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": _environment_payload(),
        "controls": {
            "row_count": row_count,
            "synthetic_data_only": True,
            "source_shape": "GIRR delta CRIF-like Arrow table",
            "memory_proxy": (
                "tracemalloc peak bytes for Python allocations; Arrow and NumPy "
                "native buffers may not be fully counted"
            ),
        },
        "common_static_mapping": {
            "row_compatibility_path": {
                "seconds": row_seconds,
                "tracemalloc_peak_bytes": row_peak,
                "accepted_rows": row_handoff.accepted.num_rows,
                "rejected_rows": (
                    0 if row_handoff.rejected is None else row_handoff.rejected.num_rows
                ),
                "diagnostic_count": len(row_handoff.diagnostics),
            },
            "vectorized_static_mapping_path": {
                "seconds": vector_seconds,
                "tracemalloc_peak_bytes": vector_peak,
                "accepted_rows": vector_handoff.accepted.num_rows,
                "rejected_rows": (
                    0 if vector_handoff.rejected is None else vector_handoff.rejected.num_rows
                ),
                "diagnostic_count": len(vector_handoff.diagnostics),
                "accepted_row_dataclasses_materialized": 0,
            },
            "equivalence": {
                "accepted_rows_match": True,
                "rejected_rows_match": True,
                "diagnostics_match": True,
                "source_hash_match": row_handoff.source_hash == vector_handoff.source_hash,
            },
            "speedup_ratio": speedup,
            "python_peak_allocation_ratio": peak_ratio,
        },
        "sbm_girr_delta_consumer": {
            "seconds": sbm_seconds,
            "tracemalloc_peak_bytes": sbm_peak,
            "batch_rows": sbm_batch.row_count,
            "accepted_row_dataclasses_materialized": 0,
            "handoff_hash_present": bool(sbm_batch.handoff_hash),
            "source_hash_present": bool(sbm_batch.source_hash),
        },
    }


def _measure(callback: Callable[[], Any]) -> tuple[Any, float, int]:
    tracemalloc.start()
    started = time.perf_counter()
    try:
        value = callback()
        _current, peak = tracemalloc.get_traced_memory()
        return value, time.perf_counter() - started, peak
    finally:
        tracemalloc.stop()


def _assert_handoffs_match(
    row_handoff: NormalizedArrowTable,
    vector_handoff: NormalizedArrowTable,
) -> None:
    if row_handoff.accepted.to_pydict() != vector_handoff.accepted.to_pydict():
        raise RuntimeError("accepted CRIF handoff rows diverged")
    row_rejected = None if row_handoff.rejected is None else row_handoff.rejected.to_pydict()
    vector_rejected = (
        None if vector_handoff.rejected is None else vector_handoff.rejected.to_pydict()
    )
    if row_rejected != vector_rejected:
        raise RuntimeError("rejected CRIF handoff rows diverged")
    row_diagnostics = [diagnostic.as_dict() for diagnostic in row_handoff.diagnostics]
    vector_diagnostics = [diagnostic.as_dict() for diagnostic in vector_handoff.diagnostics]
    if row_diagnostics != vector_diagnostics:
        raise RuntimeError("CRIF diagnostics diverged")


def _synthetic_girr_delta_crif_table(row_count: int) -> pa.Table:
    return pa.table(
        {
            "SensitivityId": [f"crif-girr-{index:06d}" for index in range(row_count)],
            "RowId": ["" if index % 211 == 0 else f"row-{index:06d}" for index in range(row_count)],
            "RiskType": [
                "RISK_FX" if index % 97 == 0 else " RISK_IRCURVE " for index in range(row_count)
            ],
            "Qualifier": ["USD" if index % 2 == 0 else "EUR" for index in range(row_count)],
            "Bucket": [str((index % 3) + 1) for index in range(row_count)],
            "Label1": ["5y" if index % 2 == 0 else "10y" for index in range(row_count)],
            "Amount": [
                "NaN" if index % 131 == 0 else f"{100_000.0 + index:.2f}"
                for index in range(row_count)
            ],
            "AmountCurrency": ["USD"] * row_count,
            "DeskId": ["rates-desk"] * row_count,
            "LegalEntity": ["LE-001"] * row_count,
        }
    )


def _girr_delta_common_column_specs() -> tuple[CrifColumnSpec, ...]:
    return (
        CrifColumnSpec("sensitivity_id", aliases=("SensitivityId",), required=True),
        CrifColumnSpec(CRIF_SOURCE_ROW_ID_COLUMN, aliases=("RowId",)),
        CrifColumnSpec("risk_type", aliases=("RiskType",), required=True),
        CrifColumnSpec("qualifier", aliases=("Qualifier",)),
        CrifColumnSpec("bucket", aliases=("Bucket",)),
        CrifColumnSpec("label1", aliases=("Label1",)),
        CrifColumnSpec(
            "amount",
            aliases=("Amount",),
            logical_type=TabularLogicalType.FLOAT,
            required=True,
        ),
        CrifColumnSpec("amount_currency", aliases=("AmountCurrency",)),
        CrifColumnSpec("desk_id", aliases=("DeskId",)),
        CrifColumnSpec("legal_entity", aliases=("LegalEntity",)),
    )


def _girr_delta_risk_type_mappings() -> tuple[CrifRiskTypeMapping, ...]:
    return (
        CrifRiskTypeMapping(
            ("RISK_IRCURVE",),
            {"risk_class": "GIRR", "risk_measure": "DELTA"},
        ),
    )


def _environment_payload() -> dict[str, str]:
    return {
        "machine": platform.machine(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": platform.python_version(),
    }


if __name__ == "__main__":
    main()
