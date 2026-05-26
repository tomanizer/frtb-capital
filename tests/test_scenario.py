"""Tests for canonical scenario metadata and vector containers."""

from datetime import date

import numpy as np
import pytest

from frtb_ima.data_models import LiquidityHorizon, RiskClass
from frtb_ima.scenario import (
    ScenarioMetadata,
    ScenarioSetType,
    ScenarioVector,
    make_scenario_metadata,
    validate_aligned_metadata,
    validate_unique_scenarios,
)


def test_make_scenario_metadata() -> None:
    metadata = make_scenario_metadata(
        [date(2025, 1, 1), date(2025, 1, 2)],
        prefix="stress",
        scenario_set=ScenarioSetType.STRESS,
    )
    assert metadata[0].scenario_id == "stress-00000"
    assert metadata[1].scenario_set == ScenarioSetType.STRESS


def test_scenario_vector_requires_non_empty_1d_vector() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        ScenarioVector(values=np.array([]))

    with pytest.raises(ValueError, match="one-dimensional"):
        ScenarioVector(values=np.array([[1.0, 2.0]]))

    with pytest.raises(ValueError, match="finite"):
        ScenarioVector(values=np.array([1.0, np.inf]))


def test_scenario_vector_metadata_alignment() -> None:
    metadata = make_scenario_metadata([date(2025, 1, 1), date(2025, 1, 2)])
    vector = ScenarioVector(
        values=np.array([1.0, 2.0]),
        metadata=metadata,
        risk_class=RiskClass.GIRR,
        liquidity_horizon=LiquidityHorizon.LH10,
    )
    assert vector.scenario_ids == ("scenario-00000", "scenario-00001")


def test_validate_unique_scenarios_detects_duplicates() -> None:
    metadata = (
        ScenarioMetadata("A", date(2025, 1, 1)),
        ScenarioMetadata("A", date(2025, 1, 2)),
    )
    with pytest.raises(ValueError, match="duplicate scenario_id"):
        validate_unique_scenarios(metadata)


def test_validate_aligned_metadata() -> None:
    metadata = make_scenario_metadata([date(2025, 1, 1), date(2025, 1, 2)])

    vectors = {
        "v1": ScenarioVector(values=np.array([1.0, 2.0]), metadata=metadata),
        "v2": ScenarioVector(values=np.array([3.0, 4.0]), metadata=metadata),
    }

    validate_aligned_metadata(vectors)


def test_validate_aligned_metadata_detects_misalignment() -> None:
    m1 = make_scenario_metadata([date(2025, 1, 1), date(2025, 1, 2)])
    m2 = make_scenario_metadata([date(2025, 1, 2), date(2025, 1, 3)])

    vectors = {
        "v1": ScenarioVector(values=np.array([1.0, 2.0]), metadata=m1),
        "v2": ScenarioVector(values=np.array([3.0, 4.0]), metadata=m2),
    }

    with pytest.raises(ValueError, match="not aligned"):
        validate_aligned_metadata(vectors)
