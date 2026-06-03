#!/usr/bin/env python3
"""Validate client Arrow/Parquet/CSV handoff files without running capital."""

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
    NormalizedTabularHandoff,
    normalized_handoff_hash,
    source_content_hash,
)

from scripts.client_handoff_registry import empty_table_for_specs, resolve_handoff_entry


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, help="Package import name, e.g. frtb_drc")
    parser.add_argument("--handoff", required=True, help="Registered handoff id, e.g. nonsec")
    parser.add_argument("--input", required=True, type=Path, help="Input .parquet, .arrow, .ipc, or .csv file")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for validation outputs")
    args = parser.parse_args(argv)

    return validate_client_handoff(args.package, args.handoff, args.input, args.output_dir)


def validate_client_handoff(
    package: str,
    handoff_id: str,
    input_path: Path,
    output_dir: Path,
) -> int:
    entry = resolve_handoff_entry(package, handoff_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_hash = source_content_hash(input_path.read_bytes())
    table = _load_table(input_path)
    diagnostics: list[AdapterDiagnostic] = []
    batch_built = False

    try:
        handoff = entry.normalize(table, source_hash=source_hash)
    except Exception as exc:  # noqa: BLE001 - validation CLI must emit diagnostics
        diagnostics.append(
            AdapterDiagnostic(
                code="HANDOFF_NORMALIZATION_ERROR",
                message=str(exc),
                severity=DiagnosticSeverity.ERROR,
            )
        )
        handoff = NormalizedTabularHandoff(
            accepted=empty_table_for_specs(entry.column_specs),
            column_specs=entry.column_specs,
            rejected=table,
            diagnostics=tuple(diagnostics),
            source_hash=source_hash,
        )
    else:
        diagnostics.extend(handoff.diagnostics)
        if entry.build_batch is not None:
            try:
                entry.build_batch(handoff)
                batch_built = True
            except Exception as exc:  # noqa: BLE001 - validation CLI must emit diagnostics
                diagnostics.append(
                    AdapterDiagnostic(
                        code="HANDOFF_BATCH_BUILD_ERROR",
                        message=str(exc),
                        severity=DiagnosticSeverity.ERROR,
                    )
                )
                handoff = NormalizedTabularHandoff(
                    accepted=handoff.accepted,
                    column_specs=handoff.column_specs,
                    row_id_column=handoff.row_id_column,
                    rejected=handoff.rejected,
                    diagnostics=tuple(diagnostics),
                    metadata=handoff.metadata,
                    source_hash=handoff.source_hash,
                    require_unique_row_ids=handoff.require_unique_row_ids,
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
        handoff_id=handoff_id,
        handoff=handoff,
        diagnostics=sorted_diagnostics,
        batch_built=batch_built,
    )
    has_errors = any(item["severity"] == DiagnosticSeverity.ERROR.value for item in sorted_diagnostics)
    rejected_rows = handoff.rejected.num_rows if handoff.rejected is not None else 0
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
    handoff_id: str,
    handoff: NormalizedTabularHandoff,
    diagnostics: list[dict[str, object]],
    batch_built: bool,
) -> None:
    pq.write_table(handoff.accepted, output_dir / "accepted.parquet")
    rejected_rows = 0
    if handoff.rejected is not None:
        rejected_rows = handoff.rejected.num_rows
        if rejected_rows:
            pq.write_table(handoff.rejected, output_dir / "rejected.parquet")
    (output_dir / "diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, sort_keys=True) + "\n"
    )
    summary = {
        "accepted_rows": handoff.accepted.num_rows,
        "batch_built": batch_built,
        "handoff_hash": normalized_handoff_hash(handoff),
        "handoff_id": handoff_id,
        "input_hash": handoff.source_hash,
        "package": package,
        "package_version": _package_version(package),
        "rejected_rows": rejected_rows,
        "source_hash": handoff.source_hash,
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
