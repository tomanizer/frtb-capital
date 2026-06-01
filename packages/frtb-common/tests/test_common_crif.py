"""Tests for common CRIF-to-Arrow normalization helpers."""

from __future__ import annotations

import pyarrow as pa
import pytest
from frtb_common import (
    CRIF_SOURCE_ROW_ID_COLUMN,
    CRIF_SOURCE_SYSTEM,
    AdapterDiagnostic,
    CrifColumnSpec,
    CrifRiskTypeMapping,
    DiagnosticSeverity,
    NormalizedTabularHandoff,
    TabularHandoffError,
    TabularLogicalType,
    normalise_crif_risk_type,
    normalize_crif_arrow_table,
    normalize_crif_records,
    resolve_crif_column_name,
)


def _column_specs() -> tuple[CrifColumnSpec, ...]:
    return (
        CrifColumnSpec("trade_id", aliases=("TradeId", "Trade ID"), required=True),
        CrifColumnSpec(CRIF_SOURCE_ROW_ID_COLUMN, aliases=("RowId",)),
        CrifColumnSpec("risk_type", aliases=("RiskType",), required=True),
        CrifColumnSpec("amount", aliases=("Amount",), logical_type=TabularLogicalType.FLOAT),
    )


def test_normalize_crif_arrow_table_partitions_rejections_and_diagnostics() -> None:
    table = pa.table(
        {
            "TradeId": ["t-1", "t-2", "t-3"],
            "RowId": ["r-1", "r-2", "r-3"],
            "RiskType": ["RISK_IRCURVE", "RISK_IRCURVE", "UNKNOWN"],
            "Amount": ["100.25", "not-a-number", "12.0"],
        }
    )

    handoff = normalize_crif_arrow_table(
        table,
        column_specs=_column_specs(),
        risk_type_mappings=(
            CrifRiskTypeMapping(
                ("RISK_IRCURVE",),
                {"risk_class": "GIRR", "risk_measure": "delta"},
            ),
        ),
        source_file="rates.crif.csv",
    )

    assert isinstance(handoff, NormalizedTabularHandoff)
    assert handoff.metadata["source_system"] == CRIF_SOURCE_SYSTEM
    assert handoff.metadata["source_file"] == "rates.crif.csv"
    assert handoff.source_hash
    assert handoff.row_id_column == CRIF_SOURCE_ROW_ID_COLUMN
    assert handoff.accepted.to_pydict() == {
        CRIF_SOURCE_ROW_ID_COLUMN: ["r-1"],
        "amount": [100.25],
        "risk_class": ["GIRR"],
        "risk_measure": ["delta"],
        "risk_type": ["RISK_IRCURVE"],
        "trade_id": ["t-1"],
    }
    assert handoff.rejected is not None
    assert handoff.rejected["source_row_id"].to_pylist() == ["r-2", "r-3"]
    assert [diagnostic.row_id for diagnostic in handoff.diagnostics] == ["r-2", "r-3"]
    assert [diagnostic.column_name for diagnostic in handoff.diagnostics] == [
        "amount",
        "risk_type",
    ]
    assert [diagnostic.severity for diagnostic in handoff.diagnostics] == [
        DiagnosticSeverity.ERROR,
        DiagnosticSeverity.ERROR,
    ]


def test_normalize_crif_records_synthesizes_source_row_ids_and_hashes_deterministically() -> None:
    records = (
        {"TradeId": "t-1", "RiskType": "risk_ircurve", "Amount": "10.0"},
        {"TradeId": "t-2", "RiskType": "risk_ircurve", "Amount": "20.0"},
    )

    handoff = normalize_crif_records(
        records,
        column_specs=_column_specs(),
        risk_type_mappings=(CrifRiskTypeMapping(("RISK_IRCURVE",), {"risk_class": "GIRR"}),),
    )
    repeated = normalize_crif_records(
        records,
        column_specs=_column_specs(),
        risk_type_mappings=(CrifRiskTypeMapping(("RISK_IRCURVE",), {"risk_class": "GIRR"}),),
    )

    assert handoff.source_hash == repeated.source_hash
    assert handoff.accepted["source_row_id"].to_pylist() == ["0", "1"]
    assert handoff.rejected is None


def test_column_discovery_is_case_spacing_and_underscore_insensitive() -> None:
    table = pa.table({"Sensitivity ID": ["s-1"], "risk_type": ["RISK_IRCURVE"]})

    assert resolve_crif_column_name(table, ("sensitivity_id", "SensitivityId")) == (
        "Sensitivity ID"
    )
    assert resolve_crif_column_name(table, ("RiskType",)) == "risk_type"


def test_column_discovery_rejects_ambiguous_aliases() -> None:
    table = pa.table({"RiskType": ["RISK_IRCURVE"], "risk_type": ["RISK_FX"]})

    with pytest.raises(TabularHandoffError, match="multiple input columns"):
        resolve_crif_column_name(table, ("RiskType",))


def test_risk_type_callback_can_partition_without_common_semantics() -> None:
    def mapper(risk_type: str, row: dict[str, object]) -> dict[str, object] | None:
        if normalise_crif_risk_type(risk_type) != "RISK_IRCURVE":
            return None
        return {"package_bucket": f"rates:{row['trade_id']}"}

    handoff = normalize_crif_records(
        ({"TradeId": "t-1", "RiskType": "RISK_IRCURVE", "Amount": "1.0"},),
        column_specs=_column_specs(),
        risk_type_mapper=mapper,
    )

    assert handoff.accepted["package_bucket"].to_pylist() == ["rates:t-1"]
    assert handoff.diagnostics == ()


def test_diagnostics_are_immutable_handoff_records() -> None:
    handoff = normalize_crif_records(
        ({"TradeId": "t-1", "RiskType": "UNKNOWN", "Amount": "1.0"},),
        column_specs=_column_specs(),
        risk_type_mappings=(CrifRiskTypeMapping(("RISK_IRCURVE",), {}),),
    )

    assert isinstance(handoff.diagnostics[0], AdapterDiagnostic)
    assert handoff.diagnostics[0].code == "crif.unsupported_risk_type"
