from datetime import date

import pytest
from frtb_common import ImplementationStatus
from frtb_drc import (
    PACKAGE_METADATA,
    US_NPR_2_0_PROFILE_ID,
    DrcCalculationContext,
    DrcInputError,
    __version__,
    calculate_drc_capital,
)


def test_drc_package_imports_with_scaffold_status() -> None:
    assert isinstance(__version__, str)
    assert PACKAGE_METADATA.package_name == "frtb-drc"
    assert PACKAGE_METADATA.import_name == "frtb_drc"
    assert PACKAGE_METADATA.implementation_status is ImplementationStatus.PARTIAL


def test_drc_calculation_requires_positions() -> None:
    with pytest.raises(DrcInputError, match="at least one position"):
        calculate_drc_capital(
            (),
            context=DrcCalculationContext(
                run_id="run-empty",
                calculation_date=date(2026, 5, 29),
                base_currency="USD",
                profile_id=US_NPR_2_0_PROFILE_ID,
            ),
        )
