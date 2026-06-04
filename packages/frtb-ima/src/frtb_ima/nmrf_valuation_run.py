"""
NMRF valuation-run handoff and artifact reconciliation.

This module is the boundary between the capital package and an upstream
valuation or pricing engine. It reconciles NMRF valuation specifications with
returned stress artifacts before those artifacts are consumed by SES capital.
It does not generate stress scenarios, select stress periods, or price trades.

Sign convention: ``NMRFStressArtifact.losses`` uses positive values for losses
and negative values for gains, matching ``nmrf.py``.

Regulatory traceability:
    Basel MAR33 NMRF stress-scenario capital; U.S. NPR 2.0 stressed expected
    shortfall treatment for Type A / Type B NMRFs; EU CRR Article
    325bk stress scenario risk measure. See docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

from frtb_common.serialization import jsonable

from frtb_ima._mapping_utils import empty_mapping as _empty_mapping
from frtb_ima._mapping_utils import freeze_mapping as _freeze_mapping
from frtb_ima.data_models import LiquidityHorizon, ModellabilityStatus
from frtb_ima.logging import calculation_log_extra
from frtb_ima.nmrf import (
    NMRFCapitalResult,
    NMRFStressArtifact,
    NMRFStressMethod,
    calculate_nmrf_capital_for_policy,
)
from frtb_ima.nmrf_stress_spec import (
    NMRFValuationSpec,
    required_liquidity_horizons_from_valuation_specs,
    required_methods_from_valuation_specs,
)
from frtb_ima.regimes import RegulatoryPolicy

logger = logging.getLogger(__name__)


class NMRFValuationRunError(ValueError):
    """Raised when an NMRF valuation run cannot be accepted for capital use."""


@dataclass(frozen=True)
class NMRFValuationRunRequest:
    """Immutable request sent to an upstream NMRF valuation layer."""

    run_id: str
    desk_id: str
    regime: str
    specs: tuple[NMRFValuationSpec, ...]
    as_of_date: date | None = None
    source: str = "nmrf valuation run request"
    notes: str = ""
    metadata: Mapping[str, object] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if not self.desk_id:
            raise ValueError("desk_id must be non-empty")
        if not self.regime:
            raise ValueError("regime must be non-empty")
        if self.as_of_date is not None and not isinstance(self.as_of_date, date):
            raise TypeError("as_of_date must be a datetime.date when provided")
        if not self.source:
            raise ValueError("source must be non-empty")

        specs = tuple(self.specs)
        if not specs:
            raise ValueError("specs must be non-empty")
        if any(not isinstance(spec, NMRFValuationSpec) for spec in specs):
            raise TypeError("specs must contain NMRFValuationSpec values")
        risk_factor_names = [spec.risk_factor_name for spec in specs]
        if len(risk_factor_names) != len(set(risk_factor_names)):
            raise ValueError("specs contain duplicate risk_factor_name values")

        object.__setattr__(self, "specs", specs)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    @property
    def spec_count(self) -> int:
        """Number of NMRF valuation specifications in this request.
        Returns
        -------
        int
            Result of the operation.
        """
        return len(self.specs)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
        return {
            "run_id": self.run_id,
            "desk_id": self.desk_id,
            "regime": self.regime,
            "as_of_date": self.as_of_date.isoformat() if self.as_of_date is not None else None,
            "spec_count": self.spec_count,
            "specs": [spec.as_dict() for spec in self.specs],
            "source": self.source,
            "notes": self.notes,
            "metadata": jsonable(self.metadata),
        }


@dataclass(frozen=True)
class NMRFArtifactReconciliationItem:
    """Audit result for reconciling one valuation spec to returned artifacts."""

    risk_factor_name: str
    required_method: NMRFStressMethod
    required_liquidity_horizon: LiquidityHorizon
    required_stress_period: str
    artifact_count: int
    artifact_method: NMRFStressMethod | None = None
    artifact_liquidity_horizon: LiquidityHorizon | None = None
    artifact_stress_period: str | None = None
    artifact_loss_count: int | None = None
    required_scenario_count: int | None = None
    exact_artifact_count: bool = False
    method_matched: bool = False
    liquidity_horizon_matched: bool = False
    stress_period_matched: bool = False
    scenario_count_matched: bool | None = None
    scenario_ids_matched: bool | None = None
    source_present: bool = False
    generated_by_prototype: bool | None = None
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.risk_factor_name:
            raise ValueError("risk_factor_name must be non-empty")
        if not isinstance(self.required_method, NMRFStressMethod):
            raise TypeError("required_method must be an NMRFStressMethod")
        if not isinstance(self.required_liquidity_horizon, LiquidityHorizon):
            raise TypeError("required_liquidity_horizon must be a LiquidityHorizon")
        if not self.required_stress_period:
            raise ValueError("required_stress_period must be non-empty")
        if self.artifact_count < 0:
            raise ValueError("artifact_count must be non-negative")
        object.__setattr__(self, "errors", tuple(self.errors))

    @property
    def passed(self) -> bool:
        """Return True when all reconciliation checks passed.
        Returns
        -------
        bool
            Result of the operation.
        """
        return not self.errors

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable audit summary without expanding loss vectors.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
        return {
            "risk_factor_name": self.risk_factor_name,
            "required_method": self.required_method.value,
            "artifact_method": self.artifact_method.value
            if self.artifact_method is not None
            else None,
            "required_liquidity_horizon": self.required_liquidity_horizon.value,
            "artifact_liquidity_horizon": self.artifact_liquidity_horizon.value
            if self.artifact_liquidity_horizon is not None
            else None,
            "required_stress_period": self.required_stress_period,
            "artifact_stress_period": self.artifact_stress_period,
            "artifact_count": self.artifact_count,
            "artifact_loss_count": self.artifact_loss_count,
            "required_scenario_count": self.required_scenario_count,
            "exact_artifact_count": self.exact_artifact_count,
            "method_matched": self.method_matched,
            "liquidity_horizon_matched": self.liquidity_horizon_matched,
            "stress_period_matched": self.stress_period_matched,
            "scenario_count_matched": self.scenario_count_matched,
            "scenario_ids_matched": self.scenario_ids_matched,
            "source_present": self.source_present,
            "generated_by_prototype": self.generated_by_prototype,
            "passed": self.passed,
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class NMRFArtifactReconciliationResult:
    """Full reconciliation result for an NMRF valuation-run artifact batch."""

    items: tuple[NMRFArtifactReconciliationItem, ...]
    unexpected_artifacts: tuple[str, ...] = ()
    duplicate_artifacts: tuple[str, ...] = ()
    returned_artifact_count: int | None = None
    unexpected_artifact_count: int | None = None

    def __post_init__(self) -> None:
        items = tuple(self.items)
        if not items:
            raise ValueError("items must be non-empty")
        if any(not isinstance(item, NMRFArtifactReconciliationItem) for item in items):
            raise TypeError("items must contain NMRFArtifactReconciliationItem values")
        item_names = [item.risk_factor_name for item in items]
        if len(item_names) != len(set(item_names)):
            raise ValueError("items contain duplicate risk_factor_name values")
        if self.returned_artifact_count is not None and self.returned_artifact_count < 0:
            raise ValueError("returned_artifact_count must be non-negative")
        if self.unexpected_artifact_count is not None and self.unexpected_artifact_count < 0:
            raise ValueError("unexpected_artifact_count must be non-negative")
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "unexpected_artifacts", tuple(self.unexpected_artifacts))
        object.__setattr__(self, "duplicate_artifacts", tuple(self.duplicate_artifacts))

    @property
    def passed(self) -> bool:
        """Return True when all specs reconciled and no extra artifacts exist.
        Returns
        -------
        bool
            Result of the operation.
        """
        return (
            all(item.passed for item in self.items)
            and not self.unexpected_artifacts
            and not self.duplicate_artifacts
        )

    @property
    def spec_count(self) -> int:
        """Number of requested valuation specs.
        Returns
        -------
        int
            Result of the operation.
        """
        return len(self.items)

    @property
    def artifact_count(self) -> int:
        """Number of returned artifacts in the reconciled valuation batch.
        Returns
        -------
        int
            Result of the operation.
        """
        if self.returned_artifact_count is not None:
            return self.returned_artifact_count
        return sum(item.artifact_count for item in self.items) + self.unexpected_count

    @property
    def missing_count(self) -> int:
        """Number of requested specs with no returned artifact.
        Returns
        -------
        int
            Result of the operation.
        """
        return sum(1 for item in self.items if item.artifact_count == 0)

    @property
    def unexpected_count(self) -> int:
        """Number of returned artifacts for risk factors not present in the request.
        Returns
        -------
        int
            Result of the operation.
        """
        if self.unexpected_artifact_count is not None:
            return self.unexpected_artifact_count
        return len(self.unexpected_artifacts)

    @property
    def unexpected_risk_factor_count(self) -> int:
        """Number of unexpected risk-factor names in the returned artifacts.
        Returns
        -------
        int
            Result of the operation.
        """
        return len(self.unexpected_artifacts)

    @property
    def duplicate_count(self) -> int:
        """Number of requested risk factors with duplicate returned artifacts.
        Returns
        -------
        int
            Result of the operation.
        """
        return len(self.duplicate_artifacts)

    @property
    def failed_item_count(self) -> int:
        """Number of requested specs that failed one or more checks.
        Returns
        -------
        int
            Result of the operation.
        """
        return sum(1 for item in self.items if not item.passed)

    @property
    def required_methods(self) -> dict[str, NMRFStressMethod]:
        """Return required methods keyed by risk factor for capital validation.
        Returns
        -------
        dict[str, NMRFStressMethod]
            Result of the operation.
        """
        return {item.risk_factor_name: item.required_method for item in self.items}

    @property
    def required_liquidity_horizons(self) -> dict[str, LiquidityHorizon]:
        """Return required liquidity horizons keyed by risk factor.
        Returns
        -------
        dict[str, LiquidityHorizon]
            Result of the operation.
        """
        return {item.risk_factor_name: item.required_liquidity_horizon for item in self.items}

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
        return {
            "passed": self.passed,
            "spec_count": self.spec_count,
            "artifact_count": self.artifact_count,
            "missing_count": self.missing_count,
            "unexpected_count": self.unexpected_count,
            "unexpected_risk_factor_count": self.unexpected_risk_factor_count,
            "duplicate_count": self.duplicate_count,
            "failed_item_count": self.failed_item_count,
            "unexpected_artifacts": list(self.unexpected_artifacts),
            "duplicate_artifacts": list(self.duplicate_artifacts),
            "items": [item.as_dict() for item in self.items],
        }


@dataclass(frozen=True)
class NMRFValuationRunResult:
    """Returned NMRF artifacts plus their reconciliation result."""

    request: NMRFValuationRunRequest
    artifacts: tuple[NMRFStressArtifact, ...]
    reconciliation: NMRFArtifactReconciliationResult
    elapsed_seconds: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.request, NMRFValuationRunRequest):
            raise TypeError("request must be an NMRFValuationRunRequest")
        artifacts = tuple(self.artifacts)
        if any(not isinstance(artifact, NMRFStressArtifact) for artifact in artifacts):
            raise TypeError("artifacts must contain NMRFStressArtifact values")
        if not isinstance(self.reconciliation, NMRFArtifactReconciliationResult):
            raise TypeError("reconciliation must be an NMRFArtifactReconciliationResult")
        request_names = {spec.risk_factor_name for spec in self.request.specs}
        reconciliation_names = {item.risk_factor_name for item in self.reconciliation.items}
        if request_names != reconciliation_names:
            raise ValueError("reconciliation items must match request specs")
        if self.reconciliation.artifact_count != len(artifacts):
            raise ValueError("reconciliation artifact_count must match artifacts")
        if self.elapsed_seconds is not None and self.elapsed_seconds < 0.0:
            raise ValueError("elapsed_seconds must be non-negative when provided")
        object.__setattr__(self, "artifacts", artifacts)

    @property
    def passed(self) -> bool:
        """Return True when the valuation run can be consumed by capital.
        Returns
        -------
        bool
            Result of the operation.
        """
        return self.reconciliation.passed

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
        return {
            "request": self.request.as_dict(),
            "artifact_count": len(self.artifacts),
            "artifacts": [artifact.as_dict() for artifact in self.artifacts],
            "reconciliation": self.reconciliation.as_dict(),
            "passed": self.passed,
            "elapsed_seconds": self.elapsed_seconds,
            "notes": self.notes,
        }


def build_nmrf_valuation_run_request(
    specs: Sequence[NMRFValuationSpec],
    policy: RegulatoryPolicy,
    *,
    run_id: str,
    desk_id: str,
    as_of_date: date | None = None,
    source: str = "nmrf valuation run request",
    notes: str = "",
    metadata: Mapping[str, object] | None = None,
) -> NMRFValuationRunRequest:
    """Build a run-level request for upstream NMRF valuation artifacts.
    Parameters
    ----------
    specs : Sequence[NMRFValuationSpec]
        Specs.
    policy : RegulatoryPolicy
        Policy.
    run_id : str
        Run id.
    desk_id : str
        Desk id.
    as_of_date : date | None, optional
        As of date.
    source : str, optional
        Source.
    notes : str, optional
        Notes.
    metadata : Mapping[str, object] | None, optional
        Metadata.

    Returns
    -------
    NMRFValuationRunRequest
        Result of the operation.
    """
    return NMRFValuationRunRequest(
        run_id=run_id,
        desk_id=desk_id,
        regime=policy.regime.value,
        specs=tuple(specs),
        as_of_date=as_of_date,
        source=source,
        notes=notes,
        metadata={} if metadata is None else metadata,
    )


def reconcile_nmrf_valuation_artifacts(
    specs: Sequence[NMRFValuationSpec],
    artifacts: Sequence[NMRFStressArtifact],
    *,
    allow_prototype_artifacts: bool = False,
    run_id: str | None = None,
    desk_id: str | None = None,
    regime: str | None = None,
) -> NMRFArtifactReconciliationResult:
    """Reconcile upstream NMRF stress artifacts to valuation specifications.

    This function validates the handoff contract only. It does not call a
    valuation engine and does not compute SES capital.
    Parameters
    ----------
    specs : Sequence[NMRFValuationSpec]
        Specs.
    artifacts : Sequence[NMRFStressArtifact]
        Artifacts.
    allow_prototype_artifacts : bool, optional
        Allow prototype artifacts.
    run_id : str | None, optional
        Run id.
    desk_id : str | None, optional
        Desk id.
    regime : str | None, optional
        Regime.

    Returns
    -------
    NMRFArtifactReconciliationResult
        Result of the operation.
    """
    specs_tuple = tuple(specs)
    if not specs_tuple:
        raise ValueError("specs must be non-empty")
    if any(not isinstance(spec, NMRFValuationSpec) for spec in specs_tuple):
        raise TypeError("specs must contain NMRFValuationSpec values")
    spec_names = [spec.risk_factor_name for spec in specs_tuple]
    if len(spec_names) != len(set(spec_names)):
        raise ValueError("specs contain duplicate risk_factor_name values")

    artifacts_tuple = tuple(artifacts)
    artifacts_by_name: dict[str, list[NMRFStressArtifact]] = {}
    for artifact in artifacts_tuple:
        if not isinstance(artifact, NMRFStressArtifact):
            raise TypeError("artifacts must contain NMRFStressArtifact values")
        artifacts_by_name.setdefault(artifact.risk_factor_name, []).append(artifact)

    spec_name_set = set(spec_names)
    unexpected = tuple(
        sorted(
            risk_factor_name
            for risk_factor_name in artifacts_by_name
            if risk_factor_name not in spec_name_set
        )
    )
    duplicate = tuple(
        sorted(
            risk_factor_name
            for risk_factor_name, matched_artifacts in artifacts_by_name.items()
            if risk_factor_name in spec_name_set and len(matched_artifacts) > 1
        )
    )
    unexpected_artifact_count = sum(
        len(matched_artifacts)
        for risk_factor_name, matched_artifacts in artifacts_by_name.items()
        if risk_factor_name not in spec_name_set
    )
    items = tuple(
        _reconcile_one_spec(
            spec,
            tuple(artifacts_by_name.get(spec.risk_factor_name, ())),
            allow_prototype_artifacts=allow_prototype_artifacts,
        )
        for spec in specs_tuple
    )
    result = NMRFArtifactReconciliationResult(
        items=items,
        unexpected_artifacts=unexpected,
        duplicate_artifacts=duplicate,
        returned_artifact_count=len(artifacts_tuple),
        unexpected_artifact_count=unexpected_artifact_count,
    )
    logger.info(
        "nmrf_valuation_reconciliation_complete",
        extra=calculation_log_extra(
            run_id=run_id,
            desk_id=desk_id,
            regime=regime,
            passed=result.passed,
            spec_count=result.spec_count,
            artifact_count=result.artifact_count,
            missing_count=result.missing_count,
            unexpected_count=result.unexpected_count,
            duplicate_count=result.duplicate_count,
            failed_item_count=result.failed_item_count,
        ),
    )
    return result


def complete_nmrf_valuation_run(
    request: NMRFValuationRunRequest,
    artifacts: Sequence[NMRFStressArtifact],
    *,
    allow_prototype_artifacts: bool = False,
    elapsed_seconds: float | None = None,
    notes: str = "",
) -> NMRFValuationRunResult:
    """Build a completed NMRF valuation run with reconciliation detail.
    Parameters
    ----------
    request : NMRFValuationRunRequest
        Request.
    artifacts : Sequence[NMRFStressArtifact]
        Artifacts.
    allow_prototype_artifacts : bool, optional
        Allow prototype artifacts.
    elapsed_seconds : float | None, optional
        Elapsed seconds.
    notes : str, optional
        Notes.

    Returns
    -------
    NMRFValuationRunResult
        Result of the operation.
    """
    reconciliation = reconcile_nmrf_valuation_artifacts(
        request.specs,
        artifacts,
        allow_prototype_artifacts=allow_prototype_artifacts,
        run_id=request.run_id,
        desk_id=request.desk_id,
        regime=request.regime,
    )
    return NMRFValuationRunResult(
        request=request,
        artifacts=tuple(artifacts),
        reconciliation=reconciliation,
        elapsed_seconds=elapsed_seconds,
        notes=notes,
    )


def require_nmrf_valuation_reconciliation_passed(
    reconciliation: NMRFArtifactReconciliationResult,
) -> None:
    """Raise a compact error if the NMRF artifact reconciliation failed.
    Parameters
    ----------
    reconciliation : NMRFArtifactReconciliationResult
        Reconciliation.
    """
    if reconciliation.passed:
        return
    raise NMRFValuationRunError(
        "NMRF valuation artifact reconciliation failed: "
        f"missing={reconciliation.missing_count}, "
        f"unexpected={reconciliation.unexpected_count}, "
        f"duplicates={reconciliation.duplicate_count}, "
        f"failed_items={reconciliation.failed_item_count}"
    )


def calculate_nmrf_capital_from_valuation_run(
    classifications: Mapping[str, ModellabilityStatus],
    valuation_run: NMRFValuationRunResult,
    policy: RegulatoryPolicy,
    *,
    allow_linear_approximation: bool = False,
) -> NMRFCapitalResult:
    """Validate a reconciled valuation run, then delegate to NMRF capital.
    Parameters
    ----------
    classifications : Mapping[str, ModellabilityStatus]
        Classifications.
    valuation_run : NMRFValuationRunResult
        Valuation run.
    policy : RegulatoryPolicy
        Policy.
    allow_linear_approximation : bool, optional
        Allow linear approximation.

    Returns
    -------
    NMRFCapitalResult
        Result of the operation.
    """
    if valuation_run.request.regime != policy.regime.value:
        raise NMRFValuationRunError(
            "NMRF valuation run regime does not match policy: "
            f"{valuation_run.request.regime} != {policy.regime.value}"
        )
    require_nmrf_valuation_reconciliation_passed(valuation_run.reconciliation)
    return calculate_nmrf_capital_for_policy(
        classifications,
        valuation_run.artifacts,
        policy,
        required_methods=required_methods_from_valuation_specs(
            valuation_run.request.specs,
        ),
        required_liquidity_horizons=required_liquidity_horizons_from_valuation_specs(
            valuation_run.request.specs,
        ),
        allow_linear_approximation=allow_linear_approximation,
        run_id=valuation_run.request.run_id,
        desk_id=valuation_run.request.desk_id,
    )


def _reconcile_one_spec(
    spec: NMRFValuationSpec,
    artifacts: tuple[NMRFStressArtifact, ...],
    *,
    allow_prototype_artifacts: bool,
) -> NMRFArtifactReconciliationItem:
    required_scenario_count = _required_scenario_count(spec)
    errors: list[str] = []
    artifact = artifacts[0] if artifacts else None

    if len(artifacts) != 1:
        errors.append("missing_artifact" if not artifacts else "duplicate_artifacts")

    if artifact is None:
        return NMRFArtifactReconciliationItem(
            risk_factor_name=spec.risk_factor_name,
            required_method=spec.method,
            required_liquidity_horizon=spec.required_liquidity_horizon,
            required_stress_period=spec.stress_period.stress_period_id,
            required_scenario_count=required_scenario_count,
            artifact_count=len(artifacts),
            errors=tuple(errors),
        )

    method_matched = artifact.method == spec.method
    if not method_matched:
        errors.append("method_mismatch")

    liquidity_horizon_matched = (
        artifact.liquidity_horizon.value >= spec.required_liquidity_horizon.value
    )
    if not liquidity_horizon_matched:
        errors.append("liquidity_horizon_too_short")

    stress_period_matched = artifact.stress_period == spec.stress_period.stress_period_id
    if not stress_period_matched:
        errors.append("stress_period_mismatch")

    source_present = bool(artifact.source)
    if not source_present:
        errors.append("missing_source")

    if artifact.generated_by_prototype and not allow_prototype_artifacts:
        errors.append("prototype_artifact")

    scenario_count_matched = _scenario_count_matched(spec, artifact)
    if scenario_count_matched is False:
        errors.append("scenario_count_mismatch")

    scenario_ids_matched = _scenario_ids_matched(spec, artifact)
    if scenario_ids_matched is False:
        errors.append("scenario_ids_mismatch")

    return NMRFArtifactReconciliationItem(
        risk_factor_name=spec.risk_factor_name,
        required_method=spec.method,
        required_liquidity_horizon=spec.required_liquidity_horizon,
        required_stress_period=spec.stress_period.stress_period_id,
        artifact_count=len(artifacts),
        artifact_method=artifact.method,
        artifact_liquidity_horizon=artifact.liquidity_horizon,
        artifact_stress_period=artifact.stress_period,
        artifact_loss_count=len(artifact.losses),
        required_scenario_count=required_scenario_count,
        exact_artifact_count=len(artifacts) == 1,
        method_matched=method_matched,
        liquidity_horizon_matched=liquidity_horizon_matched,
        stress_period_matched=stress_period_matched,
        scenario_count_matched=scenario_count_matched,
        scenario_ids_matched=scenario_ids_matched,
        source_present=source_present,
        generated_by_prototype=artifact.generated_by_prototype,
        errors=tuple(errors),
    )


def _required_scenario_count(spec: NMRFValuationSpec) -> int | None:
    if spec.method == NMRFStressMethod.STEPWISE:
        assert spec.stepwise_grid is not None
        return spec.stepwise_grid.shock_count
    required_ids = _required_scenario_ids(spec)
    if required_ids:
        return len(required_ids)
    return None


def _required_scenario_ids(spec: NMRFValuationSpec) -> tuple[str, ...]:
    if spec.method == NMRFStressMethod.FULL_REVALUATION:
        assert spec.full_revaluation is not None
        return tuple(spec.full_revaluation.market_state_ids)
    if spec.method == NMRFStressMethod.MAX_LOSS_FALLBACK:
        assert spec.max_loss_fallback is not None
        return tuple(spec.max_loss_fallback.candidate_scenario_ids)
    return ()


def _scenario_count_matched(
    spec: NMRFValuationSpec,
    artifact: NMRFStressArtifact,
) -> bool | None:
    required_count = _required_scenario_count(spec)
    if required_count is None:
        return None
    return len(artifact.losses) == required_count


def _scenario_ids_matched(
    spec: NMRFValuationSpec,
    artifact: NMRFStressArtifact,
) -> bool | None:
    required_ids = _required_scenario_ids(spec)
    if not required_ids:
        return None
    return artifact.scenario_ids == required_ids
