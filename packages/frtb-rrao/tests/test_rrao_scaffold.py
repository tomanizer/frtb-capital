import pytest
from frtb_common import ImplementationStatus, ValidationStatus
from frtb_rrao import PACKAGE_METADATA, RraoInputError, __version__, calculate_rrao_capital


def test_rrao_package_imports_with_partial_status() -> None:
    assert isinstance(__version__, str)
    assert PACKAGE_METADATA.package_name == "frtb-rrao"
    assert PACKAGE_METADATA.import_name == "frtb_rrao"
    assert PACKAGE_METADATA.implementation_status is ImplementationStatus.PARTIAL
    assert PACKAGE_METADATA.validation_status is ValidationStatus.PENDING


def test_rrao_calculation_requires_inputs() -> None:
    with pytest.raises(RraoInputError, match="positions are required"):
        calculate_rrao_capital()
