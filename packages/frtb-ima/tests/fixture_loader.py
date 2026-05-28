"""Compatibility imports for tests using the shared capital-run fixture loader."""

from frtb_ima.capital_run_fixture import (
    CapitalRunFixture,
    _verify_manifest_checksums,
    load_capital_run_fixture,
)

__all__ = [
    "CapitalRunFixture",
    "_verify_manifest_checksums",
    "load_capital_run_fixture",
]
