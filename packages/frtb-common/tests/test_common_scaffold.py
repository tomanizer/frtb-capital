from dataclasses import FrozenInstanceError

import pytest
from frtb_common import (
    CapitalComponentMetadata,
    ImplementationStatus,
    NotImplementedCapitalComponentError,
    UnsupportedRegulatoryFeatureError,
    ValidationStatus,
    __version__,
)


def test_common_exports_version_and_status_metadata() -> None:
    metadata = CapitalComponentMetadata(
        package_name="frtb-common",
        import_name="frtb_common",
        component_name="shared primitives",
        implementation_status=ImplementationStatus.SCAFFOLDED,
        validation_status=ValidationStatus.NOT_STARTED,
    )

    assert isinstance(__version__, str)
    assert metadata.implementation_status is ImplementationStatus.SCAFFOLDED
    with pytest.raises(FrozenInstanceError):
        metadata.package_name = "mutated"  # type: ignore[misc]


def test_not_implemented_component_error_is_explicit_unsupported_error() -> None:
    error = NotImplementedCapitalComponentError(
        component="frtb-sbm",
        feature="SBM capital calculation",
    )

    assert isinstance(error, UnsupportedRegulatoryFeatureError)
    assert error.component == "frtb-sbm"
    assert error.feature == "SBM capital calculation"
    assert "does not implement" in str(error)
