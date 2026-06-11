"""SA-CVA batch capital orchestration kernel."""

from __future__ import annotations

from typing import cast

import numpy as np

from frtb_cva._batch_contracts import CvaHedgeBatch, SaCvaSensitivityBatch
from frtb_cva._batch_hedges import _eligible_sa_cva_hedge_ids
from frtb_cva._batch_utils import _empty_hedge_batch
from frtb_cva._sa_batch_weighting import _compute_weighted_sensitivities_from_batch
from frtb_cva.aggregation import aggregate_weighted_sensitivities
from frtb_cva.data_models import (
    CvaRegulatoryProfile,
    SaCvaRiskClass,
    SaCvaRiskClassCapital,
    SaCvaRiskMeasure,
)
from frtb_cva.sa_cva import sa_cva_aggregation_config
from frtb_cva.validation import CvaInputError, validate_m_cva_multiplier
from frtb_cva.weighted_sensitivity import sort_weighted_sensitivities


def calculate_sa_cva_capital_from_batch(
    sensitivities: SaCvaSensitivityBatch,
    *,
    hedges: CvaHedgeBatch | None = None,
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[SaCvaRiskClassCapital, ...]:
    """Calculate supported SA-CVA risk-class totals from a sensitivity batch.

    Parameters
    ----------
    sensitivities : SaCvaSensitivityBatch
        Columnar SA-CVA sensitivities grouped by risk class and measure.
    hedges : CvaHedgeBatch or None, optional
        Hedge batch used to filter ``HDG`` tagged sensitivities.
    m_cva, reporting_currency, profile : optional
        SA-CVA multiplier, FX reporting currency, and regulatory profile.

    Returns
    -------
    tuple[SaCvaRiskClassCapital, ...]
        One capital result per supported risk-class and measure path.
    """
    validated_m_cva = validate_m_cva_multiplier(m_cva)
    if sensitivities.row_count == 0:
        raise CvaInputError("SA-CVA requires at least one sensitivity", field="sensitivities")
    grouped = _group_sa_cva_indices_by_path(sensitivities)
    hedge_batch = hedges or _empty_hedge_batch()
    eligible_hedges = _eligible_sa_cva_hedge_ids(hedge_batch, profile=profile)
    results: list[SaCvaRiskClassCapital] = []
    for risk_class, risk_measure in sorted(grouped, key=str):
        weighted = _compute_weighted_sensitivities_from_batch(
            sensitivities,
            grouped[(risk_class, risk_measure)],
            hedge_batch=hedge_batch,
            eligible_hedge_ids=eligible_hedges,
            reporting_currency=reporting_currency,
            profile=profile,
        )
        config = sa_cva_aggregation_config(risk_class, risk_measure, profile=profile)
        results.append(
            aggregate_weighted_sensitivities(
                sort_weighted_sensitivities(weighted),
                config=config,
                m_cva=validated_m_cva,
                profile=profile,
            )
        )
    return tuple(results)


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


def _group_sa_cva_indices_by_path(
    sensitivities: SaCvaSensitivityBatch,
) -> dict[tuple[SaCvaRiskClass, SaCvaRiskMeasure], list[int]]:
    risk_classes = sensitivities.risk_classes
    risk_measures = sensitivities.risk_measures
    ccs_vega = (risk_classes == SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD.value) & (
        risk_measures == SaCvaRiskMeasure.VEGA.value
    )
    if bool(np.any(ccs_vega)):
        raise CvaInputError(
            "CCS vega capital is not permitted under MAR50.45 and MAR50.63",
            field="sensitivities",
        )

    supported_mask = np.zeros(sensitivities.row_count, dtype=np.bool_)
    grouped: dict[tuple[SaCvaRiskClass, SaCvaRiskMeasure], list[int]] = {}
    for risk_class, risk_measure in sorted(_SUPPORTED_SA_CVA_PATHS, key=str):
        path_mask = (risk_classes == risk_class.value) & (risk_measures == risk_measure.value)
        if not bool(np.any(path_mask)):
            continue
        grouped[(risk_class, risk_measure)] = np.nonzero(path_mask)[0].tolist()
        supported_mask |= path_mask

    unsupported_mask = ~supported_mask
    if bool(np.any(unsupported_mask)):
        unsupported = {
            (
                SaCvaRiskClass(cast(str, risk_classes[index])),
                SaCvaRiskMeasure(cast(str, risk_measures[index])),
            )
            for index in np.nonzero(unsupported_mask)[0]
        }
        labels = ", ".join(
            f"{risk_class.value}/{risk_measure.value}"
            for risk_class, risk_measure in sorted(unsupported, key=str)
        )
        raise CvaInputError(
            f"unsupported SA-CVA risk classes: {labels}",
            field="sensitivities",
        )
    return grouped


__all__ = ["calculate_sa_cva_capital_from_batch"]
