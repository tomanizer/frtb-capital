"""IMA capital summary contracts for suite-level aggregation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from frtb_orchestration.standardised import OrchestrationInputError

_IMA_ELIGIBLE = "IMA_ELIGIBLE"
_SA_FALLBACK = "SA_FALLBACK"


@dataclass(frozen=True)
class ImaCapitalSummary:
    """IMA capital result summary for top-of-house aggregation.

    Sign convention: ``total_ima_capital`` is a non-negative capital charge in
    ``base_currency``. ``policy_hash`` is the SHA-256 digest of the regulatory
    policy parameters; ``input_hash`` is the SHA-256 digest of the scenario
    cube inputs.

    Construct directly from IMA capital run outputs, or use
    ``recognise_ima_summary`` with a duck-typed audit log shape.
    """

    package_name: str
    run_id: str
    calculation_date: date
    base_currency: str
    profile_id: str
    total_ima_capital: float
    ima_eligible_desk_count: int
    sa_fallback_desk_count: int
    policy_hash: str
    input_hash: str
    citations: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_text(self.package_name, "package_name")
        _require_non_empty_text(self.run_id, "run_id")
        if not isinstance(self.calculation_date, date):
            raise OrchestrationInputError(
                "calculation_date must be a date", field="calculation_date"
            )
        _require_non_empty_text(self.base_currency, "base_currency")
        _require_non_empty_text(self.profile_id, "profile_id")
        object.__setattr__(
            self,
            "total_ima_capital",
            _require_non_negative_finite_number(self.total_ima_capital, "total_ima_capital"),
        )
        _require_non_negative_int(self.ima_eligible_desk_count, "ima_eligible_desk_count")
        _require_non_negative_int(self.sa_fallback_desk_count, "sa_fallback_desk_count")
        _require_non_empty_text(self.policy_hash, "policy_hash")
        _require_non_empty_text(self.input_hash, "input_hash")
        _require_text_tuple(self.citations, "citations")
        _require_text_tuple(self.warnings, "warnings")

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic audit payload for this IMA summary."""

        return {
            "package_name": self.package_name,
            "run_id": self.run_id,
            "calculation_date": self.calculation_date.isoformat(),
            "base_currency": self.base_currency,
            "profile_id": self.profile_id,
            "total_ima_capital": self.total_ima_capital,
            "ima_eligible_desk_count": self.ima_eligible_desk_count,
            "sa_fallback_desk_count": self.sa_fallback_desk_count,
            "policy_hash": self.policy_hash,
            "input_hash": self.input_hash,
            "citations": list(self.citations),
            "warnings": list(self.warnings),
        }


def recognise_ima_summary(result: object) -> ImaCapitalSummary:
    """Return an IMA capital summary from a duck-typed IMA audit log shape.

    Accepts any object that carries the fields needed for suite-level
    aggregation. Field aliases are tried in order to accommodate both the
    ``CapitalRunAuditLog`` shape (``as_of_date``, ``inputs_hash``, ``regime``)
    and direct-construction shapes (``calculation_date``, ``input_hash``,
    ``profile_id``).

    Required fields (at least one alias must be present):
    - ``run_id``
    - ``calculation_date`` or ``as_of_date``
    - ``base_currency``
    - ``profile_id`` or ``regime``
    - ``total_ima_capital`` or ``total_market_risk_capital``
    - ``policy_hash``
    - ``input_hash`` or ``inputs_hash``

    Optional fields (defaults applied when absent):
    - ``ima_eligible_desk_count`` (derived from ``desk_records`` if present)
    - ``sa_fallback_desk_count`` (derived from ``desk_records`` if present)
    - ``citations``
    - ``warnings``
    """

    run_id = _required_text_attr(result, ["run_id"], component="IMA")
    calculation_date = _required_date_attr(
        result, ["calculation_date", "as_of_date"], component="IMA"
    )
    base_currency = _required_text_attr(result, ["base_currency"], component="IMA")
    profile_id = _required_text_attr(result, ["profile_id", "regime"], component="IMA")
    total_ima_capital = _required_finite_non_negative_attr(
        result, ["total_ima_capital", "total_market_risk_capital"], component="IMA"
    )
    policy_hash = _required_text_attr(result, ["policy_hash"], component="IMA")
    input_hash = _required_text_attr(result, ["input_hash", "inputs_hash"], component="IMA")

    ima_eligible_desk_count, sa_fallback_desk_count = _desk_counts_from(result)

    citations = _text_tuple_attr(result, "citations")
    warnings = _text_tuple_attr(result, "warnings")
    package_name = _optional_text_attr(result, "package_name") or "frtb-ima"

    return ImaCapitalSummary(
        package_name=package_name,
        run_id=run_id,
        calculation_date=calculation_date,
        base_currency=base_currency,
        profile_id=profile_id,
        total_ima_capital=total_ima_capital,
        ima_eligible_desk_count=ima_eligible_desk_count,
        sa_fallback_desk_count=sa_fallback_desk_count,
        policy_hash=policy_hash,
        input_hash=input_hash,
        citations=citations,
        warnings=warnings,
    )


def _desk_counts_from(result: object) -> tuple[int, int]:
    """Return (ima_eligible, sa_fallback) desk counts from duck-typed result."""

    if hasattr(result, "desk_records"):
        records = getattr(result, "desk_records")
        if records is not None:
            eligible = 0
            fallback = 0
            for record in records:
                status_raw = getattr(record, "desk_eligibility", _IMA_ELIGIBLE)
                status = getattr(status_raw, "value", status_raw)
                if status == _SA_FALLBACK:
                    fallback += 1
                else:
                    eligible += 1
            return eligible, fallback

    maybe_eligible = _optional_non_negative_int_attr(result, "ima_eligible_desk_count")
    maybe_fallback = _optional_non_negative_int_attr(result, "sa_fallback_desk_count")
    desk_count = _optional_non_negative_int_attr(result, "desk_count")

    if maybe_eligible is not None and maybe_fallback is not None:
        return maybe_eligible, maybe_fallback
    if desk_count is not None:
        resolved_fallback = maybe_fallback if maybe_fallback is not None else 0
        resolved_eligible = desk_count - resolved_fallback
        if resolved_eligible < 0:
            raise OrchestrationInputError(
                "IMA sa_fallback_desk_count exceeds desk_count",
                field="sa_fallback_desk_count",
            )
        return resolved_eligible, resolved_fallback
    return 0, 0


def _required_text_attr(result: object, fields: list[str], *, component: str) -> str:
    for field in fields:
        if hasattr(result, field):
            value = getattr(result, field)
            str_value = getattr(value, "value", value)
            if isinstance(str_value, str) and str_value:
                return str_value
    label = " or ".join(repr(f) for f in fields)
    raise OrchestrationInputError(
        f"{component} result missing required field {label}",
        field=fields[0],
    )


def _required_date_attr(result: object, fields: list[str], *, component: str) -> date:
    for field in fields:
        if hasattr(result, field):
            value = getattr(result, field)
            if isinstance(value, date):
                return value
    label = " or ".join(repr(f) for f in fields)
    raise OrchestrationInputError(
        f"{component} result missing required date field {label}",
        field=fields[0],
    )


def _required_finite_non_negative_attr(
    result: object, fields: list[str], *, component: str
) -> float:
    for field in fields:
        if hasattr(result, field):
            value = getattr(result, field)
            if value is None:
                continue
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise OrchestrationInputError(
                    f"{component} result field {field!r} must be numeric",
                    field=field,
                )
            number = float(value)
            if not math.isfinite(number):
                raise OrchestrationInputError(
                    f"{component} result field {field!r} must be finite",
                    field=field,
                )
            if number < 0.0:
                raise OrchestrationInputError(
                    f"{component} result field {field!r} must be non-negative",
                    field=field,
                )
            return number
    label = " or ".join(repr(f) for f in fields)
    raise OrchestrationInputError(
        f"{component} result missing required numeric field {label}",
        field=fields[0],
    )


def _optional_text_attr(result: object, field: str) -> str | None:
    if not hasattr(result, field):
        return None
    value = getattr(result, field)
    str_value = getattr(value, "value", value)
    if isinstance(str_value, str) and str_value:
        return str_value
    return None


def _optional_non_negative_int_attr(result: object, field: str) -> int | None:
    if not hasattr(result, field):
        return None
    value = getattr(result, field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _text_tuple_attr(result: object, field: str) -> tuple[str, ...]:
    if not hasattr(result, field):
        return ()
    value = getattr(result, field)
    if value is None:
        return ()
    return tuple(str(item) for item in value)


def _require_non_empty_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise OrchestrationInputError(f"{field} must be non-empty text", field=field)


def _require_non_negative_finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OrchestrationInputError(f"{field} must be numeric", field=field)
    number = float(value)
    if not math.isfinite(number):
        raise OrchestrationInputError(f"{field} must be finite", field=field)
    if number < 0.0:
        raise OrchestrationInputError(f"{field} must be non-negative", field=field)
    return number


def _require_non_negative_int(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OrchestrationInputError(f"{field} must be a non-negative integer", field=field)


def _require_text_tuple(value: object, field: str) -> None:
    if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
        raise OrchestrationInputError(f"{field} must be a tuple of text values", field=field)


__all__ = [
    "ImaCapitalSummary",
    "recognise_ima_summary",
]
