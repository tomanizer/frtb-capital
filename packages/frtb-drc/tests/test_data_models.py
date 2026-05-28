"""
Unit tests for frtb_drc data_models and reference_data (Issue #25).

Deterministic. No random seeds. Tests against regulatory table values.
"""

from __future__ import annotations

import pytest

from frtb_drc.data_models import (
    CreditQuality,
    Position,
    RulesVersion,
    Seniority,
)
from frtb_drc.reference_data import (
    get_lgd,
    get_risk_weight,
    load_reference_data,
)


class TestPosition:
    def test_valid_position_roundtrip(self) -> None:
        pos = Position(
            issuer_id="ACME_CORP",
            bucket="CORPORATES",
            seniority=Seniority.SENIOR,
            credit_quality=CreditQuality.BBB,
            long_jtd=1_000_000.0,
            short_jtd=250_000.0,
            source_row_id="CRIF-ROW-42",
        )
        d = pos.as_dict()
        assert d["issuer_id"] == "ACME_CORP"
        assert d["seniority"] == "SENIOR"
        assert d["credit_quality"] == "BBB"
        assert d["long_jtd"] == 1_000_000.0

    def test_rejects_negative_jtd(self) -> None:
        with pytest.raises(ValueError, match="JTD amounts must be non-negative"):
            Position(
                issuer_id="BAD",
                bucket="CORPORATES",
                seniority=Seniority.SENIOR,
                credit_quality=CreditQuality.BBB,
                long_jtd=-100.0,
            )

    def test_rejects_zero_exposure(self) -> None:
        with pytest.raises(ValueError, match="At least one of long_jtd or short_jtd"):
            Position(
                issuer_id="ZERO",
                bucket="CORPORATES",
                seniority=Seniority.SENIOR,
                credit_quality=CreditQuality.BBB,
                long_jtd=0.0,
                short_jtd=0.0,
            )


class TestGetRiskWeight:
    """Exact match to reference tables (drc_common.py values)."""

    def test_bcbs_unrated_default(self) -> None:
        rw = get_risk_weight("CORPORATES", CreditQuality.UNRATED.value, RulesVersion.BCBS)
        assert rw == 0.15

    def test_crr2_cqs1(self) -> None:
        rw = get_risk_weight("SOVEREIGNS", "1", RulesVersion.CRR2)
        assert rw == 0.005

    def test_frb_non_us_sovereign_ig(self) -> None:
        rw = get_risk_weight("NON_US_SOVEREIGNS", "IG", RulesVersion.FRB)
        assert rw == 0.005

    def test_frb_pse_gse_sg(self) -> None:
        rw = get_risk_weight("PSE_GSE_DEBT", "SG", RulesVersion.FRB)
        assert rw == 0.12

    def test_frb_corporate_ssg(self) -> None:
        rw = get_risk_weight("CORPORATES", "SSG", RulesVersion.FRB)
        assert rw == 0.50

    def test_frb_defaulted(self) -> None:
        rw = get_risk_weight("DEFAULTED", "DEFAULTED", RulesVersion.FRB)
        assert rw == 1.00

    def test_frb_unknown_bucket_falls_back(self) -> None:
        # Reference behaviour: unknown FRB bucket -> 0.50
        rw = get_risk_weight("MYSTERY_BUCKET", "IG", RulesVersion.FRB)
        assert rw == 0.50

    def test_unknown_rating_falls_back_to_unrated_default(self) -> None:
        # Non-FRB path returns table default (0.15) for unknown rating per reference
        rw = get_risk_weight("CORPORATES", "MYSTERY_RATING", RulesVersion.BCBS)
        assert rw == 0.15

    def test_frb_unknown_bucket_uses_conservative(self) -> None:
        rw = get_risk_weight("MYSTERY", "IG", RulesVersion.FRB)
        assert rw == 0.50


class TestReferenceDataLoader:
    def test_load_default_crr2(self) -> None:
        ref = load_reference_data(RulesVersion.CRR2)
        assert ref.rules_version == RulesVersion.CRR2
        assert "CORPORATES" in ref.buckets
        assert ref.risk_weights["1"] == 0.005

    def test_override_risk_weight(self) -> None:
        ref = load_reference_data(
            RulesVersion.FRB,
            overrides={"risk_weights": {("CORPORATES", "IG"): 0.025}},
        )
        assert ref.risk_weights[("CORPORATES", "IG")] == 0.025

    def test_lgd_senior_vs_non_senior(self) -> None:
        assert get_lgd("SENIOR") == 0.25
        assert get_lgd("NON-SENIOR") == 0.75
        assert get_lgd("EQUITY") == 0.75

    def test_lgd_override_validation(self) -> None:
        with pytest.raises(ValueError):
            get_lgd("SENIOR", override=1.5)
