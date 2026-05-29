"""Loader for the RRAO sample-book v1 fixture.

The fixture covers 25 positions across 7 desks and 3 legal entities, exercising
every evidence type supported by US NPR 2.0.  The primary calculation profile
is US NPR 2.0; positions 15, 16, 17, 23, 24, and 25 are US-NPR-specific and
will fail under Basel MAR23 (see notebook 04).

Usage in notebooks:
    from examples.rrao_fixture import (
        load_context,
        load_positions,
        load_expected_outputs,
        PROFILE_US_NPR,
        PROFILE_BASEL,
        COMMON_POSITION_IDS,
    )
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from frtb_rrao import (
    RraoBackToBackMatch,
    RraoCalculationContext,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInvestmentFundDescriptor,
    RraoInvestmentFundExposureType,
    RraoInvestmentFundMethod,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
)

_FIXTURE_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "rrao_sample_book_v1"

PROFILE_US_NPR = RraoRegulatoryProfile.US_NPR_2_0
PROFILE_BASEL = RraoRegulatoryProfile.BASEL_MAR23

# Position IDs that are valid under BOTH Basel MAR23 and US NPR 2.0.
# Excludes: supervisor-directed (sb-015), investment funds (sb-016/017),
# and US NPR-only exclusion positions (sb-023/024/025).
COMMON_POSITION_IDS: frozenset[str] = frozenset({
    "exotic-longevity-001",
    "exotic-temperature-001",
    "exotic-nat-cat-001",
    "exotic-carbon-001",
    "gap-autocall-001",
    "gap-barrier-note-001",
    "corr-swap-equity-001",
    "corr-dispersion-001",
    "structured-multi-barrier-001",
    "ctp-basket-4under-001",
    "ctp-rainbow-3eq-001",
    "nro-illiquid-vol-001",
    "behav-agency-mbs-001",
    "behav-callable-deposit-001",
    "excl-listed-spx-opt-001",
    "excl-lch-irs-001",
    "excl-vanilla-call-001",
    "excl-btb-weather-A",
    "excl-btb-weather-B",
})

# Position IDs that are US NPR 2.0-specific (fail under Basel MAR23).
US_NPR_ONLY_POSITION_IDS: frozenset[str] = frozenset({
    "supdir-complex-deriv-001",
    "fund-alpha-exotic-001",
    "fund-beta-residual-001",
    "excl-deliverable-fx-001",
    "excl-us-tsy-option-001",
    "excl-fallback-capital-001",
})


def load_context(
    profile: RraoRegulatoryProfile = PROFILE_US_NPR,
) -> RraoCalculationContext:
    """Load the fixture calculation context, optionally overriding the profile."""

    payload = _load_json("positions.json")
    ctx = payload["context"]
    return RraoCalculationContext(
        run_id=str(ctx["run_id"]),
        calculation_date=date.fromisoformat(str(ctx["calculation_date"])),
        base_currency=str(ctx["base_currency"]),
        profile=profile,
    )


def load_positions(
    position_ids: frozenset[str] | None = None,
) -> tuple[RraoPosition, ...]:
    """Load all fixture positions, optionally filtered to a subset by ID."""

    payload = _load_json("positions.json")
    positions = tuple(
        _position_from_payload(p)
        for p in payload["positions"]
        if position_ids is None or p["position_id"] in position_ids
    )
    return positions


def load_expected_outputs() -> dict[str, Any]:
    """Load the expected capital outputs for the primary US NPR 2.0 run."""

    return _load_json("expected_outputs.json")


def _position_from_payload(payload: dict[str, Any]) -> RraoPosition:
    source_row_id = str(payload["source_row_id"])
    lineage = RraoSourceLineage(
        source_system="synthetic-rrao-sample-book",
        source_file="positions.json",
        source_row_id=source_row_id,
        source_column_map=(
            ("evidence_type", "evidence_type"),
            ("gross_effective_notional", "gross_effective_notional"),
        ),
    )
    return RraoPosition(
        position_id=str(payload["position_id"]),
        source_row_id=source_row_id,
        desk_id=str(payload["desk_id"]),
        legal_entity=str(payload["legal_entity"]),
        gross_effective_notional=float(payload["gross_effective_notional"]),
        currency=str(payload["currency"]),
        evidence_type=RraoEvidenceType(str(payload["evidence_type"])),
        evidence_label=str(payload["evidence_label"]),
        lineage=lineage,
        classification_hint=_optional_classification(payload.get("classification_hint")),
        exclusion_reason=_optional_exclusion_reason(payload.get("exclusion_reason")),
        exclusion_evidence_id=_optional_text(payload.get("exclusion_evidence_id")),
        back_to_back_match=_optional_btb_match(payload.get("back_to_back_match")),
        supervisor_directive_id=_optional_text(payload.get("supervisor_directive_id")),
        underlying_count=_optional_int(payload.get("underlying_count")),
        is_path_dependent=_optional_bool(payload.get("is_path_dependent")),
        is_ctp_hedge=bool(payload.get("is_ctp_hedge", False)),
        is_investment_fund_exposure=bool(payload.get("is_investment_fund_exposure", False)),
        investment_fund_descriptor=_optional_fund_descriptor(
            payload.get("investment_fund_descriptor")
        ),
        citations=tuple(str(c) for c in payload.get("citations", [])),
    )


def _optional_classification(value: object) -> RraoClassification | None:
    return RraoClassification(str(value)) if value is not None else None


def _optional_exclusion_reason(value: object) -> RraoExclusionReason | None:
    return RraoExclusionReason(str(value)) if value is not None else None


def _optional_btb_match(value: object) -> RraoBackToBackMatch | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError(f"expected back-to-back match object, got {value!r}")
    return RraoBackToBackMatch(
        match_group_id=str(value["match_group_id"]),
        matched_position_id=str(value["matched_position_id"]),
    )


def _optional_fund_descriptor(value: object) -> RraoInvestmentFundDescriptor | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError(f"expected investment fund descriptor object, got {value!r}")
    return RraoInvestmentFundDescriptor(
        fund_id=str(value["fund_id"]),
        section_205_method=RraoInvestmentFundMethod(str(value["section_205_method"])),
        included_exposure_type=RraoInvestmentFundExposureType(
            str(value["included_exposure_type"])
        ),
        mandate_evidence_id=str(value["mandate_evidence_id"]),
        section_205_evidence_id=str(value["section_205_evidence_id"]),
        fund_gross_effective_notional=float(value["fund_gross_effective_notional"]),
        included_exposure_ratio=float(value["included_exposure_ratio"]),
        look_through_available=bool(value["look_through_available"]),
        mandate_allows_rrao_exposures=bool(value["mandate_allows_rrao_exposures"]),
    )


def _optional_text(value: object) -> str | None:
    return str(value) if value is not None else None


def _optional_int(value: object) -> int | None:
    return int(value) if value is not None else None


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise TypeError(f"expected bool, got {value!r}")
    return value


def _load_json(filename: str) -> Any:
    return json.loads((_FIXTURE_DIR / filename).read_text(encoding="utf-8"))


__all__ = [
    "COMMON_POSITION_IDS",
    "PROFILE_BASEL",
    "PROFILE_US_NPR",
    "US_NPR_ONLY_POSITION_IDS",
    "load_context",
    "load_expected_outputs",
    "load_positions",
]
