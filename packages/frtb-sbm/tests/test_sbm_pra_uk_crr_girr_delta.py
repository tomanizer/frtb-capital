from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pyarrow as pa
import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    SbmInputError,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    build_sbm_batch,
    calculate_sbm_capital,
    calculate_sbm_capital_from_batch,
    serialize_sbm_result,
    validate_sbm_result_reconciliation,
)
from sbm_registry_helpers import (
    calculate_sbm_capital_from_path_arrow,
    normalize_sbm_path,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "girr_delta_pra_uk_crr_v1"


def load_fixture_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "girr_delta_pra_uk_crr_v1_loader",
        FIXTURE_DIR / "loader.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pra_uk_crr_girr_delta_fixture_matches_expected_outputs() -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()
    expected = loader.load_expected_outputs()

    result = calculate_sbm_capital(sensitivities, context=context)
    validate_sbm_result_reconciliation(result)
    payload = serialize_sbm_result(result)

    assert payload == expected
    assert not _contains_forbidden_non_pra_citation(payload)


def test_pra_uk_crr_girr_delta_batch_and_arrow_match_row_result() -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()

    row_payload = serialize_sbm_result(calculate_sbm_capital(sensitivities, context=context))
    batch = build_sbm_batch(sensitivities, SbmRiskClass.GIRR, SbmRiskMeasure.DELTA)
    batch_payload = serialize_sbm_result(calculate_sbm_capital_from_batch(batch, context=context))
    handoff = normalize_sbm_path(
        SbmRiskClass.GIRR, SbmRiskMeasure.DELTA, _arrow_table(sensitivities)
    )
    arrow_payload = serialize_sbm_result(
        calculate_sbm_capital_from_path_arrow(
            SbmRiskClass.GIRR, SbmRiskMeasure.DELTA, handoff, context=context
        )
    )

    assert batch_payload == row_payload
    assert arrow_payload["total_capital"] == row_payload["total_capital"]
    assert arrow_payload["profile_hash"] == row_payload["profile_hash"]
    assert arrow_payload["risk_classes"] == row_payload["risk_classes"]
    assert not _contains_forbidden_non_pra_citation(arrow_payload)


@pytest.mark.parametrize(
    ("case_id", "expected_error_match", "sensitivities"),
    load_fixture_module().load_invalid_cases(),
    ids=lambda item: item if isinstance(item, str) else None,
)
def test_pra_uk_crr_unsupported_fixture_cases_fail_closed(
    case_id: str,
    expected_error_match: str,
    sensitivities: tuple[object, ...],
) -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()

    with pytest.raises(
        (SbmInputError, UnsupportedRegulatoryFeatureError),
        match=expected_error_match,
    ):
        calculate_sbm_capital(sensitivities, context=context)
    assert case_id


def _arrow_table(sensitivities: tuple[SbmSensitivity, ...]) -> pa.Table:
    return pa.table(
        {
            "sensitivity_id": [item.sensitivity_id for item in sensitivities],
            "source_row_id": [item.source_row_id for item in sensitivities],
            "desk_id": [item.desk_id for item in sensitivities],
            "legal_entity": [item.legal_entity for item in sensitivities],
            "risk_class": [item.risk_class.value for item in sensitivities],
            "risk_measure": [item.risk_measure.value for item in sensitivities],
            "bucket": [item.bucket for item in sensitivities],
            "risk_factor": [item.risk_factor for item in sensitivities],
            "amount": [item.amount for item in sensitivities],
            "amount_currency": [item.amount_currency for item in sensitivities],
            "sign_convention": [item.sign_convention.value for item in sensitivities],
            "tenor": [item.tenor for item in sensitivities],
            "lineage_source_system": [
                item.lineage.source_system if item.lineage else None for item in sensitivities
            ],
            "lineage_source_file": [
                item.lineage.source_file if item.lineage else None for item in sensitivities
            ],
        }
    )


def _contains_forbidden_non_pra_citation(payload: object) -> bool:
    if isinstance(payload, dict):
        return any(_contains_forbidden_non_pra_citation(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_forbidden_non_pra_citation(value) for value in payload)
    return isinstance(payload, str) and (
        payload.startswith("basel_") or payload.startswith("eu_") or payload.startswith("us_npr_")
    )
