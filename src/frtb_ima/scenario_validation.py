"""
Validation for nested liquidity-horizon scenario vectors.

The validator centralises structural checks required before LHA ES and IMCC
calculations consume nested liquidity-horizon vectors.

It validates shape, liquidity-horizon keys, equal scenario counts, optional
scenario metadata alignment, and optional nested subset metadata.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise

import numpy as np

from frtb_ima.data_models import LiquidityHorizon
from frtb_ima.scenario import ScenarioVector, validate_aligned_metadata


@dataclass(frozen=True)
class NestedLHValidationResult:
    """Audit-friendly summary of a nested liquidity-horizon vector validation."""

    horizons: tuple[LiquidityHorizon, ...]
    scenario_count: int
    has_metadata: bool
    metadata_aligned: bool
    nesting_evidence_checked: bool


class NestedLHValidationError(ValueError):
    """Raised when nested liquidity-horizon vectors fail structural validation."""


def _coerce_vector(value: ScenarioVector | Sequence[float], lh: LiquidityHorizon) -> ScenarioVector:
    if isinstance(value, ScenarioVector):
        return value
    return ScenarioVector(values=np.asarray(value, dtype=float), liquidity_horizon=lh)


def _normalise_vectors(
    lh_vectors: Mapping[LiquidityHorizon, ScenarioVector | Sequence[float]],
) -> dict[LiquidityHorizon, ScenarioVector]:
    normalised: dict[LiquidityHorizon, ScenarioVector] = {}
    for lh, vector in lh_vectors.items():
        if not isinstance(lh, LiquidityHorizon):
            raise NestedLHValidationError(f"invalid liquidity horizon key: {lh!r}")
        normalised[lh] = _coerce_vector(vector, lh)
    return normalised


def validate_nested_lh_vectors(
    lh_vectors: Mapping[LiquidityHorizon, ScenarioVector | Sequence[float]],
    *,
    require_metadata: bool = False,
    nesting_evidence: Mapping[LiquidityHorizon, set[str]] | None = None,
) -> NestedLHValidationResult:
    """
    Validate nested liquidity-horizon scenario vectors.

    Args:
        lh_vectors: Mapping from liquidity-horizon cutoff to a ScenarioVector or
            plain sequence of scenario values. LH10 must be present.
        require_metadata: If True, every vector must carry scenario metadata.
        nesting_evidence: Optional mapping from LH cutoff to the set of risk-factor
            IDs included in that nested subset. If supplied, the validator checks
            that longer-horizon subsets are true subsets of shorter-horizon sets.

    Returns:
        NestedLHValidationResult with validation diagnostics.

    Raises:
        NestedLHValidationError: if structural validation fails.
    """
    if not lh_vectors:
        raise NestedLHValidationError("lh_vectors must be non-empty")

    vectors = _normalise_vectors(lh_vectors)

    if LiquidityHorizon.LH10 not in vectors:
        raise NestedLHValidationError("LH10 vector is required as the full risk-factor set")

    lengths = {lh: vector.values.size for lh, vector in vectors.items()}
    scenario_count = lengths[LiquidityHorizon.LH10]
    mismatched = {lh: length for lh, length in lengths.items() if length != scenario_count}
    if mismatched:
        raise NestedLHValidationError(
            f"all LH vectors must have length {scenario_count}; mismatched lengths: {mismatched}"
        )

    has_metadata = any(vector.metadata for vector in vectors.values())
    if require_metadata and not all(vector.metadata for vector in vectors.values()):
        missing = [lh.name for lh, vector in vectors.items() if not vector.metadata]
        raise NestedLHValidationError(f"metadata required but missing for: {missing}")

    metadata_aligned = False
    if has_metadata:
        try:
            validate_aligned_metadata({lh.name: vector for lh, vector in vectors.items()})
        except ValueError as exc:
            raise NestedLHValidationError(str(exc)) from exc
        metadata_aligned = True

    nesting_evidence_checked = False
    if nesting_evidence is not None:
        _validate_nesting_evidence(tuple(vectors.keys()), nesting_evidence)
        nesting_evidence_checked = True

    horizons = tuple(sorted(vectors.keys(), key=lambda item: item.value))
    return NestedLHValidationResult(
        horizons=horizons,
        scenario_count=scenario_count,
        has_metadata=has_metadata,
        metadata_aligned=metadata_aligned,
        nesting_evidence_checked=nesting_evidence_checked,
    )


def _validate_nesting_evidence(
    supplied_horizons: Sequence[LiquidityHorizon],
    nesting_evidence: Mapping[LiquidityHorizon, set[str]],
) -> None:
    missing = [lh.name for lh in supplied_horizons if lh not in nesting_evidence]
    if missing:
        raise NestedLHValidationError(f"nesting evidence missing for: {missing}")

    ordered = sorted(supplied_horizons, key=lambda item: item.value)
    for lower, higher in pairwise(ordered):
        lower_set = nesting_evidence[lower]
        higher_set = nesting_evidence[higher]
        if not higher_set.issubset(lower_set):
            raise NestedLHValidationError(
                f"{higher.name} nesting evidence is not a subset of {lower.name}"
            )
