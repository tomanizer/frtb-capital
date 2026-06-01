"""Shared primitives for the frtb-capital suite."""

from frtb_common._version import __version__
from frtb_common.handoff import (
    DEFAULT_ROW_ID_COLUMN,
    AdapterDiagnostic,
    ChunkPolicy,
    ColumnSpec,
    DiagnosticSeverity,
    DictionaryPolicy,
    NormalizedTabularHandoff,
    NullPolicy,
    TabularHandoffError,
    TabularLogicalType,
    arrow_table_content_hash,
    dictionary_code_chunks,
    dictionary_code_column,
    normalize_arrow_table,
    normalized_handoff_hash,
    resolve_column_name,
    sort_table_by_columns,
    source_content_hash,
    validate_arrow_table,
    validate_column_specs,
)
from frtb_common.regulatory import (
    MissingRegulatoryCitationsError,
    assert_policy_has_regulatory_citations,
)
from frtb_common.serialization import jsonable
from frtb_common.status import (
    CapitalComponentMetadata,
    ImplementationStatus,
    NotImplementedCapitalComponentError,
    UnsupportedRegulatoryFeatureError,
    ValidationStatus,
)

__all__ = [
    "DEFAULT_ROW_ID_COLUMN",
    "AdapterDiagnostic",
    "CapitalComponentMetadata",
    "ChunkPolicy",
    "ColumnSpec",
    "DiagnosticSeverity",
    "DictionaryPolicy",
    "ImplementationStatus",
    "MissingRegulatoryCitationsError",
    "NormalizedTabularHandoff",
    "NotImplementedCapitalComponentError",
    "NullPolicy",
    "TabularHandoffError",
    "TabularLogicalType",
    "UnsupportedRegulatoryFeatureError",
    "ValidationStatus",
    "__version__",
    "arrow_table_content_hash",
    "assert_policy_has_regulatory_citations",
    "dictionary_code_chunks",
    "dictionary_code_column",
    "jsonable",
    "normalize_arrow_table",
    "normalized_handoff_hash",
    "resolve_column_name",
    "sort_table_by_columns",
    "source_content_hash",
    "validate_arrow_table",
    "validate_column_specs",
]
