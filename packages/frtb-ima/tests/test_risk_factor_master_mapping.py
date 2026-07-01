"""Tests for v1 risk-factor master mapping adapters."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pyarrow as pa
import pytest
from frtb_common.arrow_table import NormalizedArrowTable

from frtb_ima.adapters.mapping_spec import MappingSpecError, parse_ima_mapping_spec
from frtb_ima.adapters.risk_factor_master_mapping import (
    IMA_RISK_FACTOR_MASTER_ARROW_COLUMN_SPECS,
    IMA_RISK_FACTOR_MASTER_TARGET,
    build_risk_factor_master_batch_from_arrow,
    input_hash_for_risk_factor_master_batch,
    materialize_risk_factor_master_from_mapping,
    materialize_risk_factor_master_from_rows,
)
from frtb_ima.data_models import LiquidityHorizon, RiskClass

MAPPING_YAML = """
mapping_spec_version: 1
target_schema: ima-arrow-v1
source_system: client_risk_engine
base_currency: USD
timezone: Europe/London

sign_convention:
  pnl_positive_means: loss

tables:
  risk_factor_master:
    source: risk_factor_master.csv
    target: ima_risk_factor_master
    fields:
      risk_factor_name: RISK_FACTOR
      risk_factor_id: RISK_FACTOR_ID
      risk_factor_mapping_version: MAPPING_VERSION
      risk_class: RISK_CLASS
      liquidity_horizon: LH
      bucket: BUCKET
      effective_date: EFFECTIVE_DATE
      source_row_id: ROW_ID
"""


def test_risk_factor_master_mapping_materializes_readonly_batch() -> None:
    spec = parse_ima_mapping_spec(MAPPING_YAML)

    result = materialize_risk_factor_master_from_rows(
        [
            {
                "ROW_ID": "r2",
                "RISK_FACTOR": "CSR_IG_5Y",
                "RISK_FACTOR_ID": "rf:csr:ig:5y",
                "MAPPING_VERSION": "ima-map-v1",
                "RISK_CLASS": "CSR",
                "LH": "LH40",
                "BUCKET": "IG",
                "EFFECTIVE_DATE": "2025-01-02",
            },
            {
                "ROW_ID": "r1",
                "RISK_FACTOR": "IR_USD_SWAP_10Y",
                "RISK_FACTOR_ID": "rf:girr:usd-swap:10y",
                "MAPPING_VERSION": "ima-map-v1",
                "RISK_CLASS": "GIRR",
                "LH": "10",
                "BUCKET": "USD",
                "EFFECTIVE_DATE": "2025-01-01",
            },
        ],
        spec,
    )
    batch = result.batch

    assert batch.row_count == 2
    assert batch.risk_factor_names.tolist() == ["CSR_IG_5Y", "IR_USD_SWAP_10Y"]
    assert batch.risk_factor_ids.tolist() == ["rf:csr:ig:5y", "rf:girr:usd-swap:10y"]
    assert batch.risk_factor_mapping_versions.tolist() == ["ima-map-v1", "ima-map-v1"]
    assert batch.risk_classes.tolist() == [RiskClass.CSR.value, RiskClass.GIRR.value]
    assert batch.liquidity_horizons.tolist() == [LiquidityHorizon.LH40.value, 10]
    assert batch.effective_dates.astype("datetime64[D]").astype(str).tolist() == [
        "2025-01-02",
        "2025-01-01",
    ]
    assert batch.source_row_ids.tolist() == ["r2", "r1"]
    assert batch.input_hash == input_hash_for_risk_factor_master_batch(batch)
    assert not batch.risk_factor_names.flags.writeable
    assert not batch.effective_dates.flags.writeable
    assert batch.liquidity_horizon_by_name()["IR_USD_SWAP_10Y"] == LiquidityHorizon.LH10
    assert batch.risk_class_by_name()["CSR_IG_5Y"] == RiskClass.CSR
    assert batch.risk_factor_id_by_name()["IR_USD_SWAP_10Y"] == "rf:girr:usd-swap:10y"
    assert batch.mapping_version_by_name()["CSR_IG_5Y"] == "ima-map-v1"
    assert result.report.row_count_read == 2
    assert result.report.row_count_mapped == 2
    assert result.report.passed


def test_risk_factor_master_mapping_rejects_bad_rows_and_duplicates() -> None:
    spec = parse_ima_mapping_spec(MAPPING_YAML)

    result = materialize_risk_factor_master_from_rows(
        [
            {
                "ROW_ID": "good",
                "RISK_FACTOR": "IR_USD_SWAP_10Y",
                "RISK_CLASS": "GIRR",
                "LH": "10D",
                "BUCKET": "USD",
                "EFFECTIVE_DATE": "2025-01-01",
            },
            {
                "ROW_ID": "bad-class",
                "RISK_FACTOR": "BAD_RF",
                "RISK_CLASS": "UNKNOWN",
                "LH": "10",
                "BUCKET": "X",
                "EFFECTIVE_DATE": "2025-01-01",
            },
            {
                "ROW_ID": "bad-lh",
                "RISK_FACTOR": "BAD_LH",
                "RISK_CLASS": "FX",
                "LH": "30",
                "BUCKET": "FX",
                "EFFECTIVE_DATE": "2025-01-01",
            },
            {
                "ROW_ID": "duplicate",
                "RISK_FACTOR": "IR_USD_SWAP_10Y",
                "RISK_CLASS": "GIRR",
                "LH": "20",
                "BUCKET": "USD",
                "EFFECTIVE_DATE": "2025-01-01",
            },
        ],
        spec,
    )

    assert result.report.row_count_read == 4
    assert result.report.row_count_mapped == 1
    assert result.report.row_count_rejected == 3
    assert not result.report.passed
    assert [finding.code for finding in result.report.findings] == [
        "RISK_FACTOR_MASTER_ROW_REJECTED",
        "RISK_FACTOR_MASTER_ROW_REJECTED",
        "RISK_FACTOR_MASTER_DUPLICATE_KEY",
    ]


def test_risk_factor_master_mapping_requires_table_for_materialization() -> None:
    spec = parse_ima_mapping_spec(
        MAPPING_YAML.replace(
            "  risk_factor_master:\n"
            "    source: risk_factor_master.csv\n"
            "    target: ima_risk_factor_master\n"
            "    fields:\n"
            "      risk_factor_name: RISK_FACTOR\n"
            "      risk_factor_id: RISK_FACTOR_ID\n"
            "      risk_factor_mapping_version: MAPPING_VERSION\n"
            "      risk_class: RISK_CLASS\n"
            "      liquidity_horizon: LH\n"
            "      bucket: BUCKET\n"
            "      effective_date: EFFECTIVE_DATE\n"
            "      source_row_id: ROW_ID\n",
            "  daily_pnl_vectors:\n"
            "    source: daily.csv\n"
            "    target: ima_daily_pnl_vectors\n"
            "    fields:\n"
            "      desk_id: DESK\n"
            "      business_date: DATE\n"
            "      apl: APL\n"
            "      hpl: HPL\n"
            "      rtpl: RTPL\n",
        )
    )

    with pytest.raises(MappingSpecError, match="risk_factor_master"):
        materialize_risk_factor_master_from_rows([], spec)


def test_risk_factor_master_mapping_rejects_unknown_target_fields() -> None:
    with pytest.raises(MappingSpecError, match="unknown risk_factor_master target fields"):
        parse_ima_mapping_spec(MAPPING_YAML.replace("source_row_id: ROW_ID", "mystery: X"))


def test_risk_factor_master_mapping_exposes_column_specs() -> None:
    assert IMA_RISK_FACTOR_MASTER_TARGET == "ima_risk_factor_master"
    assert [spec.name for spec in IMA_RISK_FACTOR_MASTER_ARROW_COLUMN_SPECS] == [
        "risk_factor_name",
        "risk_factor_id",
        "risk_factor_mapping_version",
        "risk_class",
        "liquidity_horizon",
        "bucket",
        "effective_date",
        "source_row_id",
    ]


def test_risk_factor_master_mapping_materializes_from_csv(tmp_path: Path) -> None:
    source = tmp_path / "risk_factor_master.csv"
    source.write_text(
        "ROW_ID,RISK_FACTOR,RISK_FACTOR_ID,MAPPING_VERSION,RISK_CLASS,LH,BUCKET,EFFECTIVE_DATE\n"
        "r1,EURUSD_FX,rf:fx:eurusd,ima-map-v1,FX,10,FX,2025-01-01\n",
        encoding="utf-8",
    )
    spec = parse_ima_mapping_spec(MAPPING_YAML)

    result = materialize_risk_factor_master_from_mapping(spec, source_root=tmp_path)

    assert result.batch.row_count == 1
    assert result.batch.risk_factor_names.tolist() == ["EURUSD_FX"]
    assert result.batch.risk_factor_ids.tolist() == ["rf:fx:eurusd"]
    assert result.report.source_file == "risk_factor_master.csv"


def test_risk_factor_master_arrow_batch_tolerates_missing_optional_id_columns() -> None:
    table = pa.table(
        {
            "risk_factor_name": ["EURUSD_FX"],
            "risk_class": ["FX"],
            "liquidity_horizon": [10],
            "bucket": ["FX"],
            "effective_date": [date(2025, 1, 1)],
            "source_row_id": ["r1"],
        }
    )
    normalized = NormalizedArrowTable(
        accepted=table,
        column_specs=IMA_RISK_FACTOR_MASTER_ARROW_COLUMN_SPECS,
    )

    batch = build_risk_factor_master_batch_from_arrow(normalized)

    assert batch.risk_factor_ids.tolist() == [""]
    assert batch.risk_factor_mapping_versions.tolist() == [""]
