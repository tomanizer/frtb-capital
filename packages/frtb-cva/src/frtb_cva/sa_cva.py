"""
SA-CVA orchestration for supported public API slices.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from frtb_cva.aggregation import SaCvaAggregationConfig

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
from frtb_cva.risk_classes.equity import (
    calculate_equity_delta_capital,
    calculate_equity_vega_capital,
)
from frtb_cva.risk_classes.fx import (
    calculate_fx_delta_capital,
    calculate_fx_vega_capital,
)
from frtb_cva.risk_classes.girr import (
    calculate_girr_delta_capital,
    calculate_girr_vega_capital,
)
from frtb_cva.risk_classes.rcs import (
    calculate_rcs_delta_capital,
    calculate_rcs_vega_capital,
)
from frtb_cva.validation import CvaInputError, validate_m_cva_multiplier

_CapitalPathFn = Callable[..., SaCvaRiskClassCapital]
_AggregationConfigFn = Callable[
    [CvaRegulatoryProfile | str],
    "SaCvaAggregationConfig",
]


@dataclass(frozen=True)
class SaCvaPathSpec:
    """Table entry for one supported or explicitly unsupported SA-CVA path."""

    risk_class: SaCvaRiskClass
    risk_measure: SaCvaRiskMeasure
    label: str
    capital_fn: _CapitalPathFn | None
    unsupported_message: str | None = None


SA_CVA_PATH_REGISTRY: dict[
    tuple[SaCvaRiskClass, SaCvaRiskMeasure], SaCvaPathSpec
] = {
    (SaCvaRiskClass.GIRR, SaCvaRiskMeasure.DELTA): SaCvaPathSpec(
        SaCvaRiskClass.GIRR,
        SaCvaRiskMeasure.DELTA,
        "GIRR delta",
        calculate_girr_delta_capital,
    ),
    (SaCvaRiskClass.GIRR, SaCvaRiskMeasure.VEGA): SaCvaPathSpec(
        SaCvaRiskClass.GIRR,
        SaCvaRiskMeasure.VEGA,
        "GIRR vega",
        calculate_girr_vega_capital,
    ),
    (SaCvaRiskClass.FX, SaCvaRiskMeasure.DELTA): SaCvaPathSpec(
        SaCvaRiskClass.FX,
        SaCvaRiskMeasure.DELTA,
        "FX delta",
        calculate_fx_delta_capital,
    ),
    (SaCvaRiskClass.FX, SaCvaRiskMeasure.VEGA): SaCvaPathSpec(
        SaCvaRiskClass.FX,
        SaCvaRiskMeasure.VEGA,
        "FX vega",
        calculate_fx_vega_capital,
    ),
    (
        SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        SaCvaRiskMeasure.DELTA,
    ): SaCvaPathSpec(
        SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        SaCvaRiskMeasure.DELTA,
        "CCS delta",
        calculate_ccs_delta_capital,
    ),
    (
        SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        SaCvaRiskMeasure.VEGA,
    ): SaCvaPathSpec(
        SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        SaCvaRiskMeasure.VEGA,
        "CCS vega",
        None,
        unsupported_message="CCS vega capital is not permitted under MAR50.45 and MAR50.63",
    ),
    (
        SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        SaCvaRiskMeasure.DELTA,
    ): SaCvaPathSpec(
        SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        SaCvaRiskMeasure.DELTA,
        "RCS delta",
        calculate_rcs_delta_capital,
    ),
    (
        SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        SaCvaRiskMeasure.VEGA,
    ): SaCvaPathSpec(
        SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        SaCvaRiskMeasure.VEGA,
        "RCS vega",
        calculate_rcs_vega_capital,
    ),
    (SaCvaRiskClass.EQUITY, SaCvaRiskMeasure.DELTA): SaCvaPathSpec(
        SaCvaRiskClass.EQUITY,
        SaCvaRiskMeasure.DELTA,
        "equity delta",
        calculate_equity_delta_capital,
    ),
    (SaCvaRiskClass.EQUITY, SaCvaRiskMeasure.VEGA): SaCvaPathSpec(
        SaCvaRiskClass.EQUITY,
        SaCvaRiskMeasure.VEGA,
        "equity vega",
        calculate_equity_vega_capital,
    ),
    (SaCvaRiskClass.COMMODITY, SaCvaRiskMeasure.DELTA): SaCvaPathSpec(
        SaCvaRiskClass.COMMODITY,
        SaCvaRiskMeasure.DELTA,
        "commodity delta",
        calculate_commodity_delta_capital,
    ),
    (SaCvaRiskClass.COMMODITY, SaCvaRiskMeasure.VEGA): SaCvaPathSpec(
        SaCvaRiskClass.COMMODITY,
        SaCvaRiskMeasure.VEGA,
        "commodity vega",
        calculate_commodity_vega_capital,
    ),
}


def calculate_sa_cva_capital(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[SaCvaRiskClassCapital, ...]:
    """Calculate supported SA-CVA risk-class totals per MAR50.42-MAR50.45.

    Parameters
    ----------
    sensitivities :
        Raw SA-CVA sensitivities prior to weighting.

    hedges, optional :
        Declared BA-CVA or SA-CVA hedge records assessed for eligibility.

    m_cva, optional :
        SA-CVA multiplier ``M_CVA`` applied after inter-bucket aggregation (MAR50.53).

    reporting_currency, optional :
        Input for ``calculate_sa_cva_capital`` used in the CVA capital path.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    tuple[SaCvaRiskClassCapital, ...]
        Result of ``calculate_sa_cva_capital`` for audit and downstream aggregation."""

    validated_m_cva = validate_m_cva_multiplier(m_cva)
    if not sensitivities:
        raise CvaInputError(
            "SA-CVA requires at least one sensitivity", field="sensitivities"
        )

    grouped: dict[
        tuple[SaCvaRiskClass, SaCvaRiskMeasure], list[SaCvaSensitivity]
    ] = defaultdict(list)
    for item in sensitivities:
        grouped[(item.risk_class, item.risk_measure)].append(item)

    _validate_grouped_paths(grouped)

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


def _validate_grouped_paths(
    grouped: dict[tuple[SaCvaRiskClass, SaCvaRiskMeasure], list[SaCvaSensitivity]],
) -> None:
    unsupported: set[tuple[SaCvaRiskClass, SaCvaRiskMeasure]] = set()
    for risk_class, risk_measure in grouped:
        spec = SA_CVA_PATH_REGISTRY.get((risk_class, risk_measure))
        if spec is None:
            unsupported.add((risk_class, risk_measure))
            continue
        if spec.unsupported_message is not None:
            raise CvaInputError(spec.unsupported_message, field="sensitivities")
    if unsupported:
        labels = ", ".join(
            f"{risk_class.value}/{risk_measure.value}"
            for risk_class, risk_measure in sorted(unsupported, key=str)
        )
        raise CvaInputError(
            f"unsupported SA-CVA risk classes: {labels}",
            field="sensitivities",
        )


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
    spec = _capital_path_spec_for(risk_class, risk_measure)
    capital_fn = spec.capital_fn
    if capital_fn is None:
        raise CvaInputError(
            spec.unsupported_message
            or f"unsupported SA-CVA path: {risk_class.value}/{risk_measure.value}",
            field="sensitivities",
        )
    return capital_fn(
        sensitivities,
        hedges=hedges,
        m_cva=m_cva,
        reporting_currency=reporting_currency,
        profile=profile,
    )


def _capital_path_spec_for(
    risk_class: SaCvaRiskClass,
    risk_measure: SaCvaRiskMeasure,
) -> SaCvaPathSpec:
    spec = SA_CVA_PATH_REGISTRY.get((risk_class, risk_measure))
    if spec is None:
        raise CvaInputError(
            f"unsupported SA-CVA path: {risk_class.value}/{risk_measure.value}",
            field="sensitivities",
        )
    return spec


__all__ = [
    "SA_CVA_PATH_REGISTRY",
    "SaCvaPathSpec",
    "calculate_sa_cva_capital",
    "sa_cva_aggregation_config",
]


def sa_cva_aggregation_config(
    risk_class: SaCvaRiskClass,
    risk_measure: SaCvaRiskMeasure,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaAggregationConfig:
    """Return the cited aggregation config for audit reconciliation.

    Parameters
    ----------
    risk_class :
        SA-CVA risk class driving aggregation configuration.

    risk_measure :
        SA-CVA risk measure (delta or vega) for the aggregation path.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    SaCvaAggregationConfig
        Result of ``sa_cva_aggregation_config`` for audit and downstream aggregation."""

    from frtb_cva.aggregation import (
        girr_delta_aggregation_config,
        girr_vega_aggregation_config,
    )
    from frtb_cva.risk_classes.ccs import _ccs_delta_config
    from frtb_cva.risk_classes.commodity import _commodity_config
    from frtb_cva.risk_classes.equity import _equity_config
    from frtb_cva.risk_classes.fx import _fx_delta_config, _fx_vega_config
    from frtb_cva.risk_classes.rcs import _rcs_config

    def _girr_delta_config_for(
        active_profile: CvaRegulatoryProfile | str,
    ) -> SaCvaAggregationConfig:
        return girr_delta_aggregation_config(profile=active_profile)

    def _girr_vega_config_for(
        active_profile: CvaRegulatoryProfile | str,
    ) -> SaCvaAggregationConfig:
        return girr_vega_aggregation_config(profile=active_profile)

    def _rcs_delta_config_for(
        active_profile: CvaRegulatoryProfile | str,
    ) -> SaCvaAggregationConfig:
        return _rcs_config(SaCvaRiskMeasure.DELTA, profile=active_profile)

    def _rcs_vega_config_for(
        active_profile: CvaRegulatoryProfile | str,
    ) -> SaCvaAggregationConfig:
        return _rcs_config(SaCvaRiskMeasure.VEGA, profile=active_profile)

    def _equity_delta_config_for(
        active_profile: CvaRegulatoryProfile | str,
    ) -> SaCvaAggregationConfig:
        return _equity_config(SaCvaRiskMeasure.DELTA, profile=active_profile)

    def _equity_vega_config_for(
        active_profile: CvaRegulatoryProfile | str,
    ) -> SaCvaAggregationConfig:
        return _equity_config(SaCvaRiskMeasure.VEGA, profile=active_profile)

    def _commodity_delta_config_for(
        active_profile: CvaRegulatoryProfile | str,
    ) -> SaCvaAggregationConfig:
        return _commodity_config(SaCvaRiskMeasure.DELTA, profile=active_profile)

    def _commodity_vega_config_for(
        active_profile: CvaRegulatoryProfile | str,
    ) -> SaCvaAggregationConfig:
        return _commodity_config(SaCvaRiskMeasure.VEGA, profile=active_profile)

    registry: dict[tuple[SaCvaRiskClass, SaCvaRiskMeasure], _AggregationConfigFn] = {
        (SaCvaRiskClass.GIRR, SaCvaRiskMeasure.DELTA): _girr_delta_config_for,
        (SaCvaRiskClass.GIRR, SaCvaRiskMeasure.VEGA): _girr_vega_config_for,
        (SaCvaRiskClass.FX, SaCvaRiskMeasure.DELTA): _fx_delta_config,
        (SaCvaRiskClass.FX, SaCvaRiskMeasure.VEGA): _fx_vega_config,
        (
            SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
            SaCvaRiskMeasure.DELTA,
        ): _ccs_delta_config,
        (
            SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
            SaCvaRiskMeasure.DELTA,
        ): _rcs_delta_config_for,
        (
            SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
            SaCvaRiskMeasure.VEGA,
        ): _rcs_vega_config_for,
        (SaCvaRiskClass.EQUITY, SaCvaRiskMeasure.DELTA): _equity_delta_config_for,
        (SaCvaRiskClass.EQUITY, SaCvaRiskMeasure.VEGA): _equity_vega_config_for,
        (
            SaCvaRiskClass.COMMODITY,
            SaCvaRiskMeasure.DELTA,
        ): _commodity_delta_config_for,
        (
            SaCvaRiskClass.COMMODITY,
            SaCvaRiskMeasure.VEGA,
        ): _commodity_vega_config_for,
    }
    config_fn = registry.get((risk_class, risk_measure))
    if config_fn is None:
        raise CvaInputError(
            f"unsupported SA-CVA aggregation config: {risk_class.value}/{risk_measure.value}",
            field="risk_class",
        )
    return config_fn(profile)
