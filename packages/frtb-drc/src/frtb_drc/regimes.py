"""Rule-profile identity and supported-feature declarations for DRC."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_drc._hashing import hash_payload
from frtb_drc.data_models import DrcCitation, DrcRiskClass
from frtb_drc.reference_data import profile_reference_data_payload
from frtb_drc.regime_citations import (
    BASEL_MAR22_CITATIONS,
    EU_CRR3_CITATIONS,
    PRA_UK_CRR_CITATIONS,
    US_NPR_2_0_CITATIONS,
)
from frtb_drc.validation import DrcInputError

US_NPR_2_0_PROFILE_ID = "US_NPR_2_0"
BASEL_MAR22_PROFILE_ID = "BASEL_MAR22"
EU_CRR3_PROFILE_ID = "EU_CRR3"
PRA_UK_CRR_PROFILE_ID = "PRA_UK_CRR"


@dataclass(frozen=True)
class DrcRuleProfile:
    """Versioned DRC rule profile metadata."""

    profile_id: str
    regulator: str
    version: str
    publication_date: date
    effective_date: date | None
    status: str
    supported_risk_classes: frozenset[DrcRiskClass]
    citations: Mapping[str, DrcCitation] = field(default_factory=dict)
    unsupported_features: Mapping[DrcRiskClass, str] = field(default_factory=dict)
    securitisation_non_ctp_fair_value_cap_allowed: bool = False
    securitisation_non_ctp_fair_value_cap_citation_ids: tuple[str, ...] = ()
    content_hash: str = ""

    def __post_init__(self) -> None:
        supported = frozenset(DrcRiskClass(item) for item in self.supported_risk_classes)
        unsupported = {
            DrcRiskClass(risk_class): reason
            for risk_class, reason in self.unsupported_features.items()
        }
        object.__setattr__(self, "supported_risk_classes", supported)
        object.__setattr__(self, "citations", MappingProxyType(dict(self.citations)))
        object.__setattr__(self, "unsupported_features", MappingProxyType(unsupported))
        object.__setattr__(
            self,
            "securitisation_non_ctp_fair_value_cap_citation_ids",
            tuple(self.securitisation_non_ctp_fair_value_cap_citation_ids),
        )
        if not self.content_hash:
            object.__setattr__(self, "content_hash", profile_content_hash(self))

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable rule profile record.

        Returns
        -------
        dict[str, object]
            Profile metadata, citations, and support flags for audit export.
        """
        return {
            "profile_id": self.profile_id,
            "regulator": self.regulator,
            "version": self.version,
            "publication_date": self.publication_date.isoformat(),
            "effective_date": self.effective_date.isoformat()
            if self.effective_date is not None
            else None,
            "status": self.status,
            "supported_risk_classes": sorted(
                risk_class.value for risk_class in self.supported_risk_classes
            ),
            "citations": {
                citation_id: citation.as_dict()
                for citation_id, citation in sorted(self.citations.items())
            },
            "unsupported_features": {
                risk_class.value: reason
                for risk_class, reason in sorted(
                    self.unsupported_features.items(),
                    key=lambda item: item[0].value,
                )
            },
            "securitisation_non_ctp_fair_value_cap_allowed": (
                self.securitisation_non_ctp_fair_value_cap_allowed
            ),
            "securitisation_non_ctp_fair_value_cap_citation_ids": (
                self.securitisation_non_ctp_fair_value_cap_citation_ids
            ),
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class DrcProfileSupportCell:
    """One profile/risk-class support inventory cell."""

    profile_id: str
    risk_class: DrcRiskClass
    status: str
    reason: str
    citation_ids: tuple[str, ...]
    next_step: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "risk_class", DrcRiskClass(self.risk_class))
        object.__setattr__(self, "citation_ids", tuple(self.citation_ids))

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable support-matrix cell.

        Returns
        -------
        dict[str, object]
            Profile, risk class, status, and citation metadata for the cell.
        """
        return {
            "profile_id": self.profile_id,
            "risk_class": self.risk_class.value,
            "status": self.status,
            "reason": self.reason,
            "citation_ids": self.citation_ids,
            "next_step": self.next_step,
        }


def get_rule_profile(profile_id: str = US_NPR_2_0_PROFILE_ID) -> DrcRuleProfile:
    """Return a DRC rule profile by id.
    Parameters
    ----------
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    DrcRuleProfile
        Rule-profile metadata for the selected DRC profile id.
    """

    try:
        return _PROFILES[profile_id]
    except KeyError as exc:
        raise DrcInputError(f"unknown DRC rule profile: {profile_id}") from exc


def ensure_risk_class_supported(profile: DrcRuleProfile, risk_class: DrcRiskClass) -> None:
    """Raise explicitly when a profile/risk-class path is unsupported.
    Parameters
    ----------
    profile : DrcRuleProfile
        Profile.
    risk_class : DrcRiskClass
        DRC risk class for profile support lookup.
    """

    if risk_class in profile.supported_risk_classes:
        return
    reason = profile.unsupported_features.get(risk_class, "risk class is not supported")
    raise UnsupportedRegulatoryFeatureError(f"frtb-drc does not support {reason}")


def drc_profile_support_matrix() -> tuple[DrcProfileSupportCell, ...]:
    """Return the current DRC profile/risk-class support matrix.
    Returns
    -------
    tuple[DrcProfileSupportCell, ...]
        tuple[DrcProfileSupportCell, ...] produced by drc_profile_support_matrix.
    """

    cells: list[DrcProfileSupportCell] = []
    for profile_id in _PROFILE_ORDER:
        profile = get_rule_profile(profile_id)
        for risk_class in _RISK_CLASS_ORDER:
            cells.append(_profile_support_cell(profile, risk_class))
    return tuple(cells)


def profile_content_hash(profile: DrcRuleProfile) -> str:
    """Compute a deterministic hash from profile content, excluding the hash itself.
    Parameters
    ----------
    profile : DrcRuleProfile
        Profile.

    Returns
    -------
    str
        Stable hash of rule-profile metadata and reference data.
    """

    payload = _profile_hash_payload(profile)
    return hash_payload(payload)


def _profile_hash_payload(profile: DrcRuleProfile) -> dict[str, object]:
    return {
        "profile_id": profile.profile_id,
        "regulator": profile.regulator,
        "version": profile.version,
        "publication_date": profile.publication_date.isoformat(),
        "effective_date": profile.effective_date.isoformat()
        if profile.effective_date is not None
        else None,
        "status": profile.status,
        "supported_risk_classes": sorted(
            risk_class.value for risk_class in profile.supported_risk_classes
        ),
        "citations": {
            citation_id: citation.as_dict()
            for citation_id, citation in sorted(profile.citations.items())
        },
        "unsupported_features": {
            risk_class.value: reason
            for risk_class, reason in sorted(
                profile.unsupported_features.items(),
                key=lambda item: item[0].value,
            )
        },
        "securitisation_non_ctp_fair_value_cap_allowed": (
            profile.securitisation_non_ctp_fair_value_cap_allowed
        ),
        "securitisation_non_ctp_fair_value_cap_citation_ids": (
            profile.securitisation_non_ctp_fair_value_cap_citation_ids
        ),
        "reference_data": profile_reference_data_payload(profile.profile_id),
        "content_hash": "",
    }


_US_NPR_2_0_PROFILE = DrcRuleProfile(
    profile_id=US_NPR_2_0_PROFILE_ID,
    regulator="Federal Reserve/OCC/FDIC",
    version="NPR 2.0",
    publication_date=date(2026, 3, 27),
    effective_date=None,
    status="proposed",
    supported_risk_classes=frozenset(
        {
            DrcRiskClass.NON_SECURITISATION,
            DrcRiskClass.SECURITISATION_NON_CTP,
            DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        }
    ),
    citations=US_NPR_2_0_CITATIONS,
    securitisation_non_ctp_fair_value_cap_allowed=True,
    securitisation_non_ctp_fair_value_cap_citation_ids=(
        "US_NPR_210_C_3_III",
        "BASEL_MAR22_34",
    ),
    unsupported_features={},
)

_BASEL_MAR22_PROFILE = DrcRuleProfile(
    profile_id=BASEL_MAR22_PROFILE_ID,
    regulator="Basel Committee on Banking Supervision",
    version="MAR22 current",
    publication_date=date(2020, 3, 27),
    effective_date=date(2023, 1, 1),
    status="standard",
    supported_risk_classes=frozenset(
        {
            DrcRiskClass.NON_SECURITISATION,
            DrcRiskClass.SECURITISATION_NON_CTP,
            DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        }
    ),
    citations=BASEL_MAR22_CITATIONS,
    securitisation_non_ctp_fair_value_cap_allowed=True,
    securitisation_non_ctp_fair_value_cap_citation_ids=("BASEL_MAR22_34",),
    unsupported_features={},
)

_EU_CRR3_PROFILE = DrcRuleProfile(
    profile_id=EU_CRR3_PROFILE_ID,
    regulator="European Union",
    version="Regulation (EU) 2024/1623",
    publication_date=date(2024, 5, 31),
    effective_date=None,
    status="partial_nonsec_sec_supported",
    supported_risk_classes=frozenset(
        {
            DrcRiskClass.NON_SECURITISATION,
            DrcRiskClass.SECURITISATION_NON_CTP,
            DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        }
    ),
    citations=EU_CRR3_CITATIONS,
    securitisation_non_ctp_fair_value_cap_allowed=True,
    securitisation_non_ctp_fair_value_cap_citation_ids=("EU_CRR3_ARTICLE_325AA",),
    unsupported_features={},
)

_PRA_UK_CRR_PROFILE = DrcRuleProfile(
    profile_id=PRA_UK_CRR_PROFILE_ID,
    regulator="Prudential Regulation Authority",
    version="Basel 3.1 PS1/26",
    publication_date=date(2026, 1, 20),
    effective_date=date(2027, 1, 1),
    status="partial_nonsec_sec_supported",
    supported_risk_classes=frozenset(
        {
            DrcRiskClass.NON_SECURITISATION,
            DrcRiskClass.SECURITISATION_NON_CTP,
        }
    ),
    citations=PRA_UK_CRR_CITATIONS,
    securitisation_non_ctp_fair_value_cap_allowed=True,
    securitisation_non_ctp_fair_value_cap_citation_ids=("PRA_DRC_ARTICLE_325AA",),
    unsupported_features={
        DrcRiskClass.CORRELATION_TRADING_PORTFOLIO: (
            "PRA_UK_CRR CTP DRC because PS1/26 Chapter 3 and Appendix 1 CTP mappings "
            "have not been implemented"
        ),
    },
)

_PROFILES: Mapping[str, DrcRuleProfile] = MappingProxyType(
    {
        _BASEL_MAR22_PROFILE.profile_id: _BASEL_MAR22_PROFILE,
        _EU_CRR3_PROFILE.profile_id: _EU_CRR3_PROFILE,
        _PRA_UK_CRR_PROFILE.profile_id: _PRA_UK_CRR_PROFILE,
        _US_NPR_2_0_PROFILE.profile_id: _US_NPR_2_0_PROFILE,
    }
)

_PROFILE_ORDER = (
    US_NPR_2_0_PROFILE_ID,
    BASEL_MAR22_PROFILE_ID,
    EU_CRR3_PROFILE_ID,
    PRA_UK_CRR_PROFILE_ID,
)
_RISK_CLASS_ORDER = tuple(DrcRiskClass)

_SUPPORTED_CELL_DETAILS: Mapping[tuple[str, DrcRiskClass], tuple[str, tuple[str, ...], str]] = (
    MappingProxyType(
        {
            (
                US_NPR_2_0_PROFILE_ID,
                DrcRiskClass.NON_SECURITISATION,
            ): (
                "U.S. NPR 2.0 non-securitisation row and batch capital supported.",
                (
                    "US_NPR_210_B_1_IV",
                    "US_NPR_210_A_2_III",
                    "US_NPR_210_B_2",
                    "US_NPR_210_B_3_I",
                    "US_NPR_210_B_3_II",
                    "US_NPR_210_B_3_III",
                ),
                "Maintain fixture hashes and attribution compatibility.",
            ),
            (
                US_NPR_2_0_PROFILE_ID,
                DrcRiskClass.SECURITISATION_NON_CTP,
            ): (
                "U.S. NPR 2.0 securitisation non-CTP row and batch capital supported.",
                (
                    "US_NPR_210_C_1",
                    "US_NPR_210_C_2",
                    "US_NPR_210_C_3_I_II",
                    "US_NPR_210_C_3_III",
                    "US_NPR_210_C_3_IV",
                    "BASEL_MAR22_34",
                ),
                "Maintain typed evidence and legacy compatibility coverage.",
            ),
            (
                US_NPR_2_0_PROFILE_ID,
                DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
            ): (
                "U.S. NPR 2.0 CTP row and batch capital supported.",
                (
                    "US_NPR_210_D_1",
                    "US_NPR_210_D_2",
                    "US_NPR_210_D_3_I_III",
                    "US_NPR_210_D_3_IV",
                    "US_NPR_210_D_3_IV_D",
                    "US_NPR_210_D_3_V",
                ),
                "Maintain CTP decomposition evidence coverage.",
            ),
            (
                BASEL_MAR22_PROFILE_ID,
                DrcRiskClass.NON_SECURITISATION,
            ): (
                "Basel MAR22 non-securitisation row and batch capital supported.",
                (
                    "BASEL_MAR22_11",
                    "BASEL_MAR22_12",
                    "BASEL_MAR22_15_18",
                    "BASEL_MAR22_19",
                    "BASEL_MAR22_22",
                    "BASEL_MAR22_23",
                    "BASEL_MAR22_24",
                    "BASEL_MAR22_25",
                    "BASEL_MAR22_26",
                ),
                "Maintain Basel non-securitisation fixture and batch coverage.",
            ),
            (
                BASEL_MAR22_PROFILE_ID,
                DrcRiskClass.SECURITISATION_NON_CTP,
            ): (
                (
                    "Basel MAR22 securitisation non-CTP row and batch capital supported "
                    "with typed MAR22.34 banking-book risk-weight evidence."
                ),
                (
                    "BASEL_MAR22_27",
                    "BASEL_MAR22_28",
                    "BASEL_MAR22_29",
                    "BASEL_MAR22_30",
                    "BASEL_MAR22_31",
                    "BASEL_MAR22_32",
                    "BASEL_MAR22_33",
                    "BASEL_MAR22_34",
                    "BASEL_MAR22_35",
                ),
                "Maintain Basel-specific typed evidence fixtures.",
            ),
            (
                BASEL_MAR22_PROFILE_ID,
                DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
            ): (
                (
                    "Basel MAR22 CTP row and batch capital supported with typed "
                    "MAR22.42 banking-book risk-weight and decomposition evidence."
                ),
                (
                    "BASEL_MAR22_36",
                    "BASEL_MAR22_37",
                    "BASEL_MAR22_39",
                    "BASEL_MAR22_40",
                    "BASEL_MAR22_41",
                    "BASEL_MAR22_42",
                    "BASEL_MAR22_44",
                    "BASEL_MAR22_45",
                ),
                "Maintain Basel-specific CTP typed evidence fixtures.",
            ),
            (
                EU_CRR3_PROFILE_ID,
                DrcRiskClass.NON_SECURITISATION,
            ): (
                "EU CRR3 non-securitisation row and batch capital supported.",
                (
                    "EU_CRR3_ARTICLE_325W",
                    "EU_CRR3_ARTICLE_325X",
                    "EU_CRR3_ARTICLE_325Y_1_2",
                    "EU_CRR3_ARTICLE_325Y_3_5",
                    "EU_CRR3_ARTICLE_325Y_6",
                    "EU_CRR3_ECAI_CQS_MAPPING",
                ),
                "Maintain EU CRR3 non-securitisation fixture and CQS mapping evidence.",
            ),
            (
                EU_CRR3_PROFILE_ID,
                DrcRiskClass.SECURITISATION_NON_CTP,
            ): (
                (
                    "EU CRR3 securitisation non-CTP row and batch capital supported "
                    "with typed Article 325aa banking-book risk-weight and fair-value "
                    "cap evidence."
                ),
                (
                    "EU_CRR3_ARTICLE_325Z",
                    "EU_CRR3_ARTICLE_325AA",
                ),
                "Maintain EU CRR3 securitisation non-CTP fixture and typed evidence coverage.",
            ),
            (
                EU_CRR3_PROFILE_ID,
                DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
            ): (
                (
                    "EU CRR3 CTP row and batch capital supported with typed Article "
                    "325ad banking-book risk-weight and decomposition evidence."
                ),
                (
                    "EU_CRR3_ARTICLE_325AB",
                    "EU_CRR3_ARTICLE_325AC",
                    "EU_CRR3_ARTICLE_325AD",
                ),
                "Maintain EU CRR3 CTP fixture and typed decomposition evidence coverage.",
            ),
            (
                PRA_UK_CRR_PROFILE_ID,
                DrcRiskClass.SECURITISATION_NON_CTP,
            ): (
                (
                    "PRA UK CRR securitisation non-CTP row and batch capital supported "
                    "with Article 325z maturity, gross JTD, netting, and Article 325aa "
                    "bucket, risk-weight, HBR, category, and fair-value-cap evidence."
                ),
                (
                    "PRA_DRC_ARTICLE_325V",
                    "PRA_DRC_ARTICLE_325Z",
                    "PRA_DRC_ARTICLE_325AA",
                ),
                "Maintain PRA UK CRR securitisation non-CTP fixture and typed evidence coverage.",
            ),
            (
                PRA_UK_CRR_PROFILE_ID,
                DrcRiskClass.NON_SECURITISATION,
            ): (
                (
                    "PRA UK CRR non-securitisation row and batch capital supported "
                    "with Article 325w/x/y LGD, maturity, netting, bucket, risk-weight, "
                    "HBR, and category evidence."
                ),
                (
                    "PRA_DRC_ARTICLE_325V",
                    "PRA_DRC_ARTICLE_325W",
                    "PRA_DRC_ARTICLE_325X",
                    "PRA_DRC_ARTICLE_325Y",
                ),
                (
                    "Maintain PRA UK CRR non-securitisation fixture and article-level "
                    "citation coverage."
                ),
            ),
        }
    )
)

_PLANNED_CELL_DETAILS: Mapping[tuple[str, DrcRiskClass], tuple[tuple[str, ...], str]] = (
    MappingProxyType(
        {
            (
                PRA_UK_CRR_PROFILE_ID,
                DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
            ): (
                (
                    "PRA_DRC_ARTICLE_325V",
                    "PRA_DRC_ARTICLE_325AB",
                    "PRA_DRC_ARTICLE_325AC",
                    "PRA_DRC_ARTICLE_325AD",
                ),
                (
                    "Implement PRA-owned CTP mappings, typed risk-weight and "
                    "decomposition evidence, and fixture evidence before enabling runtime support."
                ),
            ),
        }
    )
)


def _profile_support_cell(
    profile: DrcRuleProfile,
    risk_class: DrcRiskClass,
) -> DrcProfileSupportCell:
    supported = risk_class in profile.supported_risk_classes
    details = _SUPPORTED_CELL_DETAILS.get((profile.profile_id, risk_class))
    if supported and details is not None:
        reason, citations, next_step = details
    elif supported:
        reason = f"{profile.profile_id} {risk_class.value} is supported."
        citations = tuple(sorted(profile.citations))
        next_step = "Maintain committed tests and fixtures."
    else:
        reason = profile.unsupported_features.get(
            risk_class,
            f"{profile.profile_id} {risk_class.value} is unsupported until mapped.",
        )
        planned = _PLANNED_CELL_DETAILS.get((profile.profile_id, risk_class))
        if planned is None:
            citations = tuple(sorted(profile.citations))
            next_step = "Add cited profile-specific mappings and deterministic fixtures."
        else:
            citations, next_step = planned
    return DrcProfileSupportCell(
        profile_id=profile.profile_id,
        risk_class=risk_class,
        status="SUPPORTED" if supported else "FAIL_CLOSED",
        reason=reason,
        citation_ids=citations,
        next_step=next_step,
    )
