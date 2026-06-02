"""
NMRF stress-method selection.

RFET determines whether a risk factor is modellable. This module runs after
RFET and before valuation to decide what an upstream risk engine must produce
for each Type A or Type B NMRF.

Regulatory traceability:
    Basel MAR33 NMRF stress-scenario capital; U.S. NPR 2.0 SES methodology for
    Type A / Type B NMRFs; EU CRR Article 325bk stress scenario risk measure.
    The method-selection rules here are package governance logic; they do not
    replace model approval or pricing-model validation.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import numpy.typing as npt

from frtb_ima._array_utils import finite_1d_float_array as _finite_1d_float_array
from frtb_ima.data_models import LiquidityHorizon, ModellabilityStatus
from frtb_ima.nmrf import NMRFStressMethod, nmrf_effective_liquidity_horizon
from frtb_ima.regimes import RegulatoryPolicy


class NMRFMethodSelectionError(ValueError):
    """Raised when no acceptable NMRF stress method can be selected."""


class NMRFDiagnosticOutcome(StrEnum):
    """Outcome of an auditable NMRF method-selection diagnostic."""

    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class NMRFMethodDiagnostic:
    """Single method-selection diagnostic used as evidence for governance."""

    name: str
    outcome: NMRFDiagnosticOutcome
    value: float | None = None
    threshold: float | None = None
    source: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("diagnostic name must be non-empty")
        if not isinstance(self.outcome, NMRFDiagnosticOutcome):
            raise TypeError("outcome must be an NMRFDiagnosticOutcome")
        if self.value is not None and not math.isfinite(self.value):
            raise ValueError("diagnostic value must be finite when provided")
        if self.threshold is not None and not math.isfinite(self.threshold):
            raise ValueError("diagnostic threshold must be finite when provided")

    @property
    def passed(self) -> bool:
        """Return True when the diagnostic explicitly passed."""
        return self.outcome == NMRFDiagnosticOutcome.PASS

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "name": self.name,
            "outcome": self.outcome.value,
            "value": self.value,
            "threshold": self.threshold,
            "source": self.source,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class NMRFMethodEvidence:
    """
    Auditable evidence used to derive NMRF method-selection booleans.

    The selector remains deterministic and simple, while this evidence object
    records why a direct, stepwise, or full-revaluation path is considered
    available. Direct shocks are treated as robust only when the vectorized
    robustness diagnostic passes and no pricing/proxy flags disqualify it.
    """

    risk_factor_name: str
    nonlinear: bool = False
    full_revaluation_available: bool = False
    direct_method_available: bool = False
    direct_shock_well_defined: bool = False
    direct_robustness: NMRFMethodDiagnostic | None = None
    stepwise_available: bool = False
    stepwise_required: bool = False
    max_loss_fallback_allowed: bool = False
    pricing_attempt_count: int = 0
    pricing_failure_count: int = 0
    proxy_or_basis_risk: bool = False
    diagnostics: tuple[NMRFMethodDiagnostic, ...] = ()
    source: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.risk_factor_name:
            raise ValueError("risk_factor_name must be non-empty")
        if self.direct_robustness is not None and not isinstance(
            self.direct_robustness,
            NMRFMethodDiagnostic,
        ):
            raise TypeError("direct_robustness must be an NMRFMethodDiagnostic")
        if self.pricing_attempt_count < 0 or self.pricing_failure_count < 0:
            raise ValueError("pricing counts must be non-negative")
        if self.pricing_failure_count > self.pricing_attempt_count:
            raise ValueError("pricing_failure_count cannot exceed pricing_attempt_count")

        diagnostics = tuple(self.diagnostics)
        if any(not isinstance(diagnostic, NMRFMethodDiagnostic) for diagnostic in diagnostics):
            raise TypeError("diagnostics must contain NMRFMethodDiagnostic values")
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def direct_robust(self) -> bool:
        """Return True when direct valuation evidence supports using direct shocks."""
        return (
            self.direct_method_available
            and self.direct_shock_well_defined
            and self.direct_robustness is not None
            and self.direct_robustness.passed
            and self.pricing_failure_count == 0
            and not self.proxy_or_basis_risk
        )

    @property
    def all_diagnostics(self) -> tuple[NMRFMethodDiagnostic, ...]:
        """Return direct robustness plus any supplemental diagnostics."""
        if self.direct_robustness is None:
            return self.diagnostics
        return (self.direct_robustness, *self.diagnostics)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "risk_factor_name": self.risk_factor_name,
            "nonlinear": self.nonlinear,
            "full_revaluation_available": self.full_revaluation_available,
            "direct_method_available": self.direct_method_available,
            "direct_shock_well_defined": self.direct_shock_well_defined,
            "direct_robust": self.direct_robust,
            "stepwise_available": self.stepwise_available,
            "stepwise_required": self.stepwise_required,
            "max_loss_fallback_allowed": self.max_loss_fallback_allowed,
            "pricing_attempt_count": self.pricing_attempt_count,
            "pricing_failure_count": self.pricing_failure_count,
            "proxy_or_basis_risk": self.proxy_or_basis_risk,
            "diagnostics": [diagnostic.as_dict() for diagnostic in self.all_diagnostics],
            "source": self.source,
            "notes": self.notes,
        }


class NMRFMethodReason(StrEnum):
    """Audit reason for an NMRF stress-method decision."""

    NONLINEAR_FULL_REVAL_AVAILABLE = "NONLINEAR_FULL_REVAL_AVAILABLE"
    DIRECT_STABLE_AND_WELL_DEFINED = "DIRECT_STABLE_AND_WELL_DEFINED"
    DIRECT_FAILED_NONLINEARITY_TEST = "DIRECT_FAILED_NONLINEARITY_TEST"
    STEPWISE_REQUIRED_FOR_GRID_SEARCH = "STEPWISE_REQUIRED_FOR_GRID_SEARCH"
    STEPWISE_ONLY_AVAILABLE_METHOD = "STEPWISE_ONLY_AVAILABLE_METHOD"
    FULL_REVALUATION_AVAILABLE = "FULL_REVALUATION_AVAILABLE"
    NO_ACCEPTABLE_SCENARIO_REQUIRES_MAX_LOSS = "NO_ACCEPTABLE_SCENARIO_REQUIRES_MAX_LOSS"
    NO_ACCEPTABLE_METHOD = "NO_ACCEPTABLE_METHOD"


@dataclass(frozen=True)
class NMRFMethodSelectionInput:
    """
    Governance and valuation-capability inputs for one NMRF.

    These flags should come from RFET outputs, product/risk-factor metadata, and
    pre-valuation capability checks. They are deliberately simple booleans so
    the selection rule remains auditable and deterministic.
    """

    risk_factor_name: str
    modellability_status: ModellabilityStatus
    liquidity_horizon: LiquidityHorizon
    nonlinear: bool = False
    full_revaluation_available: bool = False
    direct_method_available: bool = False
    direct_shock_well_defined: bool = False
    direct_robust: bool = False
    stepwise_available: bool = False
    stepwise_required: bool = False
    max_loss_fallback_allowed: bool = False
    source: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.risk_factor_name:
            raise ValueError("risk_factor_name must be non-empty")
        if not isinstance(self.modellability_status, ModellabilityStatus):
            raise TypeError("modellability_status must be a ModellabilityStatus")
        if not isinstance(self.liquidity_horizon, LiquidityHorizon):
            raise TypeError("liquidity_horizon must be a LiquidityHorizon")

    @property
    def is_nmrf(self) -> bool:
        """Return True when RFET classified this factor as Type A or Type B."""
        return self.modellability_status in {
            ModellabilityStatus.TYPE_A_NMRF,
            ModellabilityStatus.TYPE_B_NMRF,
        }


def _as_finite_1d_array(
    values: Sequence[float] | npt.NDArray[np.float64],
    name: str,
) -> npt.NDArray[np.float64]:
    return _finite_1d_float_array(
        values,
        name,
        empty_message=f"{name} must be non-empty",
    )


def assess_direct_loss_robustness(
    direct_losses: Sequence[float] | npt.NDArray[np.float64],
    benchmark_losses: Sequence[float] | npt.NDArray[np.float64],
    *,
    max_relative_error_threshold: float = 0.10,
    absolute_tolerance: float = 1e-12,
    source: str = "",
    notes: str = "",
) -> NMRFMethodDiagnostic:
    """
    Compare direct-shock losses with benchmark revaluation losses.

    The calculation is vectorized across scenario/checkpoint losses. A direct
    method passes only when the worst relative deviation from the benchmark is
    within the supplied threshold. ``absolute_tolerance`` prevents zero-loss
    checkpoints from creating unstable relative-error denominators.
    """
    if max_relative_error_threshold < 0.0 or not math.isfinite(max_relative_error_threshold):
        raise ValueError("max_relative_error_threshold must be finite and non-negative")
    if absolute_tolerance <= 0.0 or not math.isfinite(absolute_tolerance):
        raise ValueError("absolute_tolerance must be finite and positive")

    direct = _as_finite_1d_array(direct_losses, "direct_losses")
    benchmark = _as_finite_1d_array(benchmark_losses, "benchmark_losses")
    if direct.shape != benchmark.shape:
        raise ValueError("direct_losses and benchmark_losses must have the same shape")

    abs_errors = np.abs(direct - benchmark)
    denominators = np.maximum(np.abs(benchmark), absolute_tolerance)
    relative_errors = abs_errors / denominators
    max_relative_error = float(np.max(relative_errors))
    max_abs_error = float(np.max(abs_errors))
    outcome = (
        NMRFDiagnosticOutcome.PASS
        if max_relative_error <= max_relative_error_threshold
        else NMRFDiagnosticOutcome.FAIL
    )
    audit_notes = f"max_abs_error={max_abs_error:.12g}; observations={int(direct.size)}"
    if notes:
        audit_notes = f"{notes}; {audit_notes}"

    return NMRFMethodDiagnostic(
        name="direct_loss_robustness",
        outcome=outcome,
        value=max_relative_error,
        threshold=max_relative_error_threshold,
        source=source,
        notes=audit_notes,
    )


def selection_input_from_method_evidence(
    evidence: NMRFMethodEvidence,
    modellability_status: ModellabilityStatus,
    liquidity_horizon: LiquidityHorizon,
) -> NMRFMethodSelectionInput:
    """Convert auditable method evidence into the selector's stable input API."""
    if not isinstance(evidence, NMRFMethodEvidence):
        raise TypeError("evidence must be an NMRFMethodEvidence")
    return NMRFMethodSelectionInput(
        risk_factor_name=evidence.risk_factor_name,
        modellability_status=modellability_status,
        liquidity_horizon=liquidity_horizon,
        nonlinear=evidence.nonlinear,
        full_revaluation_available=evidence.full_revaluation_available,
        direct_method_available=evidence.direct_method_available,
        direct_shock_well_defined=evidence.direct_shock_well_defined,
        direct_robust=evidence.direct_robust,
        stepwise_available=evidence.stepwise_available,
        stepwise_required=evidence.stepwise_required,
        max_loss_fallback_allowed=evidence.max_loss_fallback_allowed,
        source=evidence.source,
        notes=evidence.notes,
    )


@dataclass(frozen=True)
class NMRFValuationInstruction:
    """Instruction emitted to the upstream valuation layer for one NMRF."""

    risk_factor_name: str
    modellability_status: ModellabilityStatus
    method: NMRFStressMethod
    risk_factor_liquidity_horizon: LiquidityHorizon
    required_liquidity_horizon: LiquidityHorizon
    reason: NMRFMethodReason
    source: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.risk_factor_name:
            raise ValueError("risk_factor_name must be non-empty")
        if self.modellability_status not in {
            ModellabilityStatus.TYPE_A_NMRF,
            ModellabilityStatus.TYPE_B_NMRF,
        }:
            raise ValueError("valuation instructions are only valid for NMRFs")
        if not isinstance(self.method, NMRFStressMethod):
            raise TypeError("method must be an NMRFStressMethod")
        if not isinstance(self.risk_factor_liquidity_horizon, LiquidityHorizon):
            raise TypeError("risk_factor_liquidity_horizon must be a LiquidityHorizon")
        if not isinstance(self.required_liquidity_horizon, LiquidityHorizon):
            raise TypeError("required_liquidity_horizon must be a LiquidityHorizon")
        minimum = nmrf_effective_liquidity_horizon(self.risk_factor_liquidity_horizon)
        if self.required_liquidity_horizon.value < minimum.value:
            raise ValueError("required_liquidity_horizon is below the NMRF floor")
        if not isinstance(self.reason, NMRFMethodReason):
            raise TypeError("reason must be an NMRFMethodReason")

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "risk_factor_name": self.risk_factor_name,
            "modellability_status": self.modellability_status.value,
            "method": self.method.value,
            "risk_factor_liquidity_horizon": (self.risk_factor_liquidity_horizon.value),
            "required_liquidity_horizon": self.required_liquidity_horizon.value,
            "reason": self.reason.value,
            "source": self.source,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class NMRFMethodDecision:
    """Selected NMRF stress method plus auditable rationale."""

    risk_factor_name: str
    modellability_status: ModellabilityStatus
    liquidity_horizon: LiquidityHorizon
    method: NMRFStressMethod
    reason: NMRFMethodReason
    source: str = ""
    notes: str = ""

    @property
    def required_liquidity_horizon(self) -> LiquidityHorizon:
        """Stress horizon required for this NMRF after applying the 20-day floor."""
        return nmrf_effective_liquidity_horizon(self.liquidity_horizon)

    def to_valuation_instruction(self) -> NMRFValuationInstruction:
        """Convert the decision into a valuation-run instruction."""
        return NMRFValuationInstruction(
            risk_factor_name=self.risk_factor_name,
            modellability_status=self.modellability_status,
            method=self.method,
            risk_factor_liquidity_horizon=self.liquidity_horizon,
            required_liquidity_horizon=self.required_liquidity_horizon,
            reason=self.reason,
            source=self.source,
            notes=self.notes,
        )

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "risk_factor_name": self.risk_factor_name,
            "modellability_status": self.modellability_status.value,
            "liquidity_horizon": self.liquidity_horizon.value,
            "required_liquidity_horizon": self.required_liquidity_horizon.value,
            "method": self.method.value,
            "reason": self.reason.value,
            "source": self.source,
            "notes": self.notes,
        }


def _fallback_or_error(
    selection_input: NMRFMethodSelectionInput,
    reason: NMRFMethodReason,
) -> NMRFMethodDecision:
    if selection_input.max_loss_fallback_allowed:
        return NMRFMethodDecision(
            risk_factor_name=selection_input.risk_factor_name,
            modellability_status=selection_input.modellability_status,
            liquidity_horizon=selection_input.liquidity_horizon,
            method=NMRFStressMethod.MAX_LOSS_FALLBACK,
            reason=NMRFMethodReason.NO_ACCEPTABLE_SCENARIO_REQUIRES_MAX_LOSS,
            source=selection_input.source,
            notes=selection_input.notes,
        )
    raise NMRFMethodSelectionError(
        f"No acceptable NMRF stress method for {selection_input.risk_factor_name}: {reason.value}"
    )


def select_nmrf_method(
    selection_input: NMRFMethodSelectionInput,
    policy: RegulatoryPolicy,
) -> NMRFMethodDecision:
    """
    Select the stress method for one Type A or Type B NMRF.

    Default policy:
      * full revaluation for nonlinear factors when available;
      * direct when the shock is well-defined and robust;
      * stepwise when direct is not robust or a grid/path is required;
      * max-loss fallback only when explicitly allowed.
    """
    policy.require_supported("type_a_type_b_nmrf_taxonomy")
    if not selection_input.is_nmrf:
        raise NMRFMethodSelectionError("NMRF method selection requires TYPE_A_NMRF or TYPE_B_NMRF")

    if selection_input.nonlinear and selection_input.full_revaluation_available:
        return NMRFMethodDecision(
            risk_factor_name=selection_input.risk_factor_name,
            modellability_status=selection_input.modellability_status,
            liquidity_horizon=selection_input.liquidity_horizon,
            method=NMRFStressMethod.FULL_REVALUATION,
            reason=NMRFMethodReason.NONLINEAR_FULL_REVAL_AVAILABLE,
            source=selection_input.source,
            notes=selection_input.notes,
        )

    if selection_input.stepwise_required:
        if selection_input.stepwise_available:
            return NMRFMethodDecision(
                risk_factor_name=selection_input.risk_factor_name,
                modellability_status=selection_input.modellability_status,
                liquidity_horizon=selection_input.liquidity_horizon,
                method=NMRFStressMethod.STEPWISE,
                reason=NMRFMethodReason.STEPWISE_REQUIRED_FOR_GRID_SEARCH,
                source=selection_input.source,
                notes=selection_input.notes,
            )
        return _fallback_or_error(
            selection_input,
            NMRFMethodReason.STEPWISE_REQUIRED_FOR_GRID_SEARCH,
        )

    direct_is_usable = (
        selection_input.direct_method_available
        and selection_input.direct_shock_well_defined
        and selection_input.direct_robust
    )
    if direct_is_usable:
        return NMRFMethodDecision(
            risk_factor_name=selection_input.risk_factor_name,
            modellability_status=selection_input.modellability_status,
            liquidity_horizon=selection_input.liquidity_horizon,
            method=NMRFStressMethod.DIRECT,
            reason=NMRFMethodReason.DIRECT_STABLE_AND_WELL_DEFINED,
            source=selection_input.source,
            notes=selection_input.notes,
        )

    direct_was_attempted = (
        selection_input.direct_method_available
        and selection_input.direct_shock_well_defined
        and not selection_input.direct_robust
    )
    if direct_was_attempted and selection_input.stepwise_available:
        return NMRFMethodDecision(
            risk_factor_name=selection_input.risk_factor_name,
            modellability_status=selection_input.modellability_status,
            liquidity_horizon=selection_input.liquidity_horizon,
            method=NMRFStressMethod.STEPWISE,
            reason=NMRFMethodReason.DIRECT_FAILED_NONLINEARITY_TEST,
            source=selection_input.source,
            notes=selection_input.notes,
        )

    if selection_input.full_revaluation_available:
        return NMRFMethodDecision(
            risk_factor_name=selection_input.risk_factor_name,
            modellability_status=selection_input.modellability_status,
            liquidity_horizon=selection_input.liquidity_horizon,
            method=NMRFStressMethod.FULL_REVALUATION,
            reason=NMRFMethodReason.FULL_REVALUATION_AVAILABLE,
            source=selection_input.source,
            notes=selection_input.notes,
        )

    if selection_input.stepwise_available:
        return NMRFMethodDecision(
            risk_factor_name=selection_input.risk_factor_name,
            modellability_status=selection_input.modellability_status,
            liquidity_horizon=selection_input.liquidity_horizon,
            method=NMRFStressMethod.STEPWISE,
            reason=NMRFMethodReason.STEPWISE_ONLY_AVAILABLE_METHOD,
            source=selection_input.source,
            notes=selection_input.notes,
        )

    return _fallback_or_error(
        selection_input,
        NMRFMethodReason.NO_ACCEPTABLE_METHOD,
    )


def select_nmrf_method_from_evidence(
    evidence: NMRFMethodEvidence,
    modellability_status: ModellabilityStatus,
    liquidity_horizon: LiquidityHorizon,
    policy: RegulatoryPolicy,
) -> NMRFMethodDecision:
    """Select one NMRF stress method from auditable method evidence."""
    return select_nmrf_method(
        selection_input_from_method_evidence(
            evidence,
            modellability_status,
            liquidity_horizon,
        ),
        policy,
    )


def select_nmrf_methods(
    selection_inputs: Sequence[NMRFMethodSelectionInput],
    policy: RegulatoryPolicy,
) -> tuple[NMRFMethodDecision, ...]:
    """Select stress methods for a deterministic sequence of NMRF inputs."""
    if not selection_inputs:
        raise ValueError("selection_inputs must be non-empty")
    return tuple(
        select_nmrf_method(selection_input, policy) for selection_input in selection_inputs
    )
