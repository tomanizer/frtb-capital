from frtb_common import ImplementationStatus
from frtb_sbm import PACKAGE_METADATA, __version__, calculate_sbm_capital


def test_sbm_package_imports_with_partial_runtime_status() -> None:
    assert isinstance(__version__, str)
    assert PACKAGE_METADATA.package_name == "frtb-sbm"
    assert PACKAGE_METADATA.import_name == "frtb_sbm"
    assert PACKAGE_METADATA.implementation_status is ImplementationStatus.PARTIAL


def test_sbm_calculation_entrypoint_is_callable() -> None:
    assert callable(calculate_sbm_capital)
