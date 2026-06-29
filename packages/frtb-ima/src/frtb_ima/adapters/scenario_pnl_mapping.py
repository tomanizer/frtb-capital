"""Public scenario P&L mapping adapter exports."""

from frtb_ima.adapters._scenario_pnl_mapping_cube import build_scenario_pnl_batch_from_arrow
from frtb_ima.adapters._scenario_pnl_mapping_materialize import (
    ScenarioPnlMappingResult,
    materialize_scenario_pnl_vectors_from_mapping,
    materialize_scenario_pnl_vectors_from_rows,
)
from frtb_ima.adapters._scenario_pnl_mapping_types import (
    IMA_SCENARIO_PNL_VECTOR_ARROW_COLUMN_SPECS,
    IMA_SCENARIO_PNL_VECTOR_TARGET,
    ScenarioPnlTableMapping,
    ScenarioPnlValidationReport,
    ScenarioPnlVectorBatch,
    input_hash_for_scenario_pnl_batch,
)

__all__ = [
    "IMA_SCENARIO_PNL_VECTOR_ARROW_COLUMN_SPECS",
    "IMA_SCENARIO_PNL_VECTOR_TARGET",
    "ScenarioPnlMappingResult",
    "ScenarioPnlTableMapping",
    "ScenarioPnlValidationReport",
    "ScenarioPnlVectorBatch",
    "build_scenario_pnl_batch_from_arrow",
    "input_hash_for_scenario_pnl_batch",
    "materialize_scenario_pnl_vectors_from_mapping",
    "materialize_scenario_pnl_vectors_from_rows",
]
