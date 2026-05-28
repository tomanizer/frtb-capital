"""Input lineage and data-quality manifest contracts for capital runs."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

from frtb_ima.audit_inputs import compute_inputs_hash


class InputValidationStatus(StrEnum):
    """Validation status for one input artifact lineage record."""

    PASSED = "PASSED"
    WARNING = "WARNING"
    FAILED = "FAILED"


@dataclass(frozen=True)
class InputArtifactLineage:
    """Lineage and data-quality evidence for one upstream input artifact."""

    artifact_name: str
    artifact_type: str
    schema_version: str
    source_system: str
    source_version: str
    extraction_timestamp: datetime
    as_of_date: date
    record_count: int
    vector_count: int
    checksum: str
    sign_convention: str
    validation_status: InputValidationStatus = InputValidationStatus.PASSED
    validation_messages: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "artifact_name",
            "artifact_type",
            "schema_version",
            "source_system",
            "source_version",
            "checksum",
            "sign_convention",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")
        _validate_sha256_hex(self.checksum, "checksum")
        if self.extraction_timestamp.tzinfo is None:
            raise ValueError("extraction_timestamp must be timezone-aware")
        if type(self.as_of_date) is not date:
            raise TypeError("as_of_date must be a datetime.date")
        if self.record_count < 0:
            raise ValueError("record_count must be non-negative")
        if self.vector_count < 0:
            raise ValueError("vector_count must be non-negative")
        validation_status = InputValidationStatus(self.validation_status)
        validation_messages = tuple(str(item) for item in self.validation_messages)
        if validation_status == InputValidationStatus.FAILED and not validation_messages:
            raise ValueError("failed validation_status requires validation_messages")
        object.__setattr__(self, "validation_status", validation_status)
        object.__setattr__(self, "validation_messages", validation_messages)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable lineage record."""
        return {
            "artifact_name": self.artifact_name,
            "artifact_type": self.artifact_type,
            "schema_version": self.schema_version,
            "source_system": self.source_system,
            "source_version": self.source_version,
            "extraction_timestamp": self.extraction_timestamp.isoformat(),
            "as_of_date": self.as_of_date.isoformat(),
            "record_count": self.record_count,
            "vector_count": self.vector_count,
            "checksum": self.checksum,
            "sign_convention": self.sign_convention,
            "validation_status": self.validation_status.value,
            "validation_messages": list(self.validation_messages),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CapitalRunInputManifest:
    """Run-level input lineage manifest for production-style audit evidence."""

    run_id: str
    as_of_date: date
    artifacts: tuple[InputArtifactLineage, ...]
    schema_version: str = "frtb_ima_capital_run_input_manifest_v1"
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if type(self.as_of_date) is not date:
            raise TypeError("as_of_date must be a datetime.date")
        if not self.schema_version:
            raise ValueError("schema_version must be non-empty")
        artifacts = tuple(self.artifacts)
        if not artifacts:
            raise ValueError("artifacts must be non-empty")
        names = [artifact.artifact_name for artifact in artifacts]
        if len(names) != len(set(names)):
            raise ValueError("artifacts contains duplicate artifact_name values")
        for artifact in artifacts:
            if artifact.as_of_date != self.as_of_date:
                raise ValueError("all artifacts must have the manifest as_of_date")
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def artifact_count(self) -> int:
        """Number of lineage records in the manifest."""
        return len(self.artifacts)

    @property
    def manifest_hash(self) -> str:
        """Stable SHA-256 digest over the manifest payload."""
        return self.manifest_hash_without_self_reference()

    def artifact(self, artifact_name: str) -> InputArtifactLineage:
        """Return one artifact lineage record by name."""
        for artifact in self.artifacts:
            if artifact.artifact_name == artifact_name:
                return artifact
        raise KeyError(f"missing input artifact lineage for {artifact_name}")

    def require_artifact(
        self,
        artifact_name: str,
        *,
        checksum: str | None = None,
        sign_convention: str | None = None,
        record_count: int | None = None,
        vector_count: int | None = None,
    ) -> InputArtifactLineage:
        """Validate expected lineage controls for one artifact."""
        artifact = self.artifact(artifact_name)
        if checksum is not None and artifact.checksum != checksum:
            raise ValueError(f"checksum mismatch for {artifact_name}")
        if sign_convention is not None and artifact.sign_convention != sign_convention:
            raise ValueError(f"sign_convention mismatch for {artifact_name}")
        if record_count is not None and artifact.record_count != record_count:
            raise ValueError(f"record_count mismatch for {artifact_name}")
        if vector_count is not None and artifact.vector_count != vector_count:
            raise ValueError(f"vector_count mismatch for {artifact_name}")
        return artifact

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable run manifest."""
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "as_of_date": self.as_of_date.isoformat(),
            "artifact_count": self.artifact_count,
            "manifest_hash": self.manifest_hash_without_self_reference(),
            "artifacts": [artifact.as_dict() for artifact in self.artifacts],
            "metadata": dict(self.metadata),
        }

    def manifest_hash_without_self_reference(self) -> str:
        """Hash the manifest fields excluding the displayed hash field."""
        payload = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "as_of_date": self.as_of_date.isoformat(),
            "artifacts": [artifact.as_dict() for artifact in self.artifacts],
            "metadata": dict(self.metadata),
        }
        return compute_inputs_hash(input_manifest=payload)

    def compact_summary(self) -> dict[str, object]:
        """Return a compact summary suitable for audit reports."""
        failed = [
            artifact.artifact_name
            for artifact in self.artifacts
            if artifact.validation_status == InputValidationStatus.FAILED
        ]
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "as_of_date": self.as_of_date.isoformat(),
            "artifact_count": self.artifact_count,
            "manifest_hash": self.manifest_hash_without_self_reference(),
            "failed_artifacts": failed,
        }


def capital_run_input_manifest_from_fixture(
    fixture_root: str | Path,
    fixture_manifest: Mapping[str, Any],
    *,
    run_id: str,
    as_of_date: date,
    extraction_timestamp: datetime = datetime(1970, 1, 1, tzinfo=UTC),
) -> CapitalRunInputManifest:
    """Map the committed synthetic fixture manifest into lineage records."""
    root = Path(fixture_root)
    schema_version = str(fixture_manifest["schema_version"])
    source_version = str(fixture_manifest["generator_version"])
    sign_conventions = fixture_manifest.get("sign_conventions", {})
    artifacts: list[InputArtifactLineage] = []
    for relative_path, file_info in sorted(fixture_manifest["files"].items()):
        path = root / relative_path
        record_count, vector_count = _artifact_counts(path)
        sign_convention = _fixture_sign_convention(relative_path, sign_conventions)
        artifacts.append(
            InputArtifactLineage(
                artifact_name=relative_path,
                artifact_type=path.suffix.lstrip(".") or "file",
                schema_version=schema_version,
                source_system="synthetic_fixture",
                source_version=source_version,
                extraction_timestamp=extraction_timestamp,
                as_of_date=as_of_date,
                record_count=record_count,
                vector_count=vector_count,
                checksum=str(file_info["sha256"]),
                sign_convention=sign_convention,
                metadata={"fixture": root.name},
            )
        )
    return CapitalRunInputManifest(
        run_id=run_id,
        as_of_date=as_of_date,
        artifacts=tuple(artifacts),
        metadata={
            "source": "capital_run_v1_fixture",
            "generator": str(fixture_manifest["generator"]),
        },
    )


def _artifact_counts(path: Path) -> tuple[int, int]:
    if path.suffix == ".csv":
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            return sum(1 for _row in reader), 0
    if path.suffix == ".npz":
        with np.load(path, allow_pickle=False, mmap_mode="r") as payload:
            record_count = 0
            for name in payload.files:
                array = payload[name]
                if array.ndim:
                    record_count = max(record_count, int(array.shape[0]))
            return record_count, len(payload.files)
    if path.suffix == ".json":
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            return len(payload), 0
        if isinstance(payload, list):
            return len(payload), 0
    return 0, 0


def _fixture_sign_convention(
    relative_path: str,
    sign_conventions: Mapping[str, object],
) -> str:
    convention = sign_conventions.get(relative_path)
    if convention is None:
        return "not_applicable"
    return json.dumps(convention, sort_keys=True, separators=(",", ":"))


def _validate_sha256_hex(value: str, field_name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
