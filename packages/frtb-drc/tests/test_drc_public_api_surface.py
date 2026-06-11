from __future__ import annotations

from pathlib import Path

import frtb_drc
import pyarrow.parquet as pq

HANDOFF_SURFACE = (
    "DRC_NONSEC_ARROW_COLUMN_SPECS",
    "DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS",
    "DRC_CTP_ARROW_COLUMN_SPECS",
    "normalize_drc_nonsec_arrow_table",
    "normalize_drc_securitisation_non_ctp_arrow_table",
    "normalize_drc_ctp_arrow_table",
    "build_drc_nonsec_batch_from_arrow",
    "build_drc_securitisation_non_ctp_batch_from_arrow",
    "build_drc_ctp_batch_from_arrow",
    "calculate_drc_capital_from_batch",
    "input_hash_for_drc_batch",
)
ADAPTER_SURFACE = (
    "DrcCrifAdapterResult",
    "DrcCrifDirectionStrategy",
    "DrcRejectedCrifRow",
    "adapt_drc_crif_rows",
    "drc_crif_result_to_arrow_tables",
)
IMPACT_SURFACE = (
    "DrcImpactAnalysis",
    "DrcImpactMethod",
    "DrcImpactRecord",
    "calculate_drc_impact",
    "validate_drc_impact_reconciliation",
)


def test_documented_handoff_surface_is_top_level_importable() -> None:
    exported = set(frtb_drc.__all__)
    documented = _public_api_doc()
    for name in HANDOFF_SURFACE:
        assert name in exported
        assert hasattr(frtb_drc, name)
        assert f"`{name}`" in documented


def test_documented_adapter_surface_is_top_level_importable() -> None:
    exported = set(frtb_drc.__all__)
    documented = _public_api_doc()
    for name in ADAPTER_SURFACE:
        assert name in exported
        assert hasattr(frtb_drc, name)
        assert f"`{name}`" in documented


def test_documented_impact_surface_is_top_level_importable() -> None:
    exported = set(frtb_drc.__all__)
    documented = _public_api_doc()
    for name in IMPACT_SURFACE:
        assert name in exported
        assert hasattr(frtb_drc, name)
        assert f"`{name}`" in documented


def test_minimal_handoff_fixtures_round_trip_to_batches() -> None:
    cases = (
        (
            "drc_nonsec_minimal.parquet",
            frtb_drc.normalize_drc_nonsec_arrow_table,
            frtb_drc.build_drc_nonsec_batch_from_arrow,
            "NON_SECURITISATION",
        ),
        (
            "drc_securitisation_non_ctp_minimal.parquet",
            frtb_drc.normalize_drc_securitisation_non_ctp_arrow_table,
            frtb_drc.build_drc_securitisation_non_ctp_batch_from_arrow,
            "SECURITISATION_NON_CTP",
        ),
        (
            "drc_ctp_minimal.parquet",
            frtb_drc.normalize_drc_ctp_arrow_table,
            frtb_drc.build_drc_ctp_batch_from_arrow,
            "CORRELATION_TRADING_PORTFOLIO",
        ),
    )
    for filename, normalize, build_batch, risk_class in cases:
        handoff = normalize(pq.read_table(_fixture_dir() / filename))
        batch = build_batch(handoff)
        assert handoff.accepted.num_rows == 1
        assert batch.row_count == 1
        assert batch.risk_classes[0] == risk_class
        assert batch.handoff_hash is not None


def test_top_level_public_api_surface_remains_bounded() -> None:
    assert len(frtb_drc.__all__) < 140


def test_batch_builder_adapter_compatibility_exports() -> None:
    import frtb_drc.adapters.positions as positions
    import frtb_drc.batch as batch

    names = (
        "build_drc_nonsec_batch_from_positions",
        "build_drc_nonsec_batch_from_columns",
        "build_drc_securitisation_non_ctp_batch_from_columns",
        "build_drc_ctp_batch_from_columns",
    )
    for name in names:
        assert getattr(batch, name) is getattr(positions, name)
        assert getattr(frtb_drc, name) is getattr(positions, name)


def test_arrow_adapter_compatibility_exports() -> None:
    import frtb_drc.adapters.arrow as adapter
    import frtb_drc.arrow_batch as compatibility

    names = (
        "DRC_NONSEC_ARROW_COLUMN_SPECS",
        "DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS",
        "DRC_CTP_ARROW_COLUMN_SPECS",
        "normalize_drc_nonsec_arrow_table",
        "normalize_drc_securitisation_non_ctp_arrow_table",
        "normalize_drc_ctp_arrow_table",
        "build_drc_nonsec_batch_from_arrow",
        "build_drc_securitisation_non_ctp_batch_from_arrow",
        "build_drc_ctp_batch_from_arrow",
        "build_drc_risk_weight_evidence_from_arrow",
        "build_drc_fair_value_cap_evidence_from_arrow",
    )
    for name in names:
        assert getattr(compatibility, name) is getattr(adapter, name)
        assert getattr(frtb_drc, name) is getattr(adapter, name)


def _public_api_doc() -> str:
    root = Path(__file__).resolve().parents[3]
    return (root / "docs/modules/frtb-drc/PUBLIC_API.md").read_text()


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures/handoff"
