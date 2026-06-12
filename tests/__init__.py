"""Root test helper package for cross-package fixtures.

Some package tests import helper modules through the historical ``tests.*``
namespace. When CI collects ``packages`` and root ``tests`` together, make that
namespace span package-local test helper directories too.
"""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
__path__ = [
    str(Path(__file__).resolve().parent),
    str(_REPO_ROOT / "packages" / "frtb-ima" / "tests"),
]
