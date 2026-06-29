"""Mapping-spec adapter for daily PLA and backtesting P&L vectors."""

from frtb_ima.adapters._daily_pnl_mapping_materialize import (
    materialize_daily_pnl_vectors_from_mapping,
    materialize_daily_pnl_vectors_from_rows,
)
from frtb_ima.adapters._daily_pnl_mapping_types import (
    IMA_DAILY_PNL_VECTOR_ARROW_COLUMN_SPECS,
    IMA_DAILY_PNL_VECTOR_TARGET,
    DailyPnlMappingResult,
    DailyPnlTableMapping,
    DailyPnlValidationReport,
    DailyPnlVectorBatch,
    input_hash_for_daily_pnl_vector_batch,
)
from frtb_ima.adapters.mapping_spec import (
    IMA_MAPPING_SPEC_VERSION,
    FieldMapping,
    ImaMappingSpec,
    MappingFinding,
    MappingSpecError,
    load_ima_mapping_spec,
    parse_ima_mapping_spec,
)

__all__ = [
    "IMA_DAILY_PNL_VECTOR_ARROW_COLUMN_SPECS",
    "IMA_DAILY_PNL_VECTOR_TARGET",
    "IMA_MAPPING_SPEC_VERSION",
    "DailyPnlMappingResult",
    "DailyPnlTableMapping",
    "DailyPnlValidationReport",
    "DailyPnlVectorBatch",
    "FieldMapping",
    "ImaMappingSpec",
    "MappingFinding",
    "MappingSpecError",
    "input_hash_for_daily_pnl_vector_batch",
    "load_ima_mapping_spec",
    "materialize_daily_pnl_vectors_from_mapping",
    "materialize_daily_pnl_vectors_from_rows",
    "parse_ima_mapping_spec",
]
