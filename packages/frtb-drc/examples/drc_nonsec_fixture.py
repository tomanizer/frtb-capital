"""Compatibility re-exports for the DRC non-securitisation fixture."""

from __future__ import annotations

from frtb_drc.demo_fixture import (
    DEFAULT_DRC_NONSEC_V2_ROOT,
    DrcNonSecFixture,
    load_drc_nonsec_fixture,
    load_drc_nonsec_v2_fixture,
    run_fixture_workflow,
)

__all__ = [
    "DEFAULT_DRC_NONSEC_V2_ROOT",
    "DrcNonSecFixture",
    "load_drc_nonsec_fixture",
    "load_drc_nonsec_v2_fixture",
    "run_fixture_workflow",
]
