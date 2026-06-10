"""Shared orchestration input validation helpers."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date


class OrchestrationInputError(ValueError):
    """Raised when a component summary cannot be consumed by orchestration."""

    def __init__(self, message: str, *, field: str = "") -> None:
        self.field = field
        super().__init__(message)


def require_non_empty_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise OrchestrationInputError(f"{field} must be non-empty text", field=field)


def require_non_negative_finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OrchestrationInputError(f"{field} must be numeric", field=field)
    number = float(value)
    if not math.isfinite(number):
        raise OrchestrationInputError(f"{field} must be finite", field=field)
    if number < 0.0:
        raise OrchestrationInputError(f"{field} must be non-negative", field=field)
    return number


def require_non_negative_int(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OrchestrationInputError(f"{field} must be a non-negative integer", field=field)


def require_text_tuple(value: object, field: str) -> None:
    if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
        raise OrchestrationInputError(f"{field} must be a tuple of text values", field=field)


def require_tuple_of(value: object, expected_type: type[object], field: str) -> None:
    if not isinstance(value, tuple) or not all(isinstance(item, expected_type) for item in value):
        raise OrchestrationInputError(
            f"{field} must be a tuple of {expected_type.__name__} values",
            field=field,
        )


def required_text_attr(result: object, field: str, *, component: str) -> str:
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


def required_text_alias_attr(result: object, fields: Sequence[str], *, component: str) -> str:
    """Return the first non-empty text attribute from an alias list."""

    for field in fields:
        if hasattr(result, field):
            value = getattr(result, field)
            str_value = getattr(value, "value", value)
            if isinstance(str_value, str) and str_value:
                return str_value
    label = " or ".join(repr(field) for field in fields)
    raise OrchestrationInputError(
        f"{component} result missing required field {label}",
        field=fields[0] if fields else "",
    )


def required_date_attr(result: object, field: str, *, component: str) -> date:
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


def required_date_alias_attr(result: object, fields: Sequence[str], *, component: str) -> date:
    """Return the first date-like attribute from an alias list."""

    for field in fields:
        if hasattr(result, field):
            value = getattr(result, field)
            if isinstance(value, date):
                return value.date() if hasattr(value, "date") else value
    label = " or ".join(repr(field) for field in fields)
    raise OrchestrationInputError(
        f"{component} result missing required date field {label}",
        field=fields[0] if fields else "",
    )


def required_finite_number_attr(result: object, field: str, *, component: str) -> float:
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


def required_non_negative_finite_number_alias_attr(
    result: object, fields: Sequence[str], *, component: str
) -> float:
    """Return the first finite non-negative numeric attribute from an alias list."""

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
    label = " or ".join(repr(field) for field in fields)
    raise OrchestrationInputError(
        f"{component} result missing required numeric field {label}",
        field=fields[0] if fields else "",
    )


def optional_object_attr(result: object, field: str, *, component: str) -> object | None:
    if not hasattr(result, field):
        return None
    val: object | None = getattr(result, field)
    return val


def optional_sequence_attr(result: object, field: str, *, component: str) -> tuple[object, ...]:
    if not hasattr(result, field):
        return ()
    value = getattr(result, field)
    if value is None:
        return ()
    return tuple(value)


def optional_text_attr(result: object, field: str) -> str | None:
    if not hasattr(result, field):
        return None
    value = getattr(result, field)
    str_value = getattr(value, "value", value)
    if isinstance(str_value, str) and str_value:
        return str_value
    return None


def optional_non_negative_int_attr(result: object, field: str) -> int | None:
    if not hasattr(result, field):
        return None
    value = getattr(result, field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def text_tuple_attr(result: object, field: str, *, component: str = "") -> tuple[str, ...]:
    if not hasattr(result, field):
        return ()
    value = getattr(result, field)
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    try:
        return tuple(str(item) for item in value)
    except TypeError:
        return (str(value),)
