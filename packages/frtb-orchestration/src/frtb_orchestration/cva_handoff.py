"""CVA component handoff contracts (separate from SA composition)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from frtb_orchestration.standardised import OrchestrationInputError


@dataclass(frozen=True)
class CvaResultHandoff:
    """CVA result summary for top-of-house aggregation."""

    package_name: str
    run_id: str
    calculation_date: date
    base_currency: str
    profile_id: str
    method: str
    total_cva_capital: float
    ba_cva_reduced_total: float | None
    ba_cva_full_total: float | None
    sa_cva_total: float | None
    profile_hash: str
    input_hash: str
    risk_class_count: int
    counterparty_count: int
    citations: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def recognise_cva_result(result: object) -> CvaResultHandoff:
    """Return the orchestration handoff view for a public CVA result shape."""

    method = _required_text_attr(result, "method", component="CVA")
    ba_cva_reduced = _optional_object_attr(result, "ba_cva_reduced", component="CVA")
    ba_cva_full = _optional_object_attr(result, "ba_cva_full", component="CVA")
    sa_cva_risk_class_capitals = _optional_sequence_attr(
        result, "sa_cva_risk_class_capitals", component="CVA"
    )
    ba_cva_counterparty_capitals = _optional_sequence_attr(
        result, "ba_cva_counterparty_capitals", component="CVA"
    )

    ba_reduced_total = None
    if ba_cva_reduced is not None:
        ba_reduced_total = _required_finite_number_attr(
            ba_cva_reduced, "k_reduced", component="CVA reduced"
        )

    ba_full_total = None
    if ba_cva_full is not None:
        ba_full_total = _required_finite_number_attr(ba_cva_full, "k_full", component="CVA full")

    sa_total = None
    if sa_cva_risk_class_capitals:
        sa_total = sum(
            _required_finite_number_attr(item, "post_multiplier_capital", component="SA-CVA")
            for item in sa_cva_risk_class_capitals
        )

    return CvaResultHandoff(
        package_name="frtb-cva",
        run_id=_required_text_attr(result, "run_id", component="CVA"),
        calculation_date=_required_date_attr(result, "calculation_date", component="CVA"),
        base_currency=_required_text_attr(result, "base_currency", component="CVA"),
        profile_id=_required_text_attr(result, "profile_id", component="CVA"),
        method=method,
        total_cva_capital=_required_finite_number_attr(
            result, "total_cva_capital", component="CVA"
        ),
        ba_cva_reduced_total=ba_reduced_total,
        ba_cva_full_total=ba_full_total,
        sa_cva_total=sa_total,
        profile_hash=_required_text_attr(result, "profile_hash", component="CVA"),
        input_hash=_required_text_attr(result, "input_hash", component="CVA"),
        risk_class_count=len(sa_cva_risk_class_capitals) if sa_cva_risk_class_capitals else 0,
        counterparty_count=len(ba_cva_counterparty_capitals) if ba_cva_counterparty_capitals else 0,
        citations=_text_tuple_attr(result, "citations", component="CVA"),
        warnings=_text_tuple_attr(result, "warnings", component="CVA"),
    )


def _required_text_attr(result: object, field: str, *, component: str) -> str:
    if not hasattr(result, field):
        raise OrchestrationInputError(
            f"{component} result missing required field {field}",
            field=field,
        )
    value = getattr(result, field)
    if not isinstance(value, str) or not value:
        raise OrchestrationInputError(
            f"{component} result field {field} must be a non-empty string",
            field=field,
        )
    return value


def _required_date_attr(result: object, field: str, *, component: str) -> date:
    if not hasattr(result, field):
        raise OrchestrationInputError(
            f"{component} result missing required field {field}",
            field=field,
        )
    value = getattr(result, field)
    if not isinstance(value, date):
        raise OrchestrationInputError(
            f"{component} result field {field} must be a date",
            field=field,
        )
    return value


def _required_finite_number_attr(result: object, field: str, *, component: str) -> float:
    if not hasattr(result, field):
        raise OrchestrationInputError(
            f"{component} result missing required field {field}",
            field=field,
        )
    value = getattr(result, field)
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise OrchestrationInputError(
            f"{component} result field {field} must be a finite number",
            field=field,
        )
    return float(value)


def _optional_object_attr(result: object, field: str, *, component: str) -> object | None:
    if not hasattr(result, field):
        return None
    return getattr(result, field)


def _optional_sequence_attr(result: object, field: str, *, component: str) -> tuple[object, ...]:
    if not hasattr(result, field):
        return ()
    value = getattr(result, field)
    if value is None:
        return ()
    return tuple(value)


def _text_tuple_attr(result: object, field: str, *, component: str) -> tuple[str, ...]:
    if not hasattr(result, field):
        return ()
    value = getattr(result, field)
    if value is None:
        return ()
    return tuple(str(item) for item in value)


__all__ = ["CvaResultHandoff", "recognise_cva_result"]
