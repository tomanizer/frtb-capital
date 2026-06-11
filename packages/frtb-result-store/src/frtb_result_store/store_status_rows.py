"""Run lifecycle status row helpers for result-store IO."""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import datetime
from typing import cast

from frtb_result_store._row_codecs import optional_text as _optional_text
from frtb_result_store.model import (
    CalculationRun,
    ResultStoreContractError,
    RunStatus,
    RunStatusEvent,
)


def _elapsed_ms(started_at: float) -> float:
    return (time.perf_counter() - started_at) * 1000.0


def _initial_status_event(run: CalculationRun) -> RunStatusEvent:
    return RunStatusEvent.transition(
        run_id=run.run_id,
        from_status=None,
        to_status=RunStatus.CANDIDATE,
        event_time=run.created_at,
        actor="result-store",
        reason_code="RUN_COMMITTED",
        reason_text="Run committed to result store",
    )


def _status_event_row(event: RunStatusEvent) -> dict[str, object]:
    from_status = None if event.from_status is None else cast(RunStatus, event.from_status)
    to_status = cast(RunStatus, event.to_status)
    return {
        "event_id": event.event_id,
        "run_id": event.run_id,
        "from_status": None if from_status is None else from_status.value,
        "to_status": to_status.value,
        "event_time": event.event_time.isoformat(),
        "actor": event.actor,
        "reason_code": event.reason_code,
        "reason_text": event.reason_text,
        "external_evidence_ref": event.external_evidence_ref,
    }


def _status_event_from_row(row: Sequence[object]) -> RunStatusEvent:
    from_status_text = _optional_text(row[2])
    return RunStatusEvent(
        event_id=str(row[0]),
        run_id=str(row[1]),
        from_status=None if not from_status_text else RunStatus(from_status_text),
        to_status=RunStatus(str(row[3])),
        event_time=_status_event_time_from_row(row[4]),
        actor=str(row[5]),
        reason_code=str(row[6]),
        reason_text=str(row[7]),
        external_evidence_ref=_optional_text(row[8]),
    )


def _status_event_time_from_row(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ResultStoreContractError(
            f"invalid status event_time: {value}",
            field="event_time",
        ) from exc


__all__ = [
    "_elapsed_ms",
    "_initial_status_event",
    "_status_event_from_row",
    "_status_event_row",
]
