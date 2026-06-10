"""IMA capital summary contracts for suite-level aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from frtb_orchestration._validation import OrchestrationInputError
from frtb_orchestration._validation import optional_non_negative_int_attr as _optional_int_attr
from frtb_orchestration._validation import optional_text_attr as _optional_text_attr
from frtb_orchestration._validation import require_non_empty_text as _require_non_empty_text
from frtb_orchestration._validation import require_non_negative_finite_number as _require_number
from frtb_orchestration._validation import require_non_negative_int as _require_non_negative_int
from frtb_orchestration._validation import require_text_tuple as _require_text_tuple
from frtb_orchestration._validation import required_date_alias_attr as _required_date_attr
from frtb_orchestration._validation import (
    required_non_negative_finite_number_alias_attr as _required_number_attr,
)
from frtb_orchestration._validation import required_text_alias_attr as _required_text_attr
from frtb_orchestration._validation import text_tuple_attr as _text_tuple_attr

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
        if hasattr(self.calculation_date, "date"):
            object.__setattr__(self, "calculation_date", self.calculation_date.date())
        _require_non_empty_text(self.base_currency, "base_currency")
        _require_non_empty_text(self.profile_id, "profile_id")
        object.__setattr__(
            self,
            "total_ima_capital",
            _require_number(self.total_ima_capital, "total_ima_capital"),
        )
        _require_non_negative_int(self.ima_eligible_desk_count, "ima_eligible_desk_count")
        _require_non_negative_int(self.sa_fallback_desk_count, "sa_fallback_desk_count")
        _require_non_empty_text(self.policy_hash, "policy_hash")
        _require_non_empty_text(self.input_hash, "input_hash")
        _require_text_tuple(self.citations, "citations")
        _require_text_tuple(self.warnings, "warnings")

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic audit payload for this IMA summary.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """

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
    Parameters
    ----------
    result : object
        Result.

    Returns
    -------
    ImaCapitalSummary
        Result of the operation.
    """

    run_id = _required_text_attr(result, ["run_id"], component="IMA")
    calculation_date = _required_date_attr(
        result, ["calculation_date", "as_of_date"], component="IMA"
    )
    base_currency = _required_text_attr(result, ["base_currency"], component="IMA")
    profile_id = _required_text_attr(result, ["profile_id", "regime"], component="IMA")
    total_ima_capital = _required_number_attr(
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
            try:
                for record in records:
                    status_raw = getattr(record, "desk_eligibility", _IMA_ELIGIBLE)
                    status = getattr(status_raw, "value", status_raw)
                    if status == _SA_FALLBACK:
                        fallback += 1
                    else:
                        eligible += 1
            except TypeError as exc:
                raise OrchestrationInputError(
                    "IMA desk_records must be an iterable of desk records",
                    field="desk_records",
                ) from exc
            return eligible, fallback

    maybe_eligible = _optional_int_attr(result, "ima_eligible_desk_count")
    maybe_fallback = _optional_int_attr(result, "sa_fallback_desk_count")
    desk_count = _optional_int_attr(result, "desk_count")

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


__all__ = [
    "ImaCapitalSummary",
    "recognise_ima_summary",
]
