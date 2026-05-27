"""
Structured logging helpers for FRTB IMA orchestration.

The calculation core returns result objects. Policy wrappers may emit compact
runtime events for observability, but they must never log scenario arrays or
change numerical results.

Regulatory traceability:
    Supports auditability and run traceability for Basel MAR31-MAR33, U.S. NPR
    2.0 model-risk governance working assumptions, and EU CRR internal-model
    governance. See docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

import json
import logging as py_logging
import sys
from collections.abc import Mapping
from typing import TextIO

from frtb_ima.audit import _jsonable

_STANDARD_LOG_RECORD_ATTRIBUTES = frozenset(
    py_logging.LogRecord(
        name="",
        level=0,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    ).__dict__
) | {"asctime", "message"}


class JSONFormatter(py_logging.Formatter):
    """Format log records as one compact JSON object per line."""

    def format(self, record: py_logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        legacy_extra = record.__dict__.get("extra")
        if isinstance(legacy_extra, Mapping):
            payload.update(
                {
                    str(key): _jsonable(value)
                    for key, value in legacy_extra.items()
                }
            )

        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_ATTRIBUTES and key != "extra":
                payload[key] = _jsonable(value)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def calculation_log_extra(
    *,
    run_id: str | None = None,
    desk_id: str | None = None,
    regime: str | None = None,
    **fields: object,
) -> dict[str, object]:
    """Build safe structured fields for calculation-boundary log records."""
    extra: dict[str, object] = {}
    if run_id is not None:
        extra["run_id"] = run_id
    if desk_id is not None:
        extra["desk_id"] = desk_id
    if regime is not None:
        extra["regime"] = regime
    extra.update(fields)
    return extra


def configure_json_logging(
    *,
    level: int | str = py_logging.INFO,
    stream: TextIO | None = None,
    logger_name: str | None = None,
) -> py_logging.Handler:
    """
    Attach a JSON log handler to the root logger or a named logger.

    Applications own logging configuration. This helper is intentionally small
    and dependency-free for examples, demos, and simple runners.
    """
    logger = py_logging.getLogger(logger_name)
    handler = py_logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    return handler
