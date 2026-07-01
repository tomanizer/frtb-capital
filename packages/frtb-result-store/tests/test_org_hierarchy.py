from __future__ import annotations

import re
import unicodedata
from dataclasses import replace
from datetime import date

import frtb_result_store.org_hierarchy_validation as org_validation
import pytest
from frtb_result_store import (
    FrtbComponent,
    OrgCapitalResultRow,
    OrgHierarchy,
    OrgHierarchyLevel,
    OrgHierarchyNode,
    OrgSliceKeys,
    ResultStoreContractError,
    aggregate_by_org_hierarchy,
    generate_org_aggregate_row_id,
    resolve_org_hierarchy_version,
    sample_org_capital_rows,
    sample_org_hierarchy,
    source_rows_for_org_aggregate,
    validate_org_hierarchy,
)


def test_org_contracts_normalize_parent_and_optional_node_keys() -> None:
    raw_parent = "CAFE\u0301"
    node = OrgHierarchyNode(
        "enterprise-demo",
        "2026-01",
        "CHILD",
        raw_parent,
        OrgHierarchyLevel.DESK,
        "Child",
        date(2026, 1, 1),
        None,
    )
    keys = OrgSliceKeys(
        "enterprise-demo",
        "2026-01",
        "GLOBAL_GROUP",
        legal_entity_id="US_BANK_NA",
        desk_id=raw_parent,
    )

    assert node.parent_id == unicodedata.normalize("NFC", raw_parent)
    assert keys.desk_id == unicodedata.normalize("NFC", raw_parent)


def test_org_hierarchy_fixture_validates() -> None:
    hierarchy = sample_org_hierarchy()
    rows = sample_org_capital_rows()

    validate_org_hierarchy(hierarchy, rows, as_of_date=date(2026, 6, 3))

    assert {node.node_id for node in hierarchy.nodes} >= {
        "GLOBAL_GROUP",
        "US_BANK_NA",
        "UK_BANK_PLC",
        "MARKETS",
        "TREASURY",
        "FICC",
        "FX",
        "EQUITIES",
        "USD_RATES_VOLCKER",
        "G10_FX_SPOT",
        "US_CASH_EQUITIES",
        "USD_SWAP_BOOK_01",
        "EURUSD_SPOT_BOOK",
        "US_EQ_BOOK_01",
    }
    assert any(node.level is OrgHierarchyLevel.VOLCKER_DESK for node in hierarchy.nodes)
    assert any(row.org_keys.book_id is not None for row in rows)
    assert any(row.org_keys.book_id is None and row.org_keys.desk_id for row in rows)


def test_org_hierarchy_rejects_missing_parent() -> None:
    hierarchy = sample_org_hierarchy()
    broken_nodes = tuple(
        replace(node, parent_id="MISSING_PARENT") if node.node_id == "FICC" else node
        for node in hierarchy.nodes
    )

    with pytest.raises(ResultStoreContractError, match="parent node not found"):
        validate_org_hierarchy(OrgHierarchy(hierarchy.hierarchy_id, broken_nodes))


def test_org_hierarchy_rejects_duplicate_node() -> None:
    hierarchy = sample_org_hierarchy()
    duplicate_ficc = next(node for node in hierarchy.nodes if node.node_id == "FICC")
    duplicate_us = next(node for node in hierarchy.nodes if node.node_id == "US_BANK_NA")

    with pytest.raises(
        ResultStoreContractError,
        match="duplicate org hierarchy nodes: FICC, US_BANK_NA",
    ):
        validate_org_hierarchy(
            OrgHierarchy(hierarchy.hierarchy_id, (*hierarchy.nodes, duplicate_us, duplicate_ficc))
        )


def test_org_hierarchy_rejects_cycles() -> None:
    hierarchy = sample_org_hierarchy()
    broken_nodes = tuple(
        replace(node, parent_id="USD_SWAP_BOOK_01") if node.node_id == "FICC" else node
        for node in hierarchy.nodes
    )

    with pytest.raises(ResultStoreContractError, match="cycle"):
        validate_org_hierarchy(OrgHierarchy(hierarchy.hierarchy_id, broken_nodes))


def test_org_hierarchy_resolves_version_by_run_date() -> None:
    hierarchy = sample_org_hierarchy()

    assert resolve_org_hierarchy_version(hierarchy, date(2025, 6, 3)) == "2025-01"
    assert resolve_org_hierarchy_version(hierarchy, date(2026, 6, 3)) == "2026-01"

    with pytest.raises(ResultStoreContractError, match="exactly one hierarchy version"):
        resolve_org_hierarchy_version(hierarchy, date(2024, 12, 31))


def test_org_toh_rollup_matches_source_rows() -> None:
    rows = sample_org_capital_rows()
    aggregates = aggregate_by_org_hierarchy(
        rows,
        sample_org_hierarchy(),
        [OrgHierarchyLevel.TOH],
        as_of_date=date(2026, 6, 3),
    )

    assert [(row.node_id, row.capital, row.source_row_count) for row in aggregates] == [
        ("GLOBAL_GROUP", 114.0, 5)
    ]
    assert aggregates[0].component_breakdown == {
        "CVA": 11.0,
        "DRC": 18.0,
        "IMA": 42.0,
        "SBM": 43.0,
    }


def test_org_validation_reports_missing_version_map_without_key_error() -> None:
    hierarchy = sample_org_hierarchy()
    row = sample_org_capital_rows()[0]
    node_index = org_validation._node_index(hierarchy.nodes)

    with pytest.raises(ResultStoreContractError, match="hierarchy version not found: 2026-01"):
        org_validation._validate_row_mapping(row, node_index, {})


def test_org_legal_entity_rollups_match_toh() -> None:
    aggregates = aggregate_by_org_hierarchy(
        sample_org_capital_rows(),
        sample_org_hierarchy(),
        [OrgHierarchyLevel.TOH, OrgHierarchyLevel.LEGAL_ENTITY],
        as_of_date=date(2026, 6, 3),
    )
    by_node = {row.node_id: row for row in aggregates}

    assert by_node["US_BANK_NA"].capital == 103.0
    assert by_node["UK_BANK_PLC"].capital == 11.0
    assert by_node["US_BANK_NA"].parent_id == by_node["GLOBAL_GROUP"].row_id
    assert by_node["UK_BANK_PLC"].parent_id == by_node["GLOBAL_GROUP"].row_id
    assert by_node["US_BANK_NA"].capital + by_node["UK_BANK_PLC"].capital == (
        by_node["GLOBAL_GROUP"].capital
    )


def test_org_aggregation_filters_other_hierarchy_rows_before_validation() -> None:
    aggregates = aggregate_by_org_hierarchy(
        (*sample_org_capital_rows(), _unmapped_other_hierarchy_row()),
        sample_org_hierarchy(),
        [OrgHierarchyLevel.TOH],
        as_of_date=date(2026, 6, 3),
    )

    assert [(row.node_id, row.capital, row.source_row_count) for row in aggregates] == [
        ("GLOBAL_GROUP", 114.0, 5)
    ]


def test_org_business_desk_book_grouping_is_stable() -> None:
    hierarchy = sample_org_hierarchy()
    rows = sample_org_capital_rows()
    grouping = [
        OrgHierarchyLevel.LEGAL_ENTITY,
        OrgHierarchyLevel.BUSINESS_DIVISION,
        OrgHierarchyLevel.BUSINESS_LINE,
        OrgHierarchyLevel.DESK,
        OrgHierarchyLevel.BOOK,
    ]

    first = aggregate_by_org_hierarchy(rows, hierarchy, grouping, as_of_date=date(2026, 6, 3))
    second = aggregate_by_org_hierarchy(rows, hierarchy, grouping, as_of_date=date(2026, 6, 3))

    assert [row.row_id for row in first] == [row.row_id for row in second]
    assert all(re.fullmatch(r"orgagg_[0-9a-f]{64}", row.row_id) for row in first)
    by_node = {row.node_id: row for row in first}
    assert by_node["MARKETS"].capital == 103.0
    assert by_node["FICC"].capital == 77.0
    assert by_node["USD_RATES_VOLCKER"].capital == 77.0
    assert by_node["USD_SWAP_BOOK_01"].capital == 35.0


def test_org_volcker_desk_is_queryable() -> None:
    aggregates = aggregate_by_org_hierarchy(
        sample_org_capital_rows(),
        sample_org_hierarchy(),
        [OrgHierarchyLevel.VOLCKER_DESK],
        as_of_date=date(2026, 6, 3),
    )

    assert [(row.node_id, row.level, row.capital) for row in aggregates] == [
        ("USD_RATES_VOLCKER", OrgHierarchyLevel.VOLCKER_DESK, 77.0)
    ]
    assert aggregates[0].metadata["volcker_desk"] == "true"


def test_org_aggregate_source_rows_are_scoped() -> None:
    hierarchy = sample_org_hierarchy()
    rows = sample_org_capital_rows()
    aggregates = aggregate_by_org_hierarchy(
        rows,
        hierarchy,
        [
            OrgHierarchyLevel.TOH,
            OrgHierarchyLevel.LEGAL_ENTITY,
            OrgHierarchyLevel.BUSINESS_DIVISION,
            OrgHierarchyLevel.BUSINESS_LINE,
            OrgHierarchyLevel.DESK,
        ],
        as_of_date=date(2026, 6, 3),
    )
    by_node = {row.node_id: row for row in aggregates}

    volcker_sources = source_rows_for_org_aggregate(
        by_node["USD_RATES_VOLCKER"].row_id,
        rows,
        hierarchy,
    )
    toh_sources = source_rows_for_org_aggregate(
        by_node["GLOBAL_GROUP"].row_id,
        rows,
        hierarchy,
    )

    assert [row.source_row_id for row in volcker_sources] == [
        "org-row-ima-rates-desk",
        "org-row-sbm-rates-book",
    ]
    assert [row.source_row_id for row in toh_sources] == sorted(row.source_row_id for row in rows)


def test_org_aggregate_source_lookup_filters_other_hierarchy_rows_before_validation() -> None:
    hierarchy = sample_org_hierarchy()
    root = next(
        node
        for node in hierarchy.nodes
        if node.node_id == "GLOBAL_GROUP" and node.version_id == "2026-01"
    )
    sources = source_rows_for_org_aggregate(
        generate_org_aggregate_row_id(root),
        (*sample_org_capital_rows(), _unmapped_other_hierarchy_row()),
        hierarchy,
    )

    assert [row.source_row_id for row in sources] == sorted(
        row.source_row_id for row in sample_org_capital_rows()
    )


def test_org_partial_book_granularity_is_supported() -> None:
    aggregates = aggregate_by_org_hierarchy(
        sample_org_capital_rows(),
        sample_org_hierarchy(),
        [OrgHierarchyLevel.DESK, OrgHierarchyLevel.BOOK],
        as_of_date=date(2026, 6, 3),
    )
    by_node = {row.node_id: row for row in aggregates}

    assert by_node["USD_RATES_VOLCKER"].capital == 77.0
    assert by_node["USD_RATES_VOLCKER"].source_row_count == 2
    assert by_node["USD_SWAP_BOOK_01"].capital == 35.0
    assert "org-row-ima-rates-desk" not in {
        row.source_row_id
        for row in source_rows_for_org_aggregate(
            by_node["USD_SWAP_BOOK_01"].row_id,
            sample_org_capital_rows(),
            sample_org_hierarchy(),
        )
    }


def _unmapped_other_hierarchy_row() -> OrgCapitalResultRow:
    return OrgCapitalResultRow(
        "org-row-other-hierarchy",
        "frtb/org-demo/2026-06-03/us-npr",
        FrtbComponent.SBM,
        999.0,
        "USD",
        OrgSliceKeys("other-hierarchy", "2026-01", "OTHER_ROOT", legal_entity_id="OTHER_LE"),
    )
