"""Capital graph node, edge, and measure dataclasses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from frtb_result_store.model_enums import (
    VALID_MEASURE_NAMES,
    EdgeType,
    FrtbComponent,
    NodeType,
)
from frtb_result_store.model_validation import (
    _coerce_enum,
    _freeze_metadata,
    _require_finite_number,
    _require_int,
    _require_non_empty_text,
    _require_registered_value,
    _require_text_tuple,
    _validate_optional_text,
)


@dataclass(frozen=True, slots=True)
class CapitalNode:
    """One node in the FRTB capital result graph."""

    run_id: str
    node_id: str
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
        _require_int(self.sort_key, "sort_key")
        _freeze_metadata(self, self.metadata)


@dataclass(frozen=True, slots=True)
class CapitalEdge:
    """Directed relationship between two capital graph nodes."""

    run_id: str
    parent_node_id: str
    child_node_id: str
    edge_type: EdgeType | str = EdgeType.AGGREGATES
    aggregation_weight: float = 1.0
    sort_key: int = 0

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.parent_node_id, "parent_node_id")
        _require_non_empty_text(self.child_node_id, "child_node_id")
        object.__setattr__(self, "edge_type", _coerce_enum(self.edge_type, EdgeType, "edge_type"))
        object.__setattr__(
            self,
            "aggregation_weight",
            _require_finite_number(self.aggregation_weight, "aggregation_weight"),
        )
        _require_int(self.sort_key, "sort_key")


@dataclass(frozen=True, slots=True)
class CapitalMeasure:
    """Scalar capital amount or intermediate FRTB result attached to a node."""

    run_id: str
    node_id: str
    measure_name: str
    amount: float
    currency: str
    unit: str = "currency"
    scenario: str | None = None
    methodology: str | None = None
    regulatory_rule_id: str | None = None
    citations: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.node_id, "node_id")
        _require_non_empty_text(self.measure_name, "measure_name")
        _require_registered_value(self.measure_name, VALID_MEASURE_NAMES, "measure_name")
        object.__setattr__(self, "amount", _require_finite_number(self.amount, "amount"))
        _require_non_empty_text(self.currency, "currency")
        _require_non_empty_text(self.unit, "unit")
        _validate_optional_text(self.scenario, "scenario")
        _validate_optional_text(self.methodology, "methodology")
        _validate_optional_text(self.regulatory_rule_id, "regulatory_rule_id")
        object.__setattr__(self, "citations", _require_text_tuple(self.citations, "citations"))
        _freeze_metadata(self, self.metadata)
