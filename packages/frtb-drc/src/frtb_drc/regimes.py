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
    "BASEL_MAR22_27": DrcCitation(
        citation_id="BASEL_MAR22_27",
        source_id="BASEL_MAR22",
        paragraph="MAR22.27",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Securitisation non-CTP gross JTD equals market value without a separate LGD.",
    ),
    "BASEL_MAR22_28": DrcCitation(
        citation_id="BASEL_MAR22_28",
        source_id="BASEL_MAR22",
        paragraph="MAR22.28",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Securitisation non-CTP decomposition into equivalent replicating tranches.",
    ),
    "BASEL_MAR22_29": DrcCitation(
        citation_id="BASEL_MAR22_29",
        source_id="BASEL_MAR22",
        paragraph="MAR22.29",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Securitisation non-CTP offsetting is limited by underlying pool and tranche.",
    ),
    "BASEL_MAR22_30": DrcCitation(
        citation_id="BASEL_MAR22_30",
        source_id="BASEL_MAR22",
        paragraph="MAR22.30",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Securitisation non-CTP maturity offsetting and replication conditions.",
    ),
    "BASEL_MAR22_31": DrcCitation(
        citation_id="BASEL_MAR22_31",
        source_id="BASEL_MAR22",
        paragraph="MAR22.31",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Securitisation non-CTP bucket taxonomy by corporate, asset class, and region.",
    ),
    "BASEL_MAR22_32": DrcCitation(
        citation_id="BASEL_MAR22_32",
        source_id="BASEL_MAR22",
        paragraph="MAR22.32",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Securitisation non-CTP bucket assignment using market classification.",
    ),
    "BASEL_MAR22_33": DrcCitation(
        citation_id="BASEL_MAR22_33",
        source_id="BASEL_MAR22",
        paragraph="MAR22.33",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Securitisation non-CTP bucket capital uses the non-securitisation HBR formula.",
    ),
    "BASEL_MAR22_34": DrcCitation(
        citation_id="BASEL_MAR22_34",
        source_id="BASEL_MAR22",
        paragraph="MAR22.34",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note=(
            "Securitisation non-CTP risk weights are defined by tranche using "
            "banking-book treatment; individual cash securitisation position capital "
            "may be capped at fair value."
        ),
    ),
    "BASEL_MAR22_35": DrcCitation(
        citation_id="BASEL_MAR22_35",
        source_id="BASEL_MAR22",
        paragraph="MAR22.35",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note=(
            "No hedging across securitisation non-CTP buckets; category capital is the bucket sum."
        ),
    ),
    "BASEL_MAR22_36": DrcCitation(
        citation_id="BASEL_MAR22_36",
        source_id="BASEL_MAR22",
        paragraph="MAR22.36",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="CTP securitisation gross JTD follows the securitisation gross JTD approach.",
    ),
    "BASEL_MAR22_37": DrcCitation(
        citation_id="BASEL_MAR22_37",
        source_id="BASEL_MAR22",
        paragraph="MAR22.37",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="CTP non-securitisation hedge gross JTD is market value.",
    ),
    "BASEL_MAR22_39": DrcCitation(
        citation_id="BASEL_MAR22_39",
        source_id="BASEL_MAR22",
        paragraph="MAR22.39",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="CTP offsetting, replication, decomposition, and residual-exposure constraints.",
    ),
    "BASEL_MAR22_40": DrcCitation(
        citation_id="BASEL_MAR22_40",
        source_id="BASEL_MAR22",
        paragraph="MAR22.40",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Each CTP index is a bucket of its own.",
    ),
    "BASEL_MAR22_41": DrcCitation(
        citation_id="BASEL_MAR22_41",
        source_id="BASEL_MAR22",
        paragraph="MAR22.41",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Bespoke CTP securitisations are allocated to the corresponding index bucket.",
    ),
    "BASEL_MAR22_44": DrcCitation(
        citation_id="BASEL_MAR22_44",
        source_id="BASEL_MAR22",
        paragraph="MAR22.44",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="CTP bucket capital uses CTP-wide HBR and has no bucket-level zero floor.",
    ),
    "BASEL_MAR22_45": DrcCitation(
        citation_id="BASEL_MAR22_45",
        source_id="BASEL_MAR22",
        paragraph="MAR22.45",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note=(
            "CTP category aggregation recognises negative bucket capital at 50% "
            "and floors total at zero."
        ),
    ),
    "US_NPR_210_SCOPE": DrcCitation(
        citation_id="US_NPR_210_SCOPE",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(a)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Default risk capital requirement scope and aggregation.",
    ),
    "US_NPR_207_A_8": DrcCitation(
        citation_id="US_NPR_207_A_8",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.207(a)(8)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note=(
            "Market-risk standardized calculations use the banking organization's "
            "reporting currency, except the approved FX base-currency case."
        ),
    ),
    "US_NPR_208_H_1_II": DrcCitation(
        citation_id="US_NPR_208_H_1_II",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.208(h)(1)(ii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note=(
            "FX risk factors use spot reporting/base exchange rates; the DRC package "
            "uses explicitly supplied spot rates to translate native-currency DRC "
            "amounts into the context base currency before aggregation."
        ),
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
    "US_NPR_210_A_2_IV_A": DrcCitation(
        citation_id="US_NPR_210_A_2_IV_A",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(a)(2)(iv)(A)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Hedge benefit ratio for long and short net default exposures within a bucket.",
    ),
    "US_NPR_210_A_2_IV_C": DrcCitation(
        citation_id="US_NPR_210_A_2_IV_C",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(a)(2)(iv)(C)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Bucket-level default-risk capital aggregation.",
    ),
    "US_NPR_210_B_2": DrcCitation(
        citation_id="US_NPR_210_B_2",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(b)(2)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Same-obligor non-securitisation offsetting and seniority rule.",
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
        paragraph="proposed section __.210(b)(3)(ii), Table 1 to section __.210",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Non-securitisation risk weights by bucket and credit quality.",
    ),
    "US_NPR_210_B_3_III": DrcCitation(
        citation_id="US_NPR_210_B_3_III",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(b)(3)(iii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Non-securitisation default-risk capital equals the sum of bucket-level requirements.",
    ),
    "US_NPR_210_C_1": DrcCitation(
        citation_id="US_NPR_210_C_1",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(c)(1)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Securitisation non-CTP gross default exposure equals market value.",
    ),
    "US_NPR_210_C_2": DrcCitation(
        citation_id="US_NPR_210_C_2",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(c)(2)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note=(
            "Securitisation non-CTP offsetting by same underlying pool and "
            "tranche, with decomposition."
        ),
    ),
    "US_NPR_210_C_3_I_II": DrcCitation(
        citation_id="US_NPR_210_C_3_I_II",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(c)(3)(i)-(ii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Securitisation non-CTP bucket definitions and assignment rules.",
    ),
    "US_NPR_210_C_3_III": DrcCitation(
        citation_id="US_NPR_210_C_3_III",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(c)(3)(iii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Securitisation non-CTP bucket-level capital formula and risk-weight source.",
    ),
    "US_NPR_210_C_3_IV": DrcCitation(
        citation_id="US_NPR_210_C_3_IV",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(c)(3)(iv)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Securitisation non-CTP category capital equals the sum of bucket-level requirements.",
    ),
    "US_NPR_210_D_1": DrcCitation(
        citation_id="US_NPR_210_D_1",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(d)(1)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="CTP gross default exposure and Nth-to-default treatment.",
    ),
    "US_NPR_210_D_2": DrcCitation(
        citation_id="US_NPR_210_D_2",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(d)(2)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note=(
            "CTP offsetting through exact maturity differences, replication, "
            "decomposition, and residual treatment."
        ),
    ),
    "US_NPR_210_D_3_I_III": DrcCitation(
        citation_id="US_NPR_210_D_3_I_III",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(d)(3)(i)-(iii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="CTP index, bespoke, and hedge bucket assignment.",
    ),
    "US_NPR_210_D_3_IV": DrcCitation(
        citation_id="US_NPR_210_D_3_IV",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(d)(3)(iv)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note=(
            "CTP bucket-level capital uses CTP-wide HBR and spans all exposures "
            "relating to the index."
        ),
    ),
    "US_NPR_210_D_3_IV_D": DrcCitation(
        citation_id="US_NPR_210_D_3_IV_D",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(d)(3)(iv)(D)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note=(
            "CTP risk-weight sources for tranched positions, non-tranched hedges, "
            "and decomposed single-name exposures."
        ),
    ),
    "US_NPR_210_D_3_V": DrcCitation(
        citation_id="US_NPR_210_D_3_V",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(d)(3)(v)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="CTP category-level aggregation of bucket-level capital requirements.",
    ),
}

BASEL_MAR22_CITATIONS: dict[str, DrcCitation] = {
    "BASEL_MAR22_11": US_NPR_2_0_CITATIONS["BASEL_MAR22_11"],
    "BASEL_MAR22_12": DrcCitation(
        citation_id="BASEL_MAR22_12",
        source_id="BASEL_MAR22",
        paragraph="MAR22.12",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note=(
            "Non-securitisation LGD ladder for equity, non-senior debt, senior debt, "
            "covered bonds, and recovery-unlinked instruments."
        ),
    ),
    "BASEL_MAR22_13": US_NPR_2_0_CITATIONS["BASEL_MAR22_13"],
    "BASEL_MAR22_15_18": DrcCitation(
        citation_id="BASEL_MAR22_15_18",
        source_id="BASEL_MAR22",
        paragraph="MAR22.15-MAR22.18",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="One-year maturity scaling with a three-month floor for exposures below three months.",
    ),
    "BASEL_MAR22_19": DrcCitation(
        citation_id="BASEL_MAR22_19",
        source_id="BASEL_MAR22",
        paragraph="MAR22.19",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Same-obligor non-securitisation offsetting and seniority rule.",
    ),
    "BASEL_MAR22_22": DrcCitation(
        citation_id="BASEL_MAR22_22",
        source_id="BASEL_MAR22",
        paragraph="MAR22.22",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note=(
            "Basel non-securitisation buckets: corporates, sovereigns, and local "
            "governments and municipalities."
        ),
    ),
    "BASEL_MAR22_23": DrcCitation(
        citation_id="BASEL_MAR22_23",
        source_id="BASEL_MAR22",
        paragraph="MAR22.23",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Hedge benefit ratio for long and short net default exposures within a bucket.",
    ),
    "BASEL_MAR22_24": DrcCitation(
        citation_id="BASEL_MAR22_24",
        source_id="BASEL_MAR22",
        paragraph="MAR22.24",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note=(
            "Basel non-securitisation risk weights by letter-grade credit quality, "
            "unrated, and defaulted categories."
        ),
    ),
    "BASEL_MAR22_25": DrcCitation(
        citation_id="BASEL_MAR22_25",
        source_id="BASEL_MAR22",
        paragraph="MAR22.25",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Bucket-level default-risk capital aggregation.",
    ),
    "BASEL_MAR22_26": DrcCitation(
        citation_id="BASEL_MAR22_26",
        source_id="BASEL_MAR22",
        paragraph="MAR22.26",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Non-securitisation default-risk capital equals the sum of bucket-level requirements.",
    ),
    "BASEL_MAR22_34": US_NPR_2_0_CITATIONS["BASEL_MAR22_34"],
    "BASEL_MAR22_42": DrcCitation(
        citation_id="BASEL_MAR22_42",
        source_id="BASEL_MAR22",
        paragraph="MAR22.42",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note=(
            "CTP securitisation risk weights use the banking-book securitisation "
            "hierarchy with one-year maturity."
        ),
    ),
}

EU_CRR3_CITATIONS: dict[str, DrcCitation] = {
    "EU_CRR3_ARTICLE_325W": DrcCitation(
        citation_id="EU_CRR3_ARTICLE_325W",
        source_id="EU_CRR3_2024_1623",
        paragraph="Article 325w",
        url="https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng",
        note=(
            "EU default-risk charge gross JTD anchor; runtime profile remains "
            "fail-closed until EU CQS and RTS mappings are implemented."
        ),
    ),
}

PRA_UK_CRR_CITATIONS: dict[str, DrcCitation] = {
    "PRA_PS1_26_MARKET_RISK": DrcCitation(
        citation_id="PRA_PS1_26_MARKET_RISK",
        source_id="UK_PRA_PS1_26_BASEL_3_1_FINAL_RULES",
        paragraph="Chapter 3 and Appendix 1",
        url="https://www.bankofengland.co.uk/prudential-regulation/publication/2026/january/implementation-of-the-basel-3-1-final-rules-policy-statement",
        note=(
            "UK Basel 3.1 market-risk profile anchor; runtime DRC profile remains "
            "fail-closed until PRA rulebook paragraph mapping is implemented."
        ),
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
    supported_risk_classes=frozenset({DrcRiskClass.NON_SECURITISATION}),
    citations=BASEL_MAR22_CITATIONS,
    unsupported_features={
        DrcRiskClass.SECURITISATION_NON_CTP: (
            "BASEL_MAR22 securitisation non-CTP because MAR22.34 banking-book "
            "securitisation risk-weight derivation and fair-value cap evidence are "
            "not implemented"
        ),
        DrcRiskClass.CORRELATION_TRADING_PORTFOLIO: (
            "BASEL_MAR22 CTP because MAR22.42 banking-book securitisation risk-weight "
            "lineage and CTP decomposition evidence are not implemented"
        ),
    },
)

_EU_CRR3_PROFILE = DrcRuleProfile(
    profile_id=EU_CRR3_PROFILE_ID,
    regulator="European Union",
    version="Regulation (EU) 2024/1623",
    publication_date=date(2024, 5, 31),
    effective_date=None,
    status="final_rule_mapping_pending",
    supported_risk_classes=frozenset(),
    citations=EU_CRR3_CITATIONS,
    unsupported_features={
        DrcRiskClass.NON_SECURITISATION: (
            "EU_CRR3 non-securitisation DRC because Article 325w and related CQS/RTS "
            "mapping have not been implemented"
        ),
        DrcRiskClass.SECURITISATION_NON_CTP: (
            "EU_CRR3 securitisation non-CTP DRC because Article 325w and related "
            "banking-book securitisation mappings have not been implemented"
        ),
        DrcRiskClass.CORRELATION_TRADING_PORTFOLIO: (
            "EU_CRR3 CTP DRC because Article 325w and related CTP mappings have not "
            "been implemented"
        ),
    },
)

_PRA_UK_CRR_PROFILE = DrcRuleProfile(
    profile_id=PRA_UK_CRR_PROFILE_ID,
    regulator="Prudential Regulation Authority",
    version="Basel 3.1 PS1/26",
    publication_date=date(2026, 1, 20),
    effective_date=date(2027, 1, 1),
    status="final_rule_mapping_pending",
    supported_risk_classes=frozenset(),
    citations=PRA_UK_CRR_CITATIONS,
    unsupported_features={
        DrcRiskClass.NON_SECURITISATION: (
            "PRA_UK_CRR non-securitisation DRC because PS1/26 Chapter 3 and "
            "Appendix 1 rulebook paragraph mappings have not been implemented"
        ),
        DrcRiskClass.SECURITISATION_NON_CTP: (
            "PRA_UK_CRR securitisation non-CTP DRC because PS1/26 Chapter 3 and "
            "Appendix 1 securitisation mappings have not been implemented"
        ),
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
