"""Attribution drillthrough rows for the Capital Navigator fixture."""

from __future__ import annotations

from fixtures.capital_navigator_record_specs import (
    NAVIGATOR_ATTRIBUTION_SPECS,
    NAVIGATOR_RESIDUAL_ATTRIBUTION_SPEC,
    NAVIGATOR_UNSUPPORTED_ATTRIBUTION_SPECS,
)


def _attr(
    attribution_id: str,
    node_id: str,
    source_id: str,
    source_level: str,
    category: str,
    base_amount: float,
    contribution: float | None,
    residual: float,
    method: str,
    artifact_id: str,
    target_type: str | None = None,
    target_id: str | None = None,
) -> dict[str, object]:
    return {
        "attribution_id": attribution_id,
        "node_id": node_id,
        "source_id": source_id,
        "source_level": source_level,
        "target_type": source_level if target_type is None else target_type,
        "target_id": source_id if target_id is None else target_id,
        "category": category,
        "base_amount": base_amount,
        "contribution": contribution,
        "residual": residual,
        "method": method,
        "artifact_id": artifact_id,
    }


def _direct_rows() -> tuple[dict[str, object], ...]:
    return tuple(
        _attr(
            attribution_id=contribution_id,
            node_id=node_id,
            source_id=source_id,
            source_level=source_level,
            category=category,
            base_amount=base_amount,
            contribution=base_amount,
            residual=0.0,
            method=method,
            artifact_id=artifact_id,
        )
        for (
            contribution_id,
            node_id,
            source_id,
            source_level,
            category,
            base_amount,
            method,
            artifact_id,
        ) in NAVIGATOR_ATTRIBUTION_SPECS
    )


def _unsupported_rows() -> tuple[dict[str, object], ...]:
    return tuple(
        _attr(
            attribution_id=contribution_id,
            node_id=node_id,
            source_id=source_id,
            source_level=source_level,
            category=category,
            base_amount=base_amount,
            contribution=None,
            residual=0.0,
            method="UNSUPPORTED",
            artifact_id=artifact_id,
        )
        for (
            contribution_id,
            node_id,
            source_id,
            source_level,
            category,
            base_amount,
            artifact_id,
            _reason,
        ) in NAVIGATOR_UNSUPPORTED_ATTRIBUTION_SPECS
    )


def _residual_row() -> dict[str, object]:
    (
        contribution_id,
        node_id,
        source_id,
        source_level,
        category,
        base_amount,
        residual,
        artifact_id,
        _reason,
        target_type,
        target_id,
    ) = NAVIGATOR_RESIDUAL_ATTRIBUTION_SPEC
    return _attr(
        attribution_id=contribution_id,
        node_id=node_id,
        source_id=source_id,
        source_level=source_level,
        category=category,
        base_amount=base_amount,
        contribution=None,
        residual=residual,
        method="RESIDUAL",
        artifact_id=artifact_id,
        target_type=target_type,
        target_id=target_id,
    )


ATTRIBUTION_ROWS = (*_direct_rows(), *_unsupported_rows(), _residual_row())
