"""
SA-CVA orchestration for supported public API slices.
"""

from __future__ import annotations

from collections import defaultdict

from frtb_cva.data_models import (
    CvaHedge,
    CvaRegulatoryProfile,
    SaCvaRiskClass,
    SaCvaRiskClassCapital,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
)
from frtb_cva.risk_classes.ccs import calculate_ccs_delta_capital
from frtb_cva.risk_classes.commodity import (
    calculate_commodity_delta_capital,
    calculate_commodity_vega_capital,
)
from frtb_cva.risk_classes.equity import calculate_equity_delta_capital, calculate_equity_vega_capital
from frtb_cva.risk_classes.fx import calculate_fx_delta_capital, calculate_fx_vega_capital
from frtb_cva.risk_classes.girr import calculate_girr_delta_capital, calculate_girr_vega_capital
from frtb_cva.risk_classes.rcs import calculate_rcs_delta_capital, calculate_rcs_vega_capital
from frtb_cva.validation import CvaInputError, validate_m_cva_multiplier

_SUPPORTED_PATHS: dict[tuple[SaCvaRiskClass, SaCvaRiskMeasure], str] = {
    (SaCvaRiskClass.GIRR, SaCvaRiskMeasure.DELTA): "GIRR delta",
    (SaCvaRiskClass.GIRR, SaCvaRiskMeasure.VEGA): "GIRR vega",
    (SaCvaRiskClass.FX, SaCvaRiskMeasure.DELTA): "FX delta",
    (SaCvaRiskClass.FX, SaCvaRiskMeasure.VEGA): "FX vega",
    (SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD, SaCvaRiskMeasure.DELTA): "CCS delta",
    (SaCvaRiskClass.REFERENCE_CREDIT_SPREAD, SaCvaRiskMeasure.DELTA): "RCS delta",
    (SaCvaRiskClass.REFERENCE_CREDIT_SPREAD, SaCvaRiskMeasure.VEGA): "RCS vega",
    (SaCvaRiskClass.EQUITY, SaCvaRiskMeasure.DELTA): "equity delta",
    (SaCvaRiskClass.EQUITY, SaCvaRiskMeasure.VEGA): "equity vega",
    (SaCvaRiskClass.COMMODITY, SaCvaRiskMeasure.DELTA): "commodity delta",
    (SaCvaRiskClass.COMMODITY, SaCvaRiskMeasure.VEGA): "commodity vega",
}


def calculate_sa_cva_capital(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[SaCvaRiskClassCapital, ...]:
    """Calculate supported SA-CVA risk-class totals per MAR50.42–MAR50.45."""

    validated_m_cva = validate_m_cva_multiplier(m_cva)
    if not sensitivities:
        raise CvaInputError("SA-CVA requires at least one sensitivity", field="sensitivities")

    grouped: dict[tuple[SaCvaRiskClass, SaCvaRiskMeasure], list[SaCvaSensitivity]] = defaultdict(list)
    for item in sensitivities:
        grouped[(item.risk_class, item.risk_measure)].append(item)

    if (SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD, SaCvaRiskMeasure.VEGA) in grouped:
        raise CvaInputError(
            "CCS vega capital is not permitted under MAR50.45 and MAR50.63",
            field="sensitivities",
        )

    unsupported = {
        key for key in grouped if key not in _SUPPORTED_PATHS
    }
    if unsupported:
        labels = ", ".join(
            f"{risk_class.value}/{risk_measure.value}"
            for risk_class, risk_measure in sorted(unsupported, key=str)
        )
        raise CvaInputError(
            f"unsupported SA-CVA risk classes: {labels}",
            field="sensitivities",
        )

    results: list[SaCvaRiskClassCapital] = []
    for (risk_class, risk_measure), items in sorted(grouped.items(), key=str):
        capital = _calculate_path(
            risk_class,
            risk_measure,
            tuple(items),
            hedges=hedges,
            m_cva=validated_m_cva,
            reporting_currency=reporting_currency,
            profile=profile,
        )
        results.append(capital)
    return tuple(results)


def _calculate_path(
    risk_class: SaCvaRiskClass,
    risk_measure: SaCvaRiskMeasure,
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...],
    m_cva: float,
    reporting_currency: str,
    profile: CvaRegulatoryProfile | str,
) -> SaCvaRiskClassCapital:
    if risk_class is SaCvaRiskClass.GIRR and risk_measure is SaCvaRiskMeasure.DELTA:
        return calculate_girr_delta_capital(
            sensitivities,
            hedges=hedges,
            m_cva=m_cva,
            reporting_currency=reporting_currency,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.GIRR and risk_measure is SaCvaRiskMeasure.VEGA:
        return calculate_girr_vega_capital(
            sensitivities,
            hedges=hedges,
            m_cva=m_cva,
            reporting_currency=reporting_currency,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.FX and risk_measure is SaCvaRiskMeasure.DELTA:
        return calculate_fx_delta_capital(
            sensitivities,
            hedges=hedges,
            m_cva=m_cva,
            reporting_currency=reporting_currency,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.FX and risk_measure is SaCvaRiskMeasure.VEGA:
        return calculate_fx_vega_capital(
            sensitivities,
            hedges=hedges,
            m_cva=m_cva,
            reporting_currency=reporting_currency,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD and risk_measure is SaCvaRiskMeasure.DELTA:
        return calculate_ccs_delta_capital(
            sensitivities,
            hedges=hedges,
            m_cva=m_cva,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.REFERENCE_CREDIT_SPREAD and risk_measure is SaCvaRiskMeasure.DELTA:
        return calculate_rcs_delta_capital(
            sensitivities,
            hedges=hedges,
            m_cva=m_cva,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.REFERENCE_CREDIT_SPREAD and risk_measure is SaCvaRiskMeasure.VEGA:
        return calculate_rcs_vega_capital(
            sensitivities,
            hedges=hedges,
            m_cva=m_cva,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.EQUITY and risk_measure is SaCvaRiskMeasure.DELTA:
        return calculate_equity_delta_capital(
            sensitivities,
            hedges=hedges,
            m_cva=m_cva,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.EQUITY and risk_measure is SaCvaRiskMeasure.VEGA:
        return calculate_equity_vega_capital(
            sensitivities,
            hedges=hedges,
            m_cva=m_cva,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.COMMODITY and risk_measure is SaCvaRiskMeasure.DELTA:
        return calculate_commodity_delta_capital(
            sensitivities,
            hedges=hedges,
            m_cva=m_cva,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.COMMODITY and risk_measure is SaCvaRiskMeasure.VEGA:
        return calculate_commodity_vega_capital(
            sensitivities,
            hedges=hedges,
            m_cva=m_cva,
            profile=profile,
        )
    raise CvaInputError(
        f"unsupported SA-CVA path: {risk_class.value}/{risk_measure.value}",
        field="sensitivities",
    )


__all__ = ["calculate_sa_cva_capital", "sa_cva_aggregation_config"]


def sa_cva_aggregation_config(
    risk_class: SaCvaRiskClass,
    risk_measure: SaCvaRiskMeasure,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
):
    """Return the cited aggregation config for audit reconciliation."""

    from frtb_cva.aggregation import (
        SaCvaAggregationConfig,
        girr_delta_aggregation_config,
        girr_vega_aggregation_config,
    )
    from frtb_cva.risk_classes.ccs import _ccs_delta_config
    from frtb_cva.risk_classes.commodity import _commodity_config
    from frtb_cva.risk_classes.equity import _equity_config
    from frtb_cva.risk_classes.fx import _fx_delta_config, _fx_vega_config
    from frtb_cva.risk_classes.rcs import _rcs_config

    if risk_class is SaCvaRiskClass.GIRR and risk_measure is SaCvaRiskMeasure.DELTA:
        return girr_delta_aggregation_config(profile=profile)
    if risk_class is SaCvaRiskClass.GIRR and risk_measure is SaCvaRiskMeasure.VEGA:
        return girr_vega_aggregation_config(profile=profile)
    if risk_class is SaCvaRiskClass.FX and risk_measure is SaCvaRiskMeasure.DELTA:
        return _fx_delta_config(profile)
    if risk_class is SaCvaRiskClass.FX and risk_measure is SaCvaRiskMeasure.VEGA:
        return _fx_vega_config(profile)
    if risk_class is SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD and risk_measure is SaCvaRiskMeasure.DELTA:
        return _ccs_delta_config(profile)
    if risk_class is SaCvaRiskClass.REFERENCE_CREDIT_SPREAD:
        return _rcs_config(risk_measure, profile=profile)
    if risk_class is SaCvaRiskClass.EQUITY:
        return _equity_config(risk_measure, profile=profile)
    if risk_class is SaCvaRiskClass.COMMODITY:
        return _commodity_config(risk_measure, profile=profile)
    raise CvaInputError(
        f"unsupported SA-CVA aggregation config: {risk_class.value}/{risk_measure.value}",
        field="risk_class",
    )
