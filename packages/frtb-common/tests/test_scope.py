from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest
from frtb_common import (
    BookId,
    BusinessDivisionId,
    BusinessLineId,
    CalculationScope,
    CalculationScopeLevel,
    DeskId,
    HierarchyNodeId,
    LegalEntityId,
    ModelApprovalScopeId,
    PortfolioId,
    TradingBookId,
    VolckerDeskId,
    jsonable,
)


def test_calculation_scope_preserves_enterprise_identifiers() -> None:
    scope = CalculationScope(
        level=CalculationScopeLevel.DESK,
        legal_entity_id=LegalEntityId("le-us-broker"),
        business_division_id=BusinessDivisionId("ficc"),
        business_line_id=BusinessLineId("rates"),
        desk_id=DeskId("rates-options"),
        volcker_desk_id=VolckerDeskId("volcker-rates"),
        book_id=BookId("usd-options"),
        trading_book_id=TradingBookId("tb-rates-usd"),
        portfolio_id=PortfolioId("portfolio-rates"),
        hierarchy_node_id=HierarchyNodeId("node-desk-rates-options"),
        model_approval_scope_id=ModelApprovalScopeId("ima-rates-approval"),
        metadata={"source_system": "unit-test"},
    )

    assert scope.level is CalculationScopeLevel.DESK
    assert scope.as_dict() == {
        "level": "DESK",
        "legal_entity_id": "le-us-broker",
        "business_division_id": "ficc",
        "business_line_id": "rates",
        "desk_id": "rates-options",
        "volcker_desk_id": "volcker-rates",
        "book_id": "usd-options",
        "trading_book_id": "tb-rates-usd",
        "portfolio_id": "portfolio-rates",
        "hierarchy_node_id": "node-desk-rates-options",
        "model_approval_scope_id": "ima-rates-approval",
        "metadata": {"source_system": "unit-test"},
    }
    assert jsonable(scope) == scope.as_dict()


def test_top_of_house_scope_can_omit_node_specific_identifiers() -> None:
    scope = CalculationScope(level="TOP_OF_HOUSE")

    assert scope.level is CalculationScopeLevel.TOP_OF_HOUSE
    assert scope.legal_entity_id is None


@pytest.mark.parametrize(
    ("level", "field_name"),
    [
        (CalculationScopeLevel.LEGAL_ENTITY, "legal_entity_id"),
        (CalculationScopeLevel.BUSINESS_DIVISION, "business_division_id"),
        (CalculationScopeLevel.BUSINESS_LINE, "business_line_id"),
        (CalculationScopeLevel.DESK, "desk_id"),
        (CalculationScopeLevel.VOLCKER_DESK, "volcker_desk_id"),
        (CalculationScopeLevel.BOOK, "book_id"),
        (CalculationScopeLevel.TRADING_BOOK, "trading_book_id"),
        (CalculationScopeLevel.PORTFOLIO, "portfolio_id"),
        (CalculationScopeLevel.MODEL_APPROVAL_SCOPE, "model_approval_scope_id"),
        (CalculationScopeLevel.HIERARCHY_NODE, "hierarchy_node_id"),
    ],
)
def test_scope_level_requires_matching_identifier(
    level: CalculationScopeLevel,
    field_name: str,
) -> None:
    with pytest.raises(ValueError, match=f"{level.value} scope requires {field_name}"):
        CalculationScope(level=level)


@pytest.mark.parametrize("value", ["", " desk ", "\tdesk"])
def test_scope_identifier_rejects_unstable_text(value: str) -> None:
    with pytest.raises(ValueError):
        CalculationScope(level=CalculationScopeLevel.DESK, desk_id=value)


def test_scope_rejects_unknown_level() -> None:
    with pytest.raises(ValueError, match="level must be one of"):
        CalculationScope(level="REGION", desk_id="desk")


def test_scope_metadata_is_text_and_immutable() -> None:
    scope = CalculationScope(
        level=CalculationScopeLevel.DESK,
        desk_id="rates-options",
        metadata={"b": "2", "a": "1"},
    )

    assert isinstance(scope.metadata, MappingProxyType)
    assert list(scope.metadata.items()) == [("a", "1"), ("b", "2")]
    with pytest.raises(TypeError):
        scope.metadata["a"] = "changed"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        scope.desk_id = "changed"  # type: ignore[misc]


def test_scope_metadata_rejects_non_text_values() -> None:
    with pytest.raises(TypeError, match="metadata values must be text"):
        CalculationScope(
            level=CalculationScopeLevel.DESK,
            desk_id="rates-options",
            metadata={"count": 1},  # type: ignore[dict-item]
        )


def test_scope_metadata_accepts_none_as_empty_metadata() -> None:
    scope = CalculationScope(
        level=CalculationScopeLevel.DESK,
        desk_id="rates-options",
        metadata=None,
    )

    assert scope.metadata == {}


def test_scope_metadata_rejects_non_mapping_values() -> None:
    with pytest.raises(TypeError, match="metadata must be a mapping"):
        CalculationScope(
            level=CalculationScopeLevel.DESK,
            desk_id="rates-options",
            metadata=("not", "a", "mapping"),  # type: ignore[arg-type]
        )
