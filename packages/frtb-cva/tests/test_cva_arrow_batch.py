from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import NoReturn

import frtb_common.arrow_conversion as arrow_conversion_module
import numpy as np
import pyarrow as pa
import pytest
from frtb_common import AdapterDiagnostic, source_content_hash
from frtb_cva import (
    CvaCapitalResult,
    CvaCounterparty,
    CvaHedge,
    CvaInputError,
    CvaNettingSet,
    SaCvaSensitivity,
    build_cva_counterparty_batch_from_arrow,
    build_cva_counterparty_batch_from_columns,
    build_cva_counterparty_batch_from_counterparties,
    build_cva_hedge_batch_from_arrow,
    build_cva_hedge_batch_from_hedges,
    build_cva_netting_set_batch_from_arrow,
    build_cva_netting_set_batch_from_columns,
    build_cva_netting_set_batch_from_netting_sets,
    build_sa_cva_sensitivity_batch_from_sensitivities,
    calculate_cva_capital,
    calculate_cva_capital_from_arrow,
    calculate_cva_capital_from_batches,
    input_hash,
    input_hash_for_cva_batches,
    normalize_cva_counterparty_arrow_table,
    normalize_cva_hedge_arrow_table,
    normalize_cva_netting_set_arrow_table,
    validate_cva_result_reconciliation,
)
from frtb_cva.arrow_batch import (
    CVA_COUNTERPARTY_ENTITY_SPEC,
    CVA_ENTITY_BATCH_SPECS,
    build_cva_batch_from_arrow,
    build_sa_cva_sensitivity_batch_from_arrow,
    normalize_cva_arrow_table,
    normalize_sa_cva_sensitivity_arrow_table,
)
from frtb_cva.batch import CvaCounterpartyBatch

BA_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ba_cva_reduced_v1"
SA_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sa_cva_girr_delta_v1"


def test_cva_entity_batch_specs_drive_arrow_ingress_contracts() -> None:
    assert set(CVA_ENTITY_BATCH_SPECS) == {
        "counterparty",
        "netting_set",
        "hedge",
        "sa_cva_sensitivity",
    }

    for spec in CVA_ENTITY_BATCH_SPECS.values():
        spec_column_names = {column.name for column in spec.column_specs}
        assert set(spec.column_to_argument) == spec_column_names
        assert set(spec.required_columns).isdisjoint(spec.optional_columns)
        assert spec.required_columns
        assert "lineage_source_row_id" in spec.optional_columns

    handoff = normalize_cva_arrow_table(
        pa.table(
            {
                "counterparty_id": ["cp-1"],
                "desk_id": ["desk-cva"],
                "legal_entity": ["LE-001"],
                "sector": ["SOVEREIGN"],
                "credit_quality": ["INVESTMENT_GRADE"],
                "region": ["EMEA"],
                "source_row_id": ["cp-row-1"],
                "lineage_source_system": ["synthetic"],
                "lineage_source_file": ["counterparties.csv"],
            }
        ),
        CVA_COUNTERPARTY_ENTITY_SPEC,
    )
    batch = build_cva_batch_from_arrow(handoff, CVA_COUNTERPARTY_ENTITY_SPEC)

    assert isinstance(batch, CvaCounterpartyBatch)
    assert batch.counterparty_ids.tolist() == ["cp-1"]
    assert batch.handoff_hash is not None


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


def test_ba_cva_arrow_batch_matches_row_fixture_case() -> None:
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

    counterparty_batch = build_cva_counterparty_batch_from_arrow(counterparty_handoff)
    netting_set_batch = build_cva_netting_set_batch_from_arrow(netting_set_handoff)
    batch_calculation = calculate_cva_capital_from_batches(
        context,
        counterparty_batch,
        netting_set_batch,
    )
    arrow_calculation = calculate_cva_capital_from_arrow(
        context,
        counterparty_handoff,
        netting_set_handoff,
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
    _assert_results_match(
        arrow_calculation.result,
        row_result,
        case_id=case_id,
        check_input_hash=False,
    )
    assert len(arrow_calculation.result.input_hash) == 64
    int(arrow_calculation.result.input_hash, 16)
    assert arrow_calculation.result.input_hash_algorithm == "arrow-columnar-v2"
    assert arrow_calculation.result.input_hash != row_result.input_hash
    assert (
        calculate_cva_capital_from_arrow(
            context,
            counterparty_handoff,
            netting_set_handoff,
        ).result.input_hash
        == arrow_calculation.result.input_hash
    )


def test_cva_handoff_wraps_arrow_object_conversion_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = pa.table(
        {
            "counterparty_id": ["cp-0001"],
            "desk_id": ["desk-cva"],
            "legal_entity": ["LE-001"],
            "sector": ["SOVEREIGN"],
            "credit_quality": ["INVESTMENT_GRADE"],
            "region": ["EMEA"],
            "source_row_id": ["cp-row-0001"],
            "lineage_source_system": ["synthetic"],
            "lineage_source_file": ["counterparties.csv"],
        }
    )
    handoff = normalize_cva_counterparty_arrow_table(table)

    def fail_arrow_object_array(_column: pa.ChunkedArray) -> NoReturn:
        raise pa.ArrowInvalid("forced conversion failure")

    monkeypatch.setattr(arrow_conversion_module, "arrow_object_array", fail_arrow_object_array)

    with pytest.raises(
        CvaInputError,
        match=r"forced conversion failure .*counterparty_id",
    ) as exc:
        build_cva_counterparty_batch_from_arrow(handoff)

    assert exc.value.field == "counterparty_id"
    assert isinstance(exc.value.__cause__, pa.ArrowInvalid)


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


def test_sa_cva_arrow_batch_matches_row_fixture_case() -> None:
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
    hedge_handoff = normalize_cva_hedge_arrow_table(
        _hedge_table(hedges),
        source_hash=source_content_hash("synthetic cva hedge source"),
    )

    sensitivity_batch = build_sa_cva_sensitivity_batch_from_arrow(sensitivity_handoff)
    hedge_batch = build_cva_hedge_batch_from_hedges(hedges)
    batch_calculation = calculate_cva_capital_from_batches(
        context,
        sensitivities=sensitivity_batch,
        hedges=hedge_batch,
    )
    arrow_calculation = calculate_cva_capital_from_arrow(
        context,
        hedges=hedge_handoff,
        sensitivities=sensitivity_handoff,
    )

    _assert_results_match(
        batch_calculation.result,
        row_result,
        case_id=case_id,
        check_input_hash=False,
    )
    _assert_results_match(
        arrow_calculation.result,
        row_result,
        case_id=case_id,
        check_input_hash=False,
    )
    assert len(arrow_calculation.result.input_hash) == 64
    int(arrow_calculation.result.input_hash, 16)
    assert arrow_calculation.result.input_hash_algorithm == "arrow-columnar-v2"
    assert arrow_calculation.result.input_hash != row_result.input_hash
    assert (
        calculate_cva_capital_from_arrow(
            context,
            hedges=hedge_handoff,
            sensitivities=sensitivity_handoff,
        ).result.input_hash
        == arrow_calculation.result.input_hash
    )
    assert sensitivity_batch.handoff_hash is not None


def test_cva_arrow_batch_reuses_float64_buffers_where_safe() -> None:
    netting_set_table = pa.table(
        {
            "netting_set_id": ["ns-1"],
            "counterparty_id": ["cp-1"],
            "ead": [100_000.0],
            "effective_maturity": [1.5],
            "discount_factor": [0.98],
            "currency": ["USD"],
            "sign_convention": ["non_negative"],
            "uses_imm_ead": [False],
            "source_row_id": ["ns-row-1"],
            "lineage_source_system": ["synthetic"],
            "lineage_source_file": ["netting-sets.csv"],
        }
    )
    netting_set_batch = build_cva_netting_set_batch_from_arrow(
        normalize_cva_netting_set_arrow_table(netting_set_table)
    )
    maturity_buffer = (
        netting_set_table.column("effective_maturity").chunk(0).to_numpy(zero_copy_only=True)
    )
    discount_buffer = (
        netting_set_table.column("discount_factor").chunk(0).to_numpy(zero_copy_only=True)
    )

    assert np.shares_memory(netting_set_batch.effective_maturities, maturity_buffer)
    assert np.shares_memory(netting_set_batch.discount_factors, discount_buffer)
    assert not netting_set_batch.effective_maturities.flags.writeable
    assert not netting_set_batch.discount_factors.flags.writeable

    hedge_table = pa.table(
        {
            "hedge_id": ["h-1"],
            "source_row_id": ["h-row-1"],
            "counterparty_id": ["cp-1"],
            "hedge_type": ["SINGLE_NAME_CDS"],
            "notional": [50_000.0],
            "remaining_maturity": [2.0],
            "discount_factor": [0.99],
            "reference_sector": ["SOVEREIGN"],
            "reference_credit_quality": ["INVESTMENT_GRADE"],
            "reference_region": ["EMEA"],
            "reference_relation": ["DIRECT"],
            "eligibility": ["ELIGIBLE"],
            "is_internal": [False],
            "eligibility_evidence_id": ["ev-1"],
            "lineage_source_system": ["synthetic"],
            "lineage_source_file": ["hedges.csv"],
        }
    )
    hedge_batch = build_cva_hedge_batch_from_arrow(normalize_cva_hedge_arrow_table(hedge_table))
    notional_buffer = hedge_table.column("notional").chunk(0).to_numpy(zero_copy_only=True)

    assert np.shares_memory(hedge_batch.notionals, notional_buffer)
    assert not hedge_batch.notionals.flags.writeable

    sensitivity_table = pa.table(
        {
            "sensitivity_id": ["s-1"],
            "risk_class": ["FX"],
            "risk_measure": ["DELTA"],
            "sensitivity_tag": ["CVA"],
            "bucket_id": ["USD"],
            "risk_factor_key": ["EURUSD"],
            "amount": [1_000.0],
            "amount_currency": ["USD"],
            "sign_convention": ["positive_loss"],
            "source_row_id": ["s-row-1"],
            "lineage_source_system": ["synthetic"],
            "lineage_source_file": ["sensitivities.csv"],
        }
    )
    sensitivity_batch = build_sa_cva_sensitivity_batch_from_arrow(
        normalize_sa_cva_sensitivity_arrow_table(sensitivity_table)
    )
    amount_buffer = sensitivity_table.column("amount").chunk(0).to_numpy(zero_copy_only=True)

    assert np.shares_memory(sensitivity_batch.amounts, amount_buffer)
    assert not sensitivity_batch.amounts.flags.writeable


def test_cva_arrow_batch_decodes_chunked_dictionary_text_columns() -> None:
    sector = pa.chunked_array(
        [
            pa.DictionaryArray.from_arrays(
                pa.array([0], type=pa.int8()),
                pa.array(["SOVEREIGN"]),
            ),
            pa.DictionaryArray.from_arrays(
                pa.array([0], type=pa.int8()),
                pa.array(["FINANCIALS"]),
            ),
        ]
    )
    credit_quality = pa.chunked_array(
        [
            pa.DictionaryArray.from_arrays(
                pa.array([0], type=pa.int8()),
                pa.array(["INVESTMENT_GRADE"]),
            ),
            pa.DictionaryArray.from_arrays(
                pa.array([0], type=pa.int8()),
                pa.array(["HIGH_YIELD"]),
            ),
        ]
    )
    table = pa.table(
        {
            "counterparty_id": ["cp-1", "cp-2"],
            "desk_id": ["desk-cva", "desk-cva"],
            "legal_entity": ["LE-001", "LE-001"],
            "sector": sector,
            "credit_quality": credit_quality,
            "region": ["EMEA", "AMER"],
            "source_row_id": ["cp-row-1", "cp-row-2"],
            "lineage_source_system": ["synthetic", "synthetic"],
            "lineage_source_file": ["counterparties.csv", "counterparties.csv"],
        }
    )

    batch = build_cva_counterparty_batch_from_arrow(normalize_cva_counterparty_arrow_table(table))

    assert batch.sectors.tolist() == ["SOVEREIGN", "FINANCIALS"]
    assert batch.credit_qualities.tolist() == ["INVESTMENT_GRADE", "HIGH_YIELD"]


def test_cva_column_builders_do_not_freeze_input_arrays_when_copy_false() -> None:
    netting_set_ids = np.array(["ns-1"], dtype=object)
    counterparty_ids = np.array(["cp-1"], dtype=object)
    eads = np.array([100_000.0], dtype=np.float64)
    effective_maturities = np.array([1.5], dtype=np.float64)
    discount_factors = np.array([1.0], dtype=np.float64)
    uses_imm_eads = np.array([False], dtype=np.bool_)

    batch = build_cva_netting_set_batch_from_columns(
        netting_set_ids=netting_set_ids,
        counterparty_ids=counterparty_ids,
        eads=eads,
        effective_maturities=effective_maturities,
        discount_factors=discount_factors,
        currencies=np.array(["USD"], dtype=object),
        sign_conventions=np.array(["non_negative"], dtype=object),
        uses_imm_eads=uses_imm_eads,
        source_row_ids=np.array(["ns-row-1"], dtype=object),
        lineage_source_systems=np.array(["synthetic"], dtype=object),
        lineage_source_files=np.array(["netting-sets.csv"], dtype=object),
        copy_arrays=False,
    )

    assert netting_set_ids.flags.writeable
    assert counterparty_ids.flags.writeable
    assert eads.flags.writeable
    assert effective_maturities.flags.writeable
    assert discount_factors.flags.writeable
    assert uses_imm_eads.flags.writeable
    assert not batch.netting_set_ids.flags.writeable
    assert not batch.effective_maturities.flags.writeable
    assert np.shares_memory(batch.effective_maturities, effective_maturities)


def test_cva_column_builders_reject_multidimensional_numpy_float_inputs() -> None:
    with pytest.raises(CvaInputError, match="ead must be 1-dimensional"):
        build_cva_netting_set_batch_from_columns(
            netting_set_ids=np.array(["ns-1"], dtype=object),
            counterparty_ids=np.array(["cp-1"], dtype=object),
            eads=np.array([[100_000.0]], dtype=np.float64),
            effective_maturities=np.array([1.5], dtype=np.float64),
            discount_factors=np.array([1.0], dtype=np.float64),
            currencies=np.array(["USD"], dtype=object),
            sign_conventions=np.array(["non_negative"], dtype=object),
            uses_imm_eads=np.array([False], dtype=np.bool_),
            source_row_ids=np.array(["ns-row-1"], dtype=object),
            lineage_source_systems=np.array(["synthetic"], dtype=object),
            lineage_source_files=np.array(["netting-sets.csv"], dtype=object),
            copy_arrays=False,
        )


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
    batch = build_cva_counterparty_batch_from_arrow(handoff)

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
    with pytest.raises(CvaInputError, match="handoff must be NormalizedArrowTable"):
        build_cva_counterparty_batch_from_arrow(object())  # type: ignore[arg-type]


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


def _hedge_table(hedges: tuple[CvaHedge, ...]) -> pa.Table:
    return pa.table(
        {
            "hedge_id": [item.hedge_id for item in hedges],
            "source_row_id": [item.source_row_id for item in hedges],
            "counterparty_id": [item.counterparty_id for item in hedges],
            "hedge_type": [
                None if item.hedge_type is None else item.hedge_type.value for item in hedges
            ],
            "notional": [item.notional for item in hedges],
            "remaining_maturity": [item.remaining_maturity for item in hedges],
            "discount_factor": [item.discount_factor for item in hedges],
            "reference_sector": [item.reference_sector.value for item in hedges],
            "reference_credit_quality": [item.reference_credit_quality.value for item in hedges],
            "reference_region": [item.reference_region for item in hedges],
            "reference_relation": [item.reference_relation.value for item in hedges],
            "eligibility": [item.eligibility.value for item in hedges],
            "is_internal": [item.is_internal for item in hedges],
            "discount_factor_explicit": [item.discount_factor_explicit for item in hedges],
            "internal_desk_counterparty_id": [
                item.internal_desk_counterparty_id for item in hedges
            ],
            "sa_cva_risk_class": [
                None if item.sa_cva_risk_class is None else item.sa_cva_risk_class.value
                for item in hedges
            ],
            "sa_cva_hedge_purpose": [
                None if item.sa_cva_hedge_purpose is None else item.sa_cva_hedge_purpose.value
                for item in hedges
            ],
            "sa_cva_hedge_instrument_type": [
                None
                if item.sa_cva_hedge_instrument_type is None
                else item.sa_cva_hedge_instrument_type.value
                for item in hedges
            ],
            "whole_transaction_evidence_id": [
                item.whole_transaction_evidence_id for item in hedges
            ],
            "market_risk_ima_eligible": [item.market_risk_ima_eligible for item in hedges],
            "market_risk_ima_exclusion_reason": [
                item.market_risk_ima_exclusion_reason for item in hedges
            ],
            "eligibility_evidence_id": [item.eligibility_evidence_id for item in hedges],
            "rejection_reason": [item.rejection_reason for item in hedges],
            "lineage_source_system": [
                "" if item.lineage is None else item.lineage.source_system for item in hedges
            ],
            "lineage_source_file": [
                "" if item.lineage is None else item.lineage.source_file for item in hedges
            ],
            "lineage_source_row_id": [
                item.source_row_id if item.lineage is None else item.lineage.source_row_id
                for item in hedges
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
