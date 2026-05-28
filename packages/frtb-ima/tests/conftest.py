"""Shared pytest configuration for FRTB-IMA tests."""

from __future__ import annotations

import os

from hypothesis import settings

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
