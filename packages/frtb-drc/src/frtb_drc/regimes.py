"""Rule-profile identity and supported-feature declarations for DRC."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType

from frtb_common import UnsupportedRegulatoryFeatureError, jsonable

from frtb_drc.data_models import DrcCitation, DrcRiskClass
from frtb_drc.reference_data import profile_reference_data_payload
from frtb_drc.validation import DrcInputError

US_NPR_2_0_PROFILE_ID = "US_NPR_2_0"


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
        if not self.content_hash:
            object.__setattr__(self, "content_hash", profile_content_hash(self))

    def as_dict(self) -> dict[str, object]:
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
            "content_hash": self.content_hash,
        }


US_NPR_2_0_CITATIONS: dict[str, DrcCitation] = {
    "BASEL_MAR22_11": DrcCitation(
        citation_id="BASEL_MAR22_11",
        source_id="BASEL_MAR22",
        paragraph="MAR22.11",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Gross JTD formula inputs: LGD, notional, and cumulative P&L.",
    ),
    "BASEL_MAR22_13": DrcCitation(
        citation_id="BASEL_MAR22_13",
        source_id="BASEL_MAR22",
        paragraph="MAR22.13",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Notional and P&L signs for long and short JTD.",
    ),
    "US_NPR_210_SCOPE": DrcCitation(
        citation_id="US_NPR_210_SCOPE",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(a)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Default risk capital requirement scope and aggregation.",
    ),
    "US_NPR_210_B_1_IV": DrcCitation(
        citation_id="US_NPR_210_B_1_IV",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(b)(1)(iv)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Non-securitisation LGD values.",
    ),
    "US_NPR_210_A_2_III": DrcCitation(
        citation_id="US_NPR_210_A_2_III",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(a)(2)(iii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Maturity weighting and floor.",
    ),
    "US_NPR_210_B_3_I": DrcCitation(
        citation_id="US_NPR_210_B_3_I",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(b)(3)(i)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Non-securitisation bucket definitions.",
    ),
    "US_NPR_210_B_3_II": DrcCitation(
        citation_id="US_NPR_210_B_3_II",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(b)(3)(ii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Non-securitisation risk weights by bucket and credit quality.",
    ),
}


def get_rule_profile(profile_id: str = US_NPR_2_0_PROFILE_ID) -> DrcRuleProfile:
    """Return a DRC rule profile by id."""

    try:
        return _PROFILES[profile_id]
    except KeyError as exc:
        raise DrcInputError(f"unknown DRC rule profile: {profile_id}") from exc


def ensure_risk_class_supported(profile: DrcRuleProfile, risk_class: DrcRiskClass) -> None:
    """Raise explicitly when a profile/risk-class path is unsupported."""

    if risk_class in profile.supported_risk_classes:
        return
    reason = profile.unsupported_features.get(risk_class, "risk class is not supported")
    raise UnsupportedRegulatoryFeatureError(f"frtb-drc does not support {reason}")


def profile_content_hash(profile: DrcRuleProfile) -> str:
    """Compute a deterministic hash from profile content, excluding the hash itself."""

    payload = _profile_hash_payload(profile)
    encoded = json.dumps(jsonable(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
    supported_risk_classes=frozenset({DrcRiskClass.NON_SECURITISATION}),
    citations=US_NPR_2_0_CITATIONS,
    unsupported_features={
        DrcRiskClass.SECURITISATION_NON_CTP: (
            "U.S. NPR 2.0 securitisation non-CTP DRC is not implemented"
        ),
        DrcRiskClass.CORRELATION_TRADING_PORTFOLIO: ("U.S. NPR 2.0 CTP DRC is not implemented"),
    },
)

_PROFILES: Mapping[str, DrcRuleProfile] = MappingProxyType(
    {_US_NPR_2_0_PROFILE.profile_id: _US_NPR_2_0_PROFILE}
)
