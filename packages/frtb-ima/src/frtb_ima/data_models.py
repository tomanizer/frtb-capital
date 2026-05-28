"""
Data models for FRTB IMA.

Minimal dataclasses and enums. No business logic here.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for data_models.py, RFET,
    liquidity horizons, scenario vectors, NMRFs, and desk capital.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, StrEnum


class RiskClass(StrEnum):
    GIRR = "GIRR"
    CSR = "CSR"
    EQUITY = "EQUITY"
    FX = "FX"
    COMMODITY = "COMMODITY"


class LiquidityHorizon(int, Enum):
    """Business-day liquidity horizons per NPR 2.0 / Basel FRTB IMA."""

    LH10 = 10
    LH20 = 20
    LH40 = 40
    LH60 = 60
    LH120 = 120


class ModellabilityStatus(StrEnum):
    MODELLABLE = "MODELLABLE"
    TYPE_A_NMRF = "TYPE_A_NMRF"  # passes qualitative, fails quantitative
    TYPE_B_NMRF = "TYPE_B_NMRF"  # fails qualitative (or not classified above)


@dataclass(frozen=True)
class RiskFactor:
    """A single risk factor with its assigned liquidity horizon."""

    name: str
    risk_class: RiskClass
    liquidity_horizon: LiquidityHorizon


@dataclass(frozen=True)
class RealPriceObservation:
    """
    A single real-price observation for a risk factor.

    'real price' means an executable price from a verifiable transaction
    or committed quote, following the RFET concepts in Basel MAR31 and the
    U.S. NPR 2.0 proposed market-risk framework.
    """

    risk_factor_name: str
    observation_date: date
    source: str = ""
    vendor_id: str = ""
    venue: str = ""
    feed: str = ""
    observation_timestamp: datetime | None = None
    date_normalization_evidence: str = ""
    verifiable: bool = True
    verifiability_reason: str = ""
    data_pool_id: str = ""
    vendor_audit_evidence_id: str = ""

    def __post_init__(self) -> None:
        if not self.risk_factor_name:
            raise ValueError("risk_factor_name must be non-empty")
        if type(self.observation_date) is not date:
            raise TypeError("observation_date must be a datetime.date")
        if self.observation_timestamp is not None and not isinstance(
            self.observation_timestamp,
            datetime,
        ):
            raise TypeError("observation_timestamp must be a datetime.datetime when provided")
        if not isinstance(self.verifiable, bool):
            raise TypeError("verifiable must be a bool")


@dataclass(frozen=True)
class ScenarioPnL:
    """
    Scenario P&L vectors for one desk, keyed by (risk_class, lh_subset).

    lh_subset identifies the minimum liquidity horizon of risk factors
    included in the sub-vector — used for the nested LHA calculation.

    Convention: positive values are losses (losses are positive).
    """

    desk: str
    # risk_class -> lh_subset -> 1-D array of scenario losses
    # lh_subset is a LiquidityHorizon value (the cutoff, not the label)
    vectors: dict[RiskClass, dict[LiquidityHorizon, list[float]]] = field(default_factory=dict)

    def add_vector(
        self,
        risk_class: RiskClass,
        lh_subset: LiquidityHorizon,
        losses: list[float],
    ) -> None:
        if risk_class not in self.vectors:
            self.vectors[risk_class] = {}
        self.vectors[risk_class][lh_subset] = losses


@dataclass(frozen=True)
class DeskCapitalResult:
    """Capital components for a single approved desk."""

    desk: str
    imcc: float
    ses: float
    models_based_capital: float
    pla_ks_statistic: float
    backtesting_apl_exceptions: int
    backtesting_hpl_exceptions: int
    notes: str = ""

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "desk": self.desk,
            "imcc": self.imcc,
            "ses": self.ses,
            "models_based_capital": self.models_based_capital,
            "pla_ks_statistic": self.pla_ks_statistic,
            "backtesting_apl_exceptions": self.backtesting_apl_exceptions,
            "backtesting_hpl_exceptions": self.backtesting_hpl_exceptions,
            "notes": self.notes,
        }
