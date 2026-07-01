"""Load the committed RRAO sample-book fixture for dashboard demos."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_rrao_fixture_module() -> ModuleType:
    fixture_path = (
        Path(__file__).resolve().parents[3]
        / "packages"
        / "frtb-rrao"
        / "examples"
        / "rrao_fixture.py"
    )
    spec = importlib.util.spec_from_file_location("rrao_fixture", fixture_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load RRAO fixture module from {fixture_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_rrao_context() -> Any:
    return _load_rrao_fixture_module().load_context()


def load_rrao_positions() -> Any:
    return _load_rrao_fixture_module().load_positions()
