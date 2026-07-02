"""Reusable loader for the committed synthetic capital-run fixture."""

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

from frtb_ima.audit_inputs import compute_inputs_hash
from frtb_ima.backtesting import trading_desk_backtest_trace_for_policy
from frtb_ima.capital import models_based_capital, supervisory_multiplier_for_policy
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
from frtb_ima.imcc import imcc_breakdown_for_policy
from frtb_ima.lha_builder import imcc_nested_lh_vectors_from_cube
from frtb_ima.nmrf import (
    NMRFStressArtifact,
    route_nmrf_classifications_for_capital,
)
from frtb_ima.nmrf_method_selection import (
    NMRFMethodEvidence,
    assess_direct_loss_robustness,
    select_nmrf_methods,
    selection_input_from_method_evidence,
)
from frtb_ima.nmrf_stress_spec import (
    NMRFDirectShockSpec,
    NMRFFullRevaluationSpec,
    NMRFShockDirection,
    NMRFValuationSpec,
    build_nmrf_valuation_specs,
)
from frtb_ima.nmrf_valuation_run import (
    build_nmrf_valuation_run_request,
    calculate_nmrf_capital_from_valuation_run,
    complete_nmrf_valuation_run,
)
from frtb_ima.pla import pla_assessment_for_policy_with_diagnostics
from frtb_ima.regimes import RegulatoryPolicy, RegulatoryRegime, get_policy
from frtb_ima.rfet_evidence import RFETEvidenceAssessment, assess_rfet_evidence
from frtb_ima.scenario import ScenarioMetadata, ScenarioSetType
from frtb_ima.stress_periods import (
    HistoricalStressSeries,
    select_stress_periods_for_policy,
    stress_period_specs_for_nmrf,
    validate_selected_stress_periods,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAPITAL_RUN_V1_ROOT = ROOT / "tests" / "fixtures" / "capital_run_v1"
DEFAULT_IMA_PRA_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "ima_pra"
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


def input_hash_for_capital_run_fixture(fixture: CapitalRunFixture) -> str:
    """Compute the canonical input hash for a loaded capital-run fixture.

    Parameters
    ----------
    fixture : CapitalRunFixture
        Loaded capital-run fixture inputs.

    Returns
    -------
    str
        SHA-256 digest over the fixture's input payloads.
    """
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


def load_capital_run_v1_fixture() -> CapitalRunFixture:
    """Load the repository's canonical capital-run v1 fixture.
    Returns
    -------
    CapitalRunFixture
        Result of the operation.
    """
    return load_capital_run_fixture(DEFAULT_CAPITAL_RUN_V1_ROOT)


def load_capital_run_pra_fixture() -> CapitalRunFixture:
    """Load the PRA UK CRR replay fixture (shared inputs, PRA policy outputs).
    Returns
    -------
    CapitalRunFixture
        Result of the operation.
    """
    return load_capital_run_fixture(DEFAULT_IMA_PRA_FIXTURE_ROOT)


def load_capital_run_fixture(root: Path) -> CapitalRunFixture:
    """Load and validate a committed capital-run fixture.
    Parameters
    ----------
    root : Path
        Root.

    Returns
    -------
    CapitalRunFixture
        Result of the operation.
    """
    manifest = _read_json(root / "manifest.json")
    _verify_manifest_checksums(root, manifest)
    params = _read_json(root / "params.json")
    risk_factors = _load_risk_factors(root / "risk_factors.csv")
    rfet_evidence = _load_rfet_evidence(
        root / "rfet_observations.csv",
        risk_factors,
        as_of_date=date.fromisoformat(str(params["as_of_date"])),
        artifact_metadata=_manifest_file_metadata(manifest, "rfet_observations.csv"),
    )
    scenario_metadata = _load_scenario_metadata(root / "scenario_metadata.csv")
    scenario_cube_arrays = _load_npz(root / "scenario_cube.npz")
    scenario_cube_metadata = _manifest_file_metadata(manifest, "scenario_cube.npz")
    scenario_cube = ScenarioCube(
        values=scenario_cube_arrays["cube"],
        scenario_metadata=scenario_metadata,
        position_ids=tuple(_to_str(item) for item in scenario_cube_arrays["position_ids"].tolist()),
        risk_factor_names=tuple(
            _to_str(item) for item in scenario_cube_arrays["risk_factor_names"].tolist()
        ),
        name="capital_run_v1_current",
        artifact_id=str(scenario_cube_metadata.get("artifact_id", "")),
        scenario_set_id=str(scenario_cube_metadata.get("scenario_set_id", "")),
        scenario_vector_ids=_scenario_vector_ids_from_metadata(
            scenario_cube_metadata,
            scenario_metadata,
        ),
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
    """Return the regulatory policy declared by a fixture's run parameters.
    Parameters
    ----------
    fixture : CapitalRunFixture
        Fixture.

    Returns
    -------
    RegulatoryPolicy
        Result of the operation.
    """
    policy = get_policy(RegulatoryRegime(str(fixture.params["regime"])))
    fixture_estimator = fixture.params.get("es_estimator")
    if fixture_estimator is not None and fixture_estimator != policy.es_estimator.value:
        raise ValueError(
            "fixture es_estimator does not match the active regulatory policy "
            f"({fixture_estimator!r} != {policy.es_estimator.value!r})"
        )
    return policy


def as_of_date_from_fixture(fixture: CapitalRunFixture) -> date:
    """Return the fixture as-of date.
    Parameters
    ----------
    fixture : CapitalRunFixture
        Fixture.

    Returns
    -------
    date
        Result of the operation.
    """
    return date.fromisoformat(str(fixture.params["as_of_date"]))


def rfet_assessments_from_fixture(
    fixture: CapitalRunFixture,
    policy: RegulatoryPolicy | None = None,
) -> dict[str, RFETEvidenceAssessment]:
    """Assess all RFET evidence packages in fixture order.
    Parameters
    ----------
    fixture : CapitalRunFixture
        Fixture.
    policy : RegulatoryPolicy | None, optional
        Policy.

    Returns
    -------
    dict[str, RFETEvidenceAssessment]
        Result of the operation.
    """
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
    """Return RFET classifications derived from the fixture evidence.
    Parameters
    ----------
    fixture : CapitalRunFixture
        Fixture.
    policy : RegulatoryPolicy | None, optional
        Policy.

    Returns
    -------
    dict[str, ModellabilityStatus]
        Result of the operation.
    """
    assessments = rfet_assessments_from_fixture(fixture, policy)
    return {
        risk_factor_name: assessments[risk_factor_name].modellability_status
        for risk_factor_name in sorted(assessments)
    }


def nmrf_method_evidence_from_fixture(
    fixture: CapitalRunFixture,
) -> dict[str, NMRFMethodEvidence]:
    """Return auditable NMRF method evidence from the fixture JSON payload.
    Parameters
    ----------
    fixture : CapitalRunFixture
        Fixture.

    Returns
    -------
    dict[str, NMRFMethodEvidence]
        Result of the operation.
    """
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
    """Return direct shock specs declared by the fixture NMRF evidence.
    Parameters
    ----------
    fixture : CapitalRunFixture
        Fixture.

    Returns
    -------
    dict[str, NMRFDirectShockSpec]
        Result of the operation.
    """
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
    """Return full-revaluation specs declared by the fixture NMRF evidence.
    Parameters
    ----------
    fixture : CapitalRunFixture
        Fixture.

    Returns
    -------
    dict[str, NMRFFullRevaluationSpec]
        Result of the operation.
    """
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
    """Return committed upstream NMRF artifacts matched to valuation specs.
    Parameters
    ----------
    fixture : CapitalRunFixture
        Fixture.
    specs : Sequence[NMRFValuationSpec]
        Specs.

    Returns
    -------
    tuple[NMRFStressArtifact, ...]
        Result of the operation.
    """
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
    """Return aligned PLA/backtesting observation dates from the fixture.
    Parameters
    ----------
    fixture : CapitalRunFixture
        Fixture.

    Returns
    -------
    tuple[date, ...]
        Result of the operation.
    """
    return tuple(
        date.fromisoformat(_to_str(value))
        for value in fixture.pla_bt_vectors["observation_dates"].tolist()
    )


def run_capital_run_fixture_workflow(fixture: CapitalRunFixture) -> dict[str, object]:
    """Run the committed fixture through the calculation workflow used by replay.
    Parameters
    ----------
    fixture : CapitalRunFixture
        Fixture.

    Returns
    -------
    dict[str, object]
        Result of the operation.
    """
    policy = policy_from_fixture(fixture)
    as_of_date = as_of_date_from_fixture(fixture)
    run_id = str(fixture.params["run_id"])
    desk_id = str(fixture.params["desk_id"])

    risk_factors_by_name = {risk_factor.name: risk_factor for risk_factor in fixture.risk_factors}
    classifications = classifications_from_fixture(fixture, policy)
    routing = route_nmrf_classifications_for_capital(classifications, policy)

    imcc_cube = _filtered_cube(fixture.scenario_cube, routing.imcc_risk_factors)
    imcc_risk_factors = tuple(risk_factors_by_name[name] for name in imcc_cube.risk_factor_names)
    nested_vectors = imcc_nested_lh_vectors_from_cube(imcc_cube, imcc_risk_factors)
    imcc_result = imcc_breakdown_for_policy(
        nested_vectors.all_risk_class_vectors,
        nested_vectors.per_risk_class_vectors,
        policy,
        run_id=run_id,
        desk_id=desk_id,
    )

    stress_selection = select_stress_periods_for_policy(
        fixture.stress_histories,
        policy,
        as_of_date=as_of_date,
        run_id=run_id,
        desk_id=desk_id,
    )
    validate_selected_stress_periods(
        stress_selection,
        tuple(risk_factors_by_name[name].risk_class for name in routing.ses_risk_factors),
    )

    method_evidence = nmrf_method_evidence_from_fixture(fixture)
    selection_inputs = tuple(
        selection_input_from_method_evidence(
            method_evidence[name],
            classifications[name],
            risk_factors_by_name[name].liquidity_horizon,
        )
        for name in routing.ses_risk_factors
    )
    decisions = select_nmrf_methods(selection_inputs, policy)
    specs = build_nmrf_valuation_specs(
        tuple(decision.to_valuation_instruction() for decision in decisions),
        {risk_factor.name: risk_factor.risk_class for risk_factor in fixture.risk_factors},
        stress_period_specs_for_nmrf(stress_selection),
        policy,
        direct_shocks=nmrf_direct_shocks_from_fixture(fixture),
        full_revaluations=nmrf_full_revaluations_from_fixture(fixture),
        source="fixture NMRF valuation spec builder",
    )
    artifacts = nmrf_artifacts_from_fixture(fixture, specs)
    valuation_request = build_nmrf_valuation_run_request(
        specs,
        policy,
        run_id=run_id,
        desk_id=desk_id,
        as_of_date=as_of_date,
    )
    valuation_run = complete_nmrf_valuation_run(valuation_request, artifacts)
    nmrf_capital = calculate_nmrf_capital_from_valuation_run(
        classifications,
        valuation_run,
        policy,
    )

    observation_dates = observation_dates_from_fixture(fixture)
    pla_result = pla_assessment_for_policy_with_diagnostics(
        fixture.pla_bt_vectors["hpl"],
        fixture.pla_bt_vectors["rtpl"],
        policy,
        observation_dates=observation_dates,
        run_id=run_id,
        desk_id=desk_id,
    )
    backtest_result = trading_desk_backtest_trace_for_policy(
        fixture.pla_bt_vectors["apl"],
        fixture.pla_bt_vectors["hpl"],
        {
            0.975: fixture.pla_bt_vectors["var_975"],
            0.99: fixture.pla_bt_vectors["var_99"],
        },
        policy,
        observation_dates=observation_dates,
        run_id=run_id,
        desk_id=desk_id,
    )
    level_99 = backtest_result.result.level(0.99)
    multiplier = supervisory_multiplier_for_policy(level_99.apl_exceptions, policy)
    capital = models_based_capital(
        imcc_t_minus_1=imcc_result.imcc,
        ses_t_minus_1=nmrf_capital.total_ses,
        imcc_60d_avg=imcc_result.imcc * 1.03,
        ses_60d_avg=nmrf_capital.total_ses * 1.02,
        multiplier=multiplier,
        pla_addon=0.0,
    )

    return {
        "scalars": {
            "imcc": imcc_result.imcc,
            "unconstrained_lha_es": imcc_result.unconstrained_lha_es,
            "constrained_lha_es": imcc_result.constrained_lha_es,
            "total_ses": nmrf_capital.total_ses,
            "pla_ks_statistic": pla_result.ks_statistic,
            "models_based_capital": capital.models_based_capital,
            "supervisory_multiplier": multiplier,
        },
        "classifications": {name: classifications[name].value for name in sorted(classifications)},
        "nmrf_methods": {
            decision.risk_factor_name: decision.method.value for decision in decisions
        },
        "selected_stress_periods": {
            risk_class.value: stress_selection.selected_by_risk_class[risk_class].period_id
            for risk_class in sorted(
                stress_selection.selected_by_risk_class,
                key=lambda item: item.value,
            )
        },
        "reconciliation": {
            "passed": valuation_run.passed,
            "failed_item_count": valuation_run.reconciliation.failed_item_count,
            "artifact_count": valuation_run.reconciliation.artifact_count,
        },
        "pla": {
            "zone": pla_result.zone,
            "window_size": pla_result.diagnostics.window_size,
        },
        "backtesting": {
            "model_eligible": backtest_result.model_eligible,
            "window_size": backtest_result.window_size,
            "levels": {
                str(level.confidence_level): {
                    "apl_exceptions": level.apl_exceptions,
                    "hpl_exceptions": level.hpl_exceptions,
                    "level_passed": level.level_passed,
                }
                for level in backtest_result.result.levels
            },
        },
        "capital": {"binding_term": capital.binding_term},
    }


def _filtered_cube(cube: ScenarioCube, risk_factor_names: Sequence[str]) -> ScenarioCube:
    allowed = set(risk_factor_names)
    selected = tuple(name for name in cube.risk_factor_names if name in allowed)
    indices = [cube.risk_factor_index[name] for name in selected]
    values = cube.values[:, :, indices].copy()
    values.flags.writeable = False
    return ScenarioCube(
        values=values,
        scenario_metadata=cube.scenario_metadata,
        position_ids=cube.position_ids,
        risk_factor_names=selected,
        name=f"{cube.name}_fixture_imcc",
        artifact_id=cube.artifact_id,
        scenario_set_id=cube.scenario_set_id,
        scenario_vector_ids=cube.scenario_vector_ids,
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


def _manifest_file_metadata(manifest: Mapping[str, Any], filename: str) -> Mapping[str, Any]:
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        return {}
    metadata = files.get(filename)
    if not isinstance(metadata, Mapping):
        return {}
    artifact_metadata = metadata.get("artifact_metadata")
    if isinstance(artifact_metadata, Mapping):
        return artifact_metadata
    return {}


def _scenario_vector_ids_from_metadata(
    artifact_metadata: Mapping[str, Any],
    scenario_metadata: Sequence[ScenarioMetadata],
) -> tuple[str, ...]:
    supplied = artifact_metadata.get("scenario_vector_ids")
    if isinstance(supplied, Sequence) and not isinstance(supplied, str):
        return tuple(str(item) for item in supplied)
    prefix = artifact_metadata.get("scenario_vector_id_prefix")
    if isinstance(prefix, str) and prefix:
        return tuple(f"{prefix}:{scenario.scenario_id}" for scenario in scenario_metadata)
    return ()


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
    artifact_metadata: Mapping[str, Any] | None = None,
) -> dict[str, RFETEvidence]:
    rows_by_name: dict[str, list[dict[str, str]]] = {}
    for row_index, row in enumerate(_read_csv(path)):
        if not row.get("source_row_id"):
            row["source_row_id"] = f"{path.name}:{row_index:05d}"
        rows_by_name.setdefault(row["risk_factor_name"], []).append(row)

    metadata = {} if artifact_metadata is None else artifact_metadata
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
                source_row_id=row["source_row_id"],
            )
            for row in rows
        )
        evidence[risk_factor.name] = RFETEvidence(
            risk_factor_name=risk_factor.name,
            as_of_date=as_of_date,
            observations=observations,
            qualitative_pass=qualitative_values.pop(),
            bucket_id=bucket_ids.pop(),
            observation_time_series_id=_rfet_time_series_id(metadata, risk_factor.name),
        )
    return evidence


def _rfet_time_series_id(artifact_metadata: Mapping[str, Any], risk_factor_name: str) -> str:
    supplied = artifact_metadata.get("time_series_ids")
    if isinstance(supplied, Mapping):
        value = supplied.get(risk_factor_name)
        if isinstance(value, str):
            return value
    prefix = artifact_metadata.get("time_series_id_prefix")
    if isinstance(prefix, str) and prefix:
        return f"{prefix}:{risk_factor_name}"
    return ""


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
