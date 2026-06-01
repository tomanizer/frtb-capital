from __future__ import annotations

from pathlib import Path
from typing import Any

import frtb_sbm.crif as crif_module
import pyarrow as pa
import pytest
from frtb_sbm import SbmRiskClass, SbmRiskMeasure
from frtb_sbm.arrow_handoff import build_girr_delta_batch_from_handoff
from frtb_sbm.crif import adapt_crif_records, normalize_girr_delta_crif_arrow_table


def test_crif_adapter_maps_girr_delta_row() -> None:
    result = adapt_crif_records(
        [
            {
                "SensitivityId": "crif-girr-001",
                "RowId": "row-1",
                "RiskType": "RISK_IRCURVE",
                "Qualifier": "USD",
                "Bucket": "1",
                "Label1": "5y",
                "Amount": 1_000_000.0,
                "AmountCurrency": "USD",
            }
        ],
        source_file="crif.csv",
    )

    assert len(result.sensitivities) == 1
    sensitivity = result.sensitivities[0]
    assert sensitivity.risk_class is SbmRiskClass.GIRR
    assert sensitivity.risk_measure is SbmRiskMeasure.DELTA
    assert sensitivity.tenor == "5y"
    assert sensitivity.lineage.source_system == "crif"
    assert sensitivity.lineage.source_row_id == "row-1"


def test_crif_adapter_maps_girr_curvature_row() -> None:
    result = adapt_crif_records(
        [
            {
                "TradeId": "crif-curv-001",
                "RiskType": "GIRR_CURVATURE",
                "Qualifier": "USD",
                "Bucket": "1",
                "Label1": "5y",
                "Label2": "5y",
                "CvrUp": -1000.0,
                "CvrDown": -1500.0,
                "AmountCurrency": "USD",
            }
        ]
    )

    sensitivity = result.sensitivities[0]
    assert sensitivity.risk_measure is SbmRiskMeasure.CURVATURE
    assert sensitivity.up_shock_amount == -1000.0
    assert sensitivity.down_shock_amount == -1500.0
    assert sensitivity.tenor == "5y"


def test_crif_adapter_rejects_non_finite_amount() -> None:
    result = adapt_crif_records(
        [
            {
                "SensitivityId": "crif-nan-001",
                "RiskType": "RISK_IRCURVE",
                "Qualifier": "USD",
                "Bucket": "1",
                "Label1": "5y",
                "Amount": "NaN",
                "AmountCurrency": "USD",
            }
        ]
    )
    assert result.rejected_rows
    assert "finite" in result.rejected_rows[0].reason
    assert result.rejected_rows[0].field == "Amount"


def test_crif_adapter_rejects_unsupported_risk_type() -> None:
    result = adapt_crif_records([{"RiskType": "UNKNOWN_RISK", "Amount": 1.0}])
    assert result.rejected_rows
    assert "unsupported CRIF RiskType" in result.rejected_rows[0].reason


def test_girr_delta_crif_arrow_handoff_partitions_without_row_dataclasses() -> None:
    table = pa.table(
        {
            "SensitivityId": ["crif-girr-001", "bad-amount", "fx-row"],
            "RowId": ["row-1", "row-2", "row-3"],
            "RiskType": ["RISK_IRCURVE", "RISK_IRCURVE", "RISK_FX"],
            "Qualifier": ["USD", "USD", "EUR"],
            "Bucket": ["1", "1", "1"],
            "Label1": ["5y", "10y", "spot"],
            "Amount": ["1000000.0", "NaN", "12.0"],
            "AmountCurrency": ["USD", "USD", "USD"],
        }
    )

    handoff = normalize_girr_delta_crif_arrow_table(table, source_file="crif.csv")
    batch = build_girr_delta_batch_from_handoff(handoff)

    assert handoff.accepted.num_rows == 1
    assert handoff.rejected is not None
    assert handoff.rejected["source_row_id"].to_pylist() == ["row-2", "row-3"]
    assert [diagnostic.column_name for diagnostic in handoff.diagnostics] == [
        "amount",
        "risk_type",
    ]
    assert batch.row_count == 1
    assert batch.sensitivity_ids.tolist() == ["crif-girr-001"]
    assert batch.risk_classes.tolist() == [SbmRiskClass.GIRR.value]
    assert batch.risk_measures.tolist() == [SbmRiskMeasure.DELTA.value]
    assert batch.risk_factors.tolist() == ["USD"]
    assert batch.tenors.tolist() == ["5y"]
    assert batch.source_hash == handoff.source_hash


def test_girr_delta_crif_arrow_handoff_does_not_construct_sensitivities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_sensitivity_construction(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("CRIF Arrow handoff must not construct SbmSensitivity rows")

    monkeypatch.setattr(crif_module, "SbmSensitivity", fail_sensitivity_construction)
    table = pa.table(
        {
            "SensitivityId": ["crif-girr-001"],
            "RowId": ["row-1"],
            "RiskType": ["RISK_IRCURVE"],
            "Qualifier": ["USD"],
            "Bucket": ["1"],
            "Label1": ["5y"],
            "Amount": ["1000000.0"],
            "AmountCurrency": ["USD"],
        }
    )

    handoff = normalize_girr_delta_crif_arrow_table(table, source_file="crif.csv")
    batch = build_girr_delta_batch_from_handoff(handoff)

    assert batch.row_count == 1
    assert batch.sensitivity_ids.tolist() == ["crif-girr-001"]


def test_crif_module_has_no_dataframe_runtime_dependency() -> None:
    assert "pandas" not in Path(crif_module.__file__).read_text(encoding="utf-8")
    assert "polars" not in Path(crif_module.__file__).read_text(encoding="utf-8")
