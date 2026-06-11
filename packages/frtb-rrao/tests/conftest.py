"""Shared pytest configuration for FRTB-RRAO tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from hypothesis import settings

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

settings.register_profile(
    "dev",
    max_examples=100,
    deadline=None,
    derandomize=True,
    database=None,
)
settings.register_profile(
    "ci",
    max_examples=500,
    deadline=None,
    derandomize=True,
    database=None,
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
