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

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from frtb_ima.data_models import LiquidityHorizon
from frtb_ima.expected_shortfall import ESEstimator


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

REGULATORY_PARAMETER_CITATIONS: Mapping[str, str] = MappingProxyType(
    {
        "es_confidence_level": "Basel MAR33.4; U.S. NPR 2.0 proposed section __.214",
        "es_estimator": "Basel MAR33 expected shortfall; documented model choice",
        "imcc_unconstrained_weight": "Basel MAR33.15; U.S. NPR 2.0 proposed section __.214",
        "rfet_short_lh_threshold": "Basel MAR31.12; U.S. NPR 2.0 proposed section __.212",
        "rfet_long_lh_threshold": "Basel MAR31.12; U.S. NPR 2.0 proposed section __.212",
        "rfet_short_lh_max_days": "Basel MAR31.12; U.S. NPR 2.0 proposed section __.212",
        "rfet_lookback_days": "Basel MAR31.12; U.S. NPR 2.0 proposed section __.212",
        "type_b_ses_rho": "Basel MAR33.16; U.S. NPR 2.0 proposed section __.215",
        "pla_green_threshold": "Basel MAR32.42; U.S. NPR 2.0 proposed section __.213",
        "pla_amber_threshold": "Basel MAR32.42; U.S. NPR 2.0 proposed section __.213",
        "pla_spearman_green_threshold": (
            "Basel MAR32.42; Delegated Regulation (EU) 2022/2059 Article 5(2)"
        ),
        "pla_spearman_amber_threshold": (
            "Basel MAR32.42; Delegated Regulation (EU) 2022/2059 Article 5(2)"
        ),
        "pla_window_days": "Basel MAR32.40; U.S. NPR 2.0 proposed section __.213",
        "pla_minimum_history_days": "Basel MAR32.40; U.S. NPR 2.0 proposed section __.213",
        "backtesting_window_days": "Basel MAR32.7; U.S. NPR 2.0 proposed section __.213",
        "backtesting_minimum_history_days": ("Basel MAR32.7; U.S. NPR 2.0 proposed section __.213"),
        "backtesting_var_confidence_levels": (
            "Basel MAR32.6; U.S. NPR 2.0 proposed section __.213"
        ),
        "backtesting_exception_limits": "Basel MAR32.8; U.S. NPR 2.0 proposed section __.213",
        "reduced_set_coverage_window_days": (
            "Basel MAR33.16; U.S. NPR 2.0 proposed section __.214"
        ),
        "reduced_set_variation_explained_threshold": (
            "Basel MAR33.16; U.S. NPR 2.0 proposed section __.214"
        ),
        "stress_period_window_observations": (
            "Basel MAR33.5; U.S. NPR 2.0 proposed section __.214"
        ),
        "stress_period_minimum_observations": (
            "Basel MAR33.5; U.S. NPR 2.0 proposed section __.214"
        ),
        "supervisory_multiplier_schedule": (
            "Basel MAR99 Table 2; U.S. NPR 2.0 proposed section __.213"
        ),
        "supervisory_multiplier_red_zone": (
            "Basel MAR99 Table 2; U.S. NPR 2.0 proposed section __.213"
        ),
    }
)


def _default_parameter_citations() -> Mapping[str, str]:
    return REGULATORY_PARAMETER_CITATIONS


_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


@dataclass(frozen=True)
class ModelVersion:
    """Immutable model identity used in audit records."""

    model_id: str
    version: str
    description: str

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ValueError("model_id must be non-empty")
        if not _SEMVER_RE.fullmatch(self.version):
            raise ValueError("version must be semver-like, for example 0.1.0")
        if not self.description:
            raise ValueError("description must be non-empty")

    def as_dict(self) -> dict[str, str]:
        """Return a JSON-serialisable model identity dictionary."""
        return {
            "model_id": self.model_id,
            "version": self.version,
            "description": self.description,
        }


DEFAULT_MODEL_VERSION = ModelVersion(
    model_id="frtb-ima",
    version="0.1.0",
    description="FRTB IMA prototype capital model",
)


@dataclass(frozen=True)
class RegulatoryPolicy:
    """Immutable run-level regulatory policy configuration."""

    regime: RegulatoryRegime
    es_confidence_level: float = 0.975
    es_estimator: ESEstimator = ESEstimator.WEIGHTED_INTERPOLATED
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
    cited_by: Mapping[str, str] = field(default_factory=_default_parameter_citations)
    unsupported_features: tuple[UnsupportedFeature, ...] = ()

    def __post_init__(self) -> None:
        citations = {
            str(parameter_name): str(citation) for parameter_name, citation in self.cited_by.items()
        }
        if any(
            not parameter_name or not citation for parameter_name, citation in citations.items()
        ):
            raise ValueError("cited_by must map non-empty parameter names to non-empty citations")
        object.__setattr__(self, "cited_by", MappingProxyType(citations))

    @property
    def policy_hash(self) -> str:
        """Stable SHA-256 over this policy's canonical serialisation."""
        payload = json.dumps(
            self.as_dict(),
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(bytes(payload, "utf-8")).hexdigest()

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serialisable policy dictionary."""
        return {field.name: _policy_jsonable(getattr(self, field.name)) for field in fields(self)}

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


def _policy_jsonable(value: Any) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _policy_jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple | list):
        return [_policy_jsonable(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _policy_jsonable(item) for key, item in value.items()}
    return value
