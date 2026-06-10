from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_cva import (
    CvaCalculationContext,
    CvaInputError,
    CvaMethod,
    CvaRegulatoryProfile,
    build_cva_counterparty_batch_from_columns,
    build_cva_hedge_batch_from_columns,
    build_cva_netting_set_batch_from_columns,
    build_sa_cva_sensitivity_batch_from_columns,
    calculate_cva_capital_from_batches,
    get_cva_rule_profile,
)
from frtb_cva._batch_columns import (
    _bool_array,
    _default_text_sequence,
    _enum_array,
    _finite_float,
    _float_array,
    _normalised_ead_array,
    _optional_float_array,
    _optional_float_value,
    _optional_text_array,
    _require_lengths,
    _require_optional_lengths,
    _required_text,
)
from frtb_cva.regimes import SUPPORTED_PROFILE_METADATA, resolve_cva_profile


def _counterparty_batch() -> Any:
    return build_cva_counterparty_batch_from_columns(
        counterparty_ids=["cp-1"],
        desk_ids=["desk-1"],
        legal_entities=["LE-001"],
        sectors=["SOVEREIGN"],
        credit_qualities=["INVESTMENT_GRADE"],
        regions=["EMEA"],
        source_row_ids=["cp-row-1"],
        lineage_source_systems=["synthetic"],
        lineage_source_files=["counterparties.csv"],
    )


def _netting_set_batch(
    *,
    netting_set_ids: list[str] | None = None,
    counterparty_ids: list[str] | None = None,
    carved_out_to_ba_cva: list[bool] | None = None,
) -> Any:
    ids = netting_set_ids or ["ns-1"]
    counterparties = counterparty_ids or ["cp-1"] * len(ids)
    carved = carved_out_to_ba_cva or [False] * len(ids)
    return build_cva_netting_set_batch_from_columns(
        netting_set_ids=ids,
        counterparty_ids=counterparties,
        eads=[100_000.0] * len(ids),
        effective_maturities=[2.5] * len(ids),
        discount_factors=[0.98] * len(ids),
        currencies=["USD"] * len(ids),
        sign_conventions=["non_negative"] * len(ids),
        uses_imm_eads=[False] * len(ids),
        carved_out_to_ba_cva=carved,
        source_row_ids=[f"ns-row-{index}" for index in range(len(ids))],
    )


def _context(
    method: CvaMethod,
    *,
    sa_cva_approved: bool = False,
    carve_out_netting_set_ids: tuple[str, ...] = (),
) -> CvaCalculationContext:
    return CvaCalculationContext(
        run_id=f"run-{method.value.lower()}",
        calculation_date=date(2026, 6, 1),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=method,
        sa_cva_approved=sa_cva_approved,
        carve_out_netting_set_ids=carve_out_netting_set_ids,
    )


def _hedge_columns(**overrides: object) -> dict[str, object]:
    columns: dict[str, object] = {
        "hedge_ids": ["h-1"],
        "source_row_ids": ["h-row-1"],
        "counterparty_ids": ["cp-1"],
        "hedge_types": ["SINGLE_NAME_CDS"],
        "notionals": [50_000.0],
        "remaining_maturities": [2.0],
        "discount_factors": [0.99],
        "reference_sectors": ["SOVEREIGN"],
        "reference_credit_qualities": ["INVESTMENT_GRADE"],
        "reference_regions": ["EMEA"],
        "reference_relations": ["DIRECT"],
        "eligibilities": ["ELIGIBLE"],
        "is_internal": [False],
        "eligibility_evidence_ids": ["ev-1"],
    }
    columns.update(overrides)
    return columns


def _sensitivity_columns(**overrides: object) -> dict[str, object]:
    columns: dict[str, object] = {
        "sensitivity_ids": ["sens-1"],
        "risk_classes": ["GIRR"],
        "risk_measures": ["DELTA"],
        "sensitivity_tags": ["CVA"],
        "bucket_ids": ["USD"],
        "risk_factor_keys": ["5y"],
        "amounts": [1_000.0],
        "amount_currencies": ["USD"],
        "sign_conventions": ["positive_loss"],
        "source_row_ids": ["sens-row-1"],
        "tenors": ["5y"],
    }
    columns.update(overrides)
    return columns


def _sa_batch_result(**overrides: object):
    batch = build_sa_cva_sensitivity_batch_from_columns(**_sensitivity_columns(**overrides))
    return calculate_cva_capital_from_batches(
        _context(CvaMethod.SA_CVA, sa_cva_approved=True),
        sensitivities=batch,
    ).result


def test_column_helpers_fail_closed_on_invalid_shapes_and_values() -> None:
    with pytest.raises(CvaInputError, match="foo length does not match ids"):
        _require_lengths(2, foo=[1])
    with pytest.raises(CvaInputError, match="bar length does not match ids"):
        _require_optional_lengths(2, bar=[1])

    with pytest.raises(CvaInputError, match="sign_convention must be one of"):
        _normalised_ead_array(
            np.array([1.0], dtype=np.float64),
            np.array(["bad"], dtype=object),
            record_ids=np.array(["ns-1"], dtype=object),
        )
    with pytest.raises(CvaInputError, match="must be 1-dimensional"):
        _float_array(np.array([[1.0]], dtype=np.float64), "amount", copy=True)
    with pytest.raises(CvaInputError, match="boolean field contains unsupported value"):
        _bool_array(["maybe"], 1, default=False, copy=True)
    with pytest.raises(CvaInputError, match="non-empty text is required"):
        _required_text("", "source_row_id")
    with pytest.raises(CvaInputError, match="invalid method"):
        _enum_array(["BAD"], CvaMethod, "method", copy=True)
    with pytest.raises(CvaInputError, match="value must be numeric"):
        _finite_float(True, "amount")
    with pytest.raises(CvaInputError, match="value must be finite"):
        _finite_float(float("inf"), "amount")

    assert _optional_text_array([None, np.nan, " "], 3, copy=True).tolist() == [
        None,
        None,
        None,
    ]
    assert np.isnan(_optional_float_array([None, np.nan, " "], 3, copy=True)).all()
    assert _optional_float_value(np.nan) is None
    assert _default_text_sequence(["explicit"], 1, "default") == ["explicit"]
    assert _default_text_sequence(None, 2, "default") == ["default", "default"]


def test_profile_resolution_fails_closed_for_unknown_and_incomplete_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(CvaInputError, match="unknown CVA regulatory profile"):
        resolve_cva_profile("NOT_A_PROFILE")

    basel_metadata = SUPPORTED_PROFILE_METADATA[CvaRegulatoryProfile.BASEL_MAR50_2020]
    monkeypatch.delitem(
        SUPPORTED_PROFILE_METADATA,
        CvaRegulatoryProfile.BASEL_MAR50_2020,
    )
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="has no supported metadata"):
        resolve_cva_profile(CvaRegulatoryProfile.BASEL_MAR50_2020)

    monkeypatch.setitem(
        SUPPORTED_PROFILE_METADATA,
        CvaRegulatoryProfile.BASEL_MAR50_2020,
        {**basel_metadata, "publication_date": "2020-07-08"},
    )
    with pytest.raises(CvaInputError, match="publication_date must be a date"):
        get_cva_rule_profile(CvaRegulatoryProfile.BASEL_MAR50_2020)


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"notionals": [-1.0]}, "notional must be non-negative"),
        ({"eligibility_evidence_ids": [None]}, "eligibility_evidence_id"),
        (
            {
                "eligibilities": ["INELIGIBLE"],
                "eligibility_evidence_ids": [None],
                "rejection_reasons": [None],
            },
            "rejection_reason",
        ),
    ],
)
def test_hedge_batch_validates_fail_closed(
    overrides: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(CvaInputError, match=match):
        build_cva_hedge_batch_from_columns(**_hedge_columns(**overrides))


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"sign_conventions": ["bad"]}, "sign_convention must be one of"),
        ({"tenors": [None]}, "GIRR delta sensitivities must specify tenor"),
        (
            {"risk_measures": ["VEGA"], "volatility_inputs": [None]},
            "vega sensitivities must specify volatility_input",
        ),
        ({"sensitivity_tags": ["HDG"], "hedge_ids": [None]}, "hedge_id"),
        ({"index_max_sector_weights": [1.5]}, "index_max_sector_weight"),
    ],
)
def test_sensitivity_batch_validates_fail_closed(
    overrides: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(CvaInputError, match=match):
        build_sa_cva_sensitivity_batch_from_columns(**_sensitivity_columns(**overrides))


def test_batch_scope_resolution_rejects_missing_approvals_and_carve_out_evidence() -> None:
    with pytest.raises(CvaInputError, match="SA-CVA requires sa_cva_approved=True"):
        calculate_cva_capital_from_batches(_context(CvaMethod.SA_CVA))

    with pytest.raises(CvaInputError, match="mixed carve-out requires sa_cva_approved=True"):
        calculate_cva_capital_from_batches(
            _context(CvaMethod.MIXED_CARVE_OUT, carve_out_netting_set_ids=("ns-1",)),
            _counterparty_batch(),
            _netting_set_batch(carved_out_to_ba_cva=[True]),
        )
    with pytest.raises(CvaInputError, match="mixed carve-out requires carve_out_netting_set_ids"):
        calculate_cva_capital_from_batches(
            _context(CvaMethod.MIXED_CARVE_OUT, sa_cva_approved=True),
            _counterparty_batch(),
            _netting_set_batch(),
        )
    with pytest.raises(CvaInputError, match="missing from inputs"):
        calculate_cva_capital_from_batches(
            _context(CvaMethod.BA_CVA_REDUCED, carve_out_netting_set_ids=("missing",)),
            _counterparty_batch(),
            _netting_set_batch(),
        )
    with pytest.raises(CvaInputError, match="must set carved_out_to_ba_cva=True"):
        calculate_cva_capital_from_batches(
            _context(
                CvaMethod.MIXED_CARVE_OUT,
                sa_cva_approved=True,
                carve_out_netting_set_ids=("ns-1",),
            ),
            _counterparty_batch(),
            _netting_set_batch(carved_out_to_ba_cva=[False]),
        )
    with pytest.raises(CvaInputError, match="must appear in carve_out_netting_set_ids"):
        calculate_cva_capital_from_batches(
            _context(
                CvaMethod.MIXED_CARVE_OUT,
                sa_cva_approved=True,
                carve_out_netting_set_ids=("ns-2",),
            ),
            _counterparty_batch(),
            _netting_set_batch(
                netting_set_ids=["ns-1", "ns-2"],
                carved_out_to_ba_cva=[True, True],
            ),
        )

    with pytest.raises(CvaInputError, match="counterparty has no netting sets"):
        calculate_cva_capital_from_batches(
            _context(CvaMethod.BA_CVA_REDUCED),
            _counterparty_batch(),
        )


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        (
            {
                "risk_classes": ["COUNTERPARTY_CREDIT_SPREAD"],
                "risk_measures": ["VEGA"],
                "bucket_ids": ["1"],
                "risk_factor_keys": ["cp-1|INVESTMENT_GRADE|EMEA"],
                "volatility_inputs": [0.2],
            },
            "CCS vega capital is not permitted",
        ),
        (
            {
                "risk_classes": ["COUNTERPARTY_CREDIT_SPREAD"],
                "bucket_ids": ["8"],
                "risk_factor_keys": ["INDEX|INVESTMENT_GRADE"],
                "index_treatments": ["LOOK_THROUGH_REQUIRED"],
            },
            "look-through sensitivities",
        ),
        (
            {"index_treatments": ["QUALIFIED_INDEX"]},
            "qualified-index routing is only supported",
        ),
        (
            {
                "risk_classes": ["COUNTERPARTY_CREDIT_SPREAD"],
                "bucket_ids": ["9"],
                "risk_factor_keys": ["INDEX|INVESTMENT_GRADE"],
                "index_treatments": ["QUALIFIED_INDEX"],
            },
            "does not support qualified-index treatment",
        ),
        (
            {
                "risk_classes": ["COUNTERPARTY_CREDIT_SPREAD"],
                "bucket_ids": ["1"],
                "risk_factor_keys": ["INDEX|INVESTMENT_GRADE"],
                "index_treatments": ["QUALIFIED_INDEX"],
            },
            "qualified CCS index must use bucket 8",
        ),
        (
            {
                "risk_classes": ["COUNTERPARTY_CREDIT_SPREAD"],
                "bucket_ids": ["8"],
                "risk_factor_keys": ["INDEX|INVESTMENT_GRADE"],
            },
            "CCS bucket 8 requires qualified-index treatment metadata",
        ),
        (
            {
                "risk_classes": ["REFERENCE_CREDIT_SPREAD"],
                "bucket_ids": ["16"],
                "risk_factor_keys": ["INDEX"],
            },
            "RCS qualified-index buckets 16/17 require QUALIFIED_INDEX treatment",
        ),
        (
            {
                "risk_classes": ["REFERENCE_CREDIT_SPREAD"],
                "bucket_ids": ["8"],
                "risk_factor_keys": ["INDEX"],
                "index_treatments": ["QUALIFIED_INDEX"],
            },
            "RCS qualified index must use buckets 16 or 17",
        ),
        (
            {
                "risk_classes": ["EQUITY"],
                "bucket_ids": ["12"],
                "risk_factor_keys": ["INDEX"],
            },
            "equity qualified-index buckets 12/13 require QUALIFIED_INDEX treatment",
        ),
        (
            {
                "risk_classes": ["EQUITY"],
                "bucket_ids": ["1"],
                "risk_factor_keys": ["INDEX"],
                "index_treatments": ["QUALIFIED_INDEX"],
            },
            "qualified equity index must use buckets 12 or 13",
        ),
        (
            {
                "risk_classes": ["COUNTERPARTY_CREDIT_SPREAD"],
                "bucket_ids": ["8"],
                "risk_factor_keys": ["INDEX|INVESTMENT_GRADE"],
                "index_treatments": ["QUALIFIED_INDEX"],
                "index_max_sector_weights": [0.8],
                "index_homogeneous_sector_quality": [False],
            },
            "must map to single-name bucket",
        ),
        (
            {
                "risk_classes": ["COUNTERPARTY_CREDIT_SPREAD"],
                "bucket_ids": ["8"],
                "risk_factor_keys": ["INDEX|INVESTMENT_GRADE"],
                "index_treatments": ["QUALIFIED_INDEX"],
                "index_max_sector_weights": [0.8],
                "index_homogeneous_sector_quality": [True],
            },
            "index_dominant_sector",
        ),
        (
            {
                "risk_classes": ["COUNTERPARTY_CREDIT_SPREAD"],
                "bucket_ids": ["8"],
                "risk_factor_keys": ["INDEX|INVESTMENT_GRADE"],
                "index_treatments": ["QUALIFIED_INDEX"],
                "index_max_sector_weights": [0.8],
                "index_homogeneous_sector_quality": [True],
                "index_remap_bucket_ids": ["8"],
            },
            "is not a single-name bucket",
        ),
        (
            {
                "risk_classes": ["REFERENCE_CREDIT_SPREAD"],
                "bucket_ids": ["16"],
                "risk_factor_keys": ["INDEX"],
                "index_treatments": ["QUALIFIED_INDEX"],
                "index_max_sector_weights": [0.8],
                "index_homogeneous_sector_quality": [True],
                "index_remap_bucket_ids": ["16"],
            },
            "is not a single-name bucket",
        ),
    ],
)
def test_batch_sa_cva_qualified_index_paths_fail_closed(
    overrides: dict[str, object],
    match: str,
) -> None:
    batch = build_sa_cva_sensitivity_batch_from_columns(**_sensitivity_columns(**overrides))
    with pytest.raises(CvaInputError, match=match):
        calculate_cva_capital_from_batches(
            _context(CvaMethod.SA_CVA, sa_cva_approved=True),
            sensitivities=batch,
        )


def test_batch_sa_cva_ccs_sector_concentration_can_use_dominant_sector_bucket() -> None:
    result = _sa_batch_result(
        risk_classes=["COUNTERPARTY_CREDIT_SPREAD"],
        bucket_ids=["8"],
        risk_factor_keys=["INDEX|INVESTMENT_GRADE"],
        index_treatments=["QUALIFIED_INDEX"],
        index_max_sector_weights=[0.8],
        index_homogeneous_sector_quality=[True],
        index_dominant_sectors=["FINANCIALS"],
    )
    assert result.total_cva_capital > 0.0
    assert result.sa_cva_risk_class_capitals[0].bucket_capitals[0].bucket_id == "3"


def test_batch_sa_cva_rcs_bucket_eight_is_single_name_bucket() -> None:
    result = _sa_batch_result(
        risk_classes=["REFERENCE_CREDIT_SPREAD"],
        bucket_ids=["8"],
        risk_factor_keys=["SOVEREIGN|HIGH_YIELD_OR_NOT_RATED"],
    )
    assert result.total_cva_capital > 0.0
    assert result.sa_cva_risk_class_capitals[0].bucket_capitals[0].bucket_id == "8"


def test_batch_sa_cva_rcs_qualified_index_uses_buckets_sixteen_or_seventeen() -> None:
    result = _sa_batch_result(
        risk_classes=["REFERENCE_CREDIT_SPREAD"],
        bucket_ids=["17"],
        risk_factor_keys=["INDEX"],
        index_treatments=["QUALIFIED_INDEX"],
    )
    assert result.total_cva_capital > 0.0
    assert result.sa_cva_risk_class_capitals[0].bucket_capitals[0].bucket_id == "17"


def test_batch_sa_cva_rcs_concentration_requires_explicit_remap_bucket() -> None:
    batch = build_sa_cva_sensitivity_batch_from_columns(
        **_sensitivity_columns(
            risk_classes=["REFERENCE_CREDIT_SPREAD"],
            bucket_ids=["16"],
            risk_factor_keys=["INDEX"],
            index_treatments=["QUALIFIED_INDEX"],
            index_max_sector_weights=[0.8],
            index_homogeneous_sector_quality=[True],
        )
    )
    with pytest.raises(CvaInputError, match="requires index_remap_bucket_id"):
        calculate_cva_capital_from_batches(
            _context(CvaMethod.SA_CVA, sa_cva_approved=True),
            sensitivities=batch,
        )
