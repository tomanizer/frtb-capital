from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any, cast

import numpy as np
import pyarrow as pa
import pytest
from frtb_common import UnsupportedRegulatoryFeatureError, source_content_hash
from frtb_drc import (
    BASEL_MAR22_PROFILE_ID,
    EU_CRR3_PROFILE_ID,
    PRA_UK_CRR_PROFILE_ID,
    DrcFairValueCapEvidence,
    DrcFxRate,
    DrcInputError,
    DrcSourceLineage,
    calculate_drc_capital,
    calculate_drc_capital_from_batch,
    fair_value_cap_evidence_by_position,
    input_hash_for_drc_batch,
    input_snapshot_hash,
    risk_weight_evidence_by_position,
    validate_reconciliation,
)
from frtb_drc.arrow_batch import (
    build_drc_ctp_batch_from_arrow,
    build_drc_nonsec_batch_from_arrow,
    build_drc_securitisation_non_ctp_batch_from_arrow,
    normalize_drc_ctp_arrow_table,
    normalize_drc_nonsec_arrow_table,
    normalize_drc_securitisation_non_ctp_arrow_table,
)
from frtb_drc.batch import (
    build_drc_ctp_batch_from_columns,
    build_drc_nonsec_batch_from_columns,
    build_drc_nonsec_batch_from_positions,
    build_drc_securitisation_non_ctp_batch_from_columns,
)
from frtb_drc.data_models import DrcCalculationContext, DrcCapitalResult, DrcPosition
from frtb_drc.demo_fixture import load_drc_nonsec_v2_fixture

from tests.drc_fixture_helpers import (
    drc_fair_value_cap_evidence_from_dict,
    drc_position_from_dict,
    drc_risk_weight_evidence_from_dict,
)


def test_drc_position_batch_from_rows_matches_row_input_hash() -> None:
    fixture = load_drc_nonsec_v2_fixture()

    batch = build_drc_nonsec_batch_from_positions(fixture.positions)

    assert batch.row_count == len(fixture.positions)
    assert len(batch.input_hash) == 64
    assert input_hash_for_drc_batch(batch) == batch.input_hash
    assert batch.input_hash == build_drc_nonsec_batch_from_positions(fixture.positions).input_hash
    assert batch.input_hash != input_snapshot_hash(fixture.positions)
    assert not batch.position_ids.flags.writeable
    assert not batch.notionals.flags.writeable


def test_drc_batch_supports_basel_nonsec_profile() -> None:
    batch = build_drc_nonsec_batch_from_columns(
        position_ids=["basel-long"],
        source_row_ids=["row-basel-long"],
        desk_ids=["desk-a"],
        legal_entities=["bank-na"],
        risk_classes=["NON_SECURITISATION"],
        instrument_types=["BOND"],
        default_directions=["LONG"],
        issuer_ids=["issuer-a"],
        bucket_keys=["SOVEREIGN"],
        seniorities=["SENIOR_DEBT"],
        credit_qualities=["AA"],
        notionals=[100.0],
        market_values=[100.0],
        cumulative_pnls=[0.0],
        maturity_years=[1.0],
        currencies=["USD"],
        lineage_source_systems=["synthetic"],
        lineage_source_files=["basel-batch.csv"],
        citation_ids=[("BASEL_MAR22_12", "BASEL_MAR22_24")],
        profile_id=BASEL_MAR22_PROFILE_ID,
    )
    context = DrcCalculationContext(
        run_id="run-basel-batch",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id=BASEL_MAR22_PROFILE_ID,
    )

    calculation = calculate_drc_capital_from_batch(batch, context=context)

    assert calculation.result.profile_id == BASEL_MAR22_PROFILE_ID
    assert calculation.result.total_drc == pytest.approx(1.5)
    assert "BASEL_MAR22_24" in calculation.result.citations
    validate_reconciliation(calculation.result)


def test_drc_batch_supports_eu_crr3_nonsec_profile() -> None:
    batch = build_drc_nonsec_batch_from_columns(
        position_ids=["eu-long"],
        source_row_ids=["row-eu-long"],
        desk_ids=["desk-a"],
        legal_entities=["bank-eu"],
        risk_classes=["NON_SECURITISATION"],
        instrument_types=["BOND"],
        default_directions=["LONG"],
        issuer_ids=["issuer-a"],
        bucket_keys=["SOVEREIGN"],
        seniorities=["SENIOR_DEBT"],
        credit_qualities=["AA"],
        notionals=[100.0],
        market_values=[100.0],
        cumulative_pnls=[0.0],
        maturity_years=[1.0],
        currencies=["EUR"],
        lineage_source_systems=["synthetic"],
        lineage_source_files=["eu-batch.csv"],
        citation_ids=[("EU_CRR3_ARTICLE_325W", "EU_CRR3_ECAI_CQS_MAPPING")],
        profile_id=EU_CRR3_PROFILE_ID,
    )
    context = DrcCalculationContext(
        run_id="run-eu-batch",
        calculation_date=date(2026, 5, 29),
        base_currency="EUR",
        profile_id=EU_CRR3_PROFILE_ID,
    )

    calculation = calculate_drc_capital_from_batch(batch, context=context)

    assert calculation.result.profile_id == EU_CRR3_PROFILE_ID
    assert calculation.result.total_drc == pytest.approx(1.5)
    assert "EU_CRR3_ARTICLE_325Y_1_2" in calculation.result.citations
    assert "EU_CRR3_ECAI_CQS_MAPPING" in calculation.result.citations
    assert not any(citation.startswith("US_NPR") for citation in calculation.result.citations)
    assert not any(citation.startswith("BASEL_MAR22") for citation in calculation.result.citations)
    validate_reconciliation(calculation.result)


def test_drc_batch_caps_nonsec_explicit_pnl_at_market_value() -> None:
    batch = build_drc_nonsec_batch_from_columns(
        position_ids=["capped-long"],
        source_row_ids=["row-capped-long"],
        desk_ids=["desk-a"],
        legal_entities=["bank-na"],
        risk_classes=["NON_SECURITISATION"],
        instrument_types=["BOND"],
        default_directions=["LONG"],
        issuer_ids=["issuer-a"],
        bucket_keys=["CORPORATE"],
        seniorities=["SENIOR_DEBT"],
        credit_qualities=["INVESTMENT_GRADE"],
        notionals=[100.0],
        market_values=[110.0],
        cumulative_pnls=[50.0],
        maturity_years=[1.0],
        currencies=["USD"],
        lineage_source_systems=["synthetic"],
        lineage_source_files=["nonsec-cap.csv"],
        citation_ids=[("US_NPR_210_SCOPE",)],
    )
    context = DrcCalculationContext(
        run_id="run-nonsec-cap-batch",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id="US_NPR_2_0",
    )

    calculation = calculate_drc_capital_from_batch(batch, context=context)

    assert calculation.gross_jtd[0] == pytest.approx(110.0)
    assert calculation.result.total_drc == pytest.approx(4.51)
    assert "US_NPR_210_A_1_II" in calculation.result.citations
    validate_reconciliation(calculation.result)


def test_drc_arrow_batch_batch_matches_nonsec_v2_row_capital() -> None:
    fixture = load_drc_nonsec_v2_fixture()
    row_result = calculate_drc_capital(fixture.positions, context=fixture.context)
    source_hash = source_content_hash("synthetic drc nonsec source")
    handoff = normalize_drc_nonsec_arrow_table(
        _arrow_table(fixture.positions),
        source_hash=source_hash,
    )

    batch = build_drc_nonsec_batch_from_arrow(handoff)
    calculation = calculate_drc_capital_from_batch(batch, context=fixture.context)

    validate_reconciliation(calculation.result)
    assert batch.source_hash == source_hash
    assert batch.handoff_hash is not None
    assert calculation.result.input_positions == ()
    assert calculation.result.gross_jtds == ()
    assert calculation.result.maturity_scaled_jtds == ()
    assert calculation.result.input_hash == batch.input_hash
    assert calculation.result.profile_hash == row_result.profile_hash
    assert calculation.result.input_count == row_result.input_count
    assert calculation.result.total_drc == pytest.approx(row_result.total_drc)
    assert _net_outputs(calculation.result.net_jtds) == _net_outputs(row_result.net_jtds)
    assert _bucket_outputs(calculation.result.categories[0].bucket_results) == _bucket_outputs(
        row_result.categories[0].bucket_results
    )
    row_gross_by_id = {record.position_id: record.gross_jtd for record in row_result.gross_jtds}
    batch_gross_by_id = {
        position_id: gross
        for position_id, gross in zip(
            batch.position_ids.tolist(), calculation.gross_jtd, strict=True
        )
    }
    assert batch_gross_by_id == pytest.approx(row_gross_by_id)


def test_drc_arrow_batch_batch_matches_securitisation_non_ctp_row_capital() -> None:
    fixture = _load_fixture("drc_sec_nonctp_v1")
    row_result = calculate_drc_capital(fixture["positions"], context=fixture["context"])
    handoff = normalize_drc_securitisation_non_ctp_arrow_table(
        _arrow_table(fixture["positions"]),
        source_hash=source_content_hash("synthetic drc sec non-ctp source"),
    )

    batch = build_drc_securitisation_non_ctp_batch_from_arrow(handoff)
    calculation = calculate_drc_capital_from_batch(batch, context=fixture["context"])

    validate_reconciliation(calculation.result)
    assert calculation.result.input_positions == ()
    assert calculation.result.gross_jtds == ()
    assert calculation.result.maturity_scaled_jtds == ()
    assert calculation.result.input_hash != batch.input_hash
    assert calculation.result.total_drc == pytest.approx(row_result.total_drc)
    assert _net_outputs(calculation.result.net_jtds) == _net_outputs(row_result.net_jtds)
    assert _bucket_outputs(calculation.result.categories[0].bucket_results) == _bucket_outputs(
        row_result.categories[0].bucket_results
    )
    assert "US_NPR_210_C_3_III" in calculation.result.citations


def test_drc_securitisation_batch_short_maturity_is_unscaled() -> None:
    batch = build_drc_securitisation_non_ctp_batch_from_columns(
        position_ids=["short-maturity-sec"],
        source_row_ids=["row-short-maturity-sec"],
        desk_ids=["sec-desk"],
        legal_entities=["bank-na"],
        risk_classes=["SECURITISATION_NON_CTP"],
        instrument_types=["SECURITISATION_TRANCHE"],
        default_directions=["LONG"],
        issuer_ids=["pool-a"],
        tranche_ids=["mezz"],
        index_series_ids=[None],
        bucket_keys=["SEC_CLO_NORTH_AMERICA"],
        notionals=[125.0],
        market_values=[125.0],
        cumulative_pnls=[None],
        maturity_years=[0.5],
        currencies=["USD"],
        lineage_source_systems=["synthetic"],
        lineage_source_files=["sec-batch.csv"],
        citation_ids=[("US_NPR_210_C_1",)],
    )
    context = DrcCalculationContext(
        run_id="run-sec-maturity-batch",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id="US_NPR_2_0",
        securitisation_non_ctp_risk_weights={"short-maturity-sec": 0.2},
    )

    calculation = calculate_drc_capital_from_batch(batch, context=context)

    assert calculation.maturity_weights[0] == pytest.approx(1.0)
    assert calculation.scaled_jtd[0] == pytest.approx(125.0)
    assert calculation.result.total_drc == pytest.approx(25.0)
    validate_reconciliation(calculation.result)


def test_drc_securitisation_batch_zero_net_group_keeps_audit_record() -> None:
    batch = build_drc_securitisation_non_ctp_batch_from_columns(
        position_ids=["zero-long", "zero-short"],
        source_row_ids=["row-zero-long", "row-zero-short"],
        desk_ids=["sec-desk", "sec-desk"],
        legal_entities=["bank-na", "bank-na"],
        risk_classes=["SECURITISATION_NON_CTP", "SECURITISATION_NON_CTP"],
        instrument_types=["SECURITISATION_TRANCHE", "SECURITISATION_TRANCHE"],
        default_directions=["LONG", "SHORT"],
        issuer_ids=["pool-a", "pool-a"],
        tranche_ids=["mezz", "mezz"],
        index_series_ids=[None, None],
        bucket_keys=["SEC_CLO_NORTH_AMERICA", "SEC_CLO_NORTH_AMERICA"],
        notionals=[100.0, 100.0],
        market_values=[100.0, 100.0],
        cumulative_pnls=[None, None],
        maturity_years=[1.0, 1.0],
        currencies=["USD", "USD"],
        lineage_source_systems=["synthetic", "synthetic"],
        lineage_source_files=["sec-batch.csv", "sec-batch.csv"],
        citation_ids=[("US_NPR_210_C_1",), ("US_NPR_210_C_1",)],
    )
    context = DrcCalculationContext(
        run_id="run-sec-zero-batch",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id="US_NPR_2_0",
        securitisation_non_ctp_risk_weights={"zero-long": 0.2, "zero-short": 0.2},
    )

    calculation = calculate_drc_capital_from_batch(batch, context=context)

    assert len(calculation.result.net_jtds) == 1
    assert calculation.result.net_jtds[0].net_amount == 0.0
    assert (
        "fully offset to zero net JTD" in calculation.result.net_jtds[0].branch_metadata[0].reason
    )
    assert calculation.result.total_drc == 0.0
    validate_reconciliation(calculation.result)


def test_drc_arrow_batch_matches_basel_securitisation_non_ctp_row_capital() -> None:
    fixture = _load_fixture("drc_basel_sec_nonctp_v1")
    expected = json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "drc_basel_sec_nonctp_v1"
            / "expected_outputs.json"
        ).read_text(encoding="utf-8")
    )
    row_result = calculate_drc_capital(fixture["positions"], context=fixture["context"])
    handoff = normalize_drc_securitisation_non_ctp_arrow_table(
        _arrow_table(fixture["positions"]),
        source_hash=source_content_hash("synthetic drc basel sec non-ctp source"),
    )

    batch = build_drc_securitisation_non_ctp_batch_from_arrow(handoff)
    calculation = calculate_drc_capital_from_batch(batch, context=fixture["context"])

    validate_reconciliation(calculation.result)
    assert calculation.result.profile_id == BASEL_MAR22_PROFILE_ID
    assert calculation.result.total_drc == pytest.approx(row_result.total_drc)
    assert calculation.result.total_drc == pytest.approx(expected["total_drc"])
    assert _net_outputs(calculation.result.net_jtds) == _net_outputs(row_result.net_jtds)
    assert _bucket_outputs(calculation.result.categories[0].bucket_results) == _bucket_outputs(
        row_result.categories[0].bucket_results
    )
    assert len(calculation.result.risk_weight_evidence) == 4
    assert len(calculation.result.fair_value_cap_evidence) == 1
    assert "BASEL_MAR22_34" in calculation.result.citations
    assert "BASEL_MAR22_35" in calculation.result.citations
    assert not any(citation.startswith("US_NPR") for citation in calculation.result.citations)


def test_drc_securitisation_non_ctp_batch_applies_fair_value_cap_evidence() -> None:
    fixture = _load_fixture("drc_sec_nonctp_v1")
    positions = fixture["positions"]
    capped_position = positions[0]
    cap_evidence = _fair_value_cap_evidence(capped_position, fair_value_cap_amount=50.0)
    context = replace(
        fixture["context"],
        securitisation_non_ctp_fair_value_cap_evidence=fair_value_cap_evidence_by_position(
            (cap_evidence,)
        ),
    )
    row_result = calculate_drc_capital(positions, context=context)
    handoff = normalize_drc_securitisation_non_ctp_arrow_table(_arrow_table(positions))
    batch = build_drc_securitisation_non_ctp_batch_from_arrow(handoff)

    calculation = calculate_drc_capital_from_batch(batch, context=context)

    assert calculation.gross_jtd[0] == pytest.approx(50.0)
    assert calculation.result.total_drc == pytest.approx(row_result.total_drc)
    assert calculation.result.fair_value_cap_evidence == (cap_evidence,)
    assert "BASEL_MAR22_34" in calculation.result.citations
    assert any(branch.branch_type.value == "CAP" for branch in calculation.result.branch_metadata)
    validate_reconciliation(calculation.result)


def test_drc_arrow_batch_batch_matches_ctp_row_capital() -> None:
    fixture = _load_fixture("drc_ctp_v1")
    row_result = calculate_drc_capital(fixture["positions"], context=fixture["context"])
    handoff = normalize_drc_ctp_arrow_table(
        _arrow_table(fixture["positions"]),
        source_hash=source_content_hash("synthetic drc ctp source"),
    )

    batch = build_drc_ctp_batch_from_arrow(handoff)
    calculation = calculate_drc_capital_from_batch(batch, context=fixture["context"])

    validate_reconciliation(calculation.result)
    assert calculation.result.input_positions == ()
    assert calculation.result.gross_jtds == ()
    assert calculation.result.maturity_scaled_jtds == ()
    assert calculation.result.input_hash != batch.input_hash
    assert calculation.result.total_drc == pytest.approx(row_result.total_drc)
    assert _net_outputs(calculation.result.net_jtds) == _net_outputs(row_result.net_jtds)
    assert _bucket_outputs(calculation.result.categories[0].bucket_results) == _bucket_outputs(
        row_result.categories[0].bucket_results
    )
    assert "US_NPR_210_D_3_IV_D" in calculation.result.citations


def test_drc_ctp_batch_short_maturity_is_unscaled() -> None:
    batch = build_drc_ctp_batch_from_columns(
        position_ids=["short-maturity-ctp"],
        source_row_ids=["row-short-maturity-ctp"],
        desk_ids=["ctp-desk"],
        legal_entities=["bank-na"],
        risk_classes=["CORRELATION_TRADING_PORTFOLIO"],
        instrument_types=["INDEX_TRANCHE"],
        default_directions=["LONG"],
        issuer_ids=[None],
        tranche_ids=["mezz"],
        index_series_ids=["CDX.NA.IG.S18"],
        bucket_keys=["CDX_NA_IG"],
        notionals=[100.0],
        market_values=[100.0],
        cumulative_pnls=[None],
        maturity_years=[0.5],
        currencies=["USD"],
        lineage_source_systems=["synthetic"],
        lineage_source_files=["ctp-batch.csv"],
        citation_ids=[("US_NPR_210_D_1",)],
    )
    context = DrcCalculationContext(
        run_id="run-ctp-maturity-batch",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id="US_NPR_2_0",
        ctp_risk_weights={"short-maturity-ctp": 0.2},
    )

    calculation = calculate_drc_capital_from_batch(batch, context=context)

    assert calculation.maturity_weights[0] == pytest.approx(1.0)
    assert calculation.scaled_jtd[0] == pytest.approx(100.0)
    assert calculation.result.total_drc == pytest.approx(20.0)
    validate_reconciliation(calculation.result)


def test_drc_basel_ctp_batch_matches_row_result_for_typed_evidence() -> None:
    fixture = _load_fixture("drc_basel_ctp_v1")
    row_result = calculate_drc_capital(fixture["positions"], context=fixture["context"])
    handoff = normalize_drc_ctp_arrow_table(
        _arrow_table(fixture["positions"]),
        source_hash=source_content_hash("synthetic basel drc ctp source"),
    )

    batch = build_drc_ctp_batch_from_arrow(handoff)
    calculation = calculate_drc_capital_from_batch(batch, context=fixture["context"])

    validate_reconciliation(calculation.result)
    assert calculation.result.total_drc == pytest.approx(row_result.total_drc)
    assert calculation.result.risk_weight_evidence == row_result.risk_weight_evidence
    assert _net_outputs(calculation.result.net_jtds) == _net_outputs(row_result.net_jtds)
    assert _bucket_outputs(calculation.result.categories[0].bucket_results) == _bucket_outputs(
        row_result.categories[0].bucket_results
    )
    assert "BASEL_MAR22_42" in calculation.result.citations
    assert "BASEL_MAR22_45" in calculation.result.citations
    assert not any(citation.startswith("US_NPR") for citation in calculation.result.citations)


@pytest.mark.parametrize(
    ("fixture_name", "normalize", "build_batch", "profile_id", "expected"),
    [
        (
            "drc_sec_nonctp_v1",
            normalize_drc_securitisation_non_ctp_arrow_table,
            build_drc_securitisation_non_ctp_batch_from_arrow,
            EU_CRR3_PROFILE_ID,
            EU_CRR3_PROFILE_ID,
        ),
        (
            "drc_ctp_v1",
            normalize_drc_ctp_arrow_table,
            build_drc_ctp_batch_from_arrow,
            EU_CRR3_PROFILE_ID,
            EU_CRR3_PROFILE_ID,
        ),
        (
            "drc_nonsec_v1",
            normalize_drc_nonsec_arrow_table,
            build_drc_nonsec_batch_from_arrow,
            PRA_UK_CRR_PROFILE_ID,
            PRA_UK_CRR_PROFILE_ID,
        ),
        (
            "drc_sec_nonctp_v1",
            normalize_drc_securitisation_non_ctp_arrow_table,
            build_drc_securitisation_non_ctp_batch_from_arrow,
            PRA_UK_CRR_PROFILE_ID,
            PRA_UK_CRR_PROFILE_ID,
        ),
        (
            "drc_ctp_v1",
            normalize_drc_ctp_arrow_table,
            build_drc_ctp_batch_from_arrow,
            PRA_UK_CRR_PROFILE_ID,
            PRA_UK_CRR_PROFILE_ID,
        ),
    ],
)
def test_arrow_batch_calculation_fails_closed_for_unsupported_profile_paths(
    fixture_name: str,
    normalize: Any,
    build_batch: Any,
    profile_id: str,
    expected: str,
) -> None:
    fixture = _load_fixture(fixture_name)
    handoff = normalize(_arrow_table(fixture["positions"]))
    batch = build_batch(handoff)
    context = replace(
        fixture["context"],
        profile_id=profile_id,
        securitisation_non_ctp_risk_weights={},
        securitisation_non_ctp_risk_weight_evidence={},
        securitisation_non_ctp_fair_value_cap_evidence={},
        securitisation_non_ctp_offset_groups={},
        ctp_risk_weights={},
        ctp_risk_weight_evidence={},
        ctp_offset_groups={},
    )

    with pytest.raises(UnsupportedRegulatoryFeatureError, match=expected):
        calculate_drc_capital_from_batch(batch, context=context)


def test_drc_arrow_batch_uses_zero_copy_float64_columns_when_possible() -> None:
    fixture = load_drc_nonsec_v2_fixture()
    handoff = normalize_drc_nonsec_arrow_table(_arrow_table(fixture.positions))

    batch = build_drc_nonsec_batch_from_arrow(handoff)

    notional_view = handoff.accepted.column("notional").chunk(0).to_numpy(zero_copy_only=True)
    maturity_view = handoff.accepted.column("maturity_years").chunk(0).to_numpy(zero_copy_only=True)
    assert np.shares_memory(batch.notionals, notional_view)
    assert np.shares_memory(batch.maturity_years, maturity_view)
    np.testing.assert_allclose(
        batch.notionals, [position.notional for position in fixture.positions]
    )


def test_drc_arrow_batch_handles_chunked_dictionary_text_columns() -> None:
    fixture = load_drc_nonsec_v2_fixture()
    table = pa.concat_tables(
        [
            _dictionary_encoded_text_table(_arrow_table(fixture.positions[:3])),
            _dictionary_encoded_text_table(_arrow_table(fixture.positions[3:])),
        ]
    )
    row_batch = build_drc_nonsec_batch_from_positions(fixture.positions)

    arrow_batch = build_drc_nonsec_batch_from_arrow(normalize_drc_nonsec_arrow_table(table))

    assert table.column("risk_class").num_chunks == 2
    assert pa.types.is_dictionary(table.column("risk_class").type)
    assert arrow_batch.input_hash == row_batch.input_hash
    np.testing.assert_array_equal(
        arrow_batch.position_ids,
        [position.position_id for position in fixture.positions],
    )
    np.testing.assert_array_equal(
        arrow_batch.issuer_ids,
        [position.issuer_id for position in fixture.positions],
    )
    np.testing.assert_array_equal(
        arrow_batch.seniorities,
        [
            position.seniority.value if position.seniority is not None else None
            for position in fixture.positions
        ],
    )


def test_drc_batch_lgd_lookup_is_by_seniority_and_default_mask(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import frtb_drc.batch as batch_module

    fixture = load_drc_nonsec_v2_fixture()
    row_count = 120
    columns = _minimal_column_payload(row_count=row_count) | {
        "is_defaulted": [index % 10 == 0 for index in range(row_count)],
    }
    batch = build_drc_nonsec_batch_from_columns(**columns)
    calls: list[object] = []
    original_get_lgd_rule = batch_module.get_lgd_rule

    def counting_get_lgd_rule(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        return original_get_lgd_rule(*args, **kwargs)

    monkeypatch.setattr(batch_module, "get_lgd_rule", counting_get_lgd_rule)

    calculate_drc_capital_from_batch(batch, context=fixture.context)

    assert len(calls) == 1


def test_drc_batch_calculation_is_deterministic_for_reversed_handoff() -> None:
    fixture = load_drc_nonsec_v2_fixture()
    table = _arrow_table(fixture.positions)
    reversed_table = table.take(pa.array(list(reversed(range(table.num_rows))), type=pa.int64()))

    first = calculate_drc_capital_from_batch(
        build_drc_nonsec_batch_from_arrow(normalize_drc_nonsec_arrow_table(table)),
        context=fixture.context,
    )
    second = calculate_drc_capital_from_batch(
        build_drc_nonsec_batch_from_arrow(normalize_drc_nonsec_arrow_table(reversed_table)),
        context=fixture.context,
    )

    assert first.result.input_hash == second.result.input_hash
    assert _net_outputs(first.result.net_jtds) == _net_outputs(second.result.net_jtds)
    assert _bucket_outputs(first.result.categories[0].bucket_results) == _bucket_outputs(
        second.result.categories[0].bucket_results
    )


def test_drc_column_batch_rejects_wrong_risk_class_without_row_fallback() -> None:
    columns = _minimal_column_payload(row_count=1) | {"risk_classes": ["SECURITISATION_NON_CTP"]}

    with pytest.raises(DrcInputError, match="requires a single supported risk_class"):
        build_drc_nonsec_batch_from_columns(**columns)


def test_drc_column_batch_rejects_mixed_risk_classes_without_row_fallback() -> None:
    columns = _minimal_column_payload(row_count=2) | {
        "risk_classes": ["SECURITISATION_NON_CTP", "CORRELATION_TRADING_PORTFOLIO"],
        "instrument_types": ["SECURITISATION_TRANCHE", "INDEX_TRANCHE"],
        "default_directions": ["LONG", "SHORT"],
        "issuer_ids": ["pool-1", None],
        "tranche_ids": ["mezz", "10-15"],
        "index_series_ids": [None, "CDX.NA.IG.S18"],
        "bucket_keys": ["SEC_CLO_NORTH_AMERICA", "CDX_NA_IG"],
        "seniorities": [None, None],
        "credit_qualities": [None, None],
        "market_values": [100.0, 40.0],
    }

    with pytest.raises(DrcInputError, match="requires a single supported risk_class"):
        build_drc_securitisation_non_ctp_batch_from_columns(**columns)

    with pytest.raises(DrcInputError, match="requires a single supported risk_class"):
        build_drc_ctp_batch_from_columns(**columns)


def test_drc_securitisation_batch_missing_weight_fails_closed() -> None:
    fixture = _load_fixture("drc_sec_nonctp_v1")
    batch = build_drc_securitisation_non_ctp_batch_from_arrow(
        normalize_drc_securitisation_non_ctp_arrow_table(_arrow_table(fixture["positions"]))
    )

    with pytest.raises(DrcInputError, match="securitisation_non_ctp_risk_weights"):
        calculate_drc_capital_from_batch(
            batch,
            context=replace(fixture["context"], securitisation_non_ctp_risk_weights={}),
        )


def test_drc_securitisation_batch_invalid_weight_fails_closed() -> None:
    fixture = _load_fixture("drc_sec_nonctp_v1")
    position_ids = [position.position_id for position in fixture["positions"]]
    risk_weights = dict(fixture["context"].securitisation_non_ctp_risk_weights)
    risk_weights[position_ids[0]] = "not-a-number"
    batch = build_drc_securitisation_non_ctp_batch_from_arrow(
        normalize_drc_securitisation_non_ctp_arrow_table(_arrow_table(fixture["positions"]))
    )

    with pytest.raises(DrcInputError, match="valid finite number"):
        calculate_drc_capital_from_batch(
            batch,
            context=replace(fixture["context"], securitisation_non_ctp_risk_weights=risk_weights),
        )


def test_drc_securitisation_batch_rejected_offsets_are_bounded_by_groups() -> None:
    fixture = _load_fixture("drc_sec_nonctp_v1")
    base = fixture["positions"][0]
    positions: list[DrcPosition] = []
    risk_weights: dict[str, float] = {}
    for index in range(4):
        position_id = f"long-sec-group-{index}"
        positions.append(
            replace(
                base,
                position_id=position_id,
                source_row_id=f"row-{position_id}",
                default_direction="LONG",
                issuer_id=f"long-pool-{index}",
                tranche_id=f"long-tranche-{index}",
                market_value=100.0 + index,
            )
        )
        risk_weights[position_id] = 0.2
    for index in range(4):
        position_id = f"short-sec-group-{index}"
        positions.append(
            replace(
                base,
                position_id=position_id,
                source_row_id=f"row-{position_id}",
                default_direction="SHORT",
                issuer_id=f"short-pool-{index}",
                tranche_id=f"short-tranche-{index}",
                market_value=40.0 + index,
            )
        )
        risk_weights[position_id] = 0.2
    batch = build_drc_securitisation_non_ctp_batch_from_arrow(
        normalize_drc_securitisation_non_ctp_arrow_table(_arrow_table(tuple(positions)))
    )

    calculation = calculate_drc_capital_from_batch(
        batch,
        context=replace(
            fixture["context"],
            securitisation_non_ctp_risk_weights=risk_weights,
            securitisation_non_ctp_offset_groups={},
        ),
    )

    rejected_counts = [len(record.rejected_offsets) for record in calculation.result.net_jtds]
    assert rejected_counts
    assert max(rejected_counts) <= 8
    assert max(rejected_counts) < 16


def test_drc_ctp_batch_missing_weight_fails_closed() -> None:
    fixture = _load_fixture("drc_ctp_v1")
    batch = build_drc_ctp_batch_from_arrow(
        normalize_drc_ctp_arrow_table(_arrow_table(fixture["positions"]))
    )

    with pytest.raises(DrcInputError, match="ctp_risk_weights"):
        calculate_drc_capital_from_batch(
            batch, context=replace(fixture["context"], ctp_risk_weights={})
        )


def test_drc_ctp_batch_invalid_weight_fails_closed() -> None:
    fixture = _load_fixture("drc_ctp_v1")
    position_ids = [position.position_id for position in fixture["positions"]]
    risk_weights = dict(fixture["context"].ctp_risk_weights)
    risk_weights[position_ids[0]] = None
    batch = build_drc_ctp_batch_from_arrow(
        normalize_drc_ctp_arrow_table(_arrow_table(fixture["positions"]))
    )

    with pytest.raises(DrcInputError, match="valid finite number"):
        calculate_drc_capital_from_batch(
            batch,
            context=replace(fixture["context"], ctp_risk_weights=risk_weights),
        )


def test_drc_column_batch_rejects_unrated_credit_quality_without_row_fallback() -> None:
    columns = _minimal_column_payload(row_count=1) | {"credit_qualities": ["UNRATED"]}

    with pytest.raises(
        DrcInputError,
        match=r"UNRATED.*not a chargeable.*US_NPR_210_B_3_II",
    ):
        build_drc_nonsec_batch_from_columns(**columns)


def test_drc_column_batch_rejects_non_chargeable_bucket_without_row_fallback() -> None:
    columns = _minimal_column_payload(row_count=1) | {"bucket_keys": ["US_SOVEREIGN"]}

    with pytest.raises(
        DrcInputError,
        match=r"US_SOVEREIGN.*not a chargeable.*US_NPR_210_B_3_I",
    ):
        build_drc_nonsec_batch_from_columns(**columns)


def test_drc_column_batch_high_volume_path_reports_zero_row_dataclasses() -> None:
    row_count = 1_000
    columns = _minimal_column_payload(row_count=row_count)

    batch = build_drc_nonsec_batch_from_columns(**columns)

    assert batch.row_count == row_count
    assert not any(isinstance(value, DrcPosition) for value in batch.__dict__.values())
    assert batch.input_hash


def test_drc_column_batch_copy_false_does_not_freeze_caller_numpy_arrays() -> None:
    notionals = np.array([100_000.0, 200_000.0], dtype=np.float64)
    maturity_years = np.array([1.0, 0.5], dtype=np.float64)
    columns = _minimal_column_payload(row_count=2) | {
        "notionals": notionals,
        "maturity_years": maturity_years,
    }

    batch = build_drc_nonsec_batch_from_columns(**columns, copy_arrays=False)

    assert notionals.flags.writeable
    assert maturity_years.flags.writeable
    assert not batch.notionals.flags.writeable
    assert not batch.maturity_years.flags.writeable
    assert np.shares_memory(batch.notionals, notionals)
    assert np.shares_memory(batch.maturity_years, maturity_years)


def test_drc_column_batch_coerces_boolean_spellings_and_rejects_invalid_values() -> None:
    columns = _minimal_column_payload(row_count=2) | {
        "is_defaulted": ["yes", "0"],
        "is_gse": ["1", "false"],
    }

    batch = build_drc_nonsec_batch_from_columns(**columns)

    assert batch.is_defaulted.tolist() == [True, False]
    assert batch.is_gse.tolist() == [True, False]
    assert not batch.is_defaulted.flags.writeable
    with pytest.raises(DrcInputError, match="boolean field contains unsupported value"):
        build_drc_nonsec_batch_from_columns(
            **(_minimal_column_payload(row_count=1) | {"is_defaulted": ["maybe"]})
        )


def test_drc_batch_rejects_unsupported_citation_policy_like_row_api() -> None:
    fixture = load_drc_nonsec_v2_fixture()
    batch = build_drc_nonsec_batch_from_arrow(
        normalize_drc_nonsec_arrow_table(_arrow_table(fixture.positions))
    )

    with pytest.raises(DrcInputError, match="unsupported citation_policy: lenient"):
        calculate_drc_capital_from_batch(
            batch,
            context=replace(fixture.context, citation_policy="lenient"),
        )


def test_drc_batch_translates_multi_currency_book_without_row_materialization() -> None:
    fixture = load_drc_nonsec_v2_fixture()
    columns = _minimal_column_payload(row_count=2) | {
        "position_ids": ["usd", "eur"],
        "source_row_ids": ["row-usd", "row-eur"],
        "issuer_ids": ["issuer-usd", "issuer-eur"],
        "notionals": [100.0, 100.0],
        "currencies": ["USD", "EUR"],
    }
    batch = build_drc_nonsec_batch_from_columns(**columns)

    calculation = calculate_drc_capital_from_batch(
        batch,
        context=replace(fixture.context, fx_rates={"EUR": _fx_rate("EUR", 1.2)}),
    )

    gross_by_position = {
        position_id: gross
        for position_id, gross in zip(
            batch.position_ids.tolist(), calculation.gross_jtd, strict=True
        )
    }
    assert gross_by_position == pytest.approx({"usd": 75.0, "eur": 90.0})
    assert calculation.result.total_drc == pytest.approx((75.0 + 90.0) * 0.041)
    assert calculation.result.fx_conversions[0].source_currency == "EUR"
    assert calculation.result.fx_conversions[0].position_count == 1
    assert "US_NPR_208_H_1_II" in calculation.result.citations
    assert calculation.result.input_hash != batch.input_hash


def test_drc_batch_missing_fx_rate_fails_closed() -> None:
    fixture = load_drc_nonsec_v2_fixture()
    columns = _minimal_column_payload(row_count=1) | {"currencies": ["EUR"]}
    batch = build_drc_nonsec_batch_from_columns(**columns)

    with pytest.raises(DrcInputError, match=r"missing FX rate EUR->USD.*p-000000"):
        calculate_drc_capital_from_batch(batch, context=fixture.context)


def test_drc_column_batch_requires_lineage() -> None:
    columns = _minimal_column_payload(row_count=1)
    columns.pop("lineage_source_systems")
    columns.pop("lineage_source_files")

    with pytest.raises(DrcInputError, match="lineage is required"):
        build_drc_nonsec_batch_from_columns(**columns)


def test_drc_column_batch_rejects_blank_lineage_fields() -> None:
    columns = _minimal_column_payload(row_count=1) | {"lineage_source_systems": [" "]}

    with pytest.raises(DrcInputError, match=r"lineage\.source_system must be non-empty"):
        build_drc_nonsec_batch_from_columns(**columns)


def test_drc_column_batch_rejects_blank_citation_ids() -> None:
    columns = _minimal_column_payload(row_count=1) | {"citation_ids": [["US_NPR_210_SCOPE", " "]]}

    with pytest.raises(DrcInputError, match="citation_ids must contain non-empty citations"):
        build_drc_nonsec_batch_from_columns(**columns)


def test_drc_batch_calculation_validates_result_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import frtb_drc.batch as batch_module

    fixture = load_drc_nonsec_v2_fixture()
    batch = build_drc_nonsec_batch_from_arrow(
        normalize_drc_nonsec_arrow_table(_arrow_table(fixture.positions))
    )
    calls: list[float] = []

    def fake_validate_reconciliation(result: DrcCapitalResult) -> None:
        calls.append(result.total_drc)

    monkeypatch.setattr(batch_module, "validate_reconciliation", fake_validate_reconciliation)

    calculation = batch_module.calculate_drc_capital_from_batch(batch, context=fixture.context)

    assert calls == [calculation.result.total_drc]


def _minimal_column_payload(*, row_count: int) -> dict[str, object]:
    return {
        "position_ids": [f"p-{index:06d}" for index in range(row_count)],
        "source_row_ids": [f"row-{index:06d}" for index in range(row_count)],
        "desk_ids": ["credit-desk"] * row_count,
        "legal_entities": ["bank-na"] * row_count,
        "risk_classes": ["NON_SECURITISATION"] * row_count,
        "instrument_types": ["BOND"] * row_count,
        "default_directions": ["LONG"] * row_count,
        "issuer_ids": [f"issuer-{index % 50:03d}" for index in range(row_count)],
        "bucket_keys": ["CORPORATE"] * row_count,
        "seniorities": ["SENIOR_DEBT"] * row_count,
        "credit_qualities": ["INVESTMENT_GRADE"] * row_count,
        "notionals": [100_000.0 + index for index in range(row_count)],
        "cumulative_pnls": [0.0] * row_count,
        "maturity_years": [1.0] * row_count,
        "currencies": ["USD"] * row_count,
        "lineage_source_systems": ["unit-test"] * row_count,
        "lineage_source_files": ["synthetic-drc.csv"] * row_count,
    }


def _load_fixture(fixture_name: str) -> dict[str, Any]:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / fixture_name
    payload = json.loads((fixture_dir / "positions.json").read_text(encoding="utf-8"))
    context_raw = payload["context"]
    positions = tuple(drc_position_from_dict(raw) for raw in payload["positions"])
    return {
        "positions": positions,
        "context": DrcCalculationContext(
            run_id=context_raw["run_id"],
            calculation_date=date.fromisoformat(context_raw["calculation_date"]),
            base_currency=context_raw["base_currency"],
            profile_id=context_raw["profile_id"],
            securitisation_non_ctp_risk_weights=context_raw.get(
                "securitisation_non_ctp_risk_weights",
                {},
            ),
            securitisation_non_ctp_offset_groups=context_raw.get(
                "securitisation_non_ctp_offset_groups",
                {},
            ),
            ctp_risk_weights=context_raw.get("ctp_risk_weights", {}),
            ctp_risk_weight_evidence=risk_weight_evidence_by_position(
                drc_risk_weight_evidence_from_dict(raw)
                for raw in context_raw.get("ctp_risk_weight_evidence", ())
            ),
            securitisation_non_ctp_risk_weight_evidence=risk_weight_evidence_by_position(
                drc_risk_weight_evidence_from_dict(raw)
                for raw in context_raw.get("securitisation_non_ctp_risk_weight_evidence", ())
            ),
            securitisation_non_ctp_fair_value_cap_evidence=fair_value_cap_evidence_by_position(
                drc_fair_value_cap_evidence_from_dict(raw)
                for raw in context_raw.get("securitisation_non_ctp_fair_value_cap_evidence", ())
            ),
            ctp_offset_groups=context_raw.get("ctp_offset_groups", {}),
        ),
    }


def _fair_value_cap_evidence(
    position: DrcPosition,
    *,
    fair_value_cap_amount: float,
) -> DrcFairValueCapEvidence:
    return DrcFairValueCapEvidence(
        position_id=position.position_id,
        source_profile_id="US_NPR_2_0",
        eligible=True,
        fair_value_cap_amount=fair_value_cap_amount,
        eligibility_reason="synthetic cash securitisation cap eligible",
        as_of_date=date(2026, 5, 29),
        source_id="fair-value-cap-source",
        lineage=DrcSourceLineage(
            source_system="synthetic-risk-weight-engine",
            source_file="securitisation-fair-value-cap.csv",
            source_row_id=f"cap-{position.position_id}",
            source_column_map={"fair_value_cap_amount": "fair_value_cap_amount"},
        ),
        citation_ids=("US_NPR_210_C_3_III", "BASEL_MAR22_34"),
    )


def _arrow_table(positions: tuple[DrcPosition, ...]) -> pa.Table:
    return pa.table(
        {
            "position_id": [position.position_id for position in positions],
            "source_row_id": [position.source_row_id for position in positions],
            "desk_id": [position.desk_id for position in positions],
            "legal_entity": [position.legal_entity for position in positions],
            "risk_class": [position.risk_class.value for position in positions],
            "instrument_type": [position.instrument_type.value for position in positions],
            "default_direction": [position.default_direction.value for position in positions],
            "issuer_id": [position.issuer_id for position in positions],
            "tranche_id": [position.tranche_id for position in positions],
            "index_series_id": [position.index_series_id for position in positions],
            "bucket_key": [position.bucket_key for position in positions],
            "seniority": [
                None if position.seniority is None else position.seniority.value
                for position in positions
            ],
            "credit_quality": [
                None if position.credit_quality is None else position.credit_quality.value
                for position in positions
            ],
            "notional": pa.array([position.notional for position in positions], type=pa.float64()),
            "market_value": pa.array(
                [position.market_value for position in positions], type=pa.float64()
            ),
            "cumulative_pnl": pa.array(
                [position.cumulative_pnl for position in positions], type=pa.float64()
            ),
            "maturity_years": pa.array(
                [position.maturity_years for position in positions], type=pa.float64()
            ),
            "currency": [position.currency for position in positions],
            "lgd_override": pa.array(
                [position.lgd_override for position in positions], type=pa.float64()
            ),
            "is_defaulted": [position.is_defaulted for position in positions],
            "is_gse": [position.is_gse for position in positions],
            "is_pse": [position.is_pse for position in positions],
            "is_covered_bond": [position.is_covered_bond for position in positions],
            "lineage_source_system": [
                "" if position.lineage is None else position.lineage.source_system
                for position in positions
            ],
            "lineage_source_file": [
                "" if position.lineage is None else position.lineage.source_file
                for position in positions
            ],
            "citation_ids": [",".join(position.citation_ids) for position in positions],
        }
    )


def _fx_rate(source_currency: str, rate: float) -> DrcFxRate:
    return DrcFxRate(
        source_currency=source_currency,
        target_currency="USD",
        rate=rate,
        as_of_date=load_drc_nonsec_v2_fixture().context.calculation_date,
        source_id="unit-fx-source",
        lineage=DrcSourceLineage(
            source_system="unit-test",
            source_file="fx-rates.csv",
            source_row_id="EUR-USD",
            source_column_map={"rate": "rate"},
        ),
    )


_DICTIONARY_TEXT_COLUMNS = {
    "position_id",
    "source_row_id",
    "desk_id",
    "legal_entity",
    "risk_class",
    "instrument_type",
    "default_direction",
    "issuer_id",
    "tranche_id",
    "index_series_id",
    "bucket_key",
    "seniority",
    "credit_quality",
    "currency",
    "lineage_source_system",
    "lineage_source_file",
    "citation_ids",
}


def _dictionary_encoded_text_table(table: pa.Table) -> pa.Table:
    columns = {}
    for column_name in table.column_names:
        column = table.column(column_name).combine_chunks()
        columns[column_name] = (
            column.dictionary_encode() if column_name in _DICTIONARY_TEXT_COLUMNS else column
        )
    return pa.table(columns)


def _net_outputs(records: object) -> dict[str, object]:
    return {
        record.net_jtd_id: {
            "amount": record.net_amount,
            "bucket": record.bucket_key,
            "direction": record.net_direction.value,
            "issuer": record.obligor_or_tranche_key,
            "position_ids": record.position_ids,
            "rejected_offsets": [offset.reason_code for offset in record.rejected_offsets],
        }
        for record in cast(tuple[object, ...], records)
    }


def _bucket_outputs(records: object) -> dict[str, object]:
    return {
        record.bucket_key: {
            "capital": record.capital,
            "floor_applied": record.floor_applied,
            "hbr": record.hbr.ratio,
            "weighted_long": record.weighted_long,
            "weighted_short": record.weighted_short,
        }
        for record in cast(tuple[object, ...], records)
    }
