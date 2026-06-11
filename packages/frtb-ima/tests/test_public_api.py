"""Tests for package-level public API consistency."""

from frtb_common import ImplementationStatus, ValidationStatus

import frtb_ima


def test_all_exports_resolve_to_package_attributes() -> None:
    exported_names = frtb_ima.__all__

    assert len(exported_names) == len(set(exported_names))
    for name in exported_names:
        assert hasattr(frtb_ima, name), name


def test_package_metadata_reports_implemented_ima_status() -> None:
    assert frtb_ima.PACKAGE_METADATA.package_name == "frtb-ima"
    assert frtb_ima.PACKAGE_METADATA.import_name == "frtb_ima"
    assert frtb_ima.PACKAGE_METADATA.implementation_status is ImplementationStatus.IMPLEMENTED
    assert frtb_ima.PACKAGE_METADATA.validation_status is ValidationStatus.AVAILABLE


def test_arrow_batch_compatibility_path_exports_adapter_names() -> None:
    import frtb_ima.adapters.arrow as arrow
    import frtb_ima.arrow_batch as compatibility

    expected_names = (
        "IMA_INPUT_MANIFEST_ARROW_COLUMN_SPECS",
        "IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS",
        "IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS",
        "build_capital_run_input_manifest_from_arrow",
        "build_rfet_observation_batch_from_arrow",
        "build_scenario_metadata_batch_from_arrow",
        "normalize_ima_input_manifest_arrow_table",
        "normalize_ima_rfet_observation_arrow_table",
        "normalize_ima_scenario_metadata_arrow_table",
    )

    assert compatibility.__all__ == arrow.__all__
    for name in expected_names:
        assert getattr(compatibility, name) is getattr(arrow, name)
