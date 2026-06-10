from __future__ import annotations

from pathlib import Path

import frtb_cva
import pyarrow.parquet as pq

HANDOFF_SURFACE = (
    "CVA_COUNTERPARTY_ARROW_COLUMN_SPECS",
    "CVA_NETTING_SET_ARROW_COLUMN_SPECS",
    "CVA_HEDGE_ARROW_COLUMN_SPECS",
    "SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS",
    "normalize_cva_counterparty_arrow_table",
    "normalize_cva_netting_set_arrow_table",
    "normalize_cva_hedge_arrow_table",
    "normalize_sa_cva_sensitivity_arrow_table",
    "build_cva_counterparty_batch_from_arrow",
    "build_cva_netting_set_batch_from_arrow",
    "build_cva_hedge_batch_from_arrow",
    "build_sa_cva_sensitivity_batch_from_arrow",
    "calculate_cva_capital_from_batches",
)

LOW_LEVEL_BATCH_INTERNALS = (
    "_validate_netting_set_batch",
    "calculate_reduced_portfolio_from_batches",
    "calculate_full_portfolio_from_batches",
    "calculate_sa_cva_capital_from_batch",
)


def test_documented_handoff_surface_is_top_level_importable() -> None:
    exported = set(frtb_cva.__all__)
    documented = _public_api_doc()
    for name in HANDOFF_SURFACE:
        assert name in exported
        assert hasattr(frtb_cva, name)
        assert f"`{name}`" in documented


def test_low_level_batch_internals_are_not_public_api() -> None:
    import frtb_cva.batch

    exported = set(frtb_cva.__all__)
    batch_exported = set(frtb_cva.batch.__all__)
    documented = _public_api_doc()
    for name in LOW_LEVEL_BATCH_INTERNALS:
        assert name not in exported
        assert not hasattr(frtb_cva, name)
        assert name not in batch_exported
        assert not hasattr(frtb_cva.batch, name)
        assert f"`{name}`" not in documented


def test_minimal_handoff_fixtures_round_trip_to_batches() -> None:
    cases = (
        (
            "cva_counterparty_minimal.parquet",
            frtb_cva.normalize_cva_counterparty_arrow_table,
            frtb_cva.build_cva_counterparty_batch_from_arrow,
            "row_count",
        ),
        (
            "cva_netting_set_minimal.parquet",
            frtb_cva.normalize_cva_netting_set_arrow_table,
            frtb_cva.build_cva_netting_set_batch_from_arrow,
            "row_count",
        ),
        (
            "cva_hedge_minimal.parquet",
            frtb_cva.normalize_cva_hedge_arrow_table,
            frtb_cva.build_cva_hedge_batch_from_arrow,
            "row_count",
        ),
        (
            "sa_cva_sensitivity_minimal.parquet",
            frtb_cva.normalize_sa_cva_sensitivity_arrow_table,
            frtb_cva.build_sa_cva_sensitivity_batch_from_arrow,
            "row_count",
        ),
    )
    for filename, normalize, build_batch, row_count_attr in cases:
        handoff = normalize(pq.read_table(_fixture_dir() / filename))
        batch = build_batch(handoff)
        assert handoff.accepted.num_rows == 1
        assert getattr(batch, row_count_attr) == 1
        assert batch.handoff_hash is not None


def test_top_level_public_api_surface_remains_bounded() -> None:
    assert len(frtb_cva.__all__) < 125


def _public_api_doc() -> str:
    root = Path(__file__).resolve().parents[3]
    return (root / "docs/modules/frtb-cva/PUBLIC_API.md").read_text()


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures/handoff"
