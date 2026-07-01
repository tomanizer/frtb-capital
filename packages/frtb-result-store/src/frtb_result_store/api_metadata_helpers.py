"""Helpers shared by artifact metadata API routes."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from frtb_result_store.api_artifacts import artifact_page_payload
from frtb_result_store.io import DuckDbParquetResultStore
from frtb_result_store.model import ArtifactRef, ArtifactType

_Jsonable = Callable[[object], object]


def metadata_refs_payload(
    payload_key: str,
    refs: Sequence[ArtifactRef],
    partition_keys: Sequence[str],
    to_jsonable: _Jsonable,
) -> dict[str, object]:
    """Return references, catalog rows, and status counts for a metadata artifact list."""
    return {
        payload_key: to_jsonable(refs),
        "catalog": artifact_metadata_catalog(refs, partition_keys),
        "status_counts": artifact_ref_status_counts(refs),
    }


def artifact_ref_for_partition_value(
    result_store: DuckDbParquetResultStore,
    run_id: str,
    artifact_type: ArtifactType,
    partition_key: str,
    partition_value: str,
    http_exception_type: type[Exception],
) -> ArtifactRef:
    """Return the artifact ref matching one semantic partition value."""
    refs = result_store.artifact_refs(run_id, artifact_type=artifact_type)
    saw_partition_key = False
    for ref in refs:
        partitions = ref.metadata.get("partition_values")
        if isinstance(partitions, Mapping) and partition_key in partitions:
            saw_partition_key = True
            if partitions.get(partition_key) == partition_value:
                return ref
        if ref.artifact_id == partition_value:
            return ref
    if len(refs) == 1 and not saw_partition_key:
        return refs[0]
    raise http_exception_type(  # type: ignore[call-arg]
        status_code=404,
        detail=f"{artifact_type.value} artifact not found for {partition_key}: {partition_value}",
    )


def artifact_ref_for_partition_values(
    result_store: DuckDbParquetResultStore,
    run_id: str,
    artifact_type: ArtifactType,
    partition_values: Mapping[str, str],
    http_exception_type: type[Exception],
) -> ArtifactRef:
    """Return the artifact ref matching all requested semantic partition values."""
    refs = result_store.artifact_refs(run_id, artifact_type=artifact_type)
    for ref in refs:
        partitions = ref.metadata.get("partition_values")
        if not isinstance(partitions, Mapping):
            continue
        if all(partitions.get(key) == value for key, value in partition_values.items()):
            return ref
    requested = ", ".join(f"{key}={value}" for key, value in partition_values.items())
    raise http_exception_type(  # type: ignore[call-arg]
        status_code=404,
        detail=f"{artifact_type.value} artifact not found for partitions: {requested}",
    )


def filtered_artifact_page(
    result_store: DuckDbParquetResultStore,
    ref: ArtifactRef,
    filters: Sequence[str],
    limit: int,
    offset: int,
    http_exception_type: type[Exception],
    to_jsonable: _Jsonable,
) -> dict[str, object]:
    """Return one filtered artifact page using route-local serialization."""
    return artifact_page_payload(
        result_store,
        ref,
        columns=None,
        filters=filters,
        limit=limit,
        offset=offset,
        http_exception_type=http_exception_type,
        to_jsonable=to_jsonable,
    )


def artifact_metadata_catalog(
    refs: Sequence[ArtifactRef],
    partition_keys: Sequence[str],
) -> list[dict[str, object]]:
    """Return lightweight catalog rows from artifact refs and semantic partitions."""
    catalog: list[dict[str, object]] = []
    for ref in refs:
        partitions = ref.metadata.get("partition_values")
        partition_values = partitions if isinstance(partitions, Mapping) else {}
        catalog.append(
            {
                "artifact_id": ref.artifact_id,
                "artifact_type": ArtifactType(ref.artifact_type).value,
                "component": ref.component.value,
                "artifact_status": ref.metadata.get("artifact_status", "AVAILABLE"),
                "status_reason": ref.metadata.get("status_reason", ""),
                "navigator_role": ref.metadata.get("navigator_role", ""),
                "row_count": ref.row_count,
                "partition_values": {
                    key: partition_values[key]
                    for key in partition_keys
                    if key in partition_values
                },
            }
        )
    return catalog


def artifact_ref_status_counts(refs: Sequence[ArtifactRef]) -> dict[str, int]:
    """Return artifact availability counts expected by the navigator UI."""
    counts = {"AVAILABLE": 0, "NO_DATA": 0, "UNSUPPORTED": 0}
    for ref in refs:
        status = str(ref.metadata.get("artifact_status", "AVAILABLE"))
        counts.setdefault(status, 0)
        counts[status] += 1
    return counts
