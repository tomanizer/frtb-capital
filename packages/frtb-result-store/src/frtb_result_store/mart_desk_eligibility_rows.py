"""PLA/backtesting desk eligibility mart builders."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any, cast

from frtb_result_store._model_capital_records import CapitalAttributionRecord, CapitalNode
from frtb_result_store._model_desk_eligibility import (
    BacktestingState,
    DeskEligibilityRow,
    DeskEligibilityState,
    PLAState,
)
from frtb_result_store.desk_eligibility_rows import _desk_eligibility_mart_row
from frtb_result_store.model import ResultBundle

__all__ = ["_desk_eligibility_mart_rows"]


def _desk_eligibility_mart_rows(bundle: ResultBundle) -> list[dict[str, object]]:
    """Build PLA/backtesting desk eligibility rows for Navigator.

    The builder uses desk-level graph nodes as the roster and consumes optional
    upstream/governance evidence from the node metadata key ``desk_eligibility``.
    It derives only stable links and summaries already present in the committed
    bundle: books from graph nodes, SES count/amount from stored attribution,
    and artifact IDs from attribution references.
    """
    rows = [
        _desk_eligibility_mart_row(_desk_row(bundle, node))
        for node in sorted(_ima_desk_nodes(bundle), key=lambda item: item.desk_id or item.node_id)
    ]
    return rows


def _desk_row(bundle: ResultBundle, node: CapitalNode) -> DeskEligibilityRow:
    evidence = _mapping(node.metadata.get("desk_eligibility"))
    desk_id = str(node.desk_id)
    desk_attributions = _desk_attributions(bundle, desk_id)
    ses_attributions = _ses_attributions(bundle, desk_id)
    artifact_ids = _artifact_ids((*desk_attributions, *ses_attributions))
    return DeskEligibilityRow(
        run_id=bundle.run.run_id,
        desk_id=desk_id,
        desk_node_id=node.node_id,
        label=node.label,
        legal_entity_id=_optional_text(evidence.get("legal_entity_id")),
        division_id=_optional_text(evidence.get("division_id")),
        business_line_id=_optional_text(evidence.get("business_line_id")),
        volcker_desk_id=_optional_text(evidence.get("volcker_desk_id")),
        book_ids=_book_ids(bundle, desk_id),
        eligibility_state=_enum_value(
            evidence,
            "eligibility_state",
            DeskEligibilityState.NO_DATA,
        ),
        pla_state=_enum_value(evidence, "pla_state", PLAState.NO_DATA),
        pla_threshold_profile_id=_optional_text(evidence.get("pla_threshold_profile_id")),
        pla_metric_summary=_mapping(evidence.get("pla_metric_summary")),
        backtesting_state=_enum_value(
            evidence,
            "backtesting_state",
            BacktestingState.NO_DATA,
        ),
        backtesting_zone=_optional_text(evidence.get("backtesting_zone")),
        backtesting_exception_count=_optional_int(evidence.get("backtesting_exception_count")),
        backtesting_window=_optional_text(evidence.get("backtesting_window")),
        latest_exception_date=_optional_date(evidence.get("latest_exception_date")),
        rfet_modellable_count=_optional_int(evidence.get("rfet_modellable_count")),
        nmrf_count=_optional_int(evidence.get("nmrf_count"))
        if evidence.get("nmrf_count") is not None
        else len(ses_attributions),
        ses_amount=_optional_float(evidence.get("ses_amount"))
        if evidence.get("ses_amount") is not None
        else _sum_contributions(ses_attributions),
        capital_consequence_amount=_optional_float(evidence.get("capital_consequence_amount"))
        if evidence.get("capital_consequence_amount") is not None
        else _sum_contributions(desk_attributions),
        capital_consequence_currency=_optional_text(
            evidence.get("capital_consequence_currency"),
        )
        or bundle.run.base_currency,
        capital_node_id=_optional_text(evidence.get("capital_node_id")) or node.node_id,
        pnl_artifact_id=_optional_text(evidence.get("pnl_artifact_id"))
        or _first_artifact(desk_attributions),
        rfet_artifact_id=_optional_text(evidence.get("rfet_artifact_id")),
        source_artifact_id=_optional_text(evidence.get("source_artifact_id"))
        or _first_text(artifact_ids),
        model_run_id=_optional_text(evidence.get("model_run_id")) or bundle.run.run_id,
        profile_hash=_optional_text(evidence.get("profile_hash")),
        source_hashes=_text_tuple(evidence.get("source_hashes")),
        calculation_timestamp=_optional_datetime(evidence.get("calculation_timestamp")),
        metadata={
            "evidence_source": "capital_node.metadata.desk_eligibility",
            "approval_is_advisory": True,
        },
    )


def _ima_desk_nodes(bundle: ResultBundle) -> tuple[CapitalNode, ...]:
    return tuple(
        node
        for node in bundle.nodes
        if str(node.component) == "IMA" and str(node.node_type) == "DESK" and node.desk_id
    )


def _book_ids(bundle: ResultBundle, desk_id: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            {str(node.book_id) for node in bundle.nodes if node.desk_id == desk_id and node.book_id}
        )
    )


def _desk_attributions(
    bundle: ResultBundle,
    desk_id: str,
) -> tuple[CapitalAttributionRecord, ...]:
    return tuple(
        attribution
        for attribution in bundle.attributions
        if attribution.source_level == "DESK"
        and (attribution.source_id == f"desk-{desk_id}" or attribution.source_id == desk_id)
    )


def _ses_attributions(
    bundle: ResultBundle,
    desk_id: str,
) -> tuple[CapitalAttributionRecord, ...]:
    desk_node_ids = {
        node.node_id
        for node in bundle.nodes
        if node.desk_id == desk_id and "SES" in (node.calculation_branch or "")
    }
    return tuple(
        attribution
        for attribution in bundle.attributions
        if attribution.node_id in desk_node_ids and "SES" in attribution.category
    )


def _sum_contributions(attributions: tuple[CapitalAttributionRecord, ...]) -> float | None:
    amounts = [
        attribution.contribution
        if attribution.contribution is not None
        else attribution.base_amount + attribution.residual
        for attribution in attributions
    ]
    if not amounts:
        return None
    return sum(amounts)


def _artifact_ids(attributions: tuple[CapitalAttributionRecord, ...]) -> tuple[str, ...]:
    return tuple(
        sorted({attribution.artifact_id for attribution in attributions if attribution.artifact_id})
    )


def _first_artifact(attributions: tuple[CapitalAttributionRecord, ...]) -> str | None:
    return _first_text(_artifact_ids(attributions))


def _first_text(values: tuple[str, ...]) -> str | None:
    return None if not values else values[0]


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _enum_value(
    evidence: Mapping[str, object],
    key: str,
    default: DeskEligibilityState | PLAState | BacktestingState,
) -> str:
    value = evidence.get(key)
    return default.value if value is None else str(value)


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: object) -> int | None:
    return None if value is None else int(cast(Any, value))


def _optional_float(value: object) -> float | None:
    return None if value is None else float(cast(Any, value))


def _optional_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value))


def _optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return (str(value),)
