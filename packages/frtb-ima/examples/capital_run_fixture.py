"""Reusable loader for the committed capital-run fixture.

The fixture is synthetic development data. This module lives under ``examples``
so notebooks, examples, and integration tests can share the same manifest
checksum validation without adding fixture-loading APIs to the runtime package.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Mapping, Sequence
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
from frtb_ima.data_models import (
    LiquidityHorizon,
    ModellabilityStatus,
    RealPriceObservation,
    RiskClass,
)
from frtb_ima.nmrf import NMRFStressArtifact
from frtb_ima.nmrf_method_selection import (
    NMRFMethodEvidence,
    assess_direct_loss_robustness,
)
from frtb_ima.nmrf_stress_spec import (
    NMRFDirectShockSpec,
    NMRFFullRevaluationSpec,
    NMRFShockDirection,
    NMRFValuationSpec,
)
from frtb_ima.regimes import RegulatoryPolicy, RegulatoryRegime, get_policy
from frtb_ima.rfet_evidence import RFETEvidenceAssessment, assess_rfet_evidence
from frtb_ima.scenario import ScenarioMetadata, ScenarioSetType
from frtb_ima.stress_periods import HistoricalStressSeries

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAPITAL_RUN_V1_ROOT = ROOT / "tests" / "fixtures" / "capital_run_v1"
NMRF_ARTIFACT_SOURCE = "fixture upstream valuation artifact"


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


def load_capital_run_v1_fixture() -> CapitalRunFixture:
    """Load the repository's canonical capital-run v1 fixture."""
    return load_capital_run_fixture(DEFAULT_CAPITAL_RUN_V1_ROOT)


def load_capital_run_fixture(root: Path) -> CapitalRunFixture:
    """Load and validate a committed capital-run fixture."""
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
        position_ids=tuple(_to_str(item) for item in scenario_cube_arrays["position_ids"].tolist()),
        risk_factor_names=tuple(
            _to_str(item) for item in scenario_cube_arrays["risk_factor_names"].tolist()
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


def policy_from_fixture(fixture: CapitalRunFixture) -> RegulatoryPolicy:
    """Return the regulatory policy declared by a fixture's run parameters."""
    policy = get_policy(RegulatoryRegime(str(fixture.params["regime"])))
    fixture_estimator = fixture.params.get("es_estimator")
    if fixture_estimator is not None and fixture_estimator != policy.es_estimator.value:
        raise ValueError(
            "fixture es_estimator does not match the active regulatory policy "
            f"({fixture_estimator!r} != {policy.es_estimator.value!r})"
        )
    return policy


def as_of_date_from_fixture(fixture: CapitalRunFixture) -> date:
    """Return the fixture as-of date."""
    return date.fromisoformat(str(fixture.params["as_of_date"]))


def rfet_assessments_from_fixture(
    fixture: CapitalRunFixture,
    policy: RegulatoryPolicy | None = None,
) -> dict[str, RFETEvidenceAssessment]:
    """Assess all RFET evidence packages in fixture order."""
    active_policy = policy if policy is not None else policy_from_fixture(fixture)
    return {
        risk_factor.name: assess_rfet_evidence(
            risk_factor,
            fixture.rfet_evidence[risk_factor.name],
            active_policy,
        )
        for risk_factor in fixture.risk_factors
    }


def classifications_from_fixture(
    fixture: CapitalRunFixture,
    policy: RegulatoryPolicy | None = None,
) -> dict[str, ModellabilityStatus]:
    """Return RFET classifications derived from the fixture evidence."""
    assessments = rfet_assessments_from_fixture(fixture, policy)
    return {
        risk_factor_name: assessments[risk_factor_name].modellability_status
        for risk_factor_name in sorted(assessments)
    }


def nmrf_method_evidence_from_fixture(
    fixture: CapitalRunFixture,
) -> dict[str, NMRFMethodEvidence]:
    """Return auditable NMRF method evidence from the fixture JSON payload."""
    evidence_by_name: dict[str, NMRFMethodEvidence] = {}
    for risk_factor_name, raw in fixture.nmrf_evidence.items():
        if not isinstance(raw, Mapping):
            raise TypeError(f"NMRF evidence for {risk_factor_name} must be a mapping")
        robustness = None
        check = raw.get("direct_robustness_check")
        if isinstance(check, Mapping):
            robustness = assess_direct_loss_robustness(
                check["direct_losses"],
                check["benchmark_losses"],
                max_relative_error_threshold=float(check["max_relative_error_threshold"]),
                source=str(check["source"]),
            )
        evidence_by_name[risk_factor_name] = NMRFMethodEvidence(
            risk_factor_name=risk_factor_name,
            nonlinear=bool(raw.get("nonlinear", False)),
            full_revaluation_available=bool(raw.get("full_revaluation_available", False)),
            direct_method_available=bool(raw.get("direct_method_available", False)),
            direct_shock_well_defined=bool(raw.get("direct_shock_well_defined", False)),
            direct_robustness=robustness,
            stepwise_available=bool(raw.get("stepwise_available", False)),
            stepwise_required=bool(raw.get("stepwise_required", False)),
            max_loss_fallback_allowed=bool(raw.get("max_loss_fallback_allowed", False)),
            pricing_attempt_count=int(raw.get("pricing_attempt_count", 0)),
            pricing_failure_count=int(raw.get("pricing_failure_count", 0)),
            proxy_or_basis_risk=bool(raw.get("proxy_or_basis_risk", False)),
            source=str(raw.get("source", "")),
        )
    return evidence_by_name


def nmrf_direct_shocks_from_fixture(
    fixture: CapitalRunFixture,
) -> dict[str, NMRFDirectShockSpec]:
    """Return direct shock specs declared by the fixture NMRF evidence."""
    result: dict[str, NMRFDirectShockSpec] = {}
    for risk_factor_name, raw in fixture.nmrf_evidence.items():
        if not isinstance(raw, Mapping):
            raise TypeError(f"NMRF evidence for {risk_factor_name} must be a mapping")
        shock = raw.get("direct_shock")
        if not isinstance(shock, Mapping):
            continue
        result[risk_factor_name] = NMRFDirectShockSpec(
            shock_size=float(shock["shock_size"]),
            shock_unit=str(shock["shock_unit"]),
            direction=NMRFShockDirection(str(shock["direction"])),
            calibration_source=str(shock["calibration_source"]),
            confidence_level=float(shock["confidence_level"]),
            notes=str(shock.get("notes", "")),
        )
    return result


def nmrf_full_revaluations_from_fixture(
    fixture: CapitalRunFixture,
) -> dict[str, NMRFFullRevaluationSpec]:
    """Return full-revaluation specs declared by the fixture NMRF evidence."""
    result: dict[str, NMRFFullRevaluationSpec] = {}
    for risk_factor_name, raw in fixture.nmrf_evidence.items():
        if not isinstance(raw, Mapping):
            raise TypeError(f"NMRF evidence for {risk_factor_name} must be a mapping")
        revaluation = raw.get("full_revaluation")
        if not isinstance(revaluation, Mapping):
            continue
        result[risk_factor_name] = NMRFFullRevaluationSpec(
            scenario_set_id=str(revaluation["scenario_set_id"]),
            market_state_ids=tuple(str(item) for item in revaluation["market_state_ids"]),
            calibration_source=str(revaluation["calibration_source"]),
            require_full_trade_repricing=bool(
                revaluation.get("require_full_trade_repricing", True)
            ),
            notes=str(revaluation.get("notes", "")),
        )
    return result


def nmrf_artifacts_from_fixture(
    fixture: CapitalRunFixture,
    specs: Sequence[NMRFValuationSpec],
) -> tuple[NMRFStressArtifact, ...]:
    """Return committed upstream NMRF artifacts matched to valuation specs."""
    artifacts: list[NMRFStressArtifact] = []
    for spec in specs:
        risk_factor_name = spec.risk_factor_name
        artifacts.append(
            NMRFStressArtifact(
                risk_factor_name=risk_factor_name,
                method=spec.method,
                losses=fixture.nmrf_artifacts[f"{risk_factor_name}_losses"],
                liquidity_horizon=spec.required_liquidity_horizon,
                stress_period=spec.stress_period.stress_period_id,
                source=NMRF_ARTIFACT_SOURCE,
                scenario_ids=tuple(
                    _to_str(item)
                    for item in fixture.nmrf_artifacts[f"{risk_factor_name}_scenario_ids"].tolist()
                ),
                generated_by_prototype=False,
            )
        )
    return tuple(artifacts)


def observation_dates_from_fixture(fixture: CapitalRunFixture) -> tuple[date, ...]:
    """Return aligned PLA/backtesting observation dates from the fixture."""
    return tuple(
        date.fromisoformat(_to_str(value))
        for value in fixture.pla_bt_vectors["observation_dates"].tolist()
    )


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
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
    resolved_root = root.resolve()
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise AssertionError("manifest must contain file checksums")
    for filename, metadata in files.items():
        if not isinstance(filename, str) or not isinstance(metadata, dict):
            raise AssertionError("manifest files must map file names to metadata")
        expected = metadata.get("sha256")
        if not isinstance(expected, str):
            raise AssertionError(f"manifest checksum missing for {filename}")
        target_path = (resolved_root / filename).resolve()
        if not target_path.is_relative_to(resolved_root):
            raise AssertionError(f"manifest file path escapes fixture root: {filename}")
        actual = _sha256(target_path)
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
                    date.fromisoformat(_to_str(value))
                    for value in arrays[f"{prefix}_dates"].tolist()
                ),
                source=row["source"],
                scenario_ids=tuple(
                    _to_str(value) for value in arrays[f"{prefix}_scenario_ids"].tolist()
                ),
                name=f"{prefix} fixture stress history",
            )
        )
    return tuple(histories)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _parse_bool(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise AssertionError(f"invalid boolean value: {value}")


def _to_str(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
