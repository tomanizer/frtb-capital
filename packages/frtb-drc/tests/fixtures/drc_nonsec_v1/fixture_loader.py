"""Loader for the committed DRC non-securitisation v1 fixture."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, cast

from frtb_drc import DrcCalculationContext, DrcPosition, DrcSourceLineage

FIXTURE_DIR = Path(__file__).resolve().parent
POSITIONS_PATH = FIXTURE_DIR / "positions.json"
EXPECTED_PATH = FIXTURE_DIR / "expected_outputs.json"


def load_context() -> DrcCalculationContext:
    payload = _load_json(POSITIONS_PATH)
    context = cast(dict[str, str], payload["context"])
    return DrcCalculationContext(
        run_id=context["run_id"],
        calculation_date=date.fromisoformat(context["calculation_date"]),
        base_currency=context["base_currency"],
        profile_id=context["profile_id"],
    )


def load_positions() -> tuple[DrcPosition, ...]:
    payload = _load_json(POSITIONS_PATH)
    positions: list[DrcPosition] = []
    for raw_position in cast(list[dict[str, Any]], payload["positions"]):
        position = dict(raw_position)
        position["lineage"] = DrcSourceLineage(**position["lineage"])
        positions.append(DrcPosition(**position))
    return tuple(positions)


def load_expected_outputs() -> dict[str, object]:
    return _load_json(EXPECTED_PATH)


def _load_json(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
