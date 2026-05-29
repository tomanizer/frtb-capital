import pytest
from frtb_common import ImplementationStatus, NotImplementedCapitalComponentError
from frtb_rrao import PACKAGE_METADATA, __version__, calculate_rrao_capital


def test_rrao_package_imports_with_scaffold_status() -> None:
    assert isinstance(__version__, str)
    assert PACKAGE_METADATA.package_name == "frtb-rrao"
    assert PACKAGE_METADATA.import_name == "frtb_rrao"
    assert PACKAGE_METADATA.implementation_status is ImplementationStatus.SCAFFOLDED


def test_rrao_calculation_fails_explicitly() -> None:
    with pytest.raises(NotImplementedCapitalComponentError, match="RRAO capital calculation"):
        calculate_rrao_capital()
