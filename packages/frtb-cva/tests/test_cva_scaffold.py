import pytest
from frtb_common import ImplementationStatus, NotImplementedCapitalComponentError
from frtb_cva import PACKAGE_METADATA, __version__, calculate_cva_capital


def test_cva_package_imports_with_scaffold_status() -> None:
    assert isinstance(__version__, str)
    assert PACKAGE_METADATA.package_name == "frtb-cva"
    assert PACKAGE_METADATA.import_name == "frtb_cva"
    assert PACKAGE_METADATA.implementation_status is ImplementationStatus.SCAFFOLDED


def test_cva_calculation_fails_explicitly() -> None:
    with pytest.raises(NotImplementedCapitalComponentError, match="CVA capital calculation"):
        calculate_cva_capital()
