from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
from frtb_common import (
    ColumnSpec,
    NullPolicy,
    TabularLogicalType,
    column_spec_to_json_schema,
    column_specs_to_arrow_schema,
    column_specs_to_json_schema,
    validate_arrow_table,
)

from scripts.export_handoff_schema import main as export_schema_main


def test_column_spec_json_schema_extensions_are_present() -> None:
    schema = column_spec_to_json_schema(
        ColumnSpec(
            "amount",
            aliases=("Amount", "value"),
            logical_type=TabularLogicalType.FLOAT,
            required=False,
            null_policy=NullPolicy.ALLOW,
        )
    )

    assert schema["type"] == "number"
    assert schema["x-frtb-aliases"] == ["Amount", "value"]
    assert schema["x-frtb-null-policy"] == "allow"
    assert schema["x-frtb-required"] is False


def test_arrow_schema_round_trip_accepts_validation() -> None:
    specs = (
        ColumnSpec("row_id", logical_type=TabularLogicalType.STRING),
        ColumnSpec("amount", logical_type=TabularLogicalType.FLOAT),
        ColumnSpec(
            "is_active",
            logical_type=TabularLogicalType.BOOLEAN,
            required=False,
            null_policy=NullPolicy.ALLOW,
        ),
    )
    schema = column_specs_to_arrow_schema(specs)
    table = pa.Table.from_arrays(
        [
            pa.array(["r1"], type=schema.field("row_id").type),
            pa.array([1.25], type=schema.field("amount").type),
            pa.array([None], type=schema.field("is_active").type),
        ],
        schema=schema,
    )

    validate_arrow_table(table, column_specs=specs)
    assert schema.field("amount").nullable is False
    assert schema.field("is_active").nullable is True


def test_golden_handoff_schema_files_match_public_specs() -> None:
    import frtb_drc
    import frtb_rrao
    import frtb_sbm

    cases = (
        (
            "docs/schemas/handoff/frtb_rrao.positions.schema.json",
            frtb_rrao.RRAO_HANDOFF_COLUMN_SPECS,
            "frtb_rrao.positions",
        ),
        (
            "docs/schemas/handoff/frtb_drc.nonsec.schema.json",
            frtb_drc.DRC_NONSEC_HANDOFF_COLUMN_SPECS,
            "frtb_drc.nonsec",
        ),
        (
            "docs/schemas/handoff/frtb_sbm.girr_delta.schema.json",
            frtb_sbm.GIRR_DELTA_HANDOFF_COLUMN_SPECS,
            "frtb_sbm.girr_delta",
        ),
    )
    for path, specs, title in cases:
        expected = column_specs_to_json_schema(specs, title=title)
        assert json.loads(_repo_root().joinpath(path).read_text()) == expected


def test_export_handoff_schema_cli_writes_arrow_schema_json(tmp_path: Path) -> None:
    output = tmp_path / "rrao.arrow-schema.json"

    assert (
        export_schema_main(
            (
                "--package",
                "frtb_rrao",
                "--spec",
                "RRAO_HANDOFF_COLUMN_SPECS",
                "--format",
                "arrow",
                "--output",
                str(output),
            )
        )
        == 0
    )

    payload = json.loads(output.read_text())
    first_field = payload["fields"][0]
    assert first_field["name"] == "position_id"
    assert first_field["nullable"] is False
    assert first_field["metadata"]["frtb.logical_type"] == "string"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
