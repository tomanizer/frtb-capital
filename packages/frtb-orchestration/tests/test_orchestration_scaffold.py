import pytest
from frtb_common import ImplementationStatus, NotImplementedCapitalComponentError
from frtb_orchestration import PACKAGE_METADATA, __version__, calculate_suite_capital


def test_orchestration_package_imports_with_scaffold_status() -> None:
    assert isinstance(__version__, str)
    assert PACKAGE_METADATA.package_name == "frtb-orchestration"
    assert PACKAGE_METADATA.import_name == "frtb_orchestration"
    assert PACKAGE_METADATA.implementation_status is ImplementationStatus.SCAFFOLDED


def test_suite_capital_aggregation_fails_explicitly() -> None:
    with pytest.raises(NotImplementedCapitalComponentError, match="suite capital aggregation"):
        calculate_suite_capital()
