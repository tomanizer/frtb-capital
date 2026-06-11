from __future__ import annotations

import importlib.util
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import NoReturn, cast

import frtb_common.arrow_conversion as arrow_conversion_module
import numpy as np
import pyarrow as pa
import pytest
from frtb_common import AdapterDiagnostic, NormalizedArrowTable, source_content_hash

from frtb_rrao import (
    RraoCalculationContext,
    RraoCapitalLine,
    RraoClassification,
    RraoEvidenceType,
    RraoInputError,
    RraoInvestmentFundDescriptor,
    RraoInvestmentFundExposureType,
    RraoInvestmentFundMethod,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    calculate_rrao_capital,
    calculate_rrao_capital_from_batch,
    input_hash_for_positions,
    input_hash_for_rrao_batch,
    serialize_rrao_result,
    validate_rrao_result_reconciliation,
)
from frtb_rrao.arrow_batch import (
    RRAO_ARROW_COLUMN_SPECS,
    build_rrao_batch_from_arrow,
    normalize_rrao_arrow_table,
)
from frtb_rrao.batch import build_rrao_batch_from_columns, build_rrao_batch_from_positions
from frtb_rrao.batch_registry import RRAO_BATCH_SPEC, rrao_position_column_kwargs

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "rrao_v1"


def test_rrao_position_batch_from_rows_matches_row_input_hash() -> None:
    loader = _load_fixture_module()
    positions = loader.load_fixture_positions()

    batch = build_rrao_batch_from_positions(positions)

    assert batch.row_count == len(positions)
    assert len(batch.input_hash) == 64
    assert input_hash_for_rrao_batch(batch) == batch.input_hash
    assert batch.input_hash == input_hash_for_positions(positions)
    assert not batch.position_ids.flags.writeable
    assert not batch.gross_effective_notionals.flags.writeable


def test_rrao_batch_registry_projects_positions_into_column_builder() -> None:
    positions = (_investment_fund_position(),)
    registry_batch = build_rrao_batch_from_columns(**rrao_position_column_kwargs(positions))
    position_batch = build_rrao_batch_from_positions(positions)
    arrow_column_names = {spec.name for spec in RRAO_ARROW_COLUMN_SPECS}

    assert registry_batch.input_hash == position_batch.input_hash
    assert RRAO_BATCH_SPEC.name == "rrao_position"
    assert set(RRAO_BATCH_SPEC.arrow_column_to_argument) <= arrow_column_names
    assert RRAO_BATCH_SPEC.arrow_column_to_argument["position_id"] == "position_ids"
    assert "lineage_present" in RRAO_BATCH_SPEC.builder_arguments


def test_rrao_row_entrypoint_returns_batch_kernel_result() -> None:
    loader = _load_fixture_module()
    positions = loader.load_fixture_positions()
    context = loader.load_fixture_context()

    row_result = calculate_rrao_capital(positions, context=context)
    batch = build_rrao_batch_from_positions(positions)
    batch_result = calculate_rrao_capital_from_batch(batch, context=context).result

    assert serialize_rrao_result(row_result) == serialize_rrao_result(batch_result)


def test_rrao_position_batch_preserves_distinct_lineage_source_row_hash() -> None:
    position = _investment_fund_position()
    lineage = cast(RraoSourceLineage, position.lineage)
    position = replace(
        position,
        lineage=replace(lineage, source_row_id="lineage-row-999"),
    )

    batch = build_rrao_batch_from_positions((position,))

    assert batch.source_row_ids.tolist() == ["fund-row-001"]
    assert batch.lineage_source_row_ids.tolist() == ["lineage-row-999"]
    assert batch.input_hash == input_hash_for_positions((position,))


def test_rrao_arrow_batch_batch_matches_v1_row_capital() -> None:
    loader = _load_fixture_module()
    positions = loader.load_fixture_positions()
    context = loader.load_fixture_context()
    row_result = calculate_rrao_capital(positions, context=context)
    source_hash = source_content_hash("synthetic rrao source")
    handoff = normalize_rrao_arrow_table(_arrow_table(positions), source_hash=source_hash)

    batch = build_rrao_batch_from_arrow(handoff)
    calculation = calculate_rrao_capital_from_batch(batch, context=context)

    validate_rrao_result_reconciliation(calculation.result)
    assert batch.source_hash == source_hash
    assert batch.handoff_hash is not None
    assert calculation.result.profile_hash == row_result.profile_hash
    assert calculation.result.total_rrao == pytest.approx(row_result.total_rrao)
    assert _line_outputs(calculation.result.lines) == _line_outputs(row_result.lines)
    assert _line_outputs(calculation.result.excluded_lines) == _line_outputs(
        row_result.excluded_lines
    )
    assert _subtotals(calculation.result.subtotals) == _subtotals(row_result.subtotals)
    assert (
        serialize_rrao_result(calculation.result)["citations"]
        == serialize_rrao_result(row_result)["citations"]
    )


def test_rrao_arrow_batch_uses_zero_copy_float64_columns_when_possible() -> None:
    loader = _load_fixture_module()
    positions = loader.load_fixture_positions()
    handoff = normalize_rrao_arrow_table(_arrow_table(positions))

    batch = build_rrao_batch_from_arrow(handoff)

    gross_notional_view = (
        handoff.accepted.column("gross_effective_notional").chunk(0).to_numpy(zero_copy_only=True)
    )
    assert np.shares_memory(batch.gross_effective_notionals, gross_notional_view)
    np.testing.assert_allclose(
        batch.gross_effective_notionals,
        [position.gross_effective_notional for position in positions],
    )


def test_rrao_handoff_wraps_arrow_object_conversion_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handoff = normalize_rrao_arrow_table(_arrow_table((_investment_fund_position(),)))

    def fail_arrow_object_array(_column: pa.ChunkedArray) -> NoReturn:
        raise pa.ArrowInvalid("forced conversion failure")

    monkeypatch.setattr(arrow_conversion_module, "arrow_object_array", fail_arrow_object_array)

    with pytest.raises(RraoInputError, match=r"forced conversion failure .*position_id") as exc:
        build_rrao_batch_from_arrow(handoff)

    assert exc.value.field == "position_id"
    assert isinstance(exc.value.__cause__, pa.ArrowInvalid)


def test_rrao_handoff_reader_reports_package_errors_for_required_columns() -> None:
    missing_position = NormalizedArrowTable(accepted=pa.table({}))

    with pytest.raises(RraoInputError, match=r"position_id") as missing_exc:
        build_rrao_batch_from_arrow(missing_position)

    assert missing_exc.value.field == "position_id"

    missing_notional = NormalizedArrowTable(
        accepted=_arrow_table((_investment_fund_position(),)).drop(["gross_effective_notional"])
    )

    with pytest.raises(RraoInputError, match=r"gross_effective_notional") as notional_exc:
        build_rrao_batch_from_arrow(missing_notional)

    assert notional_exc.value.field == "gross_effective_notional"

    null_notional_table = _arrow_table((_investment_fund_position(),))
    null_notional_table = null_notional_table.set_column(
        null_notional_table.column_names.index("gross_effective_notional"),
        "gross_effective_notional",
        pa.array([None], type=pa.float64()),
    )
    null_notional = NormalizedArrowTable(accepted=null_notional_table)

    with pytest.raises(RraoInputError, match=r"gross_effective_notional") as null_exc:
        build_rrao_batch_from_arrow(null_notional)

    assert null_exc.value.field == "gross_effective_notional"


def test_rrao_handoff_reader_wraps_optional_float_cast_errors() -> None:
    table = _arrow_table((_investment_fund_position(),))
    table = table.set_column(
        table.column_names.index("investment_fund_gross_effective_notional"),
        "investment_fund_gross_effective_notional",
        pa.array(["bad"], type=pa.utf8()),
    )

    with pytest.raises(
        RraoInputError,
        match=r"investment_fund_gross_effective_notional",
    ) as exc:
        build_rrao_batch_from_arrow(NormalizedArrowTable(accepted=table))

    assert exc.value.field == "investment_fund_gross_effective_notional"


def test_rrao_handoff_reader_wraps_optional_float_fill_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _minimal_column_payload(row_count=2)
    table = _minimal_arrow_table(payload).append_column(
        "investment_fund_gross_effective_notional",
        pa.array([1.0, None], type=pa.float64()),
    )

    def fail_fill_null(*_args: object, **_kwargs: object) -> NoReturn:
        raise pa.ArrowInvalid("forced fill failure")

    monkeypatch.setattr(arrow_conversion_module.pc, "fill_null", fail_fill_null)

    with pytest.raises(
        RraoInputError,
        match=r"investment_fund_gross_effective_notional",
    ) as exc:
        build_rrao_batch_from_arrow(NormalizedArrowTable(accepted=table))

    assert exc.value.field == "investment_fund_gross_effective_notional"


def test_rrao_handoff_reader_wraps_optional_bool_fill_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _minimal_column_payload(row_count=1)
    table = _minimal_arrow_table(payload).append_column(
        "is_ctp_hedge",
        pa.array([True], type=pa.bool_()),
    )

    def fail_fill_null(*_args: object, **_kwargs: object) -> NoReturn:
        raise pa.ArrowInvalid("forced fill failure")

    monkeypatch.setattr(arrow_conversion_module.pc, "fill_null", fail_fill_null)

    with pytest.raises(RraoInputError, match=r"is_ctp_hedge") as exc:
        build_rrao_batch_from_arrow(normalize_rrao_arrow_table(table))

    assert exc.value.field == "is_ctp_hedge"


def test_rrao_arrow_batch_handles_chunked_dictionary_text_columns() -> None:
    payload = _minimal_column_payload(row_count=4)
    plain_table = pa.table(
        {
            "position_id": payload["position_ids"],
            "source_row_id": payload["source_row_ids"],
            "desk_id": payload["desk_ids"],
            "legal_entity": payload["legal_entities"],
            "gross_effective_notional": payload["gross_effective_notionals"],
            "currency": payload["currencies"],
            "evidence_type": payload["evidence_types"],
            "evidence_label": payload["evidence_labels"],
            "classification_hint": payload["classification_hints"],
            "lineage_source_system": payload["lineage_source_systems"],
            "lineage_source_file": payload["lineage_source_files"],
        }
    )
    table = pa.concat_tables(
        [
            _dictionary_encoded_text_table(plain_table.slice(0, 2)),
            _dictionary_encoded_text_table(plain_table.slice(2, 2)),
        ]
    )
    column_batch = build_rrao_batch_from_columns(**payload)

    arrow_batch = build_rrao_batch_from_arrow(normalize_rrao_arrow_table(table))

    assert table.column("evidence_type").num_chunks == 2
    assert pa.types.is_dictionary(table.column("evidence_type").type)
    assert arrow_batch.input_hash == column_batch.input_hash
    np.testing.assert_array_equal(
        arrow_batch.position_ids,
        payload["position_ids"],
    )
    np.testing.assert_array_equal(
        arrow_batch.evidence_types,
        payload["evidence_types"],
    )


def test_rrao_arrow_batch_batch_matches_investment_fund_row_capital() -> None:
    position = _investment_fund_position()
    context = _sample_context()
    row_result = calculate_rrao_capital((position,), context=context)

    batch = build_rrao_batch_from_arrow(normalize_rrao_arrow_table(_arrow_table((position,))))
    calculation = calculate_rrao_capital_from_batch(batch, context=context)

    assert _line_outputs(calculation.result.lines) == _line_outputs(row_result.lines)
    assert calculation.result.total_rrao == pytest.approx(row_result.total_rrao)


def test_rrao_arrow_batch_defaults_nullable_fund_mandate_flag_to_true() -> None:
    position = _investment_fund_position()
    table = _arrow_table((position,))
    column_index = table.column_names.index("investment_fund_mandate_allows_rrao_exposures")
    table = table.set_column(
        column_index,
        "investment_fund_mandate_allows_rrao_exposures",
        pa.array([None], type=pa.bool_()),
    )

    batch = build_rrao_batch_from_arrow(normalize_rrao_arrow_table(table))
    calculation = calculate_rrao_capital_from_batch(batch, context=_sample_context())

    assert batch.investment_fund_mandate_allows_rrao_exposures.tolist() == [True]
    assert calculation.result.total_rrao > 0.0


def test_rrao_arrow_batch_preserves_bool_strings_for_batch_parser() -> None:
    payload = _minimal_column_payload(row_count=1)
    table = pa.table(
        {
            "position_id": payload["position_ids"],
            "source_row_id": payload["source_row_ids"],
            "desk_id": payload["desk_ids"],
            "legal_entity": payload["legal_entities"],
            "gross_effective_notional": payload["gross_effective_notionals"],
            "currency": payload["currencies"],
            "evidence_type": payload["evidence_types"],
            "evidence_label": payload["evidence_labels"],
            "lineage_source_system": payload["lineage_source_systems"],
            "lineage_source_file": payload["lineage_source_files"],
            "is_ctp_hedge": ["false"],
            "is_investment_fund_exposure": ["false"],
        }
    )

    batch = build_rrao_batch_from_arrow(normalize_rrao_arrow_table(table))

    assert batch.is_ctp_hedges.tolist() == [False]
    assert batch.is_investment_fund_exposures.tolist() == [False]


def test_rrao_column_batch_accepts_numpy_scalar_ints_and_bools() -> None:
    batch = build_rrao_batch_from_columns(
        **(
            _minimal_column_payload(row_count=1)
            | {
                "underlying_counts": [np.int64(3)],
                "is_ctp_hedges": [np.bool_(True)],
                "is_investment_fund_exposures": [np.bool_(False)],
            }
        )
    )

    assert batch.underlying_counts.tolist() == [3]
    assert batch.is_ctp_hedges.tolist() == [True]
    assert batch.is_investment_fund_exposures.tolist() == [False]


def test_rrao_column_batch_high_volume_path_avoids_row_dataclasses() -> None:
    row_count = 1_000
    batch = build_rrao_batch_from_columns(**_minimal_column_payload(row_count=row_count))

    calculation = calculate_rrao_capital_from_batch(batch, context=_sample_context())

    assert batch.row_count == row_count
    assert not any(isinstance(value, RraoPosition) for value in batch.__dict__.values())
    assert len(calculation.result.lines) == row_count
    assert calculation.result.excluded_lines == ()


def test_rrao_batch_decision_lookup_uses_profile_masks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import frtb_rrao.batch as batch_module

    batch = build_rrao_batch_from_columns(**_minimal_column_payload(row_count=250))
    calls: list[object] = []
    original_evidence_rules = batch_module.evidence_rules_for_profile

    def counting_evidence_rules(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        return original_evidence_rules(*args, **kwargs)

    monkeypatch.setattr(batch_module, "evidence_rules_for_profile", counting_evidence_rules)

    calculation = calculate_rrao_capital_from_batch(batch, context=_sample_context())

    assert len(calls) == 1
    assert len(calculation.result.lines) == 250


def test_rrao_column_batch_copy_false_does_not_freeze_caller_numpy_arrays() -> None:
    gross_notionals = np.array([100_000.0, 200_000.0], dtype=np.float64)
    is_ctp_hedges = np.array([False, True], dtype=np.bool_)
    columns = _minimal_column_payload(row_count=2) | {
        "gross_effective_notionals": gross_notionals,
        "is_ctp_hedges": is_ctp_hedges,
    }

    batch = build_rrao_batch_from_columns(**columns, copy_arrays=False)

    assert gross_notionals.flags.writeable
    assert is_ctp_hedges.flags.writeable
    assert not batch.gross_effective_notionals.flags.writeable
    assert not batch.is_ctp_hedges.flags.writeable
    assert np.shares_memory(batch.gross_effective_notionals, gross_notionals)
    assert np.shares_memory(batch.is_ctp_hedges, is_ctp_hedges)


def test_rrao_handoff_preserves_diagnostics_for_rejected_rows() -> None:
    rejected = pa.table({"position_id": ["bad-row"], "reason": ["invalid evidence"]})
    diagnostic = AdapterDiagnostic(
        code="rrao.invalid_evidence",
        message="unsupported evidence type",
        row_id="bad-row",
        column_name="evidence_type",
    )
    handoff = normalize_rrao_arrow_table(
        _arrow_table((_investment_fund_position(),)),
        diagnostics=(diagnostic,),
        rejected=rejected,
    )

    batch = build_rrao_batch_from_arrow(handoff)

    assert batch.diagnostics == (diagnostic.as_dict(),)


def test_rrao_handoff_rejects_opaque_nested_payload_without_row_fallback() -> None:
    table = _arrow_table((_investment_fund_position(),)).append_column(
        "unsupported_nested_payload",
        pa.array(['{"investment_fund_descriptor": {"fund_id": "fund-001"}}']),
    )
    handoff = normalize_rrao_arrow_table(table)

    with pytest.raises(RraoInputError, match="unsupported nested payload"):
        build_rrao_batch_from_arrow(handoff)


def test_rrao_column_batch_rejects_partial_investment_fund_linkage() -> None:
    columns = _minimal_column_payload(row_count=1) | {
        "evidence_types": ["INVESTMENT_FUND_EXPOSURE"],
        "classification_hints": ["OTHER_RESIDUAL_RISK"],
        "is_investment_fund_exposures": [True],
    }

    with pytest.raises(RraoInputError, match="investment fund descriptor is required"):
        build_rrao_batch_from_columns(**columns)


def test_rrao_handoff_builds_from_required_columns_only() -> None:
    payload = _minimal_column_payload(row_count=2)
    table = pa.table(
        {
            "position_id": payload["position_ids"],
            "source_row_id": payload["source_row_ids"],
            "desk_id": payload["desk_ids"],
            "legal_entity": payload["legal_entities"],
            "gross_effective_notional": payload["gross_effective_notionals"],
            "currency": payload["currencies"],
            "evidence_type": payload["evidence_types"],
            "evidence_label": payload["evidence_labels"],
            "lineage_source_system": payload["lineage_source_systems"],
            "lineage_source_file": payload["lineage_source_files"],
        }
    )

    batch = build_rrao_batch_from_arrow(normalize_rrao_arrow_table(table))

    assert batch.row_count == 2
    assert batch.citations == ((), ())


def test_rrao_batch_rejects_wrong_handoff_type() -> None:
    with pytest.raises(RraoInputError, match="handoff must be NormalizedArrowTable"):
        build_rrao_batch_from_arrow(object())  # type: ignore[arg-type]


def test_rrao_batch_rejects_empty_columns() -> None:
    with pytest.raises(RraoInputError, match="requires at least one position"):
        build_rrao_batch_from_columns(**_minimal_column_payload(row_count=0))


def test_rrao_batch_rejects_duplicate_position_ids() -> None:
    columns = _minimal_column_payload(row_count=2) | {"position_ids": ["dup", "dup"]}

    with pytest.raises(RraoInputError, match="duplicate position id"):
        build_rrao_batch_from_columns(**columns)


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"classification_hints": ["UNSUPPORTED"]}, "unsupported classification path"),
        ({"lineage_present": [False]}, "source lineage is required"),
        ({"lineage_source_systems": [" "]}, "non-empty text is required"),
        (
            {
                "evidence_types": ["SUPERVISOR_DIRECTIVE"],
                "classification_hints": ["SUPERVISOR_DIRECTED"],
            },
            "supervisor_directive_id",
        ),
        ({"classification_hints": ["EXCLUDED"]}, "excluded classification requires"),
        ({"exclusion_reasons": ["LISTED"]}, "explicit exclusion evidence type"),
        (
            {
                "evidence_types": ["EXPLICIT_EXCLUSION"],
                "classification_hints": [None],
            },
            "explicit exclusion evidence requires",
        ),
        (
            {
                "evidence_types": ["EXPLICIT_EXCLUSION"],
                "classification_hints": ["EXCLUDED"],
                "exclusion_reasons": ["EXACT_THIRD_PARTY_BACK_TO_BACK"],
                "exclusion_evidence_ids": ["match-001"],
            },
            "exact back-to-back exclusion requires match evidence",
        ),
        (
            {
                "back_to_back_match_group_ids": ["match-001"],
                "back_to_back_matched_position_ids": ["other-position"],
            },
            "only valid for exact back-to-back exclusions",
        ),
        ({"underlying_counts": [True]}, "underlying count must be an integer"),
        ({"underlying_counts": [-1]}, "underlying count must be non-negative"),
        ({"is_ctp_hedges": ["maybe"]}, "boolean field contains unsupported value"),
        ({"citations": [[" "]]}, "non-empty text is required"),
    ],
)
def test_rrao_column_batch_validation_failures(
    overrides: dict[str, object],
    match: str,
) -> None:
    columns = _minimal_column_payload(row_count=1) | overrides

    with pytest.raises(RraoInputError, match=match):
        build_rrao_batch_from_columns(**columns)


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"is_investment_fund_exposures": [False]}, "investment fund exposure flag"),
        ({"evidence_types": ["GAP_RISK"]}, "investment-fund evidence type"),
        (
            {"investment_fund_section_205_methods": ["HYPOTHETICAL_PORTFOLIO"]},
            "__.205\\(e\\)\\(3\\)\\(iii\\)",
        ),
        ({"investment_fund_included_exposure_types": [None]}, "invalid investment fund"),
        ({"investment_fund_look_through_availables": [True]}, "non-look-through"),
        ({"investment_fund_mandate_allows_rrao_exposures": [False]}, "mandate evidence"),
        ({"investment_fund_gross_effective_notionals": [None]}, "fund gross effective notional"),
        ({"investment_fund_gross_effective_notionals": [0.0]}, "fund gross effective notional"),
        ({"investment_fund_included_exposure_ratios": [0.0]}, "included exposure ratio"),
        ({"gross_effective_notionals": [1_000_000.0]}, "investment-fund included portion"),
    ],
)
def test_rrao_investment_fund_batch_validation_failures(
    overrides: dict[str, object],
    match: str,
) -> None:
    columns = _investment_fund_column_payload() | overrides

    with pytest.raises(RraoInputError, match=match):
        build_rrao_batch_from_columns(**columns)


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        (
            {"back_to_back_matched_position_ids": ["b2b-a", "b2b-a"]},
            "opposite transaction",
        ),
        (
            {"back_to_back_matched_position_ids": ["missing", "b2b-a"]},
            "matched position is missing",
        ),
        (
            {"back_to_back_matched_position_ids": ["b2b-b", "missing"]},
            "matched position is missing",
        ),
        (
            {"back_to_back_matched_position_ids": ["b2b-b", "other"]},
            "matched position is missing",
        ),
        (
            {"exclusion_evidence_ids": ["match-001", "match-002"]},
            "share the same exclusion evidence",
        ),
        ({"currencies": ["USD", "EUR"]}, "matching currency"),
        ({"gross_effective_notionals": [1_000_000.0, 1_000_001.0]}, "matching gross"),
    ],
)
def test_rrao_back_to_back_batch_validation_failures(
    overrides: dict[str, object],
    match: str,
) -> None:
    columns = _back_to_back_column_payload() | overrides

    with pytest.raises(RraoInputError, match=match):
        build_rrao_batch_from_columns(**columns)


def test_rrao_batch_rejects_conflicting_classification_hint_at_calculation() -> None:
    columns = _minimal_column_payload(row_count=1) | {"classification_hints": ["EXOTIC"]}
    batch = build_rrao_batch_from_columns(**columns)

    with pytest.raises(RraoInputError, match="classification hint conflicts"):
        calculate_rrao_capital_from_batch(batch, context=_sample_context())


def test_rrao_batch_calculates_basel_profile_without_us_warning() -> None:
    position = RraoPosition(
        position_id="basel-exotic-001",
        source_row_id="row-001",
        desk_id="desk-exotics",
        legal_entity="LE-001",
        gross_effective_notional=1_000_000.0,
        currency="USD",
        evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
        evidence_label="longevity derivative",
        lineage=RraoSourceLineage("test", "rrao.csv", "row-001"),
        classification_hint=RraoClassification.EXOTIC,
    )
    batch = build_rrao_batch_from_positions((position,))
    context = RraoCalculationContext(
        run_id="basel-rrao",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile=RraoRegulatoryProfile.BASEL_MAR23,
    )

    calculation = calculate_rrao_capital_from_batch(batch, context=context)

    assert calculation.result.warnings == ()


def test_rrao_batch_rejects_invalid_context_type() -> None:
    batch = build_rrao_batch_from_columns(**_minimal_column_payload(row_count=1))

    with pytest.raises(RraoInputError, match="calculation context"):
        calculate_rrao_capital_from_batch(batch, context=object())  # type: ignore[arg-type]


def _load_fixture_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rrao_v1_loader", FIXTURE_DIR / "loader.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sample_context() -> RraoCalculationContext:
    return RraoCalculationContext(
        run_id="rrao-batch-test",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile=RraoRegulatoryProfile.US_NPR_2_0,
    )


def _investment_fund_position() -> RraoPosition:
    return RraoPosition(
        position_id="fund-pos-001",
        source_row_id="fund-row-001",
        desk_id="equity-funds",
        legal_entity="LE-002",
        gross_effective_notional=2_500_000.0,
        currency="USD",
        evidence_type=RraoEvidenceType.INVESTMENT_FUND_EXPOSURE,
        evidence_label="investment fund mandate permits residual-risk exposure types",
        lineage=RraoSourceLineage(
            source_system="synthetic-risk",
            source_file="investment-funds.csv",
            source_row_id="fund-row-001",
            source_column_map=(
                ("FundID", "investment_fund_descriptor.fund_id"),
                ("IncludedGrossNotional", "gross_effective_notional"),
            ),
        ),
        classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
        is_investment_fund_exposure=True,
        investment_fund_descriptor=RraoInvestmentFundDescriptor(
            fund_id="fund-001",
            section_205_method=RraoInvestmentFundMethod.BACKSTOP_FUND_METHOD,
            included_exposure_type=RraoInvestmentFundExposureType.OTHER_RESIDUAL_RISK,
            mandate_evidence_id="mandate-permits-rrao-001",
            section_205_evidence_id="backstop-method-001",
            fund_gross_effective_notional=10_000_000.0,
            included_exposure_ratio=0.25,
        ),
        citations=("us_npr_211_a_3", "us_npr_205_e_3_iii"),
    )


def _minimal_column_payload(*, row_count: int) -> dict[str, object]:
    return {
        "position_ids": [f"rrao-{index:06d}" for index in range(row_count)],
        "source_row_ids": [f"row-{index:06d}" for index in range(row_count)],
        "desk_ids": ["desk-structured"] * row_count,
        "legal_entities": ["LE-001"] * row_count,
        "gross_effective_notionals": [100_000.0 + index for index in range(row_count)],
        "currencies": ["USD"] * row_count,
        "evidence_types": ["GAP_RISK"] * row_count,
        "evidence_labels": ["gap risk"] * row_count,
        "classification_hints": ["OTHER_RESIDUAL_RISK"] * row_count,
        "lineage_source_systems": ["unit-test"] * row_count,
        "lineage_source_files": ["synthetic-rrao.csv"] * row_count,
    }


def _minimal_arrow_table(payload: dict[str, object]) -> pa.Table:
    return pa.table(
        {
            "position_id": payload["position_ids"],
            "source_row_id": payload["source_row_ids"],
            "desk_id": payload["desk_ids"],
            "legal_entity": payload["legal_entities"],
            "gross_effective_notional": payload["gross_effective_notionals"],
            "currency": payload["currencies"],
            "evidence_type": payload["evidence_types"],
            "evidence_label": payload["evidence_labels"],
            "lineage_source_system": payload["lineage_source_systems"],
            "lineage_source_file": payload["lineage_source_files"],
        }
    )


def _investment_fund_column_payload() -> dict[str, object]:
    return _minimal_column_payload(row_count=1) | {
        "gross_effective_notionals": [2_500_000.0],
        "evidence_types": ["INVESTMENT_FUND_EXPOSURE"],
        "classification_hints": ["OTHER_RESIDUAL_RISK"],
        "is_investment_fund_exposures": [True],
        "investment_fund_ids": ["fund-001"],
        "investment_fund_section_205_methods": ["BACKSTOP_FUND_METHOD"],
        "investment_fund_included_exposure_types": ["OTHER_RESIDUAL_RISK"],
        "investment_fund_mandate_evidence_ids": ["mandate-permits-rrao-001"],
        "investment_fund_section_205_evidence_ids": ["backstop-method-001"],
        "investment_fund_gross_effective_notionals": [10_000_000.0],
        "investment_fund_included_exposure_ratios": [0.25],
        "investment_fund_look_through_availables": [False],
        "investment_fund_mandate_allows_rrao_exposures": [True],
    }


def _back_to_back_column_payload() -> dict[str, object]:
    return _minimal_column_payload(row_count=2) | {
        "position_ids": ["b2b-a", "b2b-b"],
        "gross_effective_notionals": [1_000_000.0, 1_000_000.0],
        "evidence_types": ["EXPLICIT_EXCLUSION", "EXPLICIT_EXCLUSION"],
        "classification_hints": ["EXCLUDED", "EXCLUDED"],
        "exclusion_reasons": [
            "EXACT_THIRD_PARTY_BACK_TO_BACK",
            "EXACT_THIRD_PARTY_BACK_TO_BACK",
        ],
        "exclusion_evidence_ids": ["match-001", "match-001"],
        "back_to_back_match_group_ids": ["match-001", "match-001"],
        "back_to_back_matched_position_ids": ["b2b-b", "b2b-a"],
    }


def _arrow_table(positions: tuple[RraoPosition, ...]) -> pa.Table:
    return pa.table(
        {
            "position_id": [position.position_id for position in positions],
            "source_row_id": [position.source_row_id for position in positions],
            "desk_id": [position.desk_id for position in positions],
            "legal_entity": [position.legal_entity for position in positions],
            "gross_effective_notional": [
                position.gross_effective_notional for position in positions
            ],
            "currency": [position.currency for position in positions],
            "evidence_type": [position.evidence_type.value for position in positions],
            "evidence_label": [position.evidence_label for position in positions],
            "classification_hint": [
                None if position.classification_hint is None else position.classification_hint.value
                for position in positions
            ],
            "exclusion_reason": [
                None if position.exclusion_reason is None else position.exclusion_reason.value
                for position in positions
            ],
            "exclusion_evidence_id": [position.exclusion_evidence_id for position in positions],
            "back_to_back_match_group_id": [
                None
                if position.back_to_back_match is None
                else position.back_to_back_match.match_group_id
                for position in positions
            ],
            "back_to_back_matched_position_id": [
                None
                if position.back_to_back_match is None
                else position.back_to_back_match.matched_position_id
                for position in positions
            ],
            "supervisor_directive_id": [position.supervisor_directive_id for position in positions],
            "underlying_count": [position.underlying_count for position in positions],
            "is_path_dependent": [position.is_path_dependent for position in positions],
            "has_maturity": [position.has_maturity for position in positions],
            "has_strike_or_barrier": [position.has_strike_or_barrier for position in positions],
            "has_multiple_strikes_or_barriers": [
                position.has_multiple_strikes_or_barriers for position in positions
            ],
            "is_ctp_hedge": [position.is_ctp_hedge for position in positions],
            "is_investment_fund_exposure": [
                position.is_investment_fund_exposure for position in positions
            ],
            "investment_fund_id": [
                None
                if position.investment_fund_descriptor is None
                else position.investment_fund_descriptor.fund_id
                for position in positions
            ],
            "investment_fund_section_205_method": [
                None
                if position.investment_fund_descriptor is None
                else position.investment_fund_descriptor.section_205_method.value
                for position in positions
            ],
            "investment_fund_included_exposure_type": [
                None
                if position.investment_fund_descriptor is None
                else position.investment_fund_descriptor.included_exposure_type.value
                for position in positions
            ],
            "investment_fund_mandate_evidence_id": [
                None
                if position.investment_fund_descriptor is None
                else position.investment_fund_descriptor.mandate_evidence_id
                for position in positions
            ],
            "investment_fund_section_205_evidence_id": [
                None
                if position.investment_fund_descriptor is None
                else position.investment_fund_descriptor.section_205_evidence_id
                for position in positions
            ],
            "investment_fund_gross_effective_notional": [
                None
                if position.investment_fund_descriptor is None
                else position.investment_fund_descriptor.fund_gross_effective_notional
                for position in positions
            ],
            "investment_fund_included_exposure_ratio": [
                None
                if position.investment_fund_descriptor is None
                else position.investment_fund_descriptor.included_exposure_ratio
                for position in positions
            ],
            "investment_fund_look_through_available": [
                None
                if position.investment_fund_descriptor is None
                else position.investment_fund_descriptor.look_through_available
                for position in positions
            ],
            "investment_fund_mandate_allows_rrao_exposures": [
                None
                if position.investment_fund_descriptor is None
                else position.investment_fund_descriptor.mandate_allows_rrao_exposures
                for position in positions
            ],
            "notional_source": [position.notional_source for position in positions],
            "lineage_source_system": [
                "" if position.lineage is None else position.lineage.source_system
                for position in positions
            ],
            "lineage_source_file": [
                "" if position.lineage is None else position.lineage.source_file
                for position in positions
            ],
            "lineage_source_row_id": [
                "" if position.lineage is None else position.lineage.source_row_id
                for position in positions
            ],
            "citations": [",".join(position.citations) for position in positions],
        }
    )


def _dictionary_encoded_text_table(table: pa.Table) -> pa.Table:
    columns: list[pa.ChunkedArray] = []
    for column_name in table.column_names:
        column = table.column(column_name)
        if pa.types.is_string(column.type):
            columns.append(pa.chunked_array([column.combine_chunks().dictionary_encode()]))
            continue
        columns.append(column)
    return pa.table(columns, names=table.column_names)


def _line_outputs(records: object) -> dict[str, object]:
    return {
        line.position_id: {
            "classification": line.classification.value,
            "evidence_type": line.evidence_type.value,
            "gross_effective_notional": line.gross_effective_notional,
            "risk_weight": line.risk_weight,
            "add_on": line.add_on,
            "currency": line.currency,
            "is_excluded": line.is_excluded,
            "reason_code": line.reason_code,
            "citations": line.citations,
            "desk_id": line.desk_id,
            "legal_entity": line.legal_entity,
            "source_row_id": line.source_row_id,
            "exclusion_reason": None
            if line.exclusion_reason is None
            else line.exclusion_reason.value,
            "exclusion_evidence_id": line.exclusion_evidence_id,
        }
        for line in cast(tuple[RraoCapitalLine, ...], records)
    }


def _subtotals(records: object) -> list[dict[str, object]]:
    return [
        {
            "subtotal_key": subtotal.subtotal_key,
            "subtotal_type": subtotal.subtotal_type,
            "gross_effective_notional": subtotal.gross_effective_notional,
            "add_on": subtotal.add_on,
            "position_ids": subtotal.position_ids,
        }
        for subtotal in cast(tuple[object, ...], records)
    ]
