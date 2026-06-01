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


@pytest.mark.parametrize(
    ("row", "risk_class", "risk_factor", "qualifier"),
    [
        (
            {
                "RiskType": "Risk_FXVol",
                "Qualifier": "EUR",
                "Bucket": "EUR",
                "Label1": "1y",
                "Amount": 1_000.0,
            },
            SbmRiskClass.FX,
            "EUR",
            None,
        ),
        (
            {
                "RiskType": "Risk_EquityVol",
                "Qualifier": "EQ-A",
                "Bucket": "5",
                "Label1": "1y",
                "Amount": 1_000.0,
            },
            SbmRiskClass.EQUITY,
            "SPOT",
            "EQ-A",
        ),
        (
            {
                "RiskType": "Risk_CommodityVol",
                "RiskFactor": "WTI",
                "Bucket": "2",
                "Label1": "1y",
                "Amount": 1_000.0,
            },
            SbmRiskClass.COMMODITY,
            "WTI",
            None,
        ),
        (
            {
                "RiskType": "Risk_CSRNonSecVol",
                "Qualifier": "ISS-A",
                "RiskFactor": "BOND",
                "Bucket": "4",
                "Label1": "1y",
                "Amount": 1_000.0,
            },
            SbmRiskClass.CSR_NONSEC,
            "BOND",
            "ISS-A",
        ),
        (
            {
                "RiskType": "Risk_CSRSecNonCTPVol",
                "Qualifier": "TR-A",
                "RiskFactor": "BOND",
                "Bucket": "1",
                "Label1": "1y",
                "Amount": 1_000.0,
            },
            SbmRiskClass.CSR_SEC_NONCTP,
            "BOND",
            "TR-A",
        ),
        (
            {
                "RiskType": "Risk_CSRSecCTPVol",
                "Qualifier": "UND-A",
                "RiskFactor": "BOND",
                "Bucket": "4",
                "Label1": "1y",
                "Amount": 1_000.0,
            },
            SbmRiskClass.CSR_SEC_CTP,
            "BOND",
            "UND-A",
        ),
    ],
)
def test_crif_adapter_maps_supported_non_girr_vega_rows(
    row: dict[str, object],
    risk_class: SbmRiskClass,
    risk_factor: str,
    qualifier: str | None,
) -> None:
    row = {"SensitivityId": f"{risk_class.value.lower()}-vega", "RowId": "row-vega", **row}
    result = adapt_crif_records([row], source_file="crif.csv")

    assert result.rejected_rows == ()
    assert len(result.sensitivities) == 1
    sensitivity = result.sensitivities[0]
    assert sensitivity.risk_class is risk_class
    assert sensitivity.risk_measure is SbmRiskMeasure.VEGA
    assert sensitivity.risk_factor == risk_factor
    assert sensitivity.qualifier == qualifier
    assert sensitivity.option_tenor == "1y"
    assert sensitivity.source_row_id == "row-vega"
    assert ("RiskType", "risk_measure") in sensitivity.lineage.source_column_map


@pytest.mark.parametrize(
    ("row", "risk_class", "risk_factor", "qualifier"),
    [
        (
            {
                "RiskType": "Risk_FXCurvature",
                "Bucket": "EUR",
                "CvrUp": -10.0,
                "CvrDown": -12.0,
            },
            SbmRiskClass.FX,
            "EUR",
            None,
        ),
        (
            {
                "RiskType": "Risk_EquityCurvature",
                "Qualifier": "EQ-A",
                "Bucket": "5",
                "CvrUp": -10.0,
                "CvrDown": -12.0,
            },
            SbmRiskClass.EQUITY,
            "SPOT",
            "EQ-A",
        ),
        (
            {
                "RiskType": "Risk_CommodityCurvature",
                "RiskFactor": "WTI",
                "Location": "NYMEX",
                "Bucket": "2",
                "CvrUp": -10.0,
                "CvrDown": -12.0,
            },
            SbmRiskClass.COMMODITY,
            "WTI",
            "NYMEX",
        ),
        (
            {
                "RiskType": "Risk_CSRNonSecCurvature",
                "Qualifier": "ISS-A",
                "RiskFactor": "CDS",
                "Bucket": "4",
                "CvrUp": -10.0,
                "CvrDown": -12.0,
            },
            SbmRiskClass.CSR_NONSEC,
            "CDS",
            "ISS-A",
        ),
        (
            {
                "RiskType": "Risk_CSRSecNonCTPCurvature",
                "Qualifier": "TR-A",
                "RiskFactor": "BOND",
                "Bucket": "1",
                "CvrUp": -10.0,
                "CvrDown": -12.0,
            },
            SbmRiskClass.CSR_SEC_NONCTP,
            "BOND",
            "TR-A",
        ),
        (
            {
                "RiskType": "Risk_CSRSecCTPCurvature",
                "Qualifier": "UND-A",
                "RiskFactor": "BOND",
                "Bucket": "4",
                "CvrUp": -10.0,
                "CvrDown": -12.0,
            },
            SbmRiskClass.CSR_SEC_CTP,
            "BOND",
            "UND-A",
        ),
    ],
)
def test_crif_adapter_maps_supported_non_girr_curvature_rows(
    row: dict[str, object],
    risk_class: SbmRiskClass,
    risk_factor: str,
    qualifier: str | None,
) -> None:
    row = {"SensitivityId": f"{risk_class.value.lower()}-curv", "RowId": "row-curv", **row}
    result = adapt_crif_records([row], source_file="crif.csv")

    assert result.rejected_rows == ()
    assert len(result.sensitivities) == 1
    sensitivity = result.sensitivities[0]
    assert sensitivity.risk_class is risk_class
    assert sensitivity.risk_measure is SbmRiskMeasure.CURVATURE
    assert sensitivity.risk_factor == risk_factor
    assert sensitivity.qualifier == qualifier
    assert sensitivity.amount == 0.0
    assert sensitivity.up_shock_amount == -10.0
    assert sensitivity.down_shock_amount == -12.0
    assert ("CvrUp", "up_shock_amount") in sensitivity.lineage.source_column_map
    assert ("CvrDown", "down_shock_amount") in sensitivity.lineage.source_column_map


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


def test_crif_adapter_partitions_validation_rejects_per_row() -> None:
    result = adapt_crif_records(
        [
            {
                "SensitivityId": "valid-fx-vega",
                "RiskType": "FX_VEGA",
                "Qualifier": "EUR",
                "Bucket": "EUR",
                "Label1": "1y",
                "Amount": 1.0,
            },
            {
                "SensitivityId": "missing-csr-basis",
                "RiskType": "CSR_NONSEC_VEGA",
                "Qualifier": "ISS-A",
                "Bucket": "4",
                "Label1": "1y",
                "Amount": 1.0,
            },
            {"SensitivityId": "unknown-risk", "RiskType": "UNKNOWN_RISK", "Amount": 1.0},
        ]
    )

    assert [item.sensitivity_id for item in result.sensitivities] == ["valid-fx-vega"]
    assert len(result.rejected_rows) == 2
    assert [item.field for item in result.rejected_rows] == ["RiskFactor", "RiskType"]


def test_crif_adapter_rejects_unsupported_equity_repo_vega() -> None:
    result = adapt_crif_records(
        [
            {
                "SensitivityId": "eq-repo-vega",
                "RiskType": "EQ_VEGA",
                "Qualifier": "EQ-A",
                "RiskFactor": "REPO",
                "Bucket": "5",
                "Label1": "1y",
                "Amount": 1.0,
            }
        ]
    )

    assert result.sensitivities == ()
    assert len(result.rejected_rows) == 1
    assert "repo rates" in result.rejected_rows[0].reason


def test_crif_adapter_rejects_duplicate_sensitivity_ids_without_aborting() -> None:
    result = adapt_crif_records(
        [
            {
                "SensitivityId": "dup-id",
                "RowId": "row-1",
                "RiskType": "FX_VEGA",
                "Qualifier": "EUR",
                "Bucket": "EUR",
                "Label1": "1y",
                "Amount": 1.0,
            },
            {
                "SensitivityId": "dup-id",
                "RowId": "row-2",
                "RiskType": "FX_VEGA",
                "Qualifier": "GBP",
                "Bucket": "GBP",
                "Label1": "1y",
                "Amount": 2.0,
            },
        ]
    )

    assert [item.source_row_id for item in result.sensitivities] == ["row-1"]
    assert len(result.rejected_rows) == 1
    assert result.rejected_rows[0].source_row_id == "row-2"
    assert result.rejected_rows[0].field == "sensitivity_id"


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
