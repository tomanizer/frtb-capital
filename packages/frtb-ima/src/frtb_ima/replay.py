"""Replay committed fixture audit records and report reproducibility checks."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from frtb_ima import capital_run_fixture as fixture_module
from frtb_ima._version import __version__
from frtb_ima.audit_inputs import compute_inputs_hash

SCHEMA_VERSION = "frtb_ima_replay_report_v1"
DEFAULT_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "capital_run_v1"

_SCALAR_TOLERANCE_BY_PATH: dict[tuple[str, ...], str] = {
    ("imcc", "imcc"): "imcc",
    ("imcc", "unconstrained_lha_es"): "unconstrained_lha_es",
    ("imcc", "constrained_lha_es"): "constrained_lha_es",
    ("ses", "total_ses"): "total_ses",
    ("pla", "ks_statistic"): "pla_ks_statistic",
    ("capital", "models_based_capital"): "models_based_capital",
    ("capital", "supervisory_multiplier"): "supervisory_multiplier",
}
_SECTION_PATHS: tuple[tuple[str, ...], ...] = (
    ("imcc", "imcc"),
    ("imcc", "unconstrained_lha_es"),
    ("imcc", "constrained_lha_es"),
    ("ses", "total_ses"),
    ("pla", "zone"),
    ("pla", "window_size"),
    ("pla", "ks_statistic"),
    ("backtesting", "model_eligible"),
    ("backtesting", "window_size"),
    ("backtesting", "levels", "0.975", "apl_exceptions"),
    ("backtesting", "levels", "0.975", "hpl_exceptions"),
    ("backtesting", "levels", "0.975", "level_passed"),
    ("backtesting", "levels", "0.99", "apl_exceptions"),
    ("backtesting", "levels", "0.99", "hpl_exceptions"),
    ("backtesting", "levels", "0.99", "level_passed"),
    ("capital", "binding_term"),
    ("capital", "models_based_capital"),
    ("capital", "supervisory_multiplier"),
    ("nmrf_valuation", "classifications"),
    ("nmrf_valuation", "methods"),
    ("nmrf_valuation", "reconciliation"),
    ("nmrf_valuation", "selected_stress_periods"),
)


def replay_audit_file(
    audit_path: str | Path,
    fixture_root: str | Path = DEFAULT_FIXTURE_ROOT,
    *,
    expected_code_version: str | None = None,
    expected_policy_hash: str | None = None,
    expected_inputs_hash: str | None = None,
) -> dict[str, object]:
    """Replay an audit NDJSON file against a fixture directory.
    Parameters
    ----------
    audit_path : str | Path
        Audit path.
    fixture_root : str | Path, optional
        Fixture root.
    expected_code_version : str | None, optional
        Expected code version.
    expected_policy_hash : str | None, optional
        Expected policy hash.
    expected_inputs_hash : str | None, optional
        Expected inputs hash.

    Returns
    -------
    dict[str, object]
        Result of the operation.
    """
    audit = Path(audit_path)
    fixture = Path(fixture_root)
    checks: list[dict[str, object]] = []
    mismatches: list[dict[str, object]] = []

    try:
        records = _read_audit_records(audit)
        replayed = _recompute_fixture_capital_run(fixture)
    except Exception as exc:
        return _error_report(audit, fixture, exc)

    _add_check(
        checks,
        mismatches,
        "expected_code_version",
        expected_code_version,
        __version__,
        enabled=expected_code_version is not None,
    )
    _add_check(
        checks,
        mismatches,
        "expected_policy_hash",
        expected_policy_hash,
        replayed["policy_hash"],
        enabled=expected_policy_hash is not None,
    )
    _add_check(
        checks,
        mismatches,
        "expected_inputs_hash",
        expected_inputs_hash,
        replayed["inputs_hash"],
        enabled=expected_inputs_hash is not None,
    )

    for index, record in enumerate(records):
        prefix = f"record[{index}]"
        _compare_record(prefix, record, replayed, checks, mismatches)

    status = "PASSED" if not mismatches else "FAILED"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "audit_path": str(audit),
        "fixture_root": str(fixture),
        "run_id": replayed["run_id"],
        "desk_count": len(records),
        "checks": checks,
        "mismatches": mismatches,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for ``python -m frtb_ima.replay``.
    Parameters
    ----------
    argv : Sequence[str] | None, optional
        Argv.

    Returns
    -------
    int
        Result of the operation.
    """
    parser = argparse.ArgumentParser(
        description="Replay an FRTB-IMA audit NDJSON file against a fixture input bundle.",
    )
    parser.add_argument("--audit", required=True, type=Path, help="Desk audit NDJSON file.")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE_ROOT,
        help="Fixture/input directory to replay.",
    )
    parser.add_argument("--expected-code-version", default=None)
    parser.add_argument("--expected-policy-hash", default=None)
    parser.add_argument("--expected-inputs-hash", default=None)
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Optional path for the replay JSON report.",
    )
    args = parser.parse_args(argv)

    report = replay_audit_file(
        args.audit,
        args.fixture,
        expected_code_version=args.expected_code_version,
        expected_policy_hash=args.expected_policy_hash,
        expected_inputs_hash=args.expected_inputs_hash,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered + "\n", encoding="utf-8")
    sys.stdout.write(rendered + "\n")
    sys.stderr.write(f"Replay {report['status']}: {_mismatch_count(report)} mismatch(es)\n")
    return 0 if report["status"] == "PASSED" else 1


def _compare_record(
    prefix: str,
    record: Mapping[str, object],
    replayed: Mapping[str, object],
    checks: list[dict[str, object]],
    mismatches: list[dict[str, object]],
) -> None:
    expected_outputs = _as_mapping(replayed["expected_outputs"])
    for key in ("run_id", "desk_id", "regime", "as_of_date"):
        _add_check(checks, mismatches, f"{prefix}.{key}", record.get(key), replayed[key])
    _add_check(
        checks,
        mismatches,
        f"{prefix}.code_version",
        record.get("code_version"),
        __version__,
    )
    _add_check(
        checks,
        mismatches,
        f"{prefix}.policy_hash",
        record.get("policy_hash"),
        replayed["policy_hash"],
    )
    _add_check(
        checks,
        mismatches,
        f"{prefix}.inputs_hash",
        record.get("inputs_hash"),
        replayed["inputs_hash"],
    )
    for path in _SECTION_PATHS:
        tolerance = _tolerance_for_path(expected_outputs, path)
        _add_check(
            checks,
            mismatches,
            ".".join((prefix, *path)),
            _get_path(record, path),
            _get_path(replayed, path),
            tolerance=tolerance,
        )


def _recompute_fixture_capital_run(fixture_root: Path) -> dict[str, object]:
    fixture = fixture_module.load_capital_run_fixture(fixture_root)
    policy = fixture_module.policy_from_fixture(fixture)
    as_of_date = fixture_module.as_of_date_from_fixture(fixture)
    run_id = str(fixture.params["run_id"])
    desk_id = str(fixture.params["desk_id"])
    outputs = fixture_module.run_capital_run_fixture_workflow(fixture)
    scalars = _as_mapping(outputs["scalars"])
    pla = _as_mapping(outputs["pla"])
    backtesting = _as_mapping(outputs["backtesting"])
    capital = _as_mapping(outputs["capital"])

    inputs_hash = compute_inputs_hash(
        params=fixture.params,
        risk_factors=fixture.risk_factors,
        rfet_evidence=fixture.rfet_evidence,
        scenario_cube=fixture.scenario_cube,
        stress_histories=fixture.stress_histories,
        nmrf_evidence=fixture.nmrf_evidence,
        nmrf_artifacts=fixture.nmrf_artifacts,
        pla_bt_vectors=fixture.pla_bt_vectors,
    )
    regime = str(fixture.params["regime"])
    return {
        "run_id": run_id,
        "desk_id": desk_id,
        "regime": regime,
        "as_of_date": as_of_date.isoformat(),
        "code_version": __version__,
        "policy_hash": policy.policy_hash,
        "inputs_hash": inputs_hash,
        "expected_outputs": fixture.expected_outputs,
        "imcc": {
            "imcc": scalars["imcc"],
            "unconstrained_lha_es": scalars["unconstrained_lha_es"],
            "constrained_lha_es": scalars["constrained_lha_es"],
        },
        "ses": {"total_ses": scalars["total_ses"]},
        "pla": {
            "zone": pla["zone"],
            "window_size": pla["window_size"],
            "ks_statistic": scalars["pla_ks_statistic"],
        },
        "backtesting": backtesting,
        "capital": {
            "binding_term": capital["binding_term"],
            "models_based_capital": scalars["models_based_capital"],
            "supervisory_multiplier": scalars["supervisory_multiplier"],
        },
        "nmrf_valuation": {
            "classifications": outputs["classifications"],
            "methods": outputs["nmrf_methods"],
            "reconciliation": outputs["reconciliation"],
            "selected_stress_periods": outputs["selected_stress_periods"],
        },
    }


def _read_audit_records(path: Path) -> tuple[dict[str, object], ...]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"audit line {line_number} must contain a JSON object")
        records.append(payload)
    if not records:
        raise ValueError("audit NDJSON contains no records")
    return tuple(records)


def _add_check(
    checks: list[dict[str, object]],
    mismatches: list[dict[str, object]],
    name: str,
    expected: object,
    actual: object,
    *,
    tolerance: float | None = None,
    enabled: bool = True,
) -> None:
    if not enabled:
        return
    passed = _values_match(expected, actual, tolerance)
    check = {
        "name": name,
        "status": "PASSED" if passed else "FAILED",
        "expected": expected,
        "actual": actual,
    }
    if tolerance is not None:
        check["tolerance"] = tolerance
    checks.append(check)
    if not passed:
        mismatches.append(check)


def _values_match(expected: object, actual: object, tolerance: float | None) -> bool:
    if _is_numeric(expected) and _is_numeric(actual):
        expected_float = _float_value(expected)
        actual_float = _float_value(actual)
        if tolerance is None:
            return expected_float == actual_float
        return math.isclose(actual_float, expected_float, rel_tol=0.0, abs_tol=tolerance)
    return expected == actual


def _is_numeric(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _tolerance_for_path(
    expected_outputs: Mapping[str, object],
    path: tuple[str, ...],
) -> float | None:
    scalar_name = _SCALAR_TOLERANCE_BY_PATH.get(path)
    if scalar_name is None:
        return None
    scalars = expected_outputs.get("scalars")
    if not isinstance(scalars, Mapping) or scalar_name not in scalars:
        return None
    spec = scalars[scalar_name]
    if not isinstance(spec, Mapping) or "value" not in spec:
        return None
    expected = abs(_float_value(spec["value"]))
    absolute = _float_setting(spec.get("atol"), 1e-9)
    relative = _float_setting(spec.get("rtol"), 1e-9)
    return absolute + relative * expected


def _get_path(mapping: Mapping[str, object], path: Sequence[str]) -> object:
    value: object = mapping
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            return None
        value = value[key]
    return value


def _as_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"expected mapping, got {type(value).__name__}")
    return value


def _mismatch_count(report: Mapping[str, object]) -> int:
    mismatches = report.get("mismatches", ())
    return len(mismatches) if isinstance(mismatches, Sequence) else 0


def _float_value(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise TypeError(f"expected numeric value, got {type(value).__name__}")
    return float(value)


def _float_setting(value: object, default: float) -> float:
    if value is None:
        return default
    return _float_value(value)


def _error_report(audit_path: Path, fixture_root: Path, exc: Exception) -> dict[str, object]:
    mismatch = {
        "name": "replay_setup",
        "status": "FAILED",
        "error_type": type(exc).__name__,
        "message": str(exc),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "FAILED",
        "audit_path": str(audit_path),
        "fixture_root": str(fixture_root),
        "run_id": None,
        "desk_count": 0,
        "checks": [mismatch],
        "mismatches": [mismatch],
    }


if __name__ == "__main__":
    raise SystemExit(main())
