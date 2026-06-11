"""Row-lineage validation helpers for SBM batch ingress.

Regulatory traceability:
    ADR 0045 validation stage for package-owned SBM batch lineage evidence;
    SBM-AUDIT-001 and SBM-NFR-002 deterministic row mapping diagnostics.
"""

from __future__ import annotations

from frtb_sbm._errors import SbmInputError


def validate_source_column_maps(
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None,
    row_count: int,
) -> None:
    """Validate optional source-column lineage maps for batch rows.

    Parameters
    ----------
    source_column_maps
        Optional row-aligned source-to-canonical field maps.
    row_count
        Expected batch row count.
    """

    if source_column_maps is None:
        return
    if len(source_column_maps) != row_count:
        raise SbmInputError(
            "source_column_maps length must match batch row count",
            field="lineage.source_column_map",
        )
    for row_map in source_column_maps:
        if not isinstance(row_map, tuple | list):
            raise SbmInputError(
                "source column map rows must be field-pair sequences",
                field="lineage.source_column_map",
            )
        for mapping in row_map:
            if not isinstance(mapping, tuple | list) or len(mapping) != 2:
                raise SbmInputError(
                    "source column map entries must be field pairs",
                    field="lineage.source_column_map",
                )
            source_field, canonical_field = mapping
            if not isinstance(source_field, str) or not source_field.strip():
                raise SbmInputError(
                    "source column map entries require non-empty source fields",
                    field="lineage.source_column_map",
                )
            if not isinstance(canonical_field, str) or not canonical_field.strip():
                raise SbmInputError(
                    "source column map entries require non-empty canonical fields",
                    field="lineage.source_column_map",
                )


def validate_mapping_citations(
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None,
    row_count: int,
) -> None:
    """Validate optional row-aligned mapping citation identifiers.

    Parameters
    ----------
    mapping_citation_ids
        Optional row-aligned mapping citation id tuples.
    row_count
        Expected batch row count.
    """

    if mapping_citation_ids is None:
        return
    if len(mapping_citation_ids) != row_count:
        raise SbmInputError(
            "mapping_citation_ids length must match batch row count",
            field="mapping_citation_ids",
        )
    for row_citations in mapping_citation_ids:
        if not isinstance(row_citations, tuple | list):
            raise SbmInputError(
                "mapping_citation_ids rows must be citation-id sequences",
                field="mapping_citation_ids",
            )
        for citation_id in row_citations:
            if not isinstance(citation_id, str) or not citation_id.strip():
                raise SbmInputError(
                    "mapping citation ids must be non-empty strings",
                    field="mapping_citation_ids",
                )


__all__ = ["validate_mapping_citations", "validate_source_column_maps"]
