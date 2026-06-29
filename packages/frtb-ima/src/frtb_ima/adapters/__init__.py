"""Adapter modules for IMA external data ingress."""

from frtb_ima.adapters.mapping_suggestions import (
    ImaMappingSuggestionReport,
    MappingColumnCandidate,
    MappingFieldSuggestion,
    MappingTableSuggestion,
    build_ima_mapping_suggestion_report,
)
from frtb_ima.adapters.source_profile import (
    SourceColumnProfile,
    SourceProfile,
    profile_csv_source,
    profile_source_rows,
)
from frtb_ima.adapters.validation_report import (
    ImaMappingValidationReport,
    TableValidationSummary,
    build_ima_mapping_validation_report,
)

__all__ = [
    "ImaMappingSuggestionReport",
    "ImaMappingValidationReport",
    "MappingColumnCandidate",
    "MappingFieldSuggestion",
    "MappingTableSuggestion",
    "SourceColumnProfile",
    "SourceProfile",
    "TableValidationSummary",
    "build_ima_mapping_suggestion_report",
    "build_ima_mapping_validation_report",
    "profile_csv_source",
    "profile_source_rows",
]
