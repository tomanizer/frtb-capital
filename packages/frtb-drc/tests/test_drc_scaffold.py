import pytest
from frtb_common import ImplementationStatus, NotImplementedCapitalComponentError
from frtb_drc import PACKAGE_METADATA, __version__, calculate_drc_capital


def test_drc_package_imports_with_scaffold_status() -> None:
    assert isinstance(__version__, str)
    assert PACKAGE_METADATA.package_name == "frtb-drc"
    assert PACKAGE_METADATA.import_name == "frtb_drc"
    assert PACKAGE_METADATA.implementation_status is ImplementationStatus.SCAFFOLDED


def test_drc_calculation_fails_explicitly() -> None:
    with pytest.raises(NotImplementedCapitalComponentError, match="DRC capital calculation"):
        calculate_drc_capital()
