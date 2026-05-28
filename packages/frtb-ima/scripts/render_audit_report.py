"""Render the committed capital-run v1 fixture as a Markdown audit report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from frtb_ima.audit import (
    CapitalRunAuditLog,
    DeskAuditRecord,
    write_audit_records_ndjson,
    write_capital_run_audit_report,
)
from frtb_ima.audit_inputs import compute_inputs_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEFAULT_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "capital_run_v1"
DEFAULT_OUTPUT = ROOT / "build" / "audit" / "capital_run_v1_audit_report.md"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render the committed capital-run v1 fixture audit report.",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE_ROOT,
        help="Fixture directory containing params.json and expected_outputs.json.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Markdown report output path.",
    )
    parser.add_argument(
        "--ndjson",
        type=Path,
        default=None,
        help="Optional NDJSON desk-record output path.",
    )
    parser.add_argument(
        "--title",
        default="FRTB IMA Capital Run v1 Audit Report",
        help="Markdown report title.",
    )
    args = parser.parse_args()

    log = _audit_log_from_fixture(args.fixture)
    write_capital_run_audit_report(log, args.output, title=args.title)
    if args.ndjson is not None:
        args.ndjson.parent.mkdir(parents=True, exist_ok=True)
        write_audit_records_ndjson(log.desk_records, args.ndjson)


def _audit_log_from_fixture(fixture_root: Path) -> CapitalRunAuditLog:
    from examples.capital_run_fixture import load_capital_run_fixture

    fixture = load_capital_run_fixture(fixture_root)
    params = _read_json(fixture_root / "params.json")
    expected = _read_json(fixture_root / "expected_outputs.json")
    fixture_display = _display_path(fixture_root)
    as_of_date = date.fromisoformat(str(params["as_of_date"]))
    run_id = str(params["run_id"])
    regime = str(params["regime"])
    inputs_hash = _fixture_inputs_hash(fixture)

    desk_record = DeskAuditRecord(
        run_id=run_id,
        desk_id=str(params["desk_id"]),
        regime=regime,
        inputs_hash=inputs_hash,
        as_of_date=as_of_date,
        imcc={
            "imcc": _golden_scalar(expected, "imcc"),
            "unconstrained_lha_es": _golden_scalar(expected, "unconstrained_lha_es"),
            "constrained_lha_es": _golden_scalar(expected, "constrained_lha_es"),
        },
        ses={"total_ses": _golden_scalar(expected, "total_ses")},
        pla={
            **_mapping(expected, "pla"),
            "ks_statistic": _golden_scalar(expected, "pla_ks_statistic"),
        },
        backtesting=_mapping(expected, "backtesting"),
        capital={
            **_mapping(expected, "capital"),
            "models_based_capital": _golden_scalar(expected, "models_based_capital"),
            "supervisory_multiplier": _golden_scalar(expected, "supervisory_multiplier"),
        },
        nmrf_valuation={
            "classifications": _mapping(expected, "classifications"),
            "methods": _mapping(expected, "nmrf_methods"),
            "reconciliation": _mapping(expected, "reconciliation"),
            "selected_stress_periods": _mapping(expected, "selected_stress_periods"),
        },
        elapsed_seconds=0.0,
        notes=(
            "Rendered from committed synthetic fixture outputs; no live market data or "
            "pricing was run by this report command.",
        ),
        metadata={
            "fixture_root": fixture_display,
            "schema_version": str(params["schema_version"]),
            "generator_version": str(params["generator_version"]),
            "seed": int(params["seed"]),
        },
    )
    return CapitalRunAuditLog(
        run_id=run_id,
        regime=regime,
        inputs_hash=inputs_hash,
        as_of_date=as_of_date,
        desk_records=(desk_record,),
        metadata={
            "fixture_root": fixture_display,
            "source": "tests/fixtures/capital_run_v1 expected_outputs.json",
        },
    )


def _fixture_inputs_hash(fixture: Any) -> str:
    return compute_inputs_hash(
        params=fixture.params,
        risk_factors=fixture.risk_factors,
        rfet_evidence=fixture.rfet_evidence,
        scenario_cube=fixture.scenario_cube,
        stress_histories=fixture.stress_histories,
        nmrf_evidence=fixture.nmrf_evidence,
        nmrf_artifacts=fixture.nmrf_artifacts,
        pla_bt_vectors=fixture.pla_bt_vectors,
    )


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _mapping(data: dict[str, Any], key: str) -> dict[str, object]:
    value = data[key]
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object")
    return value


def _golden_scalar(expected: dict[str, Any], name: str) -> float:
    scalars = _mapping(expected, "scalars")
    value = scalars[name]
    if not isinstance(value, dict) or "value" not in value:
        raise ValueError(f"golden scalar {name} must contain a value")
    return float(value["value"])


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    main()
