"""Persisted dashboard and drilldown mart row dataclasses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

from frtb_result_store._model_capital_records import CapitalNode
from frtb_result_store.model_enums import (
    FrtbComponent,
    NodeType,
    ResultStoreContractError,
    RunStatus,
)
from frtb_result_store.model_validation import (
    _coerce_enum,
    _freeze_metadata,
    _require_finite_number,
    _require_non_empty_text,
    _require_non_negative_int,
    _require_plain_date,
    _validate_optional_text,
)


@dataclass(frozen=True, slots=True)
class CapitalSummaryRow:
    """Persisted dashboard summary for one committed run."""

    run_id: str
    as_of_date: date
    regime_id: str
    base_currency: str
    lifecycle_status: RunStatus | str
    suggested_status: RunStatus | str | None
    total_capital: float
    currency: str
    node_count: int
    measure_count: int
    component_count: int

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_plain_date(self.as_of_date, "as_of_date")
        _require_non_empty_text(self.regime_id, "regime_id")
        _require_non_empty_text(self.base_currency, "base_currency")
        object.__setattr__(
            self,
            "lifecycle_status",
            _coerce_enum(self.lifecycle_status, RunStatus, "lifecycle_status"),
        )
        if self.suggested_status is not None:
            object.__setattr__(
                self,
                "suggested_status",
                _coerce_enum(self.suggested_status, RunStatus, "suggested_status"),
            )
        object.__setattr__(
            self,
            "total_capital",
            _require_finite_number(self.total_capital, "total_capital"),
        )
        _require_non_empty_text(self.currency, "currency")
        for field_name in ("node_count", "measure_count", "component_count"):
            _require_non_negative_int(getattr(self, field_name), field_name)


@dataclass(frozen=True, slots=True)
class CapitalTreeMartRow:
    """Persisted flattened capital tree row for dashboard drilldown."""

    run_id: str
    node_id: str
    parent_node_id: str | None
    depth: int
    node_type: NodeType | str
    component: FrtbComponent | str
    label: str
    desk_id: str | None = None
    portfolio_id: str | None = None
    book_id: str | None = None
    risk_class: str | None = None
    bucket: str | None = None
    issuer_id: str | None = None
    counterparty_id: str | None = None
    calculation_branch: str | None = None
    regulatory_rule_id: str | None = None
    sort_key: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.node_id, "node_id")
        _validate_optional_text(self.parent_node_id, "parent_node_id")
        _require_non_negative_int(self.depth, "depth")
        object.__setattr__(self, "node_type", _coerce_enum(self.node_type, NodeType, "node_type"))
        object.__setattr__(
            self, "component", _coerce_enum(self.component, FrtbComponent, "component")
        )
        _require_non_empty_text(self.label, "label")
        for field_name in (
            "desk_id",
            "portfolio_id",
            "book_id",
            "risk_class",
            "bucket",
            "issuer_id",
            "counterparty_id",
            "calculation_branch",
            "regulatory_rule_id",
        ):
            _validate_optional_text(getattr(self, field_name), field_name)
        if not isinstance(self.sort_key, int) or isinstance(self.sort_key, bool):
            raise ResultStoreContractError("sort_key must be an integer", field="sort_key")
        _freeze_metadata(self, self.metadata)

    def to_node(self) -> CapitalNode:
        """Return the capital-node contract represented by this mart row."""

        return CapitalNode(
            run_id=self.run_id,
            node_id=self.node_id,
            node_type=self.node_type,
            component=self.component,
            label=self.label,
            desk_id=self.desk_id,
            portfolio_id=self.portfolio_id,
            book_id=self.book_id,
            risk_class=self.risk_class,
            bucket=self.bucket,
            issuer_id=self.issuer_id,
            counterparty_id=self.counterparty_id,
            calculation_branch=self.calculation_branch,
            regulatory_rule_id=self.regulatory_rule_id,
            sort_key=self.sort_key,
            metadata=self.metadata,
        )


@dataclass(frozen=True, slots=True)
class ComponentBreakdownRow:
    """Persisted component-level capital total for dashboard summaries."""

    run_id: str
    component: FrtbComponent | str
    amount: float
    currency: str
    node_count: int
    measure_count: int

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        object.__setattr__(
            self, "component", _coerce_enum(self.component, FrtbComponent, "component")
        )
        object.__setattr__(self, "amount", _require_finite_number(self.amount, "amount"))
        _require_non_empty_text(self.currency, "currency")
        for field_name in ("node_count", "measure_count"):
            _require_non_negative_int(getattr(self, field_name), field_name)
