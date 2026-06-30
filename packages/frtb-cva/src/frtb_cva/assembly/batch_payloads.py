"""Audit payload hashing for CVA batch inputs."""

from __future__ import annotations

from frtb_cva._batch_contracts import (
    CvaCounterpartyBatch,
    CvaHedgeBatch,
    CvaNettingSetBatch,
    SaCvaSensitivityBatch,
)
from frtb_cva.assembly.payloads import batch_input_payload as _batch_input_payload
from frtb_cva.assembly.payloads import hash_payload as _hash_payload
from frtb_cva.data_models import (
    CvaCalculationContext,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
)

INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2 = "arrow-columnar-v2"
INPUT_HASH_ALGORITHM_JSON_ROW_V1 = "json-row-v1"


def input_hash_for_cva_batches(
    context: CvaCalculationContext,
    counterparties: CvaCounterpartyBatch | None = None,
    netting_sets: CvaNettingSetBatch | None = None,
    *,
    hedges: CvaHedgeBatch | None = None,
    sensitivities: SaCvaSensitivityBatch | None = None,
) -> str:
    """Return the row-compatible deterministic input hash for CVA batches.

    Parameters
    ----------
    context : CvaCalculationContext
        Calculation context included in the hash payload.
    counterparties : CvaCounterpartyBatch or None, optional
        Counterparty batch serialized into the payload when provided.
    netting_sets : CvaNettingSetBatch or None, optional
        Netting-set batch serialized into the payload when provided.
    hedges : CvaHedgeBatch or None, optional
        Hedge batch serialized into the payload when provided.
    sensitivities : SaCvaSensitivityBatch or None, optional
        Sensitivity batch serialized into the payload when provided.

    Returns
    -------
    str
        Stable SHA-256 digest of the canonical batch input payload.
    """

    return _hash_payload(
        _batch_input_payload(
            context,
            counterparties,
            netting_sets,
            hedges=hedges,
            sensitivities=sensitivities,
        )
    )


_SUPPORTED_SA_CVA_PATHS: frozenset[tuple[SaCvaRiskClass, SaCvaRiskMeasure]] = frozenset(
    {
        (SaCvaRiskClass.GIRR, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.GIRR, SaCvaRiskMeasure.VEGA),
        (SaCvaRiskClass.FX, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.FX, SaCvaRiskMeasure.VEGA),
        (SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.REFERENCE_CREDIT_SPREAD, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.REFERENCE_CREDIT_SPREAD, SaCvaRiskMeasure.VEGA),
        (SaCvaRiskClass.EQUITY, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.EQUITY, SaCvaRiskMeasure.VEGA),
        (SaCvaRiskClass.COMMODITY, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.COMMODITY, SaCvaRiskMeasure.VEGA),
    }
)


__all__ = [
    "INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2",
    "INPUT_HASH_ALGORITHM_JSON_ROW_V1",
    "input_hash_for_cva_batches",
]
