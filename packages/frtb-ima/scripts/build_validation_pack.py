"""Build a deterministic validation-pack manifest for the capital-run fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "capital_run_v1"
DEFAULT_NOTEBOOK_ROOT = ROOT / "notebooks"
DEFAULT_OUTPUT = ROOT / "build" / "validation" / "capital_run_v1"

NOTEBOOKS = (
    {
        "path": "notebooks/00_validation_map.ipynb",
        "purpose": "Validation-pack index, fixture lineage, assumptions, and gaps.",
        "fixture_inputs": ("manifest.json", "params.json", "expected_outputs.json"),
        "golden_checks": (),
    },
    {
        "path": "notebooks/01_rfet_evidence_classification.ipynb",
        "purpose": "RFET evidence, thresholds, coverage, and classification.",
        "fixture_inputs": (
            "risk_factors.csv",
            "rfet_observations.csv",
            "expected_outputs.json",
        ),
        "golden_checks": ("classifications",),
    },
    {
        "path": "notebooks/02_stress_period_selection.ipynb",
        "purpose": "Risk-class stress-period selection and selected window evidence.",
        "fixture_inputs": (
            "stress_history_metadata.csv",
            "stress_histories.npz",
            "expected_outputs.json",
        ),
        "golden_checks": ("selected_stress_periods",),
    },
    {
        "path": "notebooks/03_lha_es_imcc.ipynb",
        "purpose": "Nested liquidity-horizon ES and IMCC decomposition.",
        "fixture_inputs": (
            "scenario_cube.npz",
            "scenario_metadata.csv",
            "risk_factors.csv",
            "expected_outputs.json",
        ),
        "golden_checks": ("unconstrained_lha_es", "constrained_lha_es", "imcc"),
    },
    {
        "path": "notebooks/04_nmrf_chain.ipynb",
        "purpose": "NMRF method selection, valuation specs, reconciliation, and SES.",
        "fixture_inputs": (
            "nmrf_evidence.json",
            "nmrf_artifacts.npz",
            "stress_histories.npz",
            "expected_outputs.json",
        ),
        "golden_checks": ("nmrf_methods", "reconciliation", "total_ses"),
    },
    {
        "path": "notebooks/05_pla_backtesting.ipynb",
        "purpose": "PLA HPL/RTPL diagnostics and backtesting exception traces.",
        "fixture_inputs": ("pla_bt_vectors.npz", "expected_outputs.json"),
        "golden_checks": ("pla", "backtesting", "pla_ks_statistic"),
    },
    {
        "path": "notebooks/06_capital_assembly.ipynb",
        "purpose": "Models-based capital assembly and binding-term logic.",
        "fixture_inputs": ("scenario_cube.npz", "expected_outputs.json"),
        "golden_checks": ("models_based_capital", "capital.binding_term"),
    },
)

OPEN_GAPS = (
    "SBM/DRC/RRAO fallback stack, CVA, and firm/legal-entity consolidation.",
    "Trading-desk approval lifecycle and supervisory workflow evidence.",
    "Real market-data sourcing, vendor adapters, and proprietary instrument classification.",
    "Production direct, stepwise, and full-revaluation NMRF pricing engines.",
    "Full business-calendar governance beyond fixture dates and optional holiday masks.",
    "Regulatory disclosure templates and large-run storage or telemetry integrations.",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a deterministic validation-pack manifest.",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE_ROOT,
        help="Fixture directory containing manifest.json, params.json, and expected_outputs.json.",
    )
    parser.add_argument(
        "--notebook-root",
        type=Path,
        default=DEFAULT_NOTEBOOK_ROOT,
        help="Notebook directory to hash for the validation pack.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Validation pack output directory.",
    )
    args = parser.parse_args()

    fixture_root = _rooted(args.fixture)
    notebook_root = _rooted(args.notebook_root)
    output = _rooted(args.output)
    manifest = _read_json(fixture_root / "manifest.json")
    params = _read_json(fixture_root / "params.json")
    expected = _read_json(fixture_root / "expected_outputs.json")
    output.mkdir(parents=True, exist_ok=True)
    readme_path = output / "README.md"
    audit_artifacts = (
        output / "audit" / "capital_run_v1_audit_report.md",
        output / "audit" / "capital_run_v1_desk_records.ndjson",
    )
    _ensure_required_artifacts(audit_artifacts)

    pack = _pack_manifest(
        fixture_root=fixture_root,
        notebook_root=notebook_root,
        fixture_manifest=manifest,
        params=params,
        expected=expected,
        generated_artifacts=(),
    )
    _write_readme(readme_path, pack)
    pack["generated_artifacts"] = _artifact_entries((readme_path, *audit_artifacts))
    _write_json(output / "validation_pack_manifest.json", pack)


def _pack_manifest(
    *,
    fixture_root: Path,
    notebook_root: Path,
    fixture_manifest: dict[str, Any],
    params: dict[str, Any],
    expected: dict[str, Any],
    generated_artifacts: tuple[dict[str, str], ...],
) -> dict[str, Any]:
    notebook_entries = []
    for entry in NOTEBOOKS:
        path = notebook_root / Path(str(entry["path"])).name
        notebook_entries.append(
            {
                **entry,
                "sha256": _sha256(path),
            }
        )

    return {
        "schema_version": "validation_pack_v1",
        "source_fixture": _display_path(fixture_root),
        "run": {
            "run_id": str(params["run_id"]),
            "desk_id": str(params["desk_id"]),
            "regime": str(params["regime"]),
            "as_of_date": str(params["as_of_date"]),
            "fixture_schema_version": str(params["schema_version"]),
            "generator_version": str(params["generator_version"]),
            "seed": int(params["seed"]),
        },
        "notebooks": notebook_entries,
        "fixture_files": fixture_manifest["files"],
        "sign_conventions": fixture_manifest["sign_conventions"],
        "expected_outputs": _expected_summary(expected),
        "generated_artifacts": generated_artifacts,
        "open_gaps": OPEN_GAPS,
        "caution": (
            "Synthetic prototype evidence only. This pack does not present final "
            "regulatory capital or a supervisory submission."
        ),
    }


def _expected_summary(expected: dict[str, Any]) -> dict[str, Any]:
    classifications = expected["classifications"]
    class_counts: dict[str, int] = {}
    for status in classifications.values():
        key = str(status)
        class_counts[key] = class_counts.get(key, 0) + 1

    scalars = expected["scalars"]
    return {
        "scalar_values": {
            name: float(spec["value"])
            for name, spec in sorted(scalars.items())
            if isinstance(spec, dict) and "value" in spec
        },
        "classification_counts": class_counts,
        "nmrf_methods": expected["nmrf_methods"],
        "selected_stress_period_count": len(expected["selected_stress_periods"]),
        "pla": expected["pla"],
        "backtesting": expected["backtesting"],
        "capital": expected["capital"],
        "reconciliation": expected["reconciliation"],
    }


def _write_readme(path: Path, pack: dict[str, Any]) -> None:
    run = pack["run"]
    lines = [
        "# Capital Run v1 Validation Pack",
        "",
        "This generated pack is deterministic prototype evidence for the committed",
        "`capital_run_v1` synthetic fixture. It is not a regulatory report and does",
        "not present final regulatory capital.",
        "",
        "## Run",
        "",
        f"- Run ID: `{run['run_id']}`",
        f"- Desk ID: `{run['desk_id']}`",
        f"- Regime: `{run['regime']}`",
        f"- As-of date: `{run['as_of_date']}`",
        f"- Fixture schema: `{run['fixture_schema_version']}`",
        f"- Generator version: `{run['generator_version']}`",
        f"- Seed: `{run['seed']}`",
        "",
        "## Contents",
        "",
        "- `validation_pack_manifest.json`: machine-readable pack manifest.",
        "- `audit/capital_run_v1_audit_report.md`: rendered fixture audit report.",
        "- `audit/capital_run_v1_desk_records.ndjson`: serialised desk audit record.",
        "",
        "## Replay",
        "",
        "Run the replay CLI from the package root after building this pack:",
        "",
        "```bash",
        "python -m frtb_ima.replay \\",
        "  --audit build/validation/capital_run_v1/audit/capital_run_v1_desk_records.ndjson \\",
        "  --fixture tests/fixtures/capital_run_v1 \\",
        "  --json-output build/validation/capital_run_v1/audit/capital_run_v1_replay_report.json",
        "```",
        "",
        "The command emits a JSON report and exits non-zero on identity, hash,",
        "numeric, or categorical replay mismatches.",
        "",
        "## Notebook Map",
        "",
        "| Notebook | Purpose |",
        "| --- | --- |",
    ]
    for notebook in pack["notebooks"]:
        lines.append(f"| `{notebook['path']}` | {notebook['purpose']} |")

    lines.extend(
        [
            "",
            "## Open Prototype Gaps",
            "",
            *[f"- {gap}" for gap in pack["open_gaps"]],
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _ensure_required_artifacts(paths: tuple[Path, ...]) -> None:
    missing = [path for path in paths if not path.is_file()]
    if missing:
        formatted = ", ".join(_display_path(path) for path in missing)
        raise FileNotFoundError("validation pack requires audit artifacts first: " + formatted)


def _artifact_entries(paths: tuple[Path, ...]) -> tuple[dict[str, str], ...]:
    _ensure_required_artifacts(paths)
    return tuple(
        {
            "path": _display_path(path),
            "sha256": _sha256(path),
        }
        for path in sorted(paths, key=_display_path)
    )


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _rooted(path: Path) -> Path:
    return path.resolve()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    main()
