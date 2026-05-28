"""
Regulatory regime policy configuration.

The policy layer keeps jurisdiction-specific assumptions at the calculation-run
boundary. Lower-level calculators should continue to accept explicit scalar
parameters whenever possible so they remain easy to test.

Regulatory traceability:
    Basel MAR31-MAR33, U.S. NPR 2.0 proposed-rule parameters, EU CRR3
    and RTS, and UK CRR / PRA-rulebook comparison profiles. See
    docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from frtb_ima.data_models import LiquidityHorizon


class RegulatoryRegime(StrEnum):
    """Supported run-level regulatory profiles."""

    FED_NPR_2_0 = "FED_NPR_2_0"
    ECB_CRR3 = "ECB_CRR3"
    PRA_UK_CRR = "PRA_UK_CRR"


class NMRFTaxonomyMode(StrEnum):
    """How the policy labels non-modellable risk-factor treatment."""

    TYPE_A_TYPE_B = "TYPE_A_TYPE_B"
    BASEL_EU_NMRF = "BASEL_EU_NMRF"


class TypeASESAggregationMode(StrEnum):
    """Type A SES aggregation policy choices."""

    ZERO_CORRELATION_ROOT_SUM_SQUARES = "ZERO_CORRELATION_ROOT_SUM_SQUARES"
    CONSERVATIVE_LINEAR_SUM = "CONSERVATIVE_LINEAR_SUM"


class PLAMetricsRequired(StrEnum):
    """PLA metric set required by a policy profile."""

    KS_ONLY = "KS_ONLY"
    KS_AND_SPEARMAN = "KS_AND_SPEARMAN"


class DeskEligibilityStatus(StrEnum):
    """Whether a desk is currently approved for IMA capital treatment.

    Determined from trailing backtesting and PLA results before the capital run.
    SA_FALLBACK signals that SA capital is required; SA calculation is out of
    scope for this package.

    Regulatory traceability:
        U.S. NPR 2.0 proposed section `__.213` backtesting eligibility gates;
        Basel MAR32 traffic-light zones. See docs/REGULATORY_TRACEABILITY.md.
    """

    IMA_ELIGIBLE = "IMA_ELIGIBLE"
    SA_FALLBACK = "SA_FALLBACK"


@dataclass(frozen=True)
class UnsupportedFeature:
    """A policy feature intentionally not implemented in this package."""

    feature_name: str
    source_topic: str
    notes: str


class UnsupportedRegulatoryFeatureError(NotImplementedError):
    """Raised when a policy asks for a regulatory feature not implemented yet."""

    def __init__(
        self,
        regime: RegulatoryRegime,
        feature_name: str,
        source_topic: str,
    ) -> None:
        self.regime = regime
        self.feature_name = feature_name
        self.source_topic = source_topic
        super().__init__(
            f"{regime.value} requires unsupported feature '{feature_name}' ({source_topic})"
        )


UnsupportedRegulatoryFeature = UnsupportedRegulatoryFeatureError


DEFAULT_LIQUIDITY_HORIZONS: tuple[LiquidityHorizon, ...] = (
    LiquidityHorizon.LH10,
    LiquidityHorizon.LH20,
    LiquidityHorizon.LH40,
    LiquidityHorizon.LH60,
    LiquidityHorizon.LH120,
)

# weight = (lh_upper - lh_lower) / 10-day base horizon.
DEFAULT_LHA_WEIGHTS: tuple[tuple[LiquidityHorizon, float], ...] = (
    (LiquidityHorizon.LH10, 1.0),
    (LiquidityHorizon.LH20, (20 - 10) / 10),
    (LiquidityHorizon.LH40, (40 - 20) / 10),
    (LiquidityHorizon.LH60, (60 - 40) / 10),
    (LiquidityHorizon.LH120, (120 - 60) / 10),
)

DEFAULT_SUPERVISORY_MULTIPLIER_SCHEDULE: tuple[tuple[int, float], ...] = (
    # Basel MAR99 Table 2 backtesting-dependent multipliers.
    (0, 1.50),
    (1, 1.50),
    (2, 1.50),
    (3, 1.50),
    (4, 1.50),
    (5, 1.70),
    (6, 1.76),
    (7, 1.83),
    (8, 1.88),
    (9, 1.92),
)

DEFAULT_BACKTESTING_EXCEPTION_LIMITS: tuple[tuple[float, int], ...] = (
    (0.975, 30),
    (0.99, 12),
)


@dataclass(frozen=True)
class RegulatoryPolicy:
    """Immutable run-level regulatory policy configuration."""

    regime: RegulatoryRegime
    es_confidence_level: float = 0.975
    liquidity_horizons: tuple[LiquidityHorizon, ...] = DEFAULT_LIQUIDITY_HORIZONS
    lha_weights: tuple[tuple[LiquidityHorizon, float], ...] = DEFAULT_LHA_WEIGHTS
    imcc_unconstrained_weight: float = 0.5
    rfet_short_lh_threshold: int = 24
    rfet_long_lh_threshold: int = 16
    rfet_short_lh_max_days: int = 20
    rfet_lookback_days: int = 365
    nmrf_taxonomy_mode: NMRFTaxonomyMode = NMRFTaxonomyMode.TYPE_A_TYPE_B
    type_a_ses_aggregation_mode: TypeASESAggregationMode = (
        TypeASESAggregationMode.ZERO_CORRELATION_ROOT_SUM_SQUARES
    )
    # Type B SES rho: U.S. NPR 2.0 proposed section `__.215`; Basel MAR33.16 anchor.
    type_b_ses_rho: float = 0.36
    pla_metrics_required: PLAMetricsRequired = PLAMetricsRequired.KS_ONLY
    # KS PLA thresholds: Basel MAR32.42; U.S. NPR 2.0 proposed section `__.213`.
    pla_green_threshold: float = 0.09
    pla_amber_threshold: float = 0.12
    # Spearman PLA thresholds: Basel MAR32.42; Delegated Regulation (EU) 2022/2059 Article 5(2).
    pla_spearman_green_threshold: float = 0.80
    pla_spearman_amber_threshold: float = 0.70
    pla_zone_labels: tuple[str, str, str] = ("GREEN", "AMBER", "RED")
    pla_window_days: int = 250
    pla_minimum_history_days: int = 250
    backtesting_window_days: int = 250
    backtesting_minimum_history_days: int = 250
    backtesting_var_confidence_levels: tuple[float, ...] = (0.975, 0.99)
    backtesting_exception_limits: tuple[tuple[float, int], ...] = (
        DEFAULT_BACKTESTING_EXCEPTION_LIMITS
    )
    reduced_set_coverage_window_days: int = 60
    reduced_set_variation_explained_threshold: float = 0.75
    stress_period_window_observations: int = 250
    stress_period_minimum_observations: int = 250
    supervisory_multiplier_schedule: tuple[tuple[int, float], ...] = (
        DEFAULT_SUPERVISORY_MULTIPLIER_SCHEDULE
    )
    supervisory_multiplier_red_zone: float = 2.00
    unsupported_features: tuple[UnsupportedFeature, ...] = ()

    def unsupported_feature(self, feature_name: str) -> UnsupportedFeature | None:
        """Return an unsupported-feature descriptor by name, if present."""
        for feature in self.unsupported_features:
            if feature.feature_name == feature_name:
                return feature
        return None

    def require_supported(self, feature_name: str) -> None:
        """Raise if this profile explicitly marks a feature as unsupported."""
        feature = self.unsupported_feature(feature_name)
        if feature is not None:
            raise UnsupportedRegulatoryFeature(
                self.regime,
                feature.feature_name,
                feature.source_topic,
            )


@dataclass(frozen=True)
class CalculationContext:
    """Run-level calculation metadata and immutable policy selection."""

    policy: RegulatoryPolicy
    as_of_date: date
    legal_entity: str | None = None
    desk: str | None = None
    run_id: str | None = None


def get_policy(regime: RegulatoryRegime = RegulatoryRegime.FED_NPR_2_0) -> RegulatoryPolicy:
    """Return the immutable policy for a supported regulatory regime."""
    if regime == RegulatoryRegime.FED_NPR_2_0:
        return _fed_npr_2_0_policy()
    if regime == RegulatoryRegime.ECB_CRR3:
        return _ecb_crr3_policy()
    if regime == RegulatoryRegime.PRA_UK_CRR:
        return _pra_uk_crr_policy()
    raise ValueError(f"Unsupported regulatory regime: {regime}")


def _fed_npr_2_0_policy() -> RegulatoryPolicy:
    return RegulatoryPolicy(regime=RegulatoryRegime.FED_NPR_2_0)


def _ecb_crr3_policy() -> RegulatoryPolicy:
    return RegulatoryPolicy(
        regime=RegulatoryRegime.ECB_CRR3,
        nmrf_taxonomy_mode=NMRFTaxonomyMode.BASEL_EU_NMRF,
        pla_metrics_required=PLAMetricsRequired.KS_AND_SPEARMAN,
        unsupported_features=(
            UnsupportedFeature(
                feature_name="eu_rfet_rts_detail",
                source_topic="EU RFET RTS / Delegated Regulation (EU) 2022/2060",
                notes=(
                    "Vendor reliance, data-pooling, shifted periods, and detailed "
                    "observation eligibility rules are not implemented."
                ),
            ),
            UnsupportedFeature(
                feature_name="type_a_type_b_nmrf_taxonomy",
                source_topic="EU CRR Article 325bk NMRF terminology",
                notes=(
                    "Type A / Type B labels are U.S. NPR proposed-rule terms, not native EU terms."
                ),
            ),
        ),
    )


def _pra_uk_crr_policy() -> RegulatoryPolicy:
    return RegulatoryPolicy(
        regime=RegulatoryRegime.PRA_UK_CRR,
        nmrf_taxonomy_mode=NMRFTaxonomyMode.BASEL_EU_NMRF,
        pla_metrics_required=PLAMetricsRequired.KS_AND_SPEARMAN,
        unsupported_features=(
            UnsupportedFeature(
                feature_name="eu_rfet_rts_detail",
                source_topic="UK CRR / PRA RFET source mapping",
                notes="UK/PRA RFET deltas and source mapping are not implemented.",
            ),
            UnsupportedFeature(
                feature_name="pra_specific_calibration",
                source_topic="PRA rulebook / UK CRR implementation",
                notes="Formal PRA parameter and multiplier calibration is not implemented.",
            ),
            UnsupportedFeature(
                feature_name="type_a_type_b_nmrf_taxonomy",
                source_topic="UK CRR / PRA NMRF terminology",
                notes=(
                    "Type A / Type B labels are U.S. NPR proposed-rule terms, not native UK terms."
                ),
            ),
        ),
    )
