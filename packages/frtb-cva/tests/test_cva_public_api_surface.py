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

REGISTRY_SURFACE = (
    "CVA_COUNTERPARTY_ENTITY_SPEC",
    "CVA_ENTITY_BATCH_SPECS",
    "CVA_HEDGE_ENTITY_SPEC",
    "CVA_NETTING_SET_ENTITY_SPEC",
    "SA_CVA_SENSITIVITY_ENTITY_SPEC",
    "EntityBatchSpec",
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


def test_entity_registry_is_public_and_legacy_path_is_compatible() -> None:
    import frtb_cva._arrow_entity_specs as legacy_registry
    import frtb_cva.registry as registry

    documented = _public_api_doc()
    for name in REGISTRY_SURFACE:
        assert name in frtb_cva.__all__
        assert getattr(frtb_cva, name) is getattr(registry, name)
        assert getattr(legacy_registry, name) is getattr(registry, name)
        assert name in registry.__all__
        assert name in legacy_registry.__all__
        assert f"`{name}`" in documented

    assert tuple(registry.CVA_ENTITY_BATCH_SPECS) == (
        "counterparty",
        "netting_set",
        "hedge",
        "sa_cva_sensitivity",
    )


def test_arrow_adapter_compatibility_path_exports_same_surface() -> None:
    import frtb_cva.adapters.arrow as arrow_adapter
    import frtb_cva.arrow_batch as arrow_batch

    names = (
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
        "normalize_cva_arrow_table",
        "build_cva_batch_from_arrow",
    )
    for name in names:
        assert getattr(arrow_batch, name) is getattr(arrow_adapter, name)
        assert name in arrow_adapter.__all__
        assert name in arrow_batch.__all__


def test_batch_adapter_compatibility_paths_export_same_builders() -> None:
    import frtb_cva._batch_adapters as legacy_columns
    import frtb_cva._batch_counterparty_adapter as legacy_counterparty
    import frtb_cva._batch_hedge_adapter as legacy_hedge
    import frtb_cva._batch_netting_set_adapter as legacy_netting_set
    import frtb_cva._batch_row_adapters as legacy_rows
    import frtb_cva._batch_sensitivity_adapters as legacy_sensitivity
    import frtb_cva.adapters.columns as columns
    import frtb_cva.adapters.counterparty as counterparty
    import frtb_cva.adapters.hedge as hedge
    import frtb_cva.adapters.netting_set as netting_set
    import frtb_cva.adapters.rows as rows
    import frtb_cva.adapters.sensitivity as sensitivity

    pairs = (
        (legacy_columns, columns, "build_cva_counterparty_batch_from_columns"),
        (legacy_columns, columns, "build_cva_netting_set_batch_from_columns"),
        (legacy_columns, columns, "build_cva_hedge_batch_from_columns"),
        (legacy_counterparty, counterparty, "build_cva_counterparty_batch_from_columns"),
        (legacy_netting_set, netting_set, "build_cva_netting_set_batch_from_columns"),
        (legacy_hedge, hedge, "build_cva_hedge_batch_from_columns"),
        (legacy_sensitivity, sensitivity, "build_sa_cva_sensitivity_batch_from_columns"),
        (legacy_rows, rows, "build_cva_counterparty_batch_from_counterparties"),
        (legacy_rows, rows, "build_cva_netting_set_batch_from_netting_sets"),
        (legacy_rows, rows, "build_cva_hedge_batch_from_hedges"),
        (legacy_rows, rows, "build_sa_cva_sensitivity_batch_from_sensitivities"),
    )
    for legacy_module, adapter_module, name in pairs:
        assert getattr(legacy_module, name) is getattr(adapter_module, name)


def test_validation_stage_package_and_legacy_batch_path_are_compatible() -> None:
    import frtb_cva._batch_validation as legacy_batch_validation
    import frtb_cva.validation as validation
    import frtb_cva.validation.batches as batch_validation

    assert validation.CvaInputError is frtb_cva.CvaInputError

    names = (
        "_netting_indices_by_counterparty",
        "_resolve_scope_for_batches",
        "_validate_ba_relationships",
        "_validate_hedge_batch",
        "_validate_netting_set_batch",
        "_validate_sensitivity_batch",
    )
    for name in names:
        assert getattr(legacy_batch_validation, name) is getattr(batch_validation, name)
        assert name in legacy_batch_validation.__all__
        assert name in batch_validation.__all__


def test_assembly_compatibility_paths_export_same_helpers() -> None:
    import frtb_cva._batch_assembly as legacy_assembly
    import frtb_cva._batch_payloads as legacy_batch_payloads
    import frtb_cva._payloads as legacy_payloads
    import frtb_cva.assembly.batch_payloads as batch_payloads
    import frtb_cva.assembly.batches as batches
    import frtb_cva.assembly.payloads as payloads

    pairs = (
        (legacy_assembly, batches, "calculate_cva_capital_from_batches"),
        (legacy_batch_payloads, batch_payloads, "input_hash_for_cva_batches"),
        (legacy_payloads, payloads, "hash_payload"),
        (legacy_payloads, payloads, "input_payload"),
        (legacy_payloads, payloads, "batch_input_payload"),
    )
    for legacy_module, assembly_module, name in pairs:
        assert getattr(legacy_module, name) is getattr(assembly_module, name)


def test_kernel_compatibility_paths_export_same_helpers() -> None:
    import frtb_cva._ba_batch_kernel as legacy_ba
    import frtb_cva._ba_full_batch_kernel as legacy_ba_full
    import frtb_cva._ba_reduced_batch_kernel as legacy_ba_reduced
    import frtb_cva._sa_batch_kernel as legacy_sa
    import frtb_cva.kernel.ba as ba
    import frtb_cva.kernel.ba_full as ba_full
    import frtb_cva.kernel.ba_reduced as ba_reduced
    import frtb_cva.kernel.sa as sa

    pairs = (
        (legacy_ba, ba, "calculate_full_portfolio_from_batches"),
        (legacy_ba, ba, "calculate_reduced_portfolio_from_batches"),
        (legacy_ba_full, ba_full, "calculate_full_portfolio_from_batches"),
        (legacy_ba_reduced, ba_reduced, "calculate_reduced_portfolio_from_batches"),
        (legacy_sa, sa, "calculate_sa_cva_capital_from_batch"),
    )
    for legacy_module, kernel_module, name in pairs:
        assert getattr(legacy_module, name) is getattr(kernel_module, name)


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
    assert len(frtb_cva.__all__) < 132


def _public_api_doc() -> str:
    root = Path(__file__).resolve().parents[3]
    return (root / "docs/modules/frtb-cva/PUBLIC_API.md").read_text()


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures/handoff"
