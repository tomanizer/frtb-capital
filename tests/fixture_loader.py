"""Test-only loader for committed capital-run fixtures."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from frtb_ima.data_contracts import (
    RFETEvidence,
    RiskFactorBucket,
    RiskFactorDefinition,
    ScenarioCube,
)
from frtb_ima.data_models import LiquidityHorizon, RealPriceObservation, RiskClass
from frtb_ima.scenario import ScenarioMetadata, ScenarioSetType
from frtb_ima.stress_periods import HistoricalStressSeries


@dataclass(frozen=True)
class CapitalRunFixture:
    """Loaded capital-run fixture inputs and golden outputs."""

    root: Path
    manifest: dict[str, Any]
    params: dict[str, Any]
    expected_outputs: dict[str, Any]
    risk_factors: tuple[RiskFactorDefinition, ...]
    rfet_evidence: dict[str, RFETEvidence]
    scenario_cube: ScenarioCube
    stress_histories: tuple[HistoricalStressSeries, ...]
    nmrf_evidence: dict[str, Any]
    nmrf_artifacts: dict[str, npt.NDArray[Any]]
    pla_bt_vectors: dict[str, npt.NDArray[Any]]


def load_capital_run_fixture(root: Path) -> CapitalRunFixture:
    """Load and validate the committed capital-run fixture."""
    manifest = _read_json(root / "manifest.json")
    _verify_manifest_checksums(root, manifest)
    params = _read_json(root / "params.json")
    risk_factors = _load_risk_factors(root / "risk_factors.csv")
    rfet_evidence = _load_rfet_evidence(
        root / "rfet_observations.csv",
        risk_factors,
        as_of_date=date.fromisoformat(str(params["as_of_date"])),
    )
    scenario_metadata = _load_scenario_metadata(root / "scenario_metadata.csv")
    scenario_cube_arrays = _load_npz(root / "scenario_cube.npz")
    scenario_cube = ScenarioCube(
        values=scenario_cube_arrays["cube"],
        scenario_metadata=scenario_metadata,
        position_ids=tuple(str(item) for item in scenario_cube_arrays["position_ids"].tolist()),
        risk_factor_names=tuple(
            str(item) for item in scenario_cube_arrays["risk_factor_names"].tolist()
        ),
        name="capital_run_v1_current",
    )
    stress_histories = _load_stress_histories(
        root / "stress_history_metadata.csv",
        _load_npz(root / "stress_histories.npz"),
    )
    return CapitalRunFixture(
        root=root,
        manifest=manifest,
        params=params,
        expected_outputs=_read_json(root / "expected_outputs.json"),
        risk_factors=risk_factors,
        rfet_evidence=rfet_evidence,
        scenario_cube=scenario_cube,
        stress_histories=stress_histories,
        nmrf_evidence=_read_json(root / "nmrf_evidence.json"),
        nmrf_artifacts=_load_npz(root / "nmrf_artifacts.npz"),
        pla_bt_vectors=_load_npz(root / "pla_bt_vectors.npz"),
    )


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return data


def _load_npz(path: Path) -> dict[str, npt.NDArray[Any]]:
    with np.load(path, allow_pickle=False) as data:
        result: dict[str, npt.NDArray[Any]] = {}
        for name in data.files:
            arr = data[name].copy()
            arr.flags.writeable = False
            result[name] = arr
        return result


def _verify_manifest_checksums(root: Path, manifest: dict[str, Any]) -> None:
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise AssertionError("manifest must contain file checksums")
    for filename, metadata in files.items():
        if not isinstance(filename, str) or not isinstance(metadata, dict):
            raise AssertionError("manifest files must map file names to metadata")
        expected = metadata.get("sha256")
        if not isinstance(expected, str):
            raise AssertionError(f"manifest checksum missing for {filename}")
        actual = _sha256(root / filename)
        if actual != expected:
            raise AssertionError(
                f"manifest checksum mismatch for {filename}: expected {expected}, actual {actual}"
            )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_risk_factors(path: Path) -> tuple[RiskFactorDefinition, ...]:
    rows = _read_csv(path)
    result: list[RiskFactorDefinition] = []
    for row in rows:
        risk_class = RiskClass(row["risk_class"])
        liquidity_horizon = LiquidityHorizon(int(row["liquidity_horizon"]))
        bucket = RiskFactorBucket(
            bucket_id=row["bucket_id"],
            risk_class=risk_class,
            liquidity_horizon=liquidity_horizon,
        )
        result.append(
            RiskFactorDefinition(
                name=row["name"],
                risk_class=risk_class,
                liquidity_horizon=liquidity_horizon,
                bucket=bucket,
                currency=row["currency"],
            )
        )
    return tuple(result)


def _load_rfet_evidence(
    path: Path,
    risk_factors: tuple[RiskFactorDefinition, ...],
    *,
    as_of_date: date,
) -> dict[str, RFETEvidence]:
    rows_by_name: dict[str, list[dict[str, str]]] = {}
    for row in _read_csv(path):
        rows_by_name.setdefault(row["risk_factor_name"], []).append(row)

    evidence: dict[str, RFETEvidence] = {}
    for risk_factor in risk_factors:
        rows = rows_by_name.get(risk_factor.name)
        if not rows:
            raise AssertionError(f"missing RFET observations for {risk_factor.name}")
        qualitative_values = {_parse_bool(row["qualitative_pass"]) for row in rows}
        bucket_ids = {row["bucket_id"] for row in rows}
        if len(qualitative_values) != 1:
            raise AssertionError(f"inconsistent qualitative pass for {risk_factor.name}")
        if len(bucket_ids) != 1:
            raise AssertionError(f"inconsistent bucket ID for {risk_factor.name}")
        observations = tuple(
            RealPriceObservation(
                risk_factor_name=risk_factor.name,
                observation_date=date.fromisoformat(row["observation_date"]),
                source=row["source"],
            )
            for row in rows
        )
        evidence[risk_factor.name] = RFETEvidence(
            risk_factor_name=risk_factor.name,
            as_of_date=as_of_date,
            observations=observations,
            qualitative_pass=qualitative_values.pop(),
            bucket_id=bucket_ids.pop(),
        )
    return evidence


def _load_scenario_metadata(path: Path) -> tuple[ScenarioMetadata, ...]:
    return tuple(
        ScenarioMetadata(
            scenario_id=row["scenario_id"],
            scenario_date=date.fromisoformat(row["scenario_date"]),
            scenario_set=ScenarioSetType(row["set_type"]),
        )
        for row in _read_csv(path)
    )


def _load_stress_histories(
    metadata_path: Path,
    arrays: dict[str, npt.NDArray[Any]],
) -> tuple[HistoricalStressSeries, ...]:
    histories: list[HistoricalStressSeries] = []
    for row in _read_csv(metadata_path):
        risk_class = RiskClass(row["risk_class"])
        prefix = risk_class.value
        histories.append(
            HistoricalStressSeries(
                risk_class=risk_class,
                losses=arrays[f"{prefix}_losses"],
                dates=tuple(
                    date.fromisoformat(str(value)) for value in arrays[f"{prefix}_dates"].tolist()
                ),
                source=row["source"],
                scenario_ids=tuple(
                    str(value) for value in arrays[f"{prefix}_scenario_ids"].tolist()
                ),
                name=f"{prefix} fixture stress history",
            )
        )
    return tuple(histories)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _parse_bool(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise AssertionError(f"invalid boolean value: {value}")
