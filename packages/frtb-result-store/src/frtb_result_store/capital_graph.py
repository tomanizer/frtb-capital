"""Canonical FRTB capital graph construction helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from frtb_common.hashing import stable_json_hash

from frtb_result_store.capital_edges import build_standard_capital_edges
from frtb_result_store.model import (
    CapitalEdge,
    CapitalNode,
    CapitalNodeFamily,
    CapitalNodeSpec,
    FrtbComponent,
    NodeType,
    ResultStoreContractError,
    _coerce_enum,
    _normalize_identity_text,
    _normalize_identity_value,
    _require_mapping,
    _require_non_empty_text,
)

__all__ = [
    "build_standard_capital_edges",
    "build_standard_capital_graph",
    "capital_node_from_spec",
    "capital_node_identity_payload",
    "generate_capital_node_id",
]

NODE_IDENTITY_REGISTRY: Mapping[
    CapitalNodeFamily,
    tuple[tuple[str, ...], tuple[str, ...]],
] = MappingProxyType(
    {
        CapitalNodeFamily.COMPONENT: (
            ("hierarchy_leaf_path", "component"),
            ("calculation_branch",),
        ),
        CapitalNodeFamily.RISK_CLASS: (
            ("hierarchy_leaf_path", "component", "risk_class"),
            ("risk_measure", "calculation_branch"),
        ),
        CapitalNodeFamily.BUCKET: (
            ("hierarchy_leaf_path", "component", "risk_class", "bucket"),
            ("risk_measure", "calculation_branch"),
        ),
        CapitalNodeFamily.ISSUER: (
            ("hierarchy_leaf_path", "component", "risk_class", "bucket", "issuer_id"),
            ("calculation_branch",),
        ),
        CapitalNodeFamily.COUNTERPARTY: (
            ("hierarchy_leaf_path", "component", "counterparty_id"),
            ("hedge_set_id", "calculation_branch"),
        ),
        CapitalNodeFamily.RESIDUAL_BRANCH: (
            ("hierarchy_leaf_path", "component", "residual_risk_type"),
            ("exposure_category", "calculation_branch"),
        ),
        CapitalNodeFamily.RISK_FACTOR: (
            ("hierarchy_leaf_path", "component", "risk_factor_id"),
            ("risk_factor_set_id", "calculation_branch"),
        ),
        CapitalNodeFamily.POSITION: (
            ("hierarchy_leaf_path", "component", "position_id"),
            ("calculation_branch",),
        ),
    }
)


def capital_node_identity_payload(
    node_family: CapitalNodeFamily | str,
    *,
    hierarchy_leaf_path: Sequence[tuple[str, object]],
    component: FrtbComponent | str,
    risk_class: str | None = None,
    risk_measure: str | None = None,
    bucket: str | None = None,
    issuer_id: str | None = None,
    counterparty_id: str | None = None,
    hedge_set_id: str | None = None,
    residual_risk_type: str | None = None,
    exposure_category: str | None = None,
    risk_factor_id: str | None = None,
    risk_factor_set_id: str | None = None,
    position_id: str | None = None,
    calculation_branch: str | None = None,
) -> Mapping[str, object]:
    """Return the canonical ID payload for one FRTB capital node family.
    Parameters
    ----------
    node_family : CapitalNodeFamily | str
        Node family.
    hierarchy_leaf_path : Sequence[tuple[str, object]]
        Hierarchy leaf path.
    component : FrtbComponent | str
        Component.
    risk_class : str | None, optional
        Risk class.
    risk_measure : str | None, optional
        Risk measure.
    bucket : str | None, optional
        Bucket.
    issuer_id : str | None, optional
        Issuer id.
    counterparty_id : str | None, optional
        Counterparty id.
    hedge_set_id : str | None, optional
        Hedge set id.
    residual_risk_type : str | None, optional
        Residual risk type.
    exposure_category : str | None, optional
        Exposure category.
    risk_factor_id : str | None, optional
        Risk factor id.
    risk_factor_set_id : str | None, optional
        Risk factor set id.
    position_id : str | None, optional
        Position id.
    calculation_branch : str | None, optional
        Calculation branch.

    Returns
    -------
    Mapping[str, object]
        Result of the operation.
    """

    family = _coerce_enum(node_family, CapitalNodeFamily, "node_family")
    component_value = _coerce_enum(component, FrtbComponent, "component").value
    values: dict[str, object | None] = {
        "hierarchy_leaf_path": _normalized_leaf_path(hierarchy_leaf_path),
        "component": component_value,
        "risk_class": risk_class,
        "risk_measure": risk_measure,
        "bucket": bucket,
        "issuer_id": issuer_id,
        "counterparty_id": counterparty_id,
        "hedge_set_id": hedge_set_id,
        "residual_risk_type": residual_risk_type,
        "exposure_category": exposure_category,
        "risk_factor_id": risk_factor_id,
        "risk_factor_set_id": risk_factor_set_id,
        "position_id": position_id,
        "calculation_branch": calculation_branch,
    }
    required_fields, optional_fields = NODE_IDENTITY_REGISTRY[family]
    payload: dict[str, object] = {"node_family": family.value, "schema_version": 1}
    for field_name in required_fields:
        value = values[field_name]
        if value is None:
            raise ResultStoreContractError(
                f"missing capital node identity field: {field_name}",
                field=field_name,
            )
        payload[field_name] = _normalize_identity_value(value, field_name)
    for field_name in optional_fields:
        value = values[field_name]
        if value is not None:
            payload[field_name] = _normalize_identity_value(value, field_name)
    return MappingProxyType(payload)


def generate_capital_node_id(identity_payload: Mapping[str, object]) -> str:
    """Generate a canonical capital node storage id from an identity payload.
    Parameters
    ----------
    identity_payload : Mapping[str, object]
        Identity payload.

    Returns
    -------
    str
        Result of the operation.
    """

    _require_mapping(identity_payload, "identity_payload")
    node_family = identity_payload.get("node_family")
    _require_non_empty_text(node_family, "node_family")
    return f"{node_family}:{stable_json_hash(identity_payload)}"


def capital_node_from_spec(
    *,
    run_id: str,
    hierarchy_leaf_node_id: str,
    hierarchy_leaf_path: Sequence[tuple[str, object]],
    spec: CapitalNodeSpec,
) -> CapitalNode:
    """Create a canonical ``CapitalNode`` under a resolved hierarchy leaf.
    Parameters
    ----------
    run_id : str
        Run id.
    hierarchy_leaf_node_id : str
        Hierarchy leaf node id.
    hierarchy_leaf_path : Sequence[tuple[str, object]]
        Hierarchy leaf path.
    spec : CapitalNodeSpec
        Spec.

    Returns
    -------
    CapitalNode
        Result of the operation.
    """

    node_family = CapitalNodeFamily(spec.node_family)
    component = FrtbComponent(spec.component)
    payload = capital_node_identity_payload(
        node_family,
        hierarchy_leaf_path=hierarchy_leaf_path,
        component=component,
        risk_class=spec.risk_class,
        risk_measure=spec.risk_measure,
        bucket=spec.bucket,
        issuer_id=spec.issuer_id,
        counterparty_id=spec.counterparty_id,
        hedge_set_id=spec.hedge_set_id,
        residual_risk_type=spec.residual_risk_type,
        exposure_category=spec.exposure_category,
        risk_factor_id=spec.risk_factor_id,
        risk_factor_set_id=spec.risk_factor_set_id,
        position_id=spec.position_id,
        calculation_branch=spec.calculation_branch,
    )
    return CapitalNode(
        run_id=run_id,
        node_id=generate_capital_node_id(payload),
        node_type=_node_type_for_family(node_family),
        component=component,
        label=spec.label,
        risk_class=spec.risk_class,
        bucket=spec.bucket,
        issuer_id=spec.issuer_id,
        counterparty_id=spec.counterparty_id,
        calculation_branch=spec.calculation_branch,
        regulatory_rule_id=spec.regulatory_rule_id,
        sort_key=spec.sort_key,
        metadata=_capital_node_metadata(spec, node_family, hierarchy_leaf_node_id, payload),
    )


def build_standard_capital_graph(
    *,
    run_id: str,
    hierarchy_leaf_node_id: str,
    hierarchy_leaf_path: Sequence[tuple[str, object]],
    specs: Sequence[CapitalNodeSpec],
    custom_edges: Sequence[CapitalEdge] = (),
) -> tuple[tuple[CapitalNode, ...], tuple[CapitalEdge, ...]]:
    """Generate canonical capital nodes and standard edges under a hierarchy leaf.
    Parameters
    ----------
    run_id : str
        Run id.
    hierarchy_leaf_node_id : str
        Hierarchy leaf node id.
    hierarchy_leaf_path : Sequence[tuple[str, object]]
        Hierarchy leaf path.
    specs : Sequence[CapitalNodeSpec]
        Specs.
    custom_edges : Sequence[CapitalEdge], optional
        Custom edges.

    Returns
    -------
    tuple[tuple[CapitalNode, ...], tuple[CapitalEdge, ...]]
        Result of the operation.
    """

    if custom_edges:
        raise ResultStoreContractError(
            "custom FRTB capital edges are not supported in the first pass",
            field="custom_edges",
        )
    nodes = tuple(
        capital_node_from_spec(
            run_id=run_id,
            hierarchy_leaf_node_id=hierarchy_leaf_node_id,
            hierarchy_leaf_path=hierarchy_leaf_path,
            spec=spec,
        )
        for spec in specs
    )
    return nodes, build_standard_capital_edges(
        run_id=run_id,
        hierarchy_leaf_node_id=hierarchy_leaf_node_id,
        nodes=nodes,
    )


def _normalized_leaf_path(path: Sequence[tuple[str, object]]) -> tuple[dict[str, object], ...]:
    if not path:
        raise ResultStoreContractError("hierarchy_leaf_path must be non-empty", field="path")
    return tuple(
        {
            "level_name": _normalize_identity_text(level_name),
            "business_key": _normalize_identity_value(business_key, "business_key"),
        }
        for level_name, business_key in path
    )


def _capital_node_metadata(
    spec: CapitalNodeSpec,
    node_family: CapitalNodeFamily,
    hierarchy_leaf_node_id: str,
    payload: Mapping[str, object],
) -> Mapping[str, object]:
    metadata = {
        **dict(spec.metadata),
        "hierarchy_leaf_node_id": hierarchy_leaf_node_id,
        "identity_payload": dict(payload),
        "node_family": node_family.value,
    }
    for field_name in (
        "risk_measure",
        "hedge_set_id",
        "residual_risk_type",
        "exposure_category",
    ):
        value = getattr(spec, field_name)
        if value is not None:
            metadata[field_name] = value
    return metadata


def _node_type_for_family(node_family: CapitalNodeFamily) -> NodeType:
    node_types = {
        CapitalNodeFamily.COMPONENT: NodeType.COMPONENT,
        CapitalNodeFamily.RISK_CLASS: NodeType.RISK_CLASS,
        CapitalNodeFamily.BUCKET: NodeType.BUCKET,
        CapitalNodeFamily.ISSUER: NodeType.ISSUER,
        CapitalNodeFamily.COUNTERPARTY: NodeType.COUNTERPARTY,
        CapitalNodeFamily.RISK_FACTOR: NodeType.RISK_FACTOR,
        CapitalNodeFamily.POSITION: NodeType.POSITION,
    }
    return node_types.get(node_family, NodeType.MEASURE_BRANCH)
