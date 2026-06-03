#!/usr/bin/env python3
"""Validate client Arrow/Parquet/CSV input table files without running capital."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.csv as pa_csv  # type: ignore[import-untyped]
import pyarrow.ipc as pa_ipc  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from frtb_common import (
    AdapterDiagnostic,
    DiagnosticSeverity,
    NormalizedArrowTable,
    normalized_arrow_table_hash,
    source_content_hash,
)

from scripts.client_input_table_registry import empty_table_for_specs, resolve_input_table_entry


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, help="Package import name, e.g. frtb_drc")
    parser.add_argument(
        "--input-table",
        required=True,
        help="Registered input table id, e.g. nonsec",
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Input .parquet, .arrow, .ipc, or .csv file",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for validation outputs",
    )
    args = parser.parse_args(argv)

    return validate_client_input_table(args.package, args.input_table, args.input, args.output_dir)


def validate_client_input_table(
    package: str,
    input_table_id: str,
    input_path: Path,
    output_dir: Path,
) -> int:
    entry = resolve_input_table_entry(package, input_table_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_hash = source_content_hash(input_path.read_bytes())
    table = _load_table(input_path)
    diagnostics: list[AdapterDiagnostic] = []
    batch_built = False

    try:
        input_table = entry.normalize(table, source_hash=source_hash)
    except Exception as exc:
        diagnostics.append(
            AdapterDiagnostic(
                code="INPUT_TABLE_NORMALIZATION_ERROR",
                message=str(exc),
                severity=DiagnosticSeverity.ERROR,
            )
        )
        input_table = NormalizedArrowTable(
            accepted=empty_table_for_specs(entry.column_specs),
            column_specs=entry.column_specs,
            rejected=table,
            diagnostics=tuple(diagnostics),
            source_hash=source_hash,
        )
    else:
        diagnostics.extend(input_table.diagnostics)
        if entry.build_batch is not None:
            try:
                entry.build_batch(input_table)
                batch_built = True
            except Exception as exc:
                diagnostics.append(
                    AdapterDiagnostic(
                        code="INPUT_TABLE_BATCH_BUILD_ERROR",
                        message=str(exc),
                        severity=DiagnosticSeverity.ERROR,
                    )
                )
                input_table = NormalizedArrowTable(
                    accepted=input_table.accepted,
                    column_specs=input_table.column_specs,
                    row_id_column=input_table.row_id_column,
                    rejected=input_table.rejected,
                    diagnostics=tuple(diagnostics),
                    metadata=input_table.metadata,
                    source_hash=input_table.source_hash,
                    require_unique_row_ids=input_table.require_unique_row_ids,
                )

    sorted_diagnostics = sorted(
        (diagnostic.as_dict() for diagnostic in diagnostics),
        key=lambda item: (
            str(item.get("row_id") or ""),
            str(item.get("code") or ""),
            str(item.get("column_name") or ""),
        ),
    )
    _write_outputs(
        output_dir=output_dir,
        package=package,
        input_table_id=input_table_id,
        input_table=input_table,
        diagnostics=sorted_diagnostics,
        batch_built=batch_built,
    )
    has_errors = any(
        item["severity"] == DiagnosticSeverity.ERROR.value for item in sorted_diagnostics
    )
    rejected_rows = input_table.rejected.num_rows if input_table.rejected is not None else 0
    return 1 if has_errors or rejected_rows else 0


def _load_table(path: Path) -> pa.Table:
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        return pq.read_table(path)
    if suffix == ".csv":
        return pa_csv.read_csv(path)
    if suffix in {".arrow", ".ipc", ".feather"}:
        with pa.memory_map(str(path), "r") as source:
            try:
                return pa_ipc.open_file(source).read_all()
            except pa.ArrowInvalid:
                source.seek(0)
                return pa_ipc.open_stream(source).read_all()
    raise ValueError(f"Unsupported input format for {path}; use Parquet, Arrow IPC, or CSV")


def _write_outputs(
    *,
    output_dir: Path,
    package: str,
    input_table_id: str,
    input_table: NormalizedArrowTable,
    diagnostics: list[dict[str, object]],
    batch_built: bool,
) -> None:
    pq.write_table(input_table.accepted, output_dir / "accepted.parquet")
    rejected_rows = 0
    if input_table.rejected is not None:
        rejected_rows = input_table.rejected.num_rows
        if rejected_rows:
            pq.write_table(input_table.rejected, output_dir / "rejected.parquet")
    (output_dir / "diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, sort_keys=True) + "\n"
    )
    summary = {
        "accepted_rows": input_table.accepted.num_rows,
        "batch_built": batch_built,
        "input_table_hash": normalized_arrow_table_hash(input_table),
        "input_table_id": input_table_id,
        "input_hash": input_table.source_hash,
        "package": package,
        "package_version": _package_version(package),
        "rejected_rows": rejected_rows,
        "source_hash": input_table.source_hash,
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


def _package_version(package: str) -> str:
    distribution = package.replace("_", "-")
    try:
        return version(distribution)
    except PackageNotFoundError:
        return ""


if __name__ == "__main__":
    raise SystemExit(main())
