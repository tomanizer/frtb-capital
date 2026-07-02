"""PLA/backtesting desk eligibility mart dataclasses.

These records are result-store read models for Capital Navigator. They persist
completed desk eligibility evidence and links to capital/artifact evidence; they
do not calculate PLA, backtesting, RFET, SES, or desk approval status.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from frtb_result_store.model_enums import ResultStoreContractError
from frtb_result_store.model_validation import (
    _freeze_mapping,
    _freeze_metadata,
    _require_finite_number,
    _require_non_empty_text,
    _require_non_negative_int,
    _require_plain_date,
    _validate_optional_text,
)

__all__ = [
    "BacktestingState",
    "DeskEligibilityRow",
    "DeskEligibilityState",
    "PLAState",
]


class DeskEligibilityState(StrEnum):
    """Persisted desk eligibility state supplied by upstream governance evidence."""

    APPROVED = "approved"
    ELIGIBLE = "eligible"
    MONITOR = "monitor"
    AMBER = "amber"
    RED = "red"
    FALLBACK_TO_SA = "fallback_to_sa"
    PENDING = "pending"
    NOT_RUN = "not_run"
    NO_DATA = "no_data"
    UNSUPPORTED = "unsupported"


class PLAState(StrEnum):
    """Persisted profit-and-loss attribution state."""

    PASSING = "passing"
    AMBER = "amber"
    RED = "red"
    NOT_RUN = "not_run"
    NO_DATA = "no_data"
    UNSUPPORTED = "unsupported"


class BacktestingState(StrEnum):
    """Persisted backtesting status for a desk."""

    GREEN = "green"
    AMBER = "amber"
    RED = "red"
    NOT_RUN = "not_run"
    NO_DATA = "no_data"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class DeskEligibilityRow:
    """Denormalized PLA/backtesting eligibility row for one desk.

    The row links a stable desk roster item to hierarchy IDs, advisory upstream
    eligibility evidence, compact PLA/backtesting metrics, RFET/NMRF/SES
    summaries, capital consequence, and source artifacts.
    """

    run_id: str
    desk_id: str
    desk_node_id: str
    label: str
    legal_entity_id: str | None
    division_id: str | None
    business_line_id: str | None
    volcker_desk_id: str | None
    book_ids: tuple[str, ...]
    eligibility_state: DeskEligibilityState | str
    pla_state: PLAState | str
    pla_threshold_profile_id: str | None
    pla_metric_summary: Mapping[str, object] = field(default_factory=dict)
    backtesting_state: BacktestingState | str = BacktestingState.NO_DATA
    backtesting_zone: str | None = None
    backtesting_exception_count: int | None = None
    backtesting_window: str | None = None
    latest_exception_date: date | None = None
    rfet_modellable_count: int | None = None
    nmrf_count: int | None = None
    ses_amount: float | None = None
    capital_consequence_amount: float | None = None
    capital_consequence_currency: str | None = None
    capital_node_id: str | None = None
    pnl_artifact_id: str | None = None
    rfet_artifact_id: str | None = None
    source_artifact_id: str | None = None
    model_run_id: str | None = None
    profile_hash: str | None = None
    source_hashes: tuple[str, ...] = ()
    calculation_timestamp: datetime | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.desk_id, "desk_id")
        _require_non_empty_text(self.desk_node_id, "desk_node_id")
        _require_non_empty_text(self.label, "label")
        for field_name in (
            "legal_entity_id",
            "division_id",
            "business_line_id",
            "volcker_desk_id",
            "pla_threshold_profile_id",
            "backtesting_zone",
            "backtesting_window",
            "capital_consequence_currency",
            "capital_node_id",
            "pnl_artifact_id",
            "rfet_artifact_id",
            "source_artifact_id",
            "model_run_id",
            "profile_hash",
        ):
            _validate_optional_text(getattr(self, field_name), field_name)
        object.__setattr__(self, "book_ids", _text_tuple(self.book_ids, "book_ids"))
        object.__setattr__(
            self,
            "eligibility_state",
            DeskEligibilityState(self.eligibility_state),
        )
        object.__setattr__(self, "pla_state", PLAState(self.pla_state))
        object.__setattr__(
            self,
            "backtesting_state",
            BacktestingState(self.backtesting_state),
        )
        if self.backtesting_exception_count is not None:
            _require_non_negative_int(
                self.backtesting_exception_count,
                "backtesting_exception_count",
            )
        if self.latest_exception_date is not None:
            _require_plain_date(self.latest_exception_date, "latest_exception_date")
        if self.rfet_modellable_count is not None:
            _require_non_negative_int(self.rfet_modellable_count, "rfet_modellable_count")
        if self.nmrf_count is not None:
            _require_non_negative_int(self.nmrf_count, "nmrf_count")
        if self.ses_amount is not None:
            object.__setattr__(
                self,
                "ses_amount",
                _require_finite_number(self.ses_amount, "ses_amount"),
            )
        if self.capital_consequence_amount is not None:
            object.__setattr__(
                self,
                "capital_consequence_amount",
                _require_finite_number(
                    self.capital_consequence_amount,
                    "capital_consequence_amount",
                ),
            )
        object.__setattr__(self, "source_hashes", _text_tuple(self.source_hashes, "source_hashes"))
        if self.calculation_timestamp is not None and self.calculation_timestamp.tzinfo is None:
            raise ResultStoreContractError(
                "calculation_timestamp must be timezone-aware",
                field="calculation_timestamp",
            )
        _freeze_mapping(self, "pla_metric_summary", self.pla_metric_summary)
        _freeze_metadata(self, self.metadata)


def _text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if not isinstance(values, tuple) or not all(isinstance(value, str) for value in values):
        raise ResultStoreContractError(f"{field_name} must be a tuple of text", field=field_name)
    for value in values:
        _require_non_empty_text(value, field_name)
    return tuple(values)
