"""Tests for nested liquidity-horizon validation."""

from datetime import date

import numpy as np
import pytest

from frtb_ima.data_models import LiquidityHorizon
from frtb_ima.scenario import ScenarioVector, make_scenario_metadata
from frtb_ima.scenario_validation import (
    NestedLHValidationError,
    validate_nested_lh_vectors,
)

METADATA = make_scenario_metadata(
    [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3)]
)


def _vector(values: list[float]) -> ScenarioVector:
    return ScenarioVector(values=np.asarray(values), metadata=METADATA)


def test_validate_nested_lh_vectors_success() -> None:
    result = validate_nested_lh_vectors(
        {
            LiquidityHorizon.LH10: _vector([1.0, 2.0, 3.0]),
            LiquidityHorizon.LH20: _vector([1.0, 2.0, 3.0]),
        }
    )
    assert result.scenario_count == 3
    assert result.metadata_aligned is True


def test_validate_nested_lh_vectors_requires_lh10() -> None:
    with pytest.raises(NestedLHValidationError, match="LH10"):
        validate_nested_lh_vectors(
            {
                LiquidityHorizon.LH20: _vector([1.0, 2.0, 3.0]),
            }
        )


def test_validate_nested_lh_vectors_detects_length_mismatch() -> None:
    with pytest.raises(NestedLHValidationError, match="mismatched lengths"):
        validate_nested_lh_vectors(
            {
                LiquidityHorizon.LH10: ScenarioVector(values=np.array([1.0, 2.0, 3.0])),
                LiquidityHorizon.LH20: ScenarioVector(values=np.array([1.0, 2.0])),
            }
        )


def test_validate_nested_lh_vectors_requires_metadata() -> None:
    with pytest.raises(NestedLHValidationError, match="metadata required"):
        validate_nested_lh_vectors(
            {
                LiquidityHorizon.LH10: ScenarioVector(values=np.array([1.0, 2.0])),
            },
            require_metadata=True,
        )


def test_validate_nested_lh_vectors_detects_metadata_misalignment() -> None:
    m1 = make_scenario_metadata([date(2025, 1, 1), date(2025, 1, 2)])
    m2 = make_scenario_metadata([date(2025, 1, 2), date(2025, 1, 3)])

    with pytest.raises(NestedLHValidationError, match="not aligned"):
        validate_nested_lh_vectors(
            {
                LiquidityHorizon.LH10: ScenarioVector(
                    values=np.array([1.0, 2.0]), metadata=m1
                ),
                LiquidityHorizon.LH20: ScenarioVector(
                    values=np.array([1.0, 2.0]), metadata=m2
                ),
            }
        )


def test_validate_nested_lh_vectors_checks_nesting_evidence() -> None:
    with pytest.raises(NestedLHValidationError, match="not a subset"):
        validate_nested_lh_vectors(
            {
                LiquidityHorizon.LH10: _vector([1.0, 2.0, 3.0]),
                LiquidityHorizon.LH20: _vector([1.0, 2.0, 3.0]),
            },
            nesting_evidence={
                LiquidityHorizon.LH10: {"RF1"},
                LiquidityHorizon.LH20: {"RF1", "RF2"},
            },
        )
