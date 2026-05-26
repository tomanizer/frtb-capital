"""Tests for vector-friendly market-risk data contracts."""

from datetime import date
from types import MappingProxyType

import numpy as np
import pytest

from frtb_ima.data_contracts import (
    CapitalRunResult,
    DeskRun,
    Position,
    RFETEvidence,
    RiskFactorBucket,
    RiskFactorDefinition,
    ScenarioCube,
)
from frtb_ima.data_models import (
    DeskCapitalResult,
    LiquidityHorizon,
    RealPriceObservation,
    RiskClass,
)
from frtb_ima.regimes import CalculationContext, RegulatoryRegime, get_policy
from frtb_ima.scenario import ScenarioSetType, make_scenario_metadata

AS_OF = date(2025, 6, 30)


def _metadata(n: int = 2) -> tuple:
    return make_scenario_metadata(
        [date(2025, 1, day) for day in range(1, n + 1)],
        scenario_set=ScenarioSetType.CURRENT,
    )


def test_risk_factor_definition_validates_bucket_alignment() -> None:
    bucket = RiskFactorBucket(
        bucket_id="USD_RATES",
        risk_class=RiskClass.GIRR,
        liquidity_horizon=LiquidityHorizon.LH10,
        metadata={"source": "policy"},
    )
    rf = RiskFactorDefinition(
        name="USD_SWAP_5Y",
        risk_class=RiskClass.GIRR,
        liquidity_horizon=LiquidityHorizon.LH10,
        bucket=bucket,
        currency="USD",
    )

    assert rf.bucket == bucket
    assert isinstance(bucket.metadata, MappingProxyType)

    bad_bucket = RiskFactorBucket(
        bucket_id="EQUITY",
        risk_class=RiskClass.EQUITY,
        liquidity_horizon=LiquidityHorizon.LH20,
    )
    with pytest.raises(ValueError, match="risk_class"):
        RiskFactorDefinition(
            name="USD_SWAP_5Y",
            risk_class=RiskClass.GIRR,
            liquidity_horizon=LiquidityHorizon.LH10,
            bucket=bad_bucket,
        )


def test_position_freezes_metadata_and_requires_unique_risk_factors() -> None:
    position = Position(
        position_id="P1",
        desk="Rates",
        instrument_id="Bond1",
        fair_value=10.0,
        currency="USD",
        risk_factor_names=("USD_SWAP_5Y",),
        metadata={"book": "A"},
    )

    assert position.risk_factor_names == ("USD_SWAP_5Y",)
    assert isinstance(position.metadata, MappingProxyType)

    with pytest.raises(ValueError, match="duplicates"):
        Position(
            position_id="P2",
            desk="Rates",
            instrument_id="Bond2",
            fair_value=10.0,
            currency="USD",
            risk_factor_names=("RF", "RF"),
        )


def test_rfet_evidence_requires_matching_observations() -> None:
    evidence = RFETEvidence(
        risk_factor_name="RF",
        as_of_date=AS_OF,
        observations=(
            RealPriceObservation("RF", AS_OF, source="VENDOR_A"),
            RealPriceObservation("RF", date(2025, 6, 1), source="VENDOR_B"),
        ),
        qualitative_pass=True,
    )

    assert evidence.observation_count == 2

    with pytest.raises(ValueError, match="observations"):
        RFETEvidence(
            risk_factor_name="RF",
            as_of_date=AS_OF,
            observations=(RealPriceObservation("OTHER", AS_OF),),
            qualitative_pass=True,
        )


def test_scenario_cube_validates_shape_and_axis_labels() -> None:
    cube = ScenarioCube(
        values=np.array(
            [
                [[1.0, 10.0], [100.0, 1_000.0]],
                [[2.0, 20.0], [200.0, 2_000.0]],
            ]
        ),
        scenario_metadata=_metadata(2),
        position_ids=("P1", "P2"),
        risk_factor_names=("RF1", "RF2"),
    )

    assert cube.scenario_count == 2
    assert cube.position_count == 2
    assert cube.risk_factor_count == 2
    assert cube.total_scenario_pnl().tolist() == pytest.approx([1_111.0, 2_222.0])
    assert cube.pnl_for_positions(("P1",)).tolist() == pytest.approx([11.0, 22.0])
    assert cube.pnl_for_risk_factors(("RF2",)).tolist() == pytest.approx([1_010.0, 2_020.0])

    with pytest.raises(ValueError, match="scenario_metadata"):
        ScenarioCube(
            values=np.ones((2, 1, 1)),
            scenario_metadata=_metadata(1),
            position_ids=("P1",),
            risk_factor_names=("RF1",),
        )
    with pytest.raises(KeyError, match="Unknown risk_factor_names"):
        cube.pnl_for_risk_factors(("MISSING",))


def test_desk_run_validates_position_desk_alignment() -> None:
    context = CalculationContext(
        policy=get_policy(RegulatoryRegime.FED_NPR_2_0),
        as_of_date=AS_OF,
        desk="Rates",
    )
    position = Position(
        position_id="P1",
        desk="Rates",
        instrument_id="Bond1",
        fair_value=10.0,
        currency="USD",
        risk_factor_names=("RF",),
    )
    risk_factor = RiskFactorDefinition(
        name="RF",
        risk_class=RiskClass.GIRR,
        liquidity_horizon=LiquidityHorizon.LH10,
    )

    run = DeskRun(context=context, positions=(position,), risk_factors=(risk_factor,))
    assert run.context == context

    other_position = Position(
        position_id="P2",
        desk="Credit",
        instrument_id="Bond2",
        fair_value=20.0,
        currency="USD",
        risk_factor_names=("RF",),
    )
    with pytest.raises(ValueError, match=r"context\.desk"):
        DeskRun(
            context=context,
            positions=(position, other_position),
            risk_factors=(risk_factor,),
        )


def test_capital_run_result_freezes_desk_results() -> None:
    desk_result = DeskCapitalResult(
        desk="Rates",
        imcc=1.0,
        ses=2.0,
        models_based_capital=3.0,
        pla_ks_statistic=0.0,
        backtesting_apl_exceptions=0,
        backtesting_hpl_exceptions=0,
    )
    result = CapitalRunResult(
        as_of_date=AS_OF,
        regime=RegulatoryRegime.FED_NPR_2_0,
        desk_results={"Rates": desk_result},
        total_market_risk_capital=3.0,
    )

    assert result.desk_results["Rates"] == desk_result
    assert isinstance(result.desk_results, MappingProxyType)
