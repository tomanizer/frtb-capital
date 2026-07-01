"""Result contracts for organisation hierarchy query APIs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from frtb_result_store.org_hierarchy_model import (
    OrgAggregateRow,
    OrgCapitalResultRow,
    OrgHierarchyNode,
)


class OrgQueryStatus:
    """Stable status values returned by hierarchy-node query APIs."""

    OK = "OK"
    NO_DATA = "NO_DATA"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class OrgHierarchyEdge:
    """Parent-child edge in one effective organisation hierarchy snapshot."""

    hierarchy_id: str
    version_id: str
    parent_node_id: str
    child_node_id: str


@dataclass(frozen=True, slots=True)
class OrgHierarchySnapshot:
    """Effective organisation hierarchy nodes and edges for one query date."""

    hierarchy_id: str
    version_id: str
    as_of_date: date
    nodes: tuple[OrgHierarchyNode, ...]
    edges: tuple[OrgHierarchyEdge, ...]


@dataclass(frozen=True, slots=True)
class OrgNodeAggregateResult:
    """Aggregate result for one selected organisation node."""

    run_id: str
    node_id: str
    status: str
    aggregate: OrgAggregateRow | None
    source_row_count: int
    component_filter: tuple[str, ...]
    message: str = ""


@dataclass(frozen=True, slots=True)
class OrgSourceRowPage:
    """Paginated source rows that contribute to one organisation node."""

    run_id: str
    node_id: str
    status: str
    rows: tuple[OrgCapitalResultRow, ...]
    total_row_count: int
    limit: int
    offset: int
    next_offset: int | None
    component_filter: tuple[str, ...]
    message: str = ""


__all__ = [
    "OrgHierarchyEdge",
    "OrgHierarchySnapshot",
    "OrgNodeAggregateResult",
    "OrgQueryStatus",
    "OrgSourceRowPage",
]
