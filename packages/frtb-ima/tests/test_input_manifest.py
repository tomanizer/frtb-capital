"""Tests for capital-run input lineage manifests."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

import pyarrow as pa
import pytest
from frtb_common import NormalizedTabularHandoff, normalized_handoff_hash, source_content_hash

from frtb_ima import (
    build_capital_run_input_manifest_from_handoff,
    normalize_ima_input_manifest_arrow_table,
)
from frtb_ima.input_manifest import (
    CapitalRunInputManifest,
    InputArtifactLineage,
    InputValidationStatus,
    capital_run_input_manifest_from_fixture,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "capital_run_v1"
AS_OF = date(2026, 5, 27)


def _lineage(name: str = "scenario_cube.npz") -> InputArtifactLineage:
    return InputArtifactLineage(
        artifact_name=name,
        artifact_type="npz",
        schema_version="capital_run_fixture_v1",
        source_system="synthetic_fixture",
        source_version="1",
        extraction_timestamp=datetime(2026, 5, 27, tzinfo=UTC),
        as_of_date=AS_OF,
        record_count=10,
        vector_count=1,
        checksum="a" * 64,
        sign_convention="positive_loss",
    )


def test_input_artifact_lineage_validates_required_controls() -> None:
    lineage = _lineage()

    assert lineage.as_dict()["validation_status"] == InputValidationStatus.PASSED.value
    with pytest.raises(ValueError, match="artifact_name"):
        replace(lineage, artifact_name="")
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(lineage, extraction_timestamp=datetime(2026, 5, 27))
    with pytest.raises(ValueError, match="record_count"):
        replace(lineage, record_count=-1)
    with pytest.raises(ValueError, match="SHA-256"):
        replace(lineage, checksum="not-a-sha")
    with pytest.raises(ValueError, match="lowercase"):
        replace(lineage, checksum="A" * 64)
    with pytest.raises(ValueError, match="validation_messages"):
        replace(lineage, validation_status=InputValidationStatus.FAILED)


def test_capital_run_input_manifest_validates_expectations() -> None:
    manifest = CapitalRunInputManifest(
        run_id="run-1",
        as_of_date=AS_OF,
        artifacts=(_lineage(),),
    )

    assert manifest.require_artifact("scenario_cube.npz", checksum="a" * 64) == _lineage()
    assert manifest.manifest_hash == manifest.manifest_hash_without_self_reference()
    assert manifest.as_dict()["manifest_hash"] == manifest.manifest_hash
    assert manifest.compact_summary()["artifact_count"] == 1
    with pytest.raises(KeyError, match="missing input artifact"):
        manifest.artifact("missing.csv")
    with pytest.raises(ValueError, match="checksum mismatch"):
        manifest.require_artifact("scenario_cube.npz", checksum="b" * 64)
    with pytest.raises(ValueError, match="sign_convention mismatch"):
        manifest.require_artifact("scenario_cube.npz", sign_convention="positive_profit")
    with pytest.raises(ValueError, match="record_count mismatch"):
        manifest.require_artifact("scenario_cube.npz", record_count=11)
    with pytest.raises(ValueError, match="vector_count mismatch"):
        manifest.require_artifact("scenario_cube.npz", vector_count=2)


def test_capital_run_input_manifest_rejects_missing_and_duplicate_artifacts() -> None:
    with pytest.raises(ValueError, match="artifacts"):
        CapitalRunInputManifest(run_id="run-1", as_of_date=AS_OF, artifacts=())
    with pytest.raises(ValueError, match="duplicate"):
        CapitalRunInputManifest(
            run_id="run-1",
            as_of_date=AS_OF,
            artifacts=(_lineage(), _lineage()),
        )
    with pytest.raises(ValueError, match="as_of_date"):
        CapitalRunInputManifest(
            run_id="run-1",
            as_of_date=AS_OF,
            artifacts=(replace(_lineage(), as_of_date=date(2026, 5, 28)),),
        )


def test_fixture_manifest_maps_to_capital_run_input_manifest() -> None:
    fixture_manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text())
    manifest = capital_run_input_manifest_from_fixture(
        FIXTURE_ROOT,
        fixture_manifest,
        run_id="capital_run_v1",
        as_of_date=AS_OF,
    )

    scenario_cube = manifest.require_artifact(
        "scenario_cube.npz",
        checksum=fixture_manifest["files"]["scenario_cube.npz"]["sha256"],
        vector_count=3,
    )
    rfet_observations = manifest.require_artifact("rfet_observations.csv")

    assert manifest.artifact_count == len(fixture_manifest["files"])
    assert scenario_cube.sign_convention == '{"cube":"positive_loss"}'
    assert scenario_cube.metadata["fixture"] == "capital_run_v1"
    assert str(FIXTURE_ROOT) not in json.dumps(scenario_cube.as_dict())
    assert rfet_observations.record_count > 0
    assert manifest.as_dict()["run_id"] == "capital_run_v1"


def test_arrow_handoff_builds_capital_run_input_manifest_with_lineage() -> None:
    source_hash = source_content_hash("synthetic ima lineage table")
    handoff = normalize_ima_input_manifest_arrow_table(
        _artifact_handoff_table(("scenario_cube.npz", "rfet_observations.csv")),
        metadata={"run_id": "ima-run-001", "producer": "risk-engine"},
        source_hash=source_hash,
    )

    manifest = build_capital_run_input_manifest_from_handoff(handoff)

    scenario_cube = manifest.artifact("scenario_cube.npz")
    rfet_observations = manifest.artifact("rfet_observations.csv")
    assert manifest.run_id == "ima-run-001"
    assert manifest.as_of_date == AS_OF
    assert manifest.metadata["producer"] == "risk-engine"
    assert manifest.metadata["source_hash"] == source_hash
    assert len(normalized_handoff_hash(handoff)) == 64
    assert scenario_cube.metadata["fixture"] == "capital_run_v1"
    assert scenario_cube.metadata["source_row_id"] == "row-scenario_cube.npz"
    assert rfet_observations.validation_status is InputValidationStatus.WARNING
    assert rfet_observations.validation_messages == ("row count was adapter-normalised",)


def test_arrow_handoff_manifest_hash_is_stable_across_row_order() -> None:
    source_hash = source_content_hash("same source")
    first = build_capital_run_input_manifest_from_handoff(
        normalize_ima_input_manifest_arrow_table(
            _artifact_handoff_table(("scenario_cube.npz", "rfet_observations.csv")),
            metadata={"run_id": "ima-run-001"},
            source_hash=source_hash,
        )
    )
    second = build_capital_run_input_manifest_from_handoff(
        normalize_ima_input_manifest_arrow_table(
            _artifact_handoff_table(("rfet_observations.csv", "scenario_cube.npz")),
            metadata={"run_id": "ima-run-001"},
            source_hash=source_hash,
        )
    )

    assert first.manifest_hash == second.manifest_hash


def test_arrow_handoff_requires_run_id_metadata_or_argument() -> None:
    handoff = normalize_ima_input_manifest_arrow_table(
        _artifact_handoff_table(("scenario_cube.npz",)),
    )

    with pytest.raises(ValueError, match="run_id"):
        build_capital_run_input_manifest_from_handoff(handoff)

    manifest = build_capital_run_input_manifest_from_handoff(handoff, run_id="explicit-run")

    assert manifest.run_id == "explicit-run"


def test_arrow_handoff_rejects_non_object_metadata_json() -> None:
    table = _artifact_handoff_table(("scenario_cube.npz",)).set_column(
        13,
        "metadata_json",
        pa.array(["[]"]),
    )
    handoff = normalize_ima_input_manifest_arrow_table(
        table,
        metadata={"run_id": "ima-run-001"},
    )

    with pytest.raises(ValueError, match="metadata_json"):
        build_capital_run_input_manifest_from_handoff(handoff)


def test_arrow_handoff_accepts_manifest_metadata_controls() -> None:
    table = _replace_handoff_column(
        _artifact_handoff_table(("scenario_cube.npz",)),
        "extractionTimestamp",
        ["2026-05-27T09:30:00Z"],
    )
    handoff = normalize_ima_input_manifest_arrow_table(
        table,
        metadata={
            "run_id": "metadata-run",
            "manifest_schema_version": "ima_manifest_v2",
            "as_of_date": AS_OF.isoformat(),
            "producer": "risk-engine",
        },
    )

    manifest = build_capital_run_input_manifest_from_handoff(
        handoff,
        metadata={"consumer": "capital-library"},
    )

    assert manifest.run_id == "metadata-run"
    assert manifest.as_of_date == AS_OF
    assert manifest.schema_version == "ima_manifest_v2"
    assert manifest.metadata == {
        "producer": "risk-engine",
        "consumer": "capital-library",
    }
    assert manifest.artifact("scenario_cube.npz").extraction_timestamp == datetime(
        2026, 5, 27, 9, 30, tzinfo=UTC
    )


def test_arrow_handoff_accepts_explicit_manifest_controls() -> None:
    handoff = normalize_ima_input_manifest_arrow_table(
        _artifact_handoff_table(("scenario_cube.npz",)),
    )

    manifest = build_capital_run_input_manifest_from_handoff(
        handoff,
        run_id="explicit-run",
        as_of_date=datetime(2026, 5, 27, tzinfo=UTC),
        schema_version="ima_manifest_explicit_v2",
    )

    assert manifest.run_id == "explicit-run"
    assert manifest.as_of_date == AS_OF
    assert manifest.schema_version == "ima_manifest_explicit_v2"


def test_arrow_handoff_defaults_when_optional_columns_are_absent() -> None:
    optional_columns = {
        "validationStatus",
        "validationMessages",
        "metadataJson",
        "sourceRowId",
    }
    base_table = _artifact_handoff_table(("scenario_cube.npz",))
    table = base_table.select(
        [
            column_name
            for column_name in base_table.column_names
            if column_name not in optional_columns
        ]
    )
    handoff = normalize_ima_input_manifest_arrow_table(
        table,
        metadata={"run_id": "ima-run-001"},
    )

    manifest = build_capital_run_input_manifest_from_handoff(handoff)
    artifact = manifest.artifact("scenario_cube.npz")

    assert artifact.validation_status is InputValidationStatus.PASSED
    assert artifact.validation_messages == ()
    assert artifact.metadata == {}


def test_arrow_handoff_accepts_plain_validation_message() -> None:
    table = _replace_handoff_column(
        _artifact_handoff_table(("scenario_cube.npz",)),
        "validationMessages",
        ["single warning"],
    )
    handoff = normalize_ima_input_manifest_arrow_table(
        table,
        metadata={"run_id": "ima-run-001"},
    )

    artifact = build_capital_run_input_manifest_from_handoff(handoff).artifact("scenario_cube.npz")

    assert artifact.validation_messages == ("single warning",)


def test_arrow_handoff_treats_invalid_json_validation_message_as_plain_text() -> None:
    table = _replace_handoff_column(
        _artifact_handoff_table(("scenario_cube.npz",)),
        "validationMessages",
        ["[not-json"],
    )
    handoff = normalize_ima_input_manifest_arrow_table(
        table,
        metadata={"run_id": "ima-run-001"},
    )

    artifact = build_capital_run_input_manifest_from_handoff(handoff).artifact("scenario_cube.npz")

    assert artifact.validation_messages == ("[not-json",)


def test_arrow_handoff_requires_explicit_manifest_date_for_mixed_artifact_dates() -> None:
    table = _replace_handoff_column(
        _artifact_handoff_table(("scenario_cube.npz", "rfet_observations.csv")),
        "asOfDate",
        [AS_OF, date(2026, 5, 28)],
    )
    handoff = normalize_ima_input_manifest_arrow_table(
        table,
        metadata={"run_id": "ima-run-001"},
    )

    with pytest.raises(ValueError, match="as_of_date"):
        build_capital_run_input_manifest_from_handoff(handoff)


@pytest.mark.parametrize(
    ("column_name", "replacement", "match"),
    (
        ("artifactName", [""], "artifact_name"),
        ("extractionTimestamp", [AS_OF], "extraction_timestamp"),
        ("asOfDate", [42], "as_of_date"),
        ("recordCount", [True], "record_count must contain integers"),
        ("recordCount", [-1], "record_count must be non-negative"),
        ("recordCount", [1.5], "record_count must contain whole-number values"),
    ),
)
def test_arrow_handoff_rejects_invalid_artifact_values(
    column_name: str,
    replacement: list[object],
    match: str,
) -> None:
    handoff = normalize_ima_input_manifest_arrow_table(
        _replace_handoff_column(
            _artifact_handoff_table(("scenario_cube.npz",)),
            column_name,
            replacement,
        ),
        metadata={"run_id": "ima-run-001"},
    )

    with pytest.raises(ValueError, match=match):
        build_capital_run_input_manifest_from_handoff(handoff)


def test_arrow_handoff_rejects_invalid_metadata_json() -> None:
    table = _replace_handoff_column(
        _artifact_handoff_table(("scenario_cube.npz",)),
        "metadataJson",
        ["{"],
    )
    handoff = normalize_ima_input_manifest_arrow_table(
        table,
        metadata={"run_id": "ima-run-001"},
    )

    with pytest.raises(ValueError, match="invalid JSON"):
        build_capital_run_input_manifest_from_handoff(handoff)


@pytest.mark.parametrize(
    ("metadata_json", "match"),
    (
        (json.dumps({"": "missing key"}), "keys"),
        (json.dumps({"desk": 3}), "values"),
    ),
)
def test_arrow_handoff_rejects_invalid_metadata_json_entries(
    metadata_json: str,
    match: str,
) -> None:
    table = _replace_handoff_column(
        _artifact_handoff_table(("scenario_cube.npz",)),
        "metadataJson",
        [metadata_json],
    )
    handoff = normalize_ima_input_manifest_arrow_table(
        table,
        metadata={"run_id": "ima-run-001"},
    )

    with pytest.raises(ValueError, match=match):
        build_capital_run_input_manifest_from_handoff(handoff)


def test_arrow_handoff_requires_normalized_handoff() -> None:
    with pytest.raises(ValueError, match="NormalizedTabularHandoff"):
        build_capital_run_input_manifest_from_handoff(cast(NormalizedTabularHandoff, object()))


def _artifact_handoff_table(artifact_names: tuple[str, ...]) -> pa.Table:
    rows = [_artifact_handoff_row(name) for name in artifact_names]
    return pa.table(
        {
            "artifactName": [row["artifact_name"] for row in rows],
            "artifactType": [row["artifact_type"] for row in rows],
            "schemaVersion": [row["schema_version"] for row in rows],
            "sourceSystem": [row["source_system"] for row in rows],
            "sourceVersion": [row["source_version"] for row in rows],
            "extractionTimestamp": [row["extraction_timestamp"] for row in rows],
            "asOfDate": [row["as_of_date"] for row in rows],
            "recordCount": [row["record_count"] for row in rows],
            "vectorCount": [row["vector_count"] for row in rows],
            "checksum": [row["checksum"] for row in rows],
            "signConvention": [row["sign_convention"] for row in rows],
            "validationStatus": [row["validation_status"] for row in rows],
            "validationMessages": [row["validation_messages"] for row in rows],
            "metadataJson": [row["metadata_json"] for row in rows],
            "sourceRowId": [row["source_row_id"] for row in rows],
        }
    )


def _artifact_handoff_row(artifact_name: str) -> dict[str, object]:
    is_warning = artifact_name == "rfet_observations.csv"
    return {
        "artifact_name": artifact_name,
        "artifact_type": "npz" if artifact_name.endswith(".npz") else "csv",
        "schema_version": "capital_run_fixture_v1",
        "source_system": "synthetic_fixture",
        "source_version": "1",
        "extraction_timestamp": datetime(2026, 5, 27, 9, 30, tzinfo=UTC),
        "as_of_date": AS_OF,
        "record_count": 10 if artifact_name.endswith(".npz") else 25,
        "vector_count": 3 if artifact_name.endswith(".npz") else 0,
        "checksum": "b" * 64 if artifact_name.endswith(".npz") else "c" * 64,
        "sign_convention": "positive_loss" if artifact_name.endswith(".npz") else "not_applicable",
        "validation_status": "WARNING" if is_warning else "PASSED",
        "validation_messages": (
            json.dumps(["row count was adapter-normalised"]) if is_warning else None
        ),
        "metadata_json": json.dumps({"fixture": "capital_run_v1"}, sort_keys=True),
        "source_row_id": f"row-{artifact_name}",
    }


def _replace_handoff_column(
    table: pa.Table,
    column_name: str,
    values: list[object],
) -> pa.Table:
    column_index = table.column_names.index(column_name)
    return table.set_column(column_index, column_name, pa.array(values))
