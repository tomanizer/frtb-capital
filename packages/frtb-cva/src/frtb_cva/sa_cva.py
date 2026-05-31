"""
SA-CVA orchestration for supported public API slices.
"""

from __future__ import annotations

from frtb_cva.data_models import (
    CvaHedge,
    SaCvaRiskClass,
    SaCvaRiskClassCapital,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
)
from frtb_cva.risk_classes.girr import calculate_girr_delta_capital
from frtb_cva.validation import CvaInputError


def calculate_sa_cva_capital(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    m_cva: float = 1.0,
) -> tuple[SaCvaRiskClassCapital, ...]:
    """Calculate supported SA-CVA risk-class totals."""

    unsupported = {
        (item.risk_class, item.risk_measure)
        for item in sensitivities
        if not (
            item.risk_class is SaCvaRiskClass.GIRR
            and item.risk_measure is SaCvaRiskMeasure.DELTA
        )
    }
    if unsupported:
        labels = ", ".join(
            f"{risk_class.value}/{risk_measure.value}"
            for risk_class, risk_measure in sorted(unsupported, key=str)
        )
        raise CvaInputError(
            f"unsupported SA-CVA risk classes in phase 2: {labels}",
            field="sensitivities",
        )
    return (calculate_girr_delta_capital(sensitivities, hedges=hedges, m_cva=m_cva),)


__all__ = ["calculate_sa_cva_capital"]
