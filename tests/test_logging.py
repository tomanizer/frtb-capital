"""Tests for structured logging helpers."""

import io
import json
import logging

import pytest

from frtb_ima.data_models import LiquidityHorizon, RiskClass
from frtb_ima.imcc import imcc_for_policy
from frtb_ima.logging import JSONFormatter, configure_json_logging
from frtb_ima.regimes import get_policy


class _SerializableResult:
    def as_dict(self) -> dict[str, object]:
        return {"value": 12.5}


def test_json_formatter_includes_structured_extra_fields() -> None:
    stream = io.StringIO()
    logger = logging.getLogger("tests.frtb_json_formatter")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    logger.info(
        "imcc_complete",
        extra={
            "run_id": "run-1",
            "desk_id": "desk-1",
            "regime": "FED_NPR_2_0",
            "imcc": 123.4,
        },
    )

    payload = json.loads(stream.getvalue())
    assert payload["msg"] == "imcc_complete"
    assert payload["run_id"] == "run-1"
    assert payload["desk_id"] == "desk-1"
    assert payload["regime"] == "FED_NPR_2_0"
    assert payload["imcc"] == pytest.approx(123.4)


def test_json_formatter_uses_canonical_json_conversion() -> None:
    stream = io.StringIO()
    logger = logging.getLogger("tests.frtb_json_formatter_canonical")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    logger.info(
        "event",
        extra={
            "result": _SerializableResult(),
            "error": RuntimeError("pricing failed"),
        },
    )

    payload = json.loads(stream.getvalue())
    assert payload["result"] == {"value": pytest.approx(12.5)}
    assert payload["error"] == "RuntimeError('pricing failed')"


def test_configure_json_logging_returns_attached_handler() -> None:
    stream = io.StringIO()
    logger_name = "tests.frtb_configure_json_logging"
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()
    logger.propagate = False

    handler = configure_json_logging(stream=stream, logger_name=logger_name)
    logger.info("event", extra={"run_id": "run-2"})

    assert handler in logger.handlers
    assert json.loads(stream.getvalue())["run_id"] == "run-2"


def test_policy_wrapper_emits_correlatable_log_record(caplog: pytest.LogCaptureFixture) -> None:
    policy = get_policy()
    vectors = {LiquidityHorizon.LH10: [1.0, 2.0, 3.0]}
    per_class = {RiskClass.GIRR: vectors}

    with caplog.at_level(logging.INFO, logger="frtb_ima.imcc"):
        imcc_for_policy(
            vectors,
            per_class,
            policy,
            run_id="run-3",
            desk_id="desk-3",
        )

    record = next(record for record in caplog.records if record.getMessage() == "imcc_complete")
    assert record.run_id == "run-3"
    assert record.desk_id == "desk-3"
    assert record.regime == policy.regime.value
    assert record.imcc >= 0.0


def test_policy_wrapper_without_run_or_desk_logs_cleanly(
    caplog: pytest.LogCaptureFixture,
) -> None:
    policy = get_policy()
    vectors = {LiquidityHorizon.LH10: [1.0, 2.0, 3.0]}
    per_class = {RiskClass.GIRR: vectors}

    with caplog.at_level(logging.INFO, logger="frtb_ima.imcc"):
        imcc_for_policy(vectors, per_class, policy)

    record = next(record for record in caplog.records if record.getMessage() == "imcc_complete")
    assert not hasattr(record, "run_id")
    assert not hasattr(record, "desk_id")
    assert record.regime == policy.regime.value
