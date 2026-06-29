"""IMA test package namespace bridge.

Pytest can import this package as top-level ``tests`` when collection starts
under ``packages/frtb-ima/tests``. Keep the historical root test helpers
available for package suites that import ``tests.sbm_fixture_helpers`` and
similar shared modules during the same collection run.
"""

from pathlib import Path

_PACKAGE_TESTS = Path(__file__).resolve().parent
_REPO_ROOT_TESTS = _PACKAGE_TESTS.parents[2] / "tests"

__path__ = [
    str(_PACKAGE_TESTS),
    str(_REPO_ROOT_TESTS),
]
