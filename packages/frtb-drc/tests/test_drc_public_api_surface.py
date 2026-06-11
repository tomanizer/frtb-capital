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
    import frtb_drc.adapters.arrow_evidence as evidence
    import frtb_drc.adapters.path_registry as paths
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

    evidence_names = (
        "DRC_RISK_WEIGHT_EVIDENCE_ARROW_COLUMN_SPECS",
        "DRC_FAIR_VALUE_CAP_EVIDENCE_ARROW_COLUMN_SPECS",
        "normalize_drc_risk_weight_evidence_arrow_table",
        "normalize_drc_fair_value_cap_evidence_arrow_table",
        "build_drc_risk_weight_evidence_from_arrow",
        "build_drc_securitisation_non_ctp_risk_weight_evidence_from_arrow",
        "build_drc_ctp_risk_weight_evidence_from_arrow",
        "build_drc_fair_value_cap_evidence_from_arrow",
    )
    for name in evidence_names:
        assert getattr(adapter, name) is getattr(evidence, name)
        assert getattr(compatibility, name) is getattr(evidence, name)
        assert getattr(frtb_drc, name) is getattr(evidence, name)

    assert (
        adapter.DRC_NONSEC_ARROW_COLUMN_SPECS
        is paths.get_drc_path_spec(paths.DRC_NONSEC_PATH).arrow_column_specs
    )
    assert (
        adapter.DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS
        is paths.get_drc_path_spec(paths.DRC_SECURITISATION_NON_CTP_PATH).arrow_column_specs
    )
    assert (
        adapter.DRC_CTP_ARROW_COLUMN_SPECS
        is paths.get_drc_path_spec(paths.DRC_CTP_PATH).arrow_column_specs
    )
    assert paths.drc_path_spec_for_risk_class(
        frtb_drc.DrcRiskClass.NON_SECURITISATION
    ) is paths.get_drc_path_spec(paths.DRC_NONSEC_PATH)


def test_hash_assembly_compatibility_exports() -> None:
    import frtb_drc.assembly.hashes as hashes
    import frtb_drc.batch as batch

    assert batch.input_hash_for_drc_batch is hashes.input_hash_for_drc_batch
    assert frtb_drc.input_hash_for_drc_batch is hashes.input_hash_for_drc_batch


def test_batch_validation_and_citation_stages_are_bounded() -> None:
    import frtb_drc.assembly.citations as citations
    import frtb_drc.assembly.fair_value_cap as fair_value_cap
    import frtb_drc.batch_validation as validation

    assert set(validation.__all__) == {
        "batch_risk_class",
        "validate_batch_columns",
        "validate_batch_context",
        "validate_supported_batch_run",
    }
    assert "collect_batch_citations" in citations.__all__
    assert "batch_fair_value_cap_citations" in fair_value_cap.__all__
    assert "fair_value_cap_branch_metadata_for_batch" in fair_value_cap.__all__

    root = Path(__file__).resolve().parents[3]
    batch_lines = (root / "packages/frtb-drc/src/frtb_drc/batch.py").read_text().splitlines()
    assert len(batch_lines) < 800


def test_net_jtd_kernel_stage_exports() -> None:
    import frtb_drc.kernel.net_jtd as net_jtd

    names = (
        "calculate_nonsec_net_jtds_from_arrays",
        "calculate_securitisation_non_ctp_net_jtds_from_arrays",
        "calculate_ctp_net_jtds_from_arrays",
    )

    assert set(net_jtd.__all__) == set(names)
    for name in names:
        assert callable(getattr(net_jtd, name))


def test_nonsec_kernel_stage_exports() -> None:
    import frtb_drc.kernel.nonsec as nonsec

    names = (
        "NonSecuritisationCalculation",
        "calculate_nonsec_drc",
        "nonsec_netting_citation",
    )

    assert set(nonsec.__all__) == set(names)
    for name in names:
        assert hasattr(nonsec, name)


def test_ctp_kernel_compatibility_exports() -> None:
    import frtb_drc.ctp as compatibility
    import frtb_drc.kernel.ctp as kernel

    names = (
        "CtpCalculation",
        "CtpCapitalInput",
        "CtpNettingInput",
        "calculate_ctp_category_drc",
        "calculate_ctp_drc",
        "calculate_ctp_gross_jtd",
        "calculate_ctp_net_jtds",
        "ctp_context_input_hash",
        "validate_ctp_context",
    )

    assert set(compatibility.__all__) == set(kernel.__all__)
    for name in names:
        assert getattr(compatibility, name) is getattr(kernel, name)

    top_level_names = set(names) - {"ctp_context_input_hash"}
    for name in top_level_names:
        assert getattr(frtb_drc, name) is getattr(kernel, name)


def test_securitisation_kernel_compatibility_exports() -> None:
    import frtb_drc.kernel.securitisation as kernel
    import frtb_drc.securitisation as compatibility

    names = (
        "SecuritisationNonCtpCalculation",
        "SecuritisationNonCtpCapitalInput",
        "SecuritisationNonCtpNettingInput",
        "calculate_securitisation_non_ctp_category_drc",
        "calculate_securitisation_non_ctp_drc",
        "calculate_securitisation_non_ctp_gross_jtd",
        "calculate_securitisation_non_ctp_net_jtds",
        "securitisation_non_ctp_context_input_hash",
        "validate_securitisation_non_ctp_context",
    )

    assert set(compatibility.__all__) == set(kernel.__all__)
    for name in names:
        assert getattr(compatibility, name) is getattr(kernel, name)

    top_level_names = set(names) - {"securitisation_non_ctp_context_input_hash"}
    for name in top_level_names:
        assert getattr(frtb_drc, name) is getattr(kernel, name)


def test_securitisation_stage_helpers_are_bounded() -> None:
    import frtb_drc.kernel.securitisation_context as context
    import frtb_drc.kernel.securitisation_gross as gross

    assert "validate_securitisation_non_ctp_context_for_positions" in context.__all__
    assert "fair_value_capped_gross_jtd" in gross.__all__


def _public_api_doc() -> str:
    root = Path(__file__).resolve().parents[3]
    return (root / "docs/modules/frtb-drc/PUBLIC_API.md").read_text()


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures/handoff"
