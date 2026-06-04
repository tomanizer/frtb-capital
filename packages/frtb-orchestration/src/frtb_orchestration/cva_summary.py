"""CVA capital summary contracts (separate from SA composition)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from frtb_orchestration._validation import (
    optional_object_attr as _optional_object_attr,
)
from frtb_orchestration._validation import (
    optional_sequence_attr as _optional_sequence_attr,
)
from frtb_orchestration._validation import (
    required_date_attr as _required_date_attr,
)
from frtb_orchestration._validation import (
    required_finite_number_attr as _required_finite_number_attr,
)
from frtb_orchestration._validation import (
    required_text_attr as _required_text_attr,
)
from frtb_orchestration._validation import (
    text_tuple_attr as _text_tuple_attr,
)


@dataclass(frozen=True)
class CvaCapitalSummary:
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


def recognise_cva_summary(result: object) -> CvaCapitalSummary:
    """Return the orchestration summary view for a public CVA result shape."""

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

    return CvaCapitalSummary(
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


__all__ = [
    "CvaCapitalSummary",
    "recognise_cva_summary",
]
