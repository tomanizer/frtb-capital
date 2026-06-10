"""
Public CVA batch contracts, adapters, and canonical capital entrypoint.
"""

from __future__ import annotations

from frtb_cva._batch_adapters import (
    build_cva_counterparty_batch_from_columns,
    build_cva_hedge_batch_from_columns,
    build_cva_netting_set_batch_from_columns,
)
from frtb_cva._batch_assembly import calculate_cva_capital_from_batches
from frtb_cva._batch_contracts import (
    CvaBatchCapitalCalculation,
    CvaCounterpartyBatch,
    CvaHedgeBatch,
    CvaNettingSetBatch,
    SaCvaSensitivityBatch,
)
from frtb_cva._batch_payloads import input_hash_for_cva_batches
from frtb_cva._batch_row_adapters import (
    build_cva_counterparty_batch_from_counterparties,
    build_cva_hedge_batch_from_hedges,
    build_cva_netting_set_batch_from_netting_sets,
    build_sa_cva_sensitivity_batch_from_sensitivities,
)
from frtb_cva._batch_sensitivity_adapters import build_sa_cva_sensitivity_batch_from_columns

__all__ = [
    "CvaBatchCapitalCalculation",
    "CvaCounterpartyBatch",
    "CvaHedgeBatch",
    "CvaNettingSetBatch",
    "SaCvaSensitivityBatch",
    "build_cva_counterparty_batch_from_columns",
    "build_cva_counterparty_batch_from_counterparties",
    "build_cva_hedge_batch_from_columns",
    "build_cva_hedge_batch_from_hedges",
    "build_cva_netting_set_batch_from_columns",
    "build_cva_netting_set_batch_from_netting_sets",
    "build_sa_cva_sensitivity_batch_from_columns",
    "build_sa_cva_sensitivity_batch_from_sensitivities",
    "calculate_cva_capital_from_batches",
    "input_hash_for_cva_batches",
]
