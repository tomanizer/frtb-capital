"""Data models for the FRTB Standardised Approach default risk charge."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import TypeVar

from frtb_common import dataclass_as_dict
from frtb_common.attribution import CapitalContribution


class DrcRiskClass(StrEnum):
    """Default-risk charge categories."""

    NON_SECURITISATION = "NON_SECURITISATION"
    SECURITISATION_NON_CTP = "SECURITISATION_NON_CTP"
    CORRELATION_TRADING_PORTFOLIO = "CORRELATION_TRADING_PORTFOLIO"


class DefaultDirection(StrEnum):
    """Default-risk direction, independent of trade accounting sign."""

    LONG = "LONG"
    SHORT = "SHORT"


class DrcInstrumentType(StrEnum):
    """Instrument families represented by canonical DRC inputs."""

    BOND = "BOND"
    EQUITY = "EQUITY"
    LOAN = "LOAN"
    CREDIT_DERIVATIVE = "CREDIT_DERIVATIVE"
    SECURITISATION_TRANCHE = "SECURITISATION_TRANCHE"
    INDEX_TRANCHE = "INDEX_TRANCHE"
    OTHER = "OTHER"


class DrcSeniority(StrEnum):
    """Non-securitisation recovery or seniority categories."""

    EQUITY = "EQUITY"
    NON_SENIOR_DEBT = "NON_SENIOR_DEBT"
    SENIOR_DEBT = "SENIOR_DEBT"
    COVERED_BOND = "COVERED_BOND"
    GSE_GUARANTEED = "GSE_GUARANTEED"
    GSE_ISSUED_NOT_GUARANTEED = "GSE_ISSUED_NOT_GUARANTEED"
    PSE = "PSE"
    NOT_RECOVERY_LINKED = "NOT_RECOVERY_LINKED"


class CreditQuality(StrEnum):
    """Credit-quality buckets used by rule-profile risk-weight lookup."""

    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    B = "B"
    CCC = "CCC"
    INVESTMENT_GRADE = "INVESTMENT_GRADE"
    SPECULATIVE_GRADE = "SPECULATIVE_GRADE"
    SUB_SPECULATIVE_GRADE = "SUB_SPECULATIVE_GRADE"
    DEFAULTED = "DEFAULTED"
    UNRATED = "UNRATED"


class DrcBucketType(StrEnum):
    """Initial public bucket labels for supported DRC profiles."""

    SOVEREIGN = "SOVEREIGN"
    LOCAL_GOVERNMENT_MUNICIPAL = "LOCAL_GOVERNMENT_MUNICIPAL"
    NON_US_SOVEREIGN = "NON_US_SOVEREIGN"
    PSE_GSE = "PSE_GSE"
    CORPORATE = "CORPORATE"
    DEFAULTED = "DEFAULTED"
    SECURITISATION_ASSET_REGION = "SECURITISATION_ASSET_REGION"
    CTP = "CTP"


class BranchType(StrEnum):
    """Capital-branch metadata retained for audit and later attribution."""

    CAP = "CAP"
    FLOOR = "FLOOR"
    ZERO_DENOMINATOR = "ZERO_DENOMINATOR"
    OFFSET_REJECTED = "OFFSET_REJECTED"
    UNSUPPORTED_FEATURE = "UNSUPPORTED_FEATURE"
    NORMAL = "NORMAL"


EnumT = TypeVar("EnumT", bound=StrEnum)


def _coerce_enum(value: EnumT | str, enum_type: type[EnumT], field_name: str) -> EnumT:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(f"{field_name} must be one of: {allowed}") from exc


class _DrcAsDictMixin:
    """Provide the public DRC dataclass ``as_dict`` contract."""

    __slots__ = ()

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable mapping of dataclass fields.

        Returns
        -------
        dict[str, object]
            Field names mapped through the shared dataclass serializer.
        """
        return dataclass_as_dict(self)


@dataclass(frozen=True)
class DrcCitation(_DrcAsDictMixin):
    """Paragraph-level regulatory or design citation."""

    citation_id: str
    source_id: str
    paragraph: str
    url: str
    note: str = ""


@dataclass(frozen=True)
class DrcSourceLineage(_DrcAsDictMixin):
    """Source-system lineage for a canonical DRC input row."""

    source_system: str
    source_file: str
    source_row_id: str
    source_column_map: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_column_map",
            MappingProxyType(dict(self.source_column_map)),
        )


@dataclass(frozen=True)
class DrcFxRate(_DrcAsDictMixin):
    """Explicit FX rate supplied for translating DRC amounts into the base currency."""

    source_currency: str
    target_currency: str
    rate: float
    as_of_date: date
    source_id: str
    lineage: DrcSourceLineage
    citation_ids: tuple[str, ...] = ("US_NPR_207_A_8", "US_NPR_208_H_1_II")

    def __post_init__(self) -> None:
        object.__setattr__(self, "citation_ids", tuple(self.citation_ids))


@dataclass(frozen=True)
class DrcFxConversion(_DrcAsDictMixin):
    """FX conversion lineage applied to one source currency in a calculation run."""

    source_currency: str
    target_currency: str
    rate: float
    as_of_date: date
    source_id: str
    position_count: int
    lineage: DrcSourceLineage
    citation_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "citation_ids", tuple(self.citation_ids))


@dataclass(frozen=True)
class DrcRiskWeightEvidence(_DrcAsDictMixin):
    """Typed upstream securitisation or CTP risk-weight derivation evidence."""

    position_id: str
    risk_class: DrcRiskClass | str
    source_profile_id: str
    source_table: str
    source_method: str
    effective_risk_weight: float
    as_of_date: date
    source_id: str
    lineage: DrcSourceLineage
    citation_ids: tuple[str, ...]
    is_stale: bool = False
    validation_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "risk_class",
            _coerce_enum(self.risk_class, DrcRiskClass, "risk_class"),
        )
        object.__setattr__(self, "citation_ids", tuple(self.citation_ids))
        object.__setattr__(self, "validation_flags", tuple(self.validation_flags))


@dataclass(frozen=True)
class DrcFairValueCapEvidence(_DrcAsDictMixin):
    """Typed evidence for optional securitisation non-CTP fair-value cap treatment."""

    position_id: str
    source_profile_id: str
    eligible: bool
    fair_value_cap_amount: float | None
    eligibility_reason: str
    as_of_date: date
    source_id: str
    lineage: DrcSourceLineage
    citation_ids: tuple[str, ...]
    is_stale: bool = False
    validation_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "citation_ids", tuple(self.citation_ids))
        object.__setattr__(self, "validation_flags", tuple(self.validation_flags))


@dataclass(frozen=True)
class DrcCalculationContext(_DrcAsDictMixin):
    """Run-scoped calculation metadata supplied to the public API."""

    run_id: str
    calculation_date: date
    base_currency: str
    profile_id: str
    desk_id: str = ""
    legal_entity: str = ""
    citation_policy: str = "strict"
    fx_rates: Mapping[str, DrcFxRate] = field(default_factory=dict)
    securitisation_non_ctp_risk_weights: Mapping[str, float] = field(default_factory=dict)
    securitisation_non_ctp_risk_weight_evidence: Mapping[str, DrcRiskWeightEvidence] = field(
        default_factory=dict
    )
    securitisation_non_ctp_fair_value_cap_evidence: Mapping[str, DrcFairValueCapEvidence] = field(
        default_factory=dict
    )
    securitisation_non_ctp_offset_groups: Mapping[str, str] = field(default_factory=dict)
    ctp_risk_weights: Mapping[str, float] = field(default_factory=dict)
    ctp_risk_weight_evidence: Mapping[str, DrcRiskWeightEvidence] = field(default_factory=dict)
    ctp_offset_groups: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "fx_rates", MappingProxyType(dict(self.fx_rates)))
        object.__setattr__(
            self,
            "securitisation_non_ctp_risk_weights",
            MappingProxyType(dict(self.securitisation_non_ctp_risk_weights)),
        )
        object.__setattr__(
            self,
            "securitisation_non_ctp_risk_weight_evidence",
            MappingProxyType(dict(self.securitisation_non_ctp_risk_weight_evidence)),
        )
        object.__setattr__(
            self,
            "securitisation_non_ctp_fair_value_cap_evidence",
            MappingProxyType(dict(self.securitisation_non_ctp_fair_value_cap_evidence)),
        )
        object.__setattr__(
            self,
            "securitisation_non_ctp_offset_groups",
            MappingProxyType(dict(self.securitisation_non_ctp_offset_groups)),
        )
        object.__setattr__(
            self,
            "ctp_risk_weights",
            MappingProxyType(dict(self.ctp_risk_weights)),
        )
        object.__setattr__(
            self,
            "ctp_risk_weight_evidence",
            MappingProxyType(dict(self.ctp_risk_weight_evidence)),
        )
        object.__setattr__(
            self,
            "ctp_offset_groups",
            MappingProxyType(dict(self.ctp_offset_groups)),
        )


@dataclass(frozen=True)
class BranchMetadata(_DrcAsDictMixin):
    """A branch choice that can affect audit or future attribution."""

    branch_id: str
    branch_type: BranchType | str
    source_id: str
    selected: bool
    reason: str
    citations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "branch_type",
            _coerce_enum(self.branch_type, BranchType, "branch_type"),
        )
        object.__setattr__(self, "citations", tuple(self.citations))


@dataclass(frozen=True)
class DrcPosition(_DrcAsDictMixin):
    """Canonical default-risk exposure before calculation."""

    position_id: str
    source_row_id: str
    desk_id: str
    legal_entity: str
    risk_class: DrcRiskClass | str
    instrument_type: DrcInstrumentType | str
    default_direction: DefaultDirection | str
    issuer_id: str | None
    tranche_id: str | None
    index_series_id: str | None
    bucket_key: str | None
    seniority: DrcSeniority | str | None
    credit_quality: CreditQuality | str | None
    notional: float
    market_value: float | None
    cumulative_pnl: float | None
    maturity_years: float
    currency: str
    lgd_override: float | None = None
    is_defaulted: bool = False
    is_gse: bool = False
    is_pse: bool = False
    is_covered_bond: bool = False
    lineage: DrcSourceLineage | None = None
    citation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "risk_class",
            _coerce_enum(self.risk_class, DrcRiskClass, "risk_class"),
        )
        object.__setattr__(
            self,
            "instrument_type",
            _coerce_enum(self.instrument_type, DrcInstrumentType, "instrument_type"),
        )
        object.__setattr__(
            self,
            "default_direction",
            _coerce_enum(self.default_direction, DefaultDirection, "default_direction"),
        )
        if self.seniority is not None:
            object.__setattr__(
                self,
                "seniority",
                _coerce_enum(self.seniority, DrcSeniority, "seniority"),
            )
        if self.credit_quality is not None:
            object.__setattr__(
                self,
                "credit_quality",
                _coerce_enum(self.credit_quality, CreditQuality, "credit_quality"),
            )
        object.__setattr__(self, "citation_ids", tuple(self.citation_ids))


@dataclass(frozen=True)
class GrossJtd(_DrcAsDictMixin):
    """Position-level gross jump-to-default amount."""

    gross_jtd_id: str
    position_id: str
    risk_class: DrcRiskClass | str
    issuer_or_tranche_key: str
    bucket_key: str
    default_direction: DefaultDirection | str
    lgd_rate: float
    lgd_source: str
    notional: float
    pnl_component: float
    gross_jtd: float
    citations: tuple[str, ...]
    branch_metadata: tuple[BranchMetadata, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "risk_class",
            _coerce_enum(self.risk_class, DrcRiskClass, "risk_class"),
        )
        object.__setattr__(
            self,
            "default_direction",
            _coerce_enum(self.default_direction, DefaultDirection, "default_direction"),
        )
        object.__setattr__(self, "citations", tuple(self.citations))
        object.__setattr__(self, "branch_metadata", tuple(self.branch_metadata))


@dataclass(frozen=True)
class MaturityScaledJtd(_DrcAsDictMixin):
    """Gross JTD after maturity weighting."""

    scaled_jtd_id: str
    gross_jtd_id: str
    position_id: str
    gross_jtd: float
    maturity_years: float
    maturity_weight: float
    scaled_jtd: float
    floor_applied: bool
    citations: tuple[str, ...]
    branch_metadata: tuple[BranchMetadata, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "citations", tuple(self.citations))
        object.__setattr__(self, "branch_metadata", tuple(self.branch_metadata))


@dataclass(frozen=True)
class RejectedOffset(_DrcAsDictMixin):
    """Audit record for an offset that was not permitted."""

    rejection_id: str
    long_source_id: str
    short_source_id: str
    reason_code: str
    citations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "citations", tuple(self.citations))


@dataclass(frozen=True)
class NetJtd(_DrcAsDictMixin):
    """Net default exposure after permitted offsetting."""

    net_jtd_id: str
    netting_group_id: str
    risk_class: DrcRiskClass | str
    bucket_key: str
    obligor_or_tranche_key: str
    seniority_layer: str
    gross_long: float
    gross_short: float
    scaled_long: float
    scaled_short: float
    net_amount: float
    net_direction: DefaultDirection | str
    position_ids: tuple[str, ...]
    scaled_jtd_ids: tuple[str, ...]
    rejected_offsets: tuple[RejectedOffset, ...] = ()
    branch_metadata: tuple[BranchMetadata, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "risk_class",
            _coerce_enum(self.risk_class, DrcRiskClass, "risk_class"),
        )
        object.__setattr__(
            self,
            "net_direction",
            _coerce_enum(self.net_direction, DefaultDirection, "net_direction"),
        )
        object.__setattr__(self, "position_ids", tuple(self.position_ids))
        object.__setattr__(self, "scaled_jtd_ids", tuple(self.scaled_jtd_ids))
        object.__setattr__(self, "rejected_offsets", tuple(self.rejected_offsets))
        object.__setattr__(self, "branch_metadata", tuple(self.branch_metadata))


@dataclass(frozen=True)
class HedgeBenefitRatio(_DrcAsDictMixin):
    """Bucket-level hedge benefit ratio."""

    hbr_id: str
    bucket_key: str
    aggregate_net_long: float
    aggregate_net_short: float
    denominator: float
    ratio: float
    citations: tuple[str, ...]
    branch_metadata: tuple[BranchMetadata, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "citations", tuple(self.citations))
        object.__setattr__(self, "branch_metadata", tuple(self.branch_metadata))


@dataclass(frozen=True)
class BucketDrc(_DrcAsDictMixin):
    """Bucket-level DRC capital result."""

    bucket_id: str
    bucket_key: str
    risk_class: DrcRiskClass | str
    hbr: HedgeBenefitRatio
    weighted_long: float
    weighted_short: float
    capital: float
    floor_applied: bool
    net_jtd_ids: tuple[str, ...]
    citations: tuple[str, ...]
    branch_metadata: tuple[BranchMetadata, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "risk_class",
            _coerce_enum(self.risk_class, DrcRiskClass, "risk_class"),
        )
        object.__setattr__(self, "net_jtd_ids", tuple(self.net_jtd_ids))
        object.__setattr__(self, "citations", tuple(self.citations))
        object.__setattr__(self, "branch_metadata", tuple(self.branch_metadata))


@dataclass(frozen=True)
class CategoryDrc(_DrcAsDictMixin):
    """Category-level DRC capital result."""

    category_id: str
    risk_class: DrcRiskClass | str
    bucket_results: tuple[BucketDrc, ...]
    capital: float
    unsupported_features: tuple[str, ...] = ()
    branch_metadata: tuple[BranchMetadata, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "risk_class",
            _coerce_enum(self.risk_class, DrcRiskClass, "risk_class"),
        )
        object.__setattr__(self, "bucket_results", tuple(self.bucket_results))
        object.__setattr__(self, "unsupported_features", tuple(self.unsupported_features))
        object.__setattr__(self, "branch_metadata", tuple(self.branch_metadata))


@dataclass(frozen=True)
class DrcCapitalResult(_DrcAsDictMixin):
    """Run-level DRC capital result."""

    result_id: str
    run_id: str
    calculation_date: date
    base_currency: str
    profile_id: str
    profile_hash: str
    input_hash: str
    categories: tuple[CategoryDrc, ...]
    total_drc: float
    citations: tuple[str, ...]
    input_hash_algorithm: str = "json-row-v1"
    warnings: tuple[str, ...] = ()
    branch_metadata: tuple[BranchMetadata, ...] = ()
    package_name: str = "frtb-drc"
    package_version: str = ""
    input_count: int = 0
    rejected_input_count: int = 0
    input_positions: tuple[DrcPosition, ...] = ()
    gross_jtds: tuple[GrossJtd, ...] = ()
    maturity_scaled_jtds: tuple[MaturityScaledJtd, ...] = ()
    net_jtds: tuple[NetJtd, ...] = ()
    fx_conversions: tuple[DrcFxConversion, ...] = ()
    risk_weight_evidence: tuple[DrcRiskWeightEvidence, ...] = ()
    fair_value_cap_evidence: tuple[DrcFairValueCapEvidence, ...] = ()
    attribution_records: tuple[CapitalContribution, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "categories", tuple(self.categories))
        object.__setattr__(self, "citations", tuple(self.citations))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "branch_metadata", tuple(self.branch_metadata))
        object.__setattr__(self, "input_positions", tuple(self.input_positions))
        object.__setattr__(self, "gross_jtds", tuple(self.gross_jtds))
        object.__setattr__(self, "maturity_scaled_jtds", tuple(self.maturity_scaled_jtds))
        object.__setattr__(self, "net_jtds", tuple(self.net_jtds))
        object.__setattr__(self, "fx_conversions", tuple(self.fx_conversions))
        object.__setattr__(self, "risk_weight_evidence", tuple(self.risk_weight_evidence))
        object.__setattr__(
            self,
            "fair_value_cap_evidence",
            tuple(self.fair_value_cap_evidence),
        )
        object.__setattr__(self, "attribution_records", tuple(self.attribution_records))
