import pytest
from frtb_common import ImplementationStatus, NotImplementedCapitalComponentError
from frtb_sbm import PACKAGE_METADATA, __version__, calculate_sbm_capital


def test_sbm_package_imports_with_scaffold_status() -> None:
    assert isinstance(__version__, str)
    assert PACKAGE_METADATA.package_name == "frtb-sbm"
    assert PACKAGE_METADATA.import_name == "frtb_sbm"
    assert PACKAGE_METADATA.implementation_status is ImplementationStatus.SCAFFOLDED


def test_sbm_calculation_fails_explicitly() -> None:
    with pytest.raises(NotImplementedCapitalComponentError, match="SBM capital calculation"):
        calculate_sbm_capital()
