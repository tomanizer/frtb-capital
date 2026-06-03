"""Optional OpenTelemetry API bridge for result-store runtime spans."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from importlib import import_module
from typing import Any

__all__ = ["current_trace_ids", "result_store_span"]


try:  # pragma: no cover - optional dependency presence is environment-specific.
    trace: Any | None = import_module("opentelemetry.trace")
except ModuleNotFoundError:  # pragma: no cover - exercised by import-smoke no-op behavior.
    trace = None


@contextmanager
def result_store_span(
    name: str,
    attributes: Mapping[str, object],
) -> Iterator[None]:
    """Start an OpenTelemetry span when the lightweight API is installed."""

    if trace is None:
        yield
        return
    tracer = trace.get_tracer("frtb_result_store")
    with tracer.start_as_current_span(name, attributes=dict(attributes)):
        yield


def current_trace_ids() -> tuple[str | None, str | None]:
    """Return current trace/span ids when a sampled OpenTelemetry span exists."""

    if trace is None:
        return None, None
    span = trace.get_current_span()
    context = span.get_span_context()
    if not context.is_valid:
        return None, None
    return f"{context.trace_id:032x}", f"{context.span_id:016x}"
