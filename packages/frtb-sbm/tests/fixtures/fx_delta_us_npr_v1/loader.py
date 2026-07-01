from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from frtb_sbm import SbmCalculationContext, SbmSensitivity

from tests.sbm_fixture_helpers import (
    load_sbm_fixture_context,
    load_sbm_invalid_cases,
    sbm_sensitivity_from_payload,
)

FIXTURE_DIR = Path(__file__).parent


def load_fixture_context() -> SbmCalculationContext:
    return load_sbm_fixture_context(_load_json("sensitivities.json"))


def load_fixture_sensitivities() -> tuple[SbmSensitivity, ...]:
    payload = _load_json("sensitivities.json")
    return tuple(_sensitivity_from_payload(sensitivity) for sensitivity in payload["sensitivities"])


def load_expected_outputs() -> dict[str, object]:
    return _load_json("expected_outputs.json")


def load_invalid_cases() -> tuple[tuple[str, str, tuple[SbmSensitivity, ...]], ...]:
    return load_sbm_invalid_cases(_load_json("invalid_cases.json"), _sensitivity_from_payload)


def _sensitivity_from_payload(payload: dict[str, Any]) -> SbmSensitivity:
    return sbm_sensitivity_from_payload(
        payload,
        text_fields=("option_tenor", "tenor", "qualifier"),
        int_fields=(),
        float_fields=("up_shock_amount", "down_shock_amount"),
    )


def _load_json(name: str) -> dict[str, object]:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)
