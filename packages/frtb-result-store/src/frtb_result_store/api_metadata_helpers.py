"""Helpers shared by artifact metadata API routes."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from frtb_result_store.api_artifacts import artifact_page_payload
from frtb_result_store.io import DuckDbParquetResultStore
from frtb_result_store.model import ArtifactRef, ArtifactType, FrtbComponent

_Jsonable = Callable[[object], object]


def metadata_refs_payload(
    payload_key: str,
    refs: Sequence[ArtifactRef],
    partition_keys: Sequence[str],
    to_jsonable: _Jsonable,
) -> dict[str, object]:
    """Return references, catalog rows, and status counts for a metadata artifact list.

    Parameters
    ----------
    payload_key : str
        Top-level payload key for the route-specific artifact reference list.
    refs : Sequence[ArtifactRef]
        Artifact references to serialize.
    partition_keys : Sequence[str]
        Semantic partition keys to expose in catalog rows.
    to_jsonable : _Jsonable
        Serializer for artifact references.

    Returns
    -------
    dict[str, object]
        JSON-ready payload containing the route-specific reference list, catalog rows,
        and availability status counts.
    """
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
    """Return the artifact ref matching one semantic partition value.

    Parameters
    ----------
    result_store : DuckDbParquetResultStore
        Store queried for committed artifact references.
    run_id : str
        Committed run identifier.
    artifact_type : ArtifactType
        Artifact family to search.
    partition_key : str
        Semantic partition key, for example ``time_series_id``.
    partition_value : str
        Requested semantic partition value.
    http_exception_type : type[Exception]
        HTTP exception class used when no ref matches.

    Returns
    -------
    ArtifactRef
        Matching artifact reference.
    """
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
    """Return the artifact ref matching all requested semantic partition values.

    Parameters
    ----------
    result_store : DuckDbParquetResultStore
        Store queried for committed artifact references.
    run_id : str
        Committed run identifier.
    artifact_type : ArtifactType
        Artifact family to search.
    partition_values : Mapping[str, str]
        Required semantic partition key/value pairs.
    http_exception_type : type[Exception]
        HTTP exception class used when no ref matches.

    Returns
    -------
    ArtifactRef
        Matching artifact reference.
    """
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
    """Return one filtered artifact page using route-local serialization.

    Parameters
    ----------
    result_store : DuckDbParquetResultStore
        Store used to locate and read the artifact payload.
    ref : ArtifactRef
        Artifact reference selected by the metadata route.
    filters : Sequence[str]
        Equality filters encoded as ``column=value`` strings.
    limit : int
        Maximum number of rows to return.
    offset : int
        Zero-based row offset for paging.
    http_exception_type : type[Exception]
        HTTP exception class used for invalid artifacts or filters.
    to_jsonable : _Jsonable
        Serializer for artifact references and row values.

    Returns
    -------
    dict[str, object]
        JSON-ready artifact page with rows, paging metadata, and artifact identity.
    """
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
    """Return lightweight catalog rows from artifact refs and semantic partitions.

    Parameters
    ----------
    refs : Sequence[ArtifactRef]
        Artifact references to summarize.
    partition_keys : Sequence[str]
        Semantic partition keys to include in each catalog row.

    Returns
    -------
    list[dict[str, object]]
        Catalog rows for UI routing and metadata selection.
    """
    catalog: list[dict[str, object]] = []
    for ref in refs:
        partitions = ref.metadata.get("partition_values")
        partition_values = partitions if isinstance(partitions, Mapping) else {}
        catalog.append(
            {
                "artifact_id": ref.artifact_id,
                "artifact_type": ArtifactType(ref.artifact_type).value,
                "component": FrtbComponent(ref.component).value,
                "artifact_status": ref.metadata.get("artifact_status", "AVAILABLE"),
                "status_reason": ref.metadata.get("status_reason", ""),
                "navigator_role": ref.metadata.get("navigator_role", ""),
                "row_count": ref.row_count,
                "partition_values": {
                    key: partition_values[key] for key in partition_keys if key in partition_values
                },
            }
        )
    return catalog


def artifact_ref_status_counts(refs: Sequence[ArtifactRef]) -> dict[str, int]:
    """Return artifact availability counts expected by the navigator UI.

    Parameters
    ----------
    refs : Sequence[ArtifactRef]
        Artifact references whose availability status should be counted.

    Returns
    -------
    dict[str, int]
        Counts keyed by artifact availability status.
    """
    counts = {"AVAILABLE": 0, "NO_DATA": 0, "UNSUPPORTED": 0}
    for ref in refs:
        status = str(ref.metadata.get("artifact_status", "AVAILABLE"))
        counts.setdefault(status, 0)
        counts[status] += 1
    return counts
