"""Tests for vector-friendly market-risk data contracts."""

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from types import MappingProxyType

import numpy as np
import pytest

from frtb_ima.data_contracts import (
    CapitalRunResult,
    DeskRun,
    Position,
    RFETEvidence,
    RFETQualitativeCriterionEvidence,
    RiskFactorBucket,
    RiskFactorDefinition,
    ScenarioCube,
)
from frtb_ima.data_models import (
    DeskCapitalResult,
    LiquidityHorizon,
    RealPriceObservation,
    RiskClass,
    ScenarioPnL,
)
from frtb_ima.input_manifest import CapitalRunInputManifest, InputArtifactLineage
from frtb_ima.regimes import CalculationContext, RegulatoryRegime, get_policy
from frtb_ima.scenario import ScenarioSetType, make_scenario_metadata

AS_OF = date(2025, 6, 30)


def _input_manifest(as_of_date: date = AS_OF) -> CapitalRunInputManifest:
    return CapitalRunInputManifest(
        run_id="run-1",
        as_of_date=as_of_date,
        artifacts=(
            InputArtifactLineage(
                artifact_name="scenario_cube.npz",
                artifact_type="npz",
                schema_version="capital_run_fixture_v1",
                source_system="synthetic_fixture",
                source_version="1",
                extraction_timestamp=datetime(2025, 6, 30, tzinfo=UTC),
                as_of_date=as_of_date,
                record_count=10,
                vector_count=1,
                checksum="a" * 64,
                sign_convention="positive_loss",
            ),
        ),
    )


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
    with pytest.raises(ValueError, match="liquidity_horizon"):
        RiskFactorDefinition(
            name="USD_SWAP_5Y",
            risk_class=RiskClass.GIRR,
            liquidity_horizon=LiquidityHorizon.LH20,
            bucket=bucket,
        )
    with pytest.raises(ValueError, match="bucket_id"):
        RiskFactorBucket(
            bucket_id="",
            risk_class=RiskClass.GIRR,
            liquidity_horizon=LiquidityHorizon.LH10,
        )
    with pytest.raises(ValueError, match="risk factor name"):
        RiskFactorDefinition(
            name="",
            risk_class=RiskClass.GIRR,
            liquidity_horizon=LiquidityHorizon.LH10,
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
    with pytest.raises(ValueError, match="desk"):
        Position(
            position_id="P2",
            desk="",
            instrument_id="Bond2",
            fair_value=10.0,
            currency="USD",
            risk_factor_names=("RF",),
        )
    with pytest.raises(ValueError, match="fair_value"):
        Position(
            position_id="P2",
            desk="Rates",
            instrument_id="Bond2",
            fair_value=float("nan"),
            currency="USD",
            risk_factor_names=("RF",),
        )
    with pytest.raises(ValueError, match="notional"):
        Position(
            position_id="P2",
            desk="Rates",
            instrument_id="Bond2",
            fair_value=10.0,
            currency="USD",
            risk_factor_names=("RF",),
            notional=float("inf"),
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
    with pytest.raises(ValueError, match="risk_factor_name"):
        RFETEvidence(
            risk_factor_name="",
            as_of_date=AS_OF,
            observations=(),
            qualitative_pass=True,
        )
    with pytest.raises(TypeError, match="as_of_date"):
        RFETEvidence(
            risk_factor_name="RF",
            as_of_date="2025-06-30",  # type: ignore[arg-type]
            observations=(),
            qualitative_pass=True,
        )


def test_rfet_qualitative_criterion_evidence_is_serialisable_and_frozen() -> None:
    criterion = RFETQualitativeCriterionEvidence(
        criterion_id="MAR31.15",
        criterion_description="Independent price-source governance",
        passed=True,
        rationale="Market-data control approved the criterion.",
        assessed_by="market-risk-control",
        metadata={"control_id": "RFET-QA-2026"},
    )

    assert isinstance(criterion.metadata, MappingProxyType)
    assert criterion.as_dict() == {
        "criterion_id": "MAR31.15",
        "criterion_description": "Independent price-source governance",
        "passed": True,
        "rationale": "Market-data control approved the criterion.",
        "assessed_by": "market-risk-control",
        "metadata": {"control_id": "RFET-QA-2026"},
    }
    with pytest.raises(ValueError, match="criterion_id"):
        RFETQualitativeCriterionEvidence(
            criterion_id="",
            criterion_description="Independent price-source governance",
            passed=True,
            rationale="Approved.",
        )
    with pytest.raises(TypeError, match="passed"):
        RFETQualitativeCriterionEvidence(
            criterion_id="MAR31.15",
            criterion_description="Independent price-source governance",
            passed="yes",  # type: ignore[arg-type]
            rationale="Approved.",
        )


def test_real_price_observation_validates_identity_dates_and_flags() -> None:
    observation = RealPriceObservation(
        "RF",
        AS_OF,
        source="VENDOR_A",
        vendor_id="VENDOR_A",
        vendor_audit_evidence_id="vendor-audit-2026",
    )

    assert observation.vendor_id == "VENDOR_A"
    with pytest.raises(ValueError, match="risk_factor_name"):
        RealPriceObservation("", AS_OF)
    with pytest.raises(TypeError, match="observation_date"):
        RealPriceObservation("RF", datetime(2025, 6, 30, 12, 0))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="observation_timestamp"):
        RealPriceObservation("RF", AS_OF, observation_timestamp=AS_OF)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="verifiable"):
        RealPriceObservation("RF", AS_OF, verifiable="yes")  # type: ignore[arg-type]


def test_scenario_cube_validates_shape_and_axis_labels() -> None:
    values = np.array(
        [
            [[1.0, 10.0], [100.0, 1_000.0]],
            [[2.0, 20.0], [200.0, 2_000.0]],
        ]
    )
    cube = ScenarioCube(
        values=values,
        scenario_metadata=_metadata(2),
        position_ids=("P1", "P2"),
        risk_factor_names=("RF1", "RF2"),
    )

    values[0, 0, 0] = 999.0
    assert not cube.values.flags.writeable
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
    with pytest.raises(ValueError, match="shape"):
        ScenarioCube(
            values=np.ones((2, 1)),
            scenario_metadata=_metadata(2),
            position_ids=("P1",),
            risk_factor_names=("RF1",),
        )
    with pytest.raises(ValueError, match="finite"):
        ScenarioCube(
            values=np.array([[[float("nan")]]]),
            scenario_metadata=_metadata(1),
            position_ids=("P1",),
            risk_factor_names=("RF1",),
        )
    with pytest.raises(ValueError, match="position_ids"):
        ScenarioCube(
            values=np.ones((1, 1, 1)),
            scenario_metadata=_metadata(1),
            position_ids=("",),
            risk_factor_names=("RF1",),
        )
    with pytest.raises(KeyError, match="Unknown position_ids"):
        cube.pnl_for_positions(("MISSING",))
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
    with pytest.raises(ValueError, match="positions"):
        DeskRun(context=context, positions=(), risk_factors=(risk_factor,))
    with pytest.raises(ValueError, match="risk_factors"):
        DeskRun(context=context, positions=(position,), risk_factors=())


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
    assert result.as_dict()["total_market_risk_capital"] == pytest.approx(3.0)

    production_result = CapitalRunResult(
        as_of_date=AS_OF,
        regime=RegulatoryRegime.FED_NPR_2_0,
        desk_results={"Rates": desk_result},
        input_manifest=_input_manifest(),
        require_input_manifest=True,
    )
    assert production_result.as_dict()["input_manifest"]["artifact_count"] == 1

    with pytest.raises(TypeError, match="as_of_date"):
        CapitalRunResult(
            as_of_date="2025-06-30",  # type: ignore[arg-type]
            regime=RegulatoryRegime.FED_NPR_2_0,
            desk_results={"Rates": desk_result},
        )
    with pytest.raises(ValueError, match="total_market_risk_capital"):
        CapitalRunResult(
            as_of_date=AS_OF,
            regime=RegulatoryRegime.FED_NPR_2_0,
            desk_results={"Rates": desk_result},
            total_market_risk_capital=float("nan"),
        )
    with pytest.raises(ValueError, match="input_manifest is required"):
        CapitalRunResult(
            as_of_date=AS_OF,
            regime=RegulatoryRegime.FED_NPR_2_0,
            desk_results={"Rates": desk_result},
            require_input_manifest=True,
        )
    with pytest.raises(ValueError, match="input_manifest as_of_date"):
        CapitalRunResult(
            as_of_date=AS_OF,
            regime=RegulatoryRegime.FED_NPR_2_0,
            desk_results={"Rates": desk_result},
            input_manifest=_input_manifest(date(2025, 7, 1)),
        )


def test_scenario_pnl_and_desk_capital_result_are_immutable() -> None:
    scenario_pnl = ScenarioPnL(desk="Rates")
    scenario_pnl_with_vector = scenario_pnl.add_vector(
        RiskClass.GIRR,
        LiquidityHorizon.LH10,
        [1.0, 2.0, 3.0],
    )
    assert RiskClass.GIRR not in scenario_pnl.vectors
    assert scenario_pnl_with_vector.vectors[RiskClass.GIRR][LiquidityHorizon.LH10] == (
        1.0,
        2.0,
        3.0,
    )

    with pytest.raises(FrozenInstanceError):
        scenario_pnl.desk = "Credit"  # type: ignore[misc]
    horizon_vectors = scenario_pnl_with_vector.vectors[RiskClass.GIRR]
    with pytest.raises(TypeError):
        horizon_vectors[LiquidityHorizon.LH10] = (4.0,)  # type: ignore[index]
    with pytest.raises(TypeError):
        vector = horizon_vectors[LiquidityHorizon.LH10]
        vector[0] = 4.0  # type: ignore[index]

    desk_result = DeskCapitalResult(
        desk="Rates",
        imcc=1.0,
        ses=2.0,
        models_based_capital=3.0,
        pla_ks_statistic=0.0,
        backtesting_apl_exceptions=0,
        backtesting_hpl_exceptions=0,
    )

    with pytest.raises(FrozenInstanceError):
        desk_result.notes = "changed"  # type: ignore[misc]
