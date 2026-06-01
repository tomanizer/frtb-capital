from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pyarrow as pa
import pytest
from frtb_common import AdapterDiagnostic, source_content_hash
from frtb_cva import (
    CvaCapitalResult,
    CvaCounterparty,
    CvaInputError,
    CvaNettingSet,
    SaCvaSensitivity,
    build_cva_counterparty_batch_from_columns,
    build_cva_counterparty_batch_from_counterparties,
    build_cva_counterparty_batch_from_handoff,
    build_cva_hedge_batch_from_hedges,
    build_cva_netting_set_batch_from_columns,
    build_cva_netting_set_batch_from_handoff,
    build_cva_netting_set_batch_from_netting_sets,
    build_sa_cva_sensitivity_batch_from_sensitivities,
    calculate_cva_capital,
    calculate_cva_capital_from_batches,
    input_hash,
    input_hash_for_cva_batches,
    normalize_cva_counterparty_arrow_table,
    normalize_cva_netting_set_arrow_table,
    validate_cva_result_reconciliation,
)
from frtb_cva.arrow_handoff import (
    build_sa_cva_sensitivity_batch_from_handoff,
    normalize_sa_cva_sensitivity_arrow_table,
)

BA_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ba_cva_reduced_v1"
SA_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sa_cva_girr_delta_v1"


def test_ba_cva_batch_matches_row_fixture_cases() -> None:
    loader = _load_fixture_module(BA_FIXTURE_DIR / "loader.py")
    context = loader.load_fixture_context()

    for case_id, counterparties, netting_sets in loader.load_fixture_cases():
        row_result = calculate_cva_capital(context, counterparties, netting_sets)
        counterparty_batch = build_cva_counterparty_batch_from_counterparties(counterparties)
        netting_set_batch = build_cva_netting_set_batch_from_netting_sets(
            netting_sets,
            counterparties=counterparties,
        )

        batch_calculation = calculate_cva_capital_from_batches(
            context,
            counterparty_batch,
            netting_set_batch,
        )

        _assert_results_match(batch_calculation.result, row_result, case_id=case_id)
        assert batch_calculation.accepted_counterparty_dataclasses_materialized == 0
        assert batch_calculation.accepted_netting_set_dataclasses_materialized == 0
        assert input_hash_for_cva_batches(context, counterparty_batch, netting_set_batch) == (
            input_hash(context, counterparties, netting_sets)
        )


def test_ba_cva_arrow_handoff_matches_row_fixture_case() -> None:
    loader = _load_fixture_module(BA_FIXTURE_DIR / "loader.py")
    context = loader.load_fixture_context()
    case_id, counterparties, netting_sets = loader.load_fixture_cases()[0]
    row_result = calculate_cva_capital(context, counterparties, netting_sets)
    source_hash = source_content_hash("synthetic cva ba source")
    counterparty_handoff = normalize_cva_counterparty_arrow_table(
        _counterparty_table(counterparties),
        source_hash=source_hash,
    )
    netting_set_handoff = normalize_cva_netting_set_arrow_table(
        _netting_set_table(netting_sets),
        source_hash=source_hash,
    )

    counterparty_batch = build_cva_counterparty_batch_from_handoff(counterparty_handoff)
    netting_set_batch = build_cva_netting_set_batch_from_handoff(netting_set_handoff)
    batch_calculation = calculate_cva_capital_from_batches(
        context,
        counterparty_batch,
        netting_set_batch,
    )

    assert counterparty_batch.source_hash == source_hash
    assert counterparty_batch.handoff_hash is not None
    assert netting_set_batch.handoff_hash is not None
    _assert_results_match(
        batch_calculation.result,
        row_result,
        case_id=case_id,
        check_input_hash=False,
    )


def test_sa_cva_batch_matches_row_fixture_cases() -> None:
    loader = _load_fixture_module(SA_FIXTURE_DIR / "loader.py")
    context = loader.load_fixture_context()

    for case_id, sensitivities, hedges in loader.load_fixture_cases():
        row_result = calculate_cva_capital(
            context,
            (),
            (),
            sensitivities=sensitivities,
            hedges=hedges,
        )
        sensitivity_batch = build_sa_cva_sensitivity_batch_from_sensitivities(sensitivities)
        hedge_batch = build_cva_hedge_batch_from_hedges(hedges)

        batch_calculation = calculate_cva_capital_from_batches(
            context,
            sensitivities=sensitivity_batch,
            hedges=hedge_batch,
        )

        _assert_results_match(batch_calculation.result, row_result, case_id=case_id)
        assert batch_calculation.accepted_sensitivity_dataclasses_materialized == 0
        assert batch_calculation.accepted_hedge_dataclasses_materialized == 0


def test_sa_cva_arrow_handoff_matches_row_fixture_case() -> None:
    loader = _load_fixture_module(SA_FIXTURE_DIR / "loader.py")
    context = loader.load_fixture_context()
    case_id, sensitivities, hedges = loader.load_fixture_cases()[0]
    row_result = calculate_cva_capital(
        context,
        (),
        (),
        sensitivities=sensitivities,
        hedges=hedges,
    )
    sensitivity_handoff = normalize_sa_cva_sensitivity_arrow_table(
        _sensitivity_table(sensitivities),
        source_hash=source_content_hash("synthetic cva sa source"),
    )

    sensitivity_batch = build_sa_cva_sensitivity_batch_from_handoff(sensitivity_handoff)
    hedge_batch = build_cva_hedge_batch_from_hedges(hedges)
    batch_calculation = calculate_cva_capital_from_batches(
        context,
        sensitivities=sensitivity_batch,
        hedges=hedge_batch,
    )

    _assert_results_match(
        batch_calculation.result,
        row_result,
        case_id=case_id,
        check_input_hash=False,
    )
    assert sensitivity_batch.handoff_hash is not None


def test_ba_cva_column_batch_high_volume_path_reports_zero_row_dataclasses(
    reduced_context,
) -> None:
    row_count = 1_000
    counterparty_batch = build_cva_counterparty_batch_from_columns(
        counterparty_ids=[f"cp-{index:04d}" for index in range(row_count)],
        desk_ids=["desk-cva"] * row_count,
        legal_entities=["LE-001"] * row_count,
        sectors=["SOVEREIGN"] * row_count,
        credit_qualities=["INVESTMENT_GRADE"] * row_count,
        regions=["EMEA"] * row_count,
        source_row_ids=[f"cp-row-{index:04d}" for index in range(row_count)],
        lineage_source_systems=["synthetic"] * row_count,
        lineage_source_files=["counterparties.csv"] * row_count,
    )
    netting_set_batch = build_cva_netting_set_batch_from_columns(
        netting_set_ids=[f"ns-{index:04d}" for index in range(row_count)],
        counterparty_ids=[f"cp-{index:04d}" for index in range(row_count)],
        eads=[100_000.0 + index for index in range(row_count)],
        effective_maturities=[1.5] * row_count,
        discount_factors=[1.0] * row_count,
        currencies=["USD"] * row_count,
        sign_conventions=["non_negative"] * row_count,
        uses_imm_eads=[False] * row_count,
        source_row_ids=[f"ns-row-{index:04d}" for index in range(row_count)],
        lineage_source_systems=["synthetic"] * row_count,
        lineage_source_files=["netting-sets.csv"] * row_count,
    )

    calculation = calculate_cva_capital_from_batches(
        reduced_context,
        counterparty_batch,
        netting_set_batch,
    )

    assert calculation.result.total_cva_capital > 0.0
    assert len(calculation.result.ba_cva_netting_set_lines) == row_count
    assert calculation.accepted_counterparty_dataclasses_materialized == 0
    assert calculation.accepted_netting_set_dataclasses_materialized == 0
    assert not any(
        isinstance(value, CvaCounterparty) for value in counterparty_batch.__dict__.values()
    )


def test_ba_cva_batch_normalises_signed_absolute_ead(reduced_context) -> None:
    counterparty_batch = build_cva_counterparty_batch_from_columns(
        **_minimal_counterparty_columns(row_count=1)
    )
    netting_set_batch = build_cva_netting_set_batch_from_columns(
        **(
            _minimal_netting_set_columns(row_count=1)
            | {
                "eads": [-100_000.0],
                "sign_conventions": ["signed_absolute"],
            }
        )
    )

    calculation = calculate_cva_capital_from_batches(
        reduced_context,
        counterparty_batch,
        netting_set_batch,
    )

    assert netting_set_batch.eads.tolist() == [100_000.0]
    assert calculation.result.ba_cva_netting_set_lines[0].ead == 100_000.0
    assert calculation.result.total_cva_capital > 0.0


def test_cva_handoff_preserves_rejected_row_diagnostics() -> None:
    loader = _load_fixture_module(BA_FIXTURE_DIR / "loader.py")
    _, counterparties, _ = loader.load_fixture_cases()[0]
    rejected = pa.table({"source_row_id": ["bad-row"], "reason": ["invalid sector"]})
    diagnostic = AdapterDiagnostic(
        code="cva.invalid_sector",
        message="invalid counterparty sector",
        row_id="bad-row",
        column_name="sector",
    )

    handoff = normalize_cva_counterparty_arrow_table(
        _counterparty_table(counterparties),
        diagnostics=(diagnostic,),
        rejected=rejected,
    )
    batch = build_cva_counterparty_batch_from_handoff(handoff)

    assert batch.diagnostics == (diagnostic.as_dict(),)


def test_cva_batch_rejects_duplicate_counterparty_ids() -> None:
    columns = _minimal_counterparty_columns(row_count=2) | {
        "counterparty_ids": ["dup", "dup"],
    }

    with pytest.raises(CvaInputError, match="duplicate counterparty id"):
        build_cva_counterparty_batch_from_columns(**columns)


def test_cva_batch_rejects_unknown_netting_set_counterparty(reduced_context) -> None:
    counterparties = build_cva_counterparty_batch_from_columns(
        **_minimal_counterparty_columns(row_count=1)
    )
    netting_sets = build_cva_netting_set_batch_from_columns(
        **(_minimal_netting_set_columns(row_count=1) | {"counterparty_ids": ["missing"]})
    )

    with pytest.raises(CvaInputError, match="unknown counterparty"):
        calculate_cva_capital_from_batches(reduced_context, counterparties, netting_sets)


def test_cva_handoff_rejects_wrong_type() -> None:
    with pytest.raises(CvaInputError, match="handoff must be NormalizedTabularHandoff"):
        build_cva_counterparty_batch_from_handoff(object())  # type: ignore[arg-type]


def _load_fixture_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_results_match(
    batch_result: CvaCapitalResult,
    row_result: CvaCapitalResult,
    *,
    case_id: str,
    check_input_hash: bool = True,
) -> None:
    validate_cva_result_reconciliation(batch_result)
    if check_input_hash:
        assert batch_result.input_hash == row_result.input_hash, case_id
    assert batch_result.total_cva_capital == pytest.approx(row_result.total_cva_capital), case_id
    assert batch_result.citations == row_result.citations
    assert batch_result.ba_cva_counterparty_capitals == row_result.ba_cva_counterparty_capitals
    assert batch_result.ba_cva_netting_set_lines == row_result.ba_cva_netting_set_lines
    assert batch_result.sa_cva_risk_class_capitals == row_result.sa_cva_risk_class_capitals


def _counterparty_table(counterparties: tuple[CvaCounterparty, ...]) -> pa.Table:
    return pa.table(
        {
            "counterparty_id": [item.counterparty_id for item in counterparties],
            "desk_id": [item.desk_id for item in counterparties],
            "legal_entity": [item.legal_entity for item in counterparties],
            "sector": [item.sector.value for item in counterparties],
            "credit_quality": [item.credit_quality.value for item in counterparties],
            "region": [item.region for item in counterparties],
            "source_row_id": [item.source_row_id for item in counterparties],
            "lineage_source_system": [
                "" if item.lineage is None else item.lineage.source_system
                for item in counterparties
            ],
            "lineage_source_file": [
                "" if item.lineage is None else item.lineage.source_file for item in counterparties
            ],
            "lineage_source_row_id": [
                item.source_row_id if item.lineage is None else item.lineage.source_row_id
                for item in counterparties
            ],
        }
    )


def _netting_set_table(netting_sets: tuple[CvaNettingSet, ...]) -> pa.Table:
    return pa.table(
        {
            "netting_set_id": [item.netting_set_id for item in netting_sets],
            "counterparty_id": [item.counterparty_id for item in netting_sets],
            "ead": [item.ead for item in netting_sets],
            "effective_maturity": [item.effective_maturity for item in netting_sets],
            "discount_factor": [item.discount_factor for item in netting_sets],
            "currency": [item.currency for item in netting_sets],
            "sign_convention": [item.sign_convention for item in netting_sets],
            "uses_imm_ead": [item.uses_imm_ead for item in netting_sets],
            "source_row_id": [item.source_row_id for item in netting_sets],
            "carved_out_to_ba_cva": [item.carved_out_to_ba_cva for item in netting_sets],
            "discount_factor_explicit": [item.discount_factor_explicit for item in netting_sets],
            "lineage_source_system": [
                "" if item.lineage is None else item.lineage.source_system for item in netting_sets
            ],
            "lineage_source_file": [
                "" if item.lineage is None else item.lineage.source_file for item in netting_sets
            ],
            "lineage_source_row_id": [
                item.source_row_id if item.lineage is None else item.lineage.source_row_id
                for item in netting_sets
            ],
        }
    )


def _sensitivity_table(sensitivities: tuple[SaCvaSensitivity, ...]) -> pa.Table:
    return pa.table(
        {
            "sensitivity_id": [item.sensitivity_id for item in sensitivities],
            "risk_class": [item.risk_class.value for item in sensitivities],
            "risk_measure": [item.risk_measure.value for item in sensitivities],
            "sensitivity_tag": [item.sensitivity_tag.value for item in sensitivities],
            "bucket_id": [item.bucket_id for item in sensitivities],
            "risk_factor_key": [item.risk_factor_key for item in sensitivities],
            "amount": [item.amount for item in sensitivities],
            "amount_currency": [item.amount_currency for item in sensitivities],
            "sign_convention": [item.sign_convention for item in sensitivities],
            "source_row_id": [item.source_row_id for item in sensitivities],
            "tenor": [item.tenor for item in sensitivities],
            "volatility_input": [item.volatility_input for item in sensitivities],
            "hedge_id": [item.hedge_id for item in sensitivities],
            "lineage_source_system": [
                "" if item.lineage is None else item.lineage.source_system for item in sensitivities
            ],
            "lineage_source_file": [
                "" if item.lineage is None else item.lineage.source_file for item in sensitivities
            ],
            "lineage_source_row_id": [
                item.source_row_id if item.lineage is None else item.lineage.source_row_id
                for item in sensitivities
            ],
        }
    )


def _minimal_counterparty_columns(*, row_count: int) -> dict[str, object]:
    return {
        "counterparty_ids": [f"cp-{index:04d}" for index in range(row_count)],
        "desk_ids": ["desk-cva"] * row_count,
        "legal_entities": ["LE-001"] * row_count,
        "sectors": ["SOVEREIGN"] * row_count,
        "credit_qualities": ["INVESTMENT_GRADE"] * row_count,
        "regions": ["EMEA"] * row_count,
        "source_row_ids": [f"cp-row-{index:04d}" for index in range(row_count)],
        "lineage_source_systems": ["synthetic"] * row_count,
        "lineage_source_files": ["counterparties.csv"] * row_count,
    }


def _minimal_netting_set_columns(*, row_count: int) -> dict[str, object]:
    return {
        "netting_set_ids": [f"ns-{index:04d}" for index in range(row_count)],
        "counterparty_ids": [f"cp-{index:04d}" for index in range(row_count)],
        "eads": [100_000.0] * row_count,
        "effective_maturities": [1.0] * row_count,
        "discount_factors": [1.0] * row_count,
        "currencies": ["USD"] * row_count,
        "sign_conventions": ["non_negative"] * row_count,
        "uses_imm_eads": [False] * row_count,
        "source_row_ids": [f"ns-row-{index:04d}" for index in range(row_count)],
        "lineage_source_systems": ["synthetic"] * row_count,
        "lineage_source_files": ["netting-sets.csv"] * row_count,
    }
