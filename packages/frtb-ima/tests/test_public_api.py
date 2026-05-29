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
