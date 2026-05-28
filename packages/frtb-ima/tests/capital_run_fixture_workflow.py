"""Compatibility imports for the shared committed-fixture workflow."""

from __future__ import annotations

from frtb_ima.capital_run_fixture import (
    DEFAULT_CAPITAL_RUN_V1_ROOT as FIXTURE_ROOT,
)
from frtb_ima.capital_run_fixture import (
    run_capital_run_fixture_workflow,
)

__all__ = ["FIXTURE_ROOT", "run_capital_run_fixture_workflow"]
