"""Shared pytest configuration for FRTB-IMA tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType

from hypothesis import settings

if os.environ.get("FRTB_IMA_MUTATION_IMPORT"):
    src_package = Path(__file__).resolve().parents[1] / "src" / "frtb_ima"
    package = ModuleType("frtb_ima")
    package.__path__ = [str(src_package)]  # type: ignore[attr-defined]
    sys.modules["frtb_ima"] = package

settings.register_profile(
    "dev",
    max_examples=100,
    deadline=None,
    derandomize=True,
    database=None,
)
settings.register_profile(
    "ci",
    max_examples=1000,
    deadline=None,
    derandomize=True,
    database=None,
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
