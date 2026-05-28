"""Tests for capital-run input lineage manifests."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

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
    with pytest.raises(ValueError, match="validation_messages"):
        replace(lineage, validation_status=InputValidationStatus.FAILED)


def test_capital_run_input_manifest_validates_expectations() -> None:
    manifest = CapitalRunInputManifest(
        run_id="run-1",
        as_of_date=AS_OF,
        artifacts=(_lineage(),),
    )

    assert manifest.require_artifact("scenario_cube.npz", checksum="a" * 64) == _lineage()
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
    assert rfet_observations.record_count > 0
    assert manifest.as_dict()["run_id"] == "capital_run_v1"
