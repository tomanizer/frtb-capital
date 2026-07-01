"""
Data models for FRTB IMA.

Minimal dataclasses and enums. No business logic here.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for data_models.py, RFET,
    liquidity horizons, scenario vectors, NMRFs, and desk capital.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, StrEnum
from types import MappingProxyType

from frtb_common import CalculationScope

from frtb_ima.org_scope import add_scope_payload, validate_scope_metadata


class RiskClass(StrEnum):
    """IMA risk-class labels for desk and factor grouping."""

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
    """RFET modellability classification for a risk factor."""

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
    vectors: Mapping[RiskClass, Mapping[LiquidityHorizon, tuple[float, ...]]] = field(
        default_factory=dict
    )
    org_scope: CalculationScope | None = None

    def __post_init__(self) -> None:
        frozen_vectors: dict[RiskClass, Mapping[LiquidityHorizon, tuple[float, ...]]] = {}
        for risk_class, horizon_vectors in self.vectors.items():
            frozen_vectors[risk_class] = MappingProxyType(
                {
                    liquidity_horizon: tuple(losses)
                    for liquidity_horizon, losses in horizon_vectors.items()
                }
            )
        object.__setattr__(self, "vectors", MappingProxyType(frozen_vectors))
        object.__setattr__(
            self,
            "org_scope",
            validate_scope_metadata(self.org_scope, field="ScenarioPnL.org_scope"),
        )

    def add_vector(
        self,
        risk_class: RiskClass,
        lh_subset: LiquidityHorizon,
        losses: list[float],
    ) -> ScenarioPnL:
        """Return a new instance with the supplied vector added.
        Parameters
        ----------
        risk_class : RiskClass
            Risk class.
        lh_subset : LiquidityHorizon
            Lh subset.
        losses : list[float]
            Losses.

        Returns
        -------
        ScenarioPnL
            Result of the operation.
        """
        vectors = {existing_class: dict(lh_map) for existing_class, lh_map in self.vectors.items()}
        vectors.setdefault(risk_class, {})[lh_subset] = tuple(losses)
        return ScenarioPnL(desk=self.desk, vectors=vectors, org_scope=self.org_scope)


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
    org_scope: CalculationScope | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "org_scope",
            validate_scope_metadata(self.org_scope, field="DeskCapitalResult.org_scope"),
        )

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
        return add_scope_payload(
            {
                "desk": self.desk,
                "imcc": self.imcc,
                "ses": self.ses,
                "models_based_capital": self.models_based_capital,
                "pla_ks_statistic": self.pla_ks_statistic,
                "backtesting_apl_exceptions": self.backtesting_apl_exceptions,
                "backtesting_hpl_exceptions": self.backtesting_hpl_exceptions,
                "notes": self.notes,
            },
            self.org_scope,
        )
