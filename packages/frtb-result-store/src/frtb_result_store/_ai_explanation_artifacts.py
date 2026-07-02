"""Artifact and source-row sampling helpers for AI explanation snapshots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlparse

from frtb_result_store._ai_explanation_common import (
    _MAX_SECTION_ROWS,
    _json_value,
    _limitation,
    _optional_text,
    _quote_identifier,
    _source_page_window,
    _sql_literal,
)
from frtb_result_store.model import ArtifactRef


def _source_samples(
    store: Any,
    run_id: str,
    target_type: str,
    state: Mapping[str, object],
) -> tuple[list[dict[str, object]], tuple[str, ...], list[dict[str, object]]]:
    source_page = state.get("source_page")
    artifact_id = _optional_text(state.get("artifact_id"))
    if isinstance(source_page, Mapping):
        artifact_id = _optional_text(source_page.get("artifact_id")) or artifact_id
    if target_type != "source_rows" and artifact_id is None:
        return [], (), []
    if not isinstance(source_page, Mapping):
        return [], (), []
    limit, offset = _source_page_window(source_page)
    if artifact_id is None:
        return (
            [],
            (),
            [
                _limitation(
                    "source_artifact_missing",
                    "No artifact_id was supplied for source-row sampling.",
                )
            ],
        )
    ref = _find_artifact_ref(store, run_id, artifact_id)
    if ref is None:
        return (
            [],
            (artifact_id,),
            [_limitation("source_artifact_missing", f"Artifact {artifact_id!r} was not found.")],
        )
    status = str(ref.metadata.get("artifact_status", "AVAILABLE"))
    if status != "AVAILABLE":
        return (
            [],
            (artifact_id,),
            [
                _limitation(
                    "source_artifact_unavailable", str(ref.metadata.get("status_reason", status))
                )
            ],
        )
    rows = _artifact_rows(store, ref, limit=limit, offset=offset)
    return rows, (artifact_id,), []


def _artifact_rows(
    store: Any, ref: ArtifactRef, *, limit: int, offset: int
) -> list[dict[str, object]]:
    path = _artifact_file_path(store, ref)
    if path is None:
        return []
    import duckdb

    relation = f"read_parquet({_sql_literal(str(path))})"
    with duckdb.connect(database=":memory:") as connection:
        columns = [
            str(row[0])
            for row in connection.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()
        ]
        order_by = ", ".join(_quote_identifier(col) for col in columns)
        rows = connection.execute(
            f"SELECT * FROM {relation} ORDER BY {order_by} LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [{column: _json_value(value) for column, value in zip(columns, row)} for row in rows]


def _artifact_file_path(store: Any, ref: ArtifactRef) -> Path | None:
    parsed = urlparse(ref.uri)
    if parsed.scheme == "file":
        path = Path(unquote(parsed.path)).resolve()
    elif parsed.scheme == "":
        path = Path(ref.uri).resolve()
    else:
        return None
    root = getattr(store, "root", None)
    if not isinstance(root, Path):
        return None
    root = root.resolve()
    if path.suffix != ".parquet" or not path.is_file() or not path.is_relative_to(root):
        return None
    return path


def _find_artifact_ref(store: Any, run_id: str, artifact_id: str) -> ArtifactRef | None:
    for ref in store.artifact_refs(run_id):
        if ref.artifact_id == artifact_id:
            return cast(ArtifactRef, ref)
    return None


def _artifact_refs_for_evidence(
    store: Any,
    run_id: str,
    attributions: Sequence[Mapping[str, object]],
    lineage: Sequence[Mapping[str, object]],
    artifact_sample_refs: Sequence[str],
    state: Mapping[str, object],
) -> tuple[ArtifactRef, ...]:
    artifact_ids = {
        str(row["artifact_id"]) for row in attributions if row.get("artifact_id") is not None
    }
    artifact_ids.update(
        str(row["source_id"])
        for row in lineage
        if row.get("source_type") == "artifact" and row.get("source_id") is not None
    )
    artifact_ids.update(artifact_sample_refs)
    state_artifact_id = _optional_text(state.get("artifact_id"))
    if state_artifact_id is not None:
        artifact_ids.add(state_artifact_id)
    refs = [ref for ref in store.artifact_refs(run_id) if ref.artifact_id in artifact_ids]
    return tuple(sorted(refs, key=lambda item: item.artifact_id))[:_MAX_SECTION_ROWS]
