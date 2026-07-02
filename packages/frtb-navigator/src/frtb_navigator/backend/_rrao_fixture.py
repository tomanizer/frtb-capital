"""Load the committed RRAO sample-book fixture for Navigator demos."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_rrao_fixture_module() -> ModuleType:
    fixture_path = (
        Path(__file__).resolve().parents[5]
        / "packages"
        / "frtb-rrao"
        / "examples"
        / "rrao_fixture.py"
    )
    if not fixture_path.exists():
        raise ImportError(f"RRAO fixture module not found at {fixture_path}")
    spec = importlib.util.spec_from_file_location("rrao_fixture", fixture_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load RRAO fixture module from {fixture_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_rrao_context() -> Any:
    """Return the committed RRAO sample-book calculation context.

    Returns
    -------
    Any
        RRAO calculation context loaded from the package example fixture.
    """

    return _load_rrao_fixture_module().load_context()


def load_rrao_positions() -> Any:
    """Return the committed RRAO sample-book positions.

    Returns
    -------
    Any
        RRAO positions loaded from the package example fixture.
    """

    return _load_rrao_fixture_module().load_positions()
