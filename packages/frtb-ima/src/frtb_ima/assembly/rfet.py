"""RFET assessment assembly helpers."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from frtb_ima.calendar import ObservationWindowBasis
from frtb_ima.data_contracts import RFETNewIssuanceEvidence
from frtb_ima.data_models import ModellabilityStatus
from frtb_ima.validation.rfet_quantitative import RFETObservationExclusion


@dataclass(frozen=True)
class RFETEvidenceAssessment:
    """Audit-friendly RFET evidence assessment result."""

    risk_factor_name: str
    as_of_date: date
    lookback_start: date
    base_required_observations: int
    required_observations: int
    eligible_observation_count: int
    eligible_observation_dates: tuple[date, ...]
    source_count: int
    qualitative_pass: bool
    quantitative_pass: bool
    bucket_representative: bool
    new_issuance_prorated: bool
    modellability_status: ModellabilityStatus
    lookback_basis: str = ObservationWindowBasis.OBSERVATION_COUNT_PROXY.value
    calendar_source: str = ""
    calendar_version: str = ""
    official_holiday_count: int = 0
    missing_business_dates: tuple[date, ...] = ()
    shift_reason: str = ""
    source_counts: tuple[tuple[str, int], ...] = ()
    vendor_counts: tuple[tuple[str, int], ...] = ()
    exclusion_counts: tuple[tuple[str, int], ...] = ()
    bucket_counts: tuple[tuple[str, int], ...] = ()
    representative_methodology_counts: tuple[tuple[str, int], ...] = ()
    data_pool_count: int = 0
    vendor_audit_evidence_count: int = 0
    new_issuance_policy_basis: str = ""
    exclusions: tuple[RFETObservationExclusion, ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
        return {
            "risk_factor_name": self.risk_factor_name,
            "as_of_date": self.as_of_date.isoformat(),
            "lookback_start": self.lookback_start.isoformat(),
            "base_required_observations": self.base_required_observations,
            "required_observations": self.required_observations,
            "eligible_observation_count": self.eligible_observation_count,
            "eligible_observation_dates": [
                observation_date.isoformat() for observation_date in self.eligible_observation_dates
            ],
            "source_count": self.source_count,
            "qualitative_pass": self.qualitative_pass,
            "quantitative_pass": self.quantitative_pass,
            "bucket_representative": self.bucket_representative,
            "new_issuance_prorated": self.new_issuance_prorated,
            "modellability_status": self.modellability_status.value,
            "lookback_basis": self.lookback_basis,
            "calendar_source": self.calendar_source,
            "calendar_version": self.calendar_version,
            "official_holiday_count": self.official_holiday_count,
            "missing_business_dates": [item.isoformat() for item in self.missing_business_dates],
            "shift_reason": self.shift_reason,
            "source_counts": dict(self.source_counts),
            "vendor_counts": dict(self.vendor_counts),
            "exclusion_counts": dict(self.exclusion_counts),
            "bucket_counts": dict(self.bucket_counts),
            "representative_methodology_counts": dict(self.representative_methodology_counts),
            "data_pool_count": self.data_pool_count,
            "vendor_audit_evidence_count": self.vendor_audit_evidence_count,
            "new_issuance_policy_basis": self.new_issuance_policy_basis,
            "exclusions": [exclusion.as_dict() for exclusion in self.exclusions],
        }


def _count_pairs(values: Iterable[str]) -> tuple[tuple[str, int], ...]:
    counter = Counter(value for value in values if value)
    return tuple(sorted(counter.items()))


def _exclusion_count_pairs(
    exclusions: Iterable[RFETObservationExclusion],
) -> tuple[tuple[str, int], ...]:
    return _count_pairs(exclusion.reason.value for exclusion in exclusions)


def _new_issuance_policy_basis(new_issuance: RFETNewIssuanceEvidence | None) -> str:
    if new_issuance is None:
        return ""
    if new_issuance.policy_citation:
        return new_issuance.policy_citation
    return new_issuance.rationale


def _status_from_tests(
    qualitative_pass: bool,
    quantitative_pass: bool,
) -> ModellabilityStatus:
    if not qualitative_pass:
        return ModellabilityStatus.TYPE_B_NMRF
    if quantitative_pass:
        return ModellabilityStatus.MODELLABLE
    return ModellabilityStatus.TYPE_A_NMRF
