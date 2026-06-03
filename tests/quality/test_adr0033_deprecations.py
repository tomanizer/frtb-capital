from __future__ import annotations

import importlib


def test_common_old_handoff_aliases_are_removed() -> None:
    common = importlib.import_module("frtb_common")
    arrow_conversion = importlib.import_module("frtb_common.arrow_conversion")
    schema = importlib.import_module("frtb_common.arrow_table_schema")

    removed = (
        "ComponentHandoffError",
        "ComponentResultHandoff",
        "NormalizedTabularHandoff",
        "TabularHandoffError",
        "normalized_handoff_hash",
        "read_handoff_columns",
        "handoff_specs_to_arrow_schema",
        "handoff_specs_to_json_schema",
    )
    for name in removed:
        assert not hasattr(common, name)
        assert name not in common.__all__

    assert not hasattr(arrow_conversion, "HandoffColumnArray")
    assert not hasattr(arrow_conversion, "read_handoff_columns")
    assert not hasattr(schema, "handoff_specs_to_arrow_schema")
    assert not hasattr(schema, "handoff_specs_to_json_schema")


def test_component_package_old_handoff_exports_are_removed() -> None:
    packages = {
        "frtb_rrao": (
            "RRAO_HANDOFF_COLUMN_SPECS",
            "build_rrao_batch_from_handoff",
            "to_orchestration_handoff",
        ),
        "frtb_drc": (
            "DRC_NONSEC_HANDOFF_COLUMN_SPECS",
            "build_drc_nonsec_batch_from_handoff",
            "to_orchestration_handoff",
        ),
        "frtb_cva": (
            "CVA_COUNTERPARTY_HANDOFF_COLUMN_SPECS",
            "build_cva_counterparty_batch_from_handoff",
        ),
        "frtb_ima": (
            "IMA_SCENARIO_METADATA_HANDOFF_COLUMN_SPECS",
            "build_scenario_metadata_batch_from_handoff",
        ),
        "frtb_sbm": (
            "GIRR_DELTA_HANDOFF_COLUMN_SPECS",
            "build_girr_delta_batch_from_handoff",
            "calculate_sbm_portfolio_capital_from_handoffs",
            "to_orchestration_handoff",
        ),
    }

    for package_name, names in packages.items():
        package = importlib.import_module(package_name)
        for name in names:
            assert not hasattr(package, name), f"{package_name}.{name} remains exported"
            assert name not in package.__all__


def test_orchestration_old_handoff_exports_are_removed() -> None:
    orchestration = importlib.import_module("frtb_orchestration")

    removed = (
        "SBM_GIRR_DELTA_HANDOFF",
        "STANDARDISED_REQUIRED_HANDOFF_KEYS",
        "ManifestHandoffRoute",
        "ManifestHandoffValidation",
        "CvaResultHandoff",
    )
    for name in removed:
        assert not hasattr(orchestration, name)
        assert name not in orchestration.__all__
