"""Movement explanation and movement-summary dataclasses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from frtb_common import AttributionMethod

from frtb_result_store.model_enums import ResultStoreContractError
from frtb_result_store.model_validation import (
    _coerce_enum,
    _freeze_metadata,
    _require_finite_number,
    _require_non_empty_text,
    _validate_optional_text,
)


@dataclass(frozen=True, slots=True)
class MovementResult:
    """Official movement explanation row between a baseline and current run."""

    run_id: str
    baseline_run_id: str
    movement_id: str
    node_id: str
    movement_type: str
    from_amount: float
    to_amount: float
    delta_amount: float
    base_currency: str
    driver_type: str
    driver_id: str
    explanation: str
    attribution_method: AttributionMethod | str | None = None
    artifact_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "run_id",
            "baseline_run_id",
            "movement_id",
            "node_id",
            "movement_type",
            "base_currency",
            "driver_type",
            "driver_id",
        ):
            _require_non_empty_text(getattr(self, field_name), field_name)
        for field_name in ("from_amount", "to_amount", "delta_amount"):
            object.__setattr__(
                self,
                field_name,
                _require_finite_number(getattr(self, field_name), field_name),
            )
        if not isinstance(self.explanation, str):
            raise ResultStoreContractError("explanation must be text", field="explanation")
        if self.attribution_method is not None:
            object.__setattr__(
                self,
                "attribution_method",
                _coerce_enum(self.attribution_method, AttributionMethod, "attribution_method"),
            )
        _validate_optional_text(self.artifact_id, "artifact_id")
        _freeze_metadata(self, self.metadata)


@dataclass(frozen=True, slots=True)
class MovementSummaryRow:
    """Persisted movement summary mart row queryable by capital node."""

    run_id: str
    baseline_run_id: str
    movement_id: str
    node_id: str
    movement_type: str
    from_amount: float
    to_amount: float
    delta_amount: float
    base_currency: str
    driver_type: str
    driver_id: str
    attribution_method: AttributionMethod | str | None = None
    artifact_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "run_id",
            "baseline_run_id",
            "movement_id",
            "node_id",
            "movement_type",
            "base_currency",
            "driver_type",
            "driver_id",
        ):
            _require_non_empty_text(getattr(self, field_name), field_name)
        for field_name in ("from_amount", "to_amount", "delta_amount"):
            object.__setattr__(
                self,
                field_name,
                _require_finite_number(getattr(self, field_name), field_name),
            )
        if self.attribution_method is not None:
            object.__setattr__(
                self,
                "attribution_method",
                _coerce_enum(self.attribution_method, AttributionMethod, "attribution_method"),
            )
        _validate_optional_text(self.artifact_id, "artifact_id")
