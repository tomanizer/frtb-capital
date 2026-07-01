"""Synthetic organisational hierarchy fixtures."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from frtb_result_store.model_enums import FrtbComponent
from frtb_result_store.org_hierarchy_model import (
    OrgCapitalResultRow,
    OrgHierarchy,
    OrgHierarchyLevel,
    OrgHierarchyNode,
    OrgSliceKeys,
)

SAMPLE_HIERARCHY_ID = "enterprise-demo"


def sample_org_hierarchy() -> OrgHierarchy:
    """Return synthetic effective-dated enterprise hierarchy fixture data.

    Returns
    -------
    OrgHierarchy
        Synthetic 2025/2026 hierarchy fixture for Navigator rollup tests.
    """

    return OrgHierarchy(
        hierarchy_id=SAMPLE_HIERARCHY_ID,
        nodes=(_historical_root(), *_sample_2026_nodes()),
    )


def sample_org_capital_rows(
    *,
    run_id: str = "frtb/org-demo/2026-06-03/us-npr",
) -> tuple[OrgCapitalResultRow, ...]:
    """Return synthetic capital rows mapped to the sample organisation tree.

    Parameters
    ----------
    run_id:
        Run identifier to stamp onto each synthetic source row.

    Returns
    -------
    tuple[OrgCapitalResultRow, ...]
        Synthetic component rows mapped at book and desk grain.
    """

    return (
        _row(
            "org-row-sbm-rates-book",
            run_id,
            FrtbComponent.SBM,
            35.0,
            _keys("US_BANK_NA", "MARKETS", "FICC", "USD_RATES_VOLCKER", None, "USD_SWAP_BOOK_01"),
            "hash-sbm-rates-book",
            "book",
        ),
        _row(
            "org-row-ima-rates-desk",
            run_id,
            FrtbComponent.IMA,
            42.0,
            _keys("US_BANK_NA", "MARKETS", "FICC", "USD_RATES_VOLCKER"),
            "hash-ima-rates-desk",
            "desk",
        ),
        _row(
            "org-row-drc-fx-book",
            run_id,
            FrtbComponent.DRC,
            18.0,
            _keys("US_BANK_NA", "MARKETS", "FX", None, "G10_FX_SPOT", "EURUSD_SPOT_BOOK"),
            "hash-drc-fx-book",
            "book",
        ),
        _row(
            "org-row-sbm-equities-book",
            run_id,
            FrtbComponent.SBM,
            8.0,
            _keys("US_BANK_NA", "MARKETS", "EQUITIES", None, "US_CASH_EQUITIES", "US_EQ_BOOK_01"),
            "hash-sbm-equities-book",
            "book",
        ),
        _row(
            "org-row-cva-uk-desk",
            run_id,
            FrtbComponent.CVA,
            11.0,
            _keys("UK_BANK_PLC", "TREASURY", "LIQUIDITY", None, "UK_LIQUIDITY_DESK"),
            "hash-cva-uk-desk",
            "desk",
        ),
    )


def _historical_root() -> OrgHierarchyNode:
    return OrgHierarchyNode(
        SAMPLE_HIERARCHY_ID,
        "2025-01",
        "GLOBAL_GROUP",
        None,
        OrgHierarchyLevel.TOH,
        "Global Group",
        date(2025, 1, 1),
        date(2025, 12, 31),
        {"fixture": "historical"},
    )


def _sample_2026_nodes() -> tuple[OrgHierarchyNode, ...]:
    return (
        _node("GLOBAL_GROUP", None, OrgHierarchyLevel.TOH, "Global Group"),
        _node("US_BANK_NA", "GLOBAL_GROUP", OrgHierarchyLevel.LEGAL_ENTITY, "US Bank NA"),
        _node("UK_BANK_PLC", "GLOBAL_GROUP", OrgHierarchyLevel.LEGAL_ENTITY, "UK Bank PLC"),
        _node("MARKETS", "US_BANK_NA", OrgHierarchyLevel.BUSINESS_DIVISION, "Markets"),
        _node("TREASURY", "UK_BANK_PLC", OrgHierarchyLevel.BUSINESS_DIVISION, "Treasury"),
        _node("FICC", "MARKETS", OrgHierarchyLevel.BUSINESS_LINE, "FICC"),
        _node("FX", "MARKETS", OrgHierarchyLevel.BUSINESS_LINE, "FX"),
        _node("EQUITIES", "MARKETS", OrgHierarchyLevel.BUSINESS_LINE, "Equities"),
        _node("LIQUIDITY", "TREASURY", OrgHierarchyLevel.BUSINESS_LINE, "Liquidity"),
        _node(
            "USD_RATES_VOLCKER",
            "FICC",
            OrgHierarchyLevel.VOLCKER_DESK,
            "USD Rates Volcker",
            {"volcker_desk": "true"},
        ),
        _node("G10_FX_SPOT", "FX", OrgHierarchyLevel.DESK, "G10 FX Spot"),
        _node("US_CASH_EQUITIES", "EQUITIES", OrgHierarchyLevel.DESK, "US Cash Equities"),
        _node("UK_LIQUIDITY_DESK", "LIQUIDITY", OrgHierarchyLevel.DESK, "UK Liquidity Desk"),
        _node("USD_SWAP_BOOK_01", "USD_RATES_VOLCKER", OrgHierarchyLevel.BOOK, "USD Swap Book 01"),
        _node("EURUSD_SPOT_BOOK", "G10_FX_SPOT", OrgHierarchyLevel.BOOK, "EURUSD Spot Book"),
        _node("US_EQ_BOOK_01", "US_CASH_EQUITIES", OrgHierarchyLevel.BOOK, "US Equity Book 01"),
    )


def _node(
    node_id: str,
    parent_id: str | None,
    level: OrgHierarchyLevel,
    label: str,
    metadata: Mapping[str, object] | None = None,
) -> OrgHierarchyNode:
    return OrgHierarchyNode(
        SAMPLE_HIERARCHY_ID,
        "2026-01",
        node_id,
        parent_id,
        level,
        label,
        date(2026, 1, 1),
        None,
        metadata or {},
    )


def _keys(
    legal_entity_id: str,
    business_division_id: str,
    business_line_id: str,
    volcker_desk_id: str | None = None,
    desk_id: str | None = None,
    book_id: str | None = None,
) -> OrgSliceKeys:
    return OrgSliceKeys(
        hierarchy_id=SAMPLE_HIERARCHY_ID,
        version_id="2026-01",
        toh_id="GLOBAL_GROUP",
        legal_entity_id=legal_entity_id,
        business_division_id=business_division_id,
        business_line_id=business_line_id,
        desk_id=desk_id,
        volcker_desk_id=volcker_desk_id,
        book_id=book_id,
    )


def _row(
    source_row_id: str,
    run_id: str,
    component: FrtbComponent,
    capital: float,
    org_keys: OrgSliceKeys,
    source_hash: str,
    grain: str,
) -> OrgCapitalResultRow:
    return OrgCapitalResultRow(
        source_row_id,
        run_id,
        component,
        capital,
        "USD",
        org_keys,
        source_hash=source_hash,
        metadata={"grain": grain},
    )


__all__ = ["SAMPLE_HIERARCHY_ID", "sample_org_capital_rows", "sample_org_hierarchy"]
