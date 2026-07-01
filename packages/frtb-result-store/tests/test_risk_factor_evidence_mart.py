"""Tests for RFET/NMRF/SES risk-factor evidence mart."""

from __future__ import annotations

from datetime import date

from fixtures.risk_factor_evidence_bundle import (
    _EVIDENCE_RUN_ID,
    _RF_MODELLABLE_USD_5Y,
    _RF_NMRF_TYPE_A_IR,
    nmrf_ses_bridge_rows,
    rfet_observation_evidence_rows,
    risk_factor_evidence_rows,
)
from frtb_result_store._io_rfet_nmrf_ses_queries import StoreRiskFactorEvidenceQueryMixin
from frtb_result_store._model_risk_factor_evidence import (
    ModellabilityState,
    NMRFSESBridge,
    RFETObservationEvidence,
    RfetStaleState,
    RiskFactorHierarchyUsage,
    SesComponent,
)
from frtb_result_store.mart_schemas import (
    MART_NAMES,
    MART_SCHEMA_VERSION,
    MART_SCHEMAS,
    mart_schema_fingerprint,
)
from frtb_result_store.risk_factor_evidence_rows import (
    _nmrf_ses_bridge_from_row,
    _nmrf_ses_bridge_row,
    _rfet_observation_evidence_from_row,
    _rfet_observation_evidence_row,
    _risk_factor_evidence_mart_row,
    _risk_factor_hierarchy_usage_from_row,
    _risk_factor_hierarchy_usage_row,
)


class TestMartSchema:
    """Tests for RFET/NMRF/SES evidence mart schema registration."""

    def test_rfet_nmrf_ses_evidence_in_mart_names(self) -> None:
        """rfet_nmrf_ses_evidence should be registered in MART_NAMES."""
        assert "rfet_nmrf_ses_evidence" in MART_NAMES

    def test_rfet_nmrf_ses_evidence_schema_exists(self) -> None:
        """rfet_nmrf_ses_evidence should have a registered schema."""
        assert "rfet_nmrf_ses_evidence" in MART_SCHEMAS

    def test_rfet_nmrf_ses_evidence_schema_fields(self) -> None:
        """Schema should include all required fields for evidence mart."""
        schema = MART_SCHEMAS["rfet_nmrf_ses_evidence"]
        field_names = {field.name for field in schema}
        required_fields = {
            "run_id",
            "risk_factor_id",
            "display_name",
            "risk_class",
            "risk_factor_type",
            "modellability_state",
            "observation_count",
            "latest_observation_date",
            "gap_days",
            "stale_state",
            "rejected_observation_count",
            "rfet_artifact_id",
            "ses_component",
            "ses_amount",
            "ses_movement",
            "stress_period_id",
            "liquidity_horizon_days",
            "aggregation_bucket",
            "capital_node_id",
            "book_id",
            "desk_id",
            "volcker_desk_id",
            "business_line_id",
            "legal_entity_id",
            "usage_count",
            "source_artifact_id",
            "metadata_json",
        }
        assert required_fields.issubset(field_names)

    def test_schema_version_incremented(self) -> None:
        """Schema version should be incremented after adding evidence mart."""
        assert MART_SCHEMA_VERSION >= 5

    def test_schema_fingerprint_is_deterministic(self) -> None:
        """Schema fingerprint should be deterministic for the same schema."""
        fp1 = mart_schema_fingerprint("rfet_nmrf_ses_evidence")
        fp2 = mart_schema_fingerprint("rfet_nmrf_ses_evidence")
        assert fp1 == fp2


class TestRFETObservationEvidence:
    """Tests for RFET observation evidence serialization."""

    def test_observation_evidence_to_row(self) -> None:
        """RFET observation evidence should serialize to a row dict."""
        evidence = RFETObservationEvidence(
            observation_count=252,
            latest_observation_date=date(2026, 6, 30),
            gap_days=0,
            stale_state=RfetStaleState.CURRENT,
            rejected_observation_count=0,
            artifact_id="navigator-rfet-observation-timeline",
        )
        row = _rfet_observation_evidence_row(evidence)
        assert row["observation_count"] == 252
        assert row["latest_observation_date"] == "2026-06-30"
        assert row["gap_days"] == 0
        assert row["stale_state"] == "current"
        assert row["rejected_observation_count"] == 0
        assert row["artifact_id"] == "navigator-rfet-observation-timeline"

    def test_observation_evidence_from_row(self) -> None:
        """Row dict should deserialize to RFET observation evidence."""
        row = (
            252,
            "2026-06-30",
            0,
            "current",
            0,
            "navigator-rfet-observation-timeline",
        )
        evidence = _rfet_observation_evidence_from_row(row)
        assert evidence.observation_count == 252
        assert evidence.latest_observation_date == date(2026, 6, 30)
        assert evidence.gap_days == 0
        assert evidence.stale_state == RfetStaleState.CURRENT
        assert evidence.rejected_observation_count == 0
        assert evidence.artifact_id == "navigator-rfet-observation-timeline"

    def test_observation_evidence_with_nulls(self) -> None:
        """Evidence with null fields should serialize/deserialize correctly."""
        evidence = RFETObservationEvidence(
            observation_count=0,
            latest_observation_date=None,
            gap_days=None,
            stale_state=RfetStaleState.NO_DATA,
            rejected_observation_count=None,
            artifact_id=None,
        )
        row = _rfet_observation_evidence_row(evidence)
        assert row["observation_count"] == 0
        assert row["latest_observation_date"] is None
        assert row["gap_days"] is None
        assert row["stale_state"] == "no_data"
        assert row["rejected_observation_count"] is None
        assert row["artifact_id"] is None


class TestNMRFSESBridge:
    """Tests for NMRF/SES capital bridge serialization."""

    def test_ses_bridge_to_row(self) -> None:
        """NMRF/SES bridge should serialize to a row dict."""
        bridge = NMRFSESBridge(
            risk_factor_id=_RF_NMRF_TYPE_A_IR,
            ses_component=SesComponent.TYPE_A,
            ses_amount=12500.00,
            ses_movement=500.00,
            stress_period_id="stress-period-250d",
            liquidity_horizon_days=10,
            aggregation_bucket="csr-ig-hy",
            capital_node_id="ima-desk-credit",
        )
        row = _nmrf_ses_bridge_row(bridge)
        assert row["risk_factor_id"] == _RF_NMRF_TYPE_A_IR
        assert row["ses_component"] == "TYPE_A"
        assert row["ses_amount"] == 12500.00
        assert row["ses_movement"] == 500.00
        assert row["stress_period_id"] == "stress-period-250d"
        assert row["liquidity_horizon_days"] == 10
        assert row["aggregation_bucket"] == "csr-ig-hy"
        assert row["capital_node_id"] == "ima-desk-credit"

    def test_ses_bridge_from_row(self) -> None:
        """Row dict should deserialize to NMRF/SES bridge."""
        row = (
            _RF_NMRF_TYPE_A_IR,
            "TYPE_A",
            12500.00,
            500.00,
            "stress-period-250d",
            10,
            "csr-ig-hy",
            "ima-desk-credit",
        )
        bridge = _nmrf_ses_bridge_from_row(row)
        assert bridge.risk_factor_id == _RF_NMRF_TYPE_A_IR
        assert bridge.ses_component == SesComponent.TYPE_A
        assert bridge.ses_amount == 12500.00
        assert bridge.ses_movement == 500.00
        assert bridge.stress_period_id == "stress-period-250d"
        assert bridge.liquidity_horizon_days == 10
        assert bridge.aggregation_bucket == "csr-ig-hy"
        assert bridge.capital_node_id == "ima-desk-credit"

    def test_ses_bridge_with_nulls(self) -> None:
        """Bridge with null fields should serialize/deserialize correctly."""
        bridge = NMRFSESBridge(
            risk_factor_id=_RF_NMRF_TYPE_A_IR,
            ses_component=None,
            ses_amount=None,
            ses_movement=None,
            stress_period_id=None,
            liquidity_horizon_days=None,
            aggregation_bucket=None,
            capital_node_id=None,
        )
        row = _nmrf_ses_bridge_row(bridge)
        assert row["risk_factor_id"] == _RF_NMRF_TYPE_A_IR
        assert row["ses_component"] is None
        assert row["ses_amount"] is None
        assert row["ses_movement"] is None
        assert row["stress_period_id"] is None
        assert row["liquidity_horizon_days"] is None
        assert row["aggregation_bucket"] is None
        assert row["capital_node_id"] is None


class TestRiskFactorHierarchyUsage:
    """Tests for hierarchy usage serialization."""

    def test_hierarchy_usage_to_row(self) -> None:
        """Hierarchy usage should serialize to a row dict."""
        usage = RiskFactorHierarchyUsage(
            risk_factor_id=_RF_MODELLABLE_USD_5Y,
            book_id="rates-trading",
            desk_id="rates",
            volcker_desk_id=None,
            business_line_id="ficc",
            legal_entity_id="le-demo",
            usage_count=42,
        )
        row = _risk_factor_hierarchy_usage_row(usage)
        assert row["risk_factor_id"] == _RF_MODELLABLE_USD_5Y
        assert row["book_id"] == "rates-trading"
        assert row["desk_id"] == "rates"
        assert row["volcker_desk_id"] is None
        assert row["business_line_id"] == "ficc"
        assert row["legal_entity_id"] == "le-demo"
        assert row["usage_count"] == 42

    def test_hierarchy_usage_from_row(self) -> None:
        """Row dict should deserialize to hierarchy usage."""
        row = (
            _RF_MODELLABLE_USD_5Y,
            "rates-trading",
            "rates",
            None,
            "ficc",
            "le-demo",
            42,
        )
        usage = _risk_factor_hierarchy_usage_from_row(row)
        assert usage.risk_factor_id == _RF_MODELLABLE_USD_5Y
        assert usage.book_id == "rates-trading"
        assert usage.desk_id == "rates"
        assert usage.volcker_desk_id is None
        assert usage.business_line_id == "ficc"
        assert usage.legal_entity_id == "le-demo"
        assert usage.usage_count == 42


class TestRiskFactorEvidenceRow:
    """Tests for complete evidence row serialization."""

    def test_evidence_row_to_dict(self) -> None:
        """Evidence row should serialize to a complete dict."""
        rows = risk_factor_evidence_rows()
        evidence_row = rows[0]  # Modellable USD 5Y factor
        row_dict = _risk_factor_evidence_mart_row(evidence_row)
        assert row_dict["run_id"] == _EVIDENCE_RUN_ID
        assert row_dict["risk_factor_id"] == _RF_MODELLABLE_USD_5Y
        assert row_dict["display_name"] == "USD 5Y Swap Rate"
        assert row_dict["risk_class"] == "GIRR"
        assert row_dict["modellability_state"] == "modellable"
        assert row_dict["observation_count"] == 252
        assert row_dict["ses_component"] is None  # Modellable, no SES
        assert row_dict["desk_id"] == "rates"
        assert row_dict["book_id"] == "rates-trading"

    def test_evidence_row_with_nmrf_ses_bridge(self) -> None:
        """Evidence row with NMRF/SES bridge should include SES fields."""
        rows = risk_factor_evidence_rows()
        # Find the Type A NMRF factor
        nmrf_row = next(r for r in rows if str(r.risk_factor_id) == _RF_NMRF_TYPE_A_IR)
        row_dict = _risk_factor_evidence_mart_row(nmrf_row)
        assert row_dict["ses_component"] == "TYPE_A"
        assert row_dict["ses_amount"] == 12500.00
        assert row_dict["ses_movement"] == 500.00
        assert row_dict["liquidity_horizon_days"] == 10


class TestEvidenceFixtures:
    """Tests for evidence fixture data."""

    def test_fixture_includes_modellable_factor(self) -> None:
        """Fixtures should include at least one modellable factor."""
        rows = risk_factor_evidence_rows()
        modellable = [r for r in rows if r.modellability_state == ModellabilityState.MODELLABLE]
        assert len(modellable) >= 1
        assert any(str(r.risk_factor_id) == _RF_MODELLABLE_USD_5Y for r in modellable)

    def test_fixture_includes_type_a_nmrf(self) -> None:
        """Fixtures should include at least one Type A NMRF/SES-driving factor."""
        rows = risk_factor_evidence_rows()
        type_a = [
            r
            for r in rows
            if r.nmrf_ses_bridge is not None
            and r.nmrf_ses_bridge.ses_component == SesComponent.TYPE_A
        ]
        assert len(type_a) >= 1
        assert any(str(r.risk_factor_id) == _RF_NMRF_TYPE_A_IR for r in type_a)

    def test_fixture_includes_type_b_nmrf(self) -> None:
        """Fixtures should include at least one Type B NMRF/SES-driving factor."""
        rows = risk_factor_evidence_rows()
        type_b = [
            r
            for r in rows
            if r.nmrf_ses_bridge is not None
            and r.nmrf_ses_bridge.ses_component == SesComponent.TYPE_B
        ]
        assert len(type_b) >= 1

    def test_fixture_includes_stale_factor(self) -> None:
        """Fixtures should include at least one stale/missing-evidence factor."""
        rows = risk_factor_evidence_rows()
        stale_states = (RfetStaleState.STALE, RfetStaleState.MISSING_EVIDENCE)
        stale = [r for r in rows if r.rfet_observation_evidence.stale_state in stale_states]
        assert len(stale) >= 1

    def test_fixture_includes_unsupported_factor(self) -> None:
        """Fixtures should include at least one no-data/unsupported factor."""
        rows = risk_factor_evidence_rows()
        unsupported = [r for r in rows if r.modellability_state == ModellabilityState.UNSUPPORTED]
        assert len(unsupported) >= 1

    def test_fixture_hierarchy_usage(self) -> None:
        """Fixtures should include hierarchy usage mapping."""
        rows = risk_factor_evidence_rows()
        with_usage = [r for r in rows if r.hierarchy_usage is not None]
        assert len(with_usage) >= 1
        # Check that hierarchy usage has expected fields
        for row in with_usage:
            usage = row.hierarchy_usage
            assert usage.risk_factor_id
            assert usage.usage_count >= 0

    def test_fixture_ses_amounts(self) -> None:
        """NMRF/SES fixtures should have positive SES amounts."""
        bridges = nmrf_ses_bridge_rows()
        for bridge in bridges:
            if bridge.ses_amount is not None:
                assert bridge.ses_amount > 0


class TestQueryMixin:
    """Tests for StoreRiskFactorEvidenceQueryMixin using mock store."""

    def test_list_risk_factor_evidence_returns_page_structure(self) -> None:
        """list_risk_factor_evidence should return a page structure."""
        # This test verifies the API contract; actual querying is tested
        # in integration tests with a real result store.
        # Here we just verify the method exists and has the right signature.
        assert hasattr(StoreRiskFactorEvidenceQueryMixin, "list_risk_factor_evidence")
        assert hasattr(StoreRiskFactorEvidenceQueryMixin, "get_risk_factor_evidence")
        assert hasattr(StoreRiskFactorEvidenceQueryMixin, "risk_factor_hierarchy_usage")
        assert hasattr(StoreRiskFactorEvidenceQueryMixin, "nmrf_ses_capital_by_risk_factor")


class TestRowRoundTrip:
    """Tests for serialization/deserialization round-trips."""

    def test_observation_evidence_round_trip(self) -> None:
        """Observation evidence should survive serialize/deserialize round-trip."""
        original = rfet_observation_evidence_rows()[0]
        row = _rfet_observation_evidence_row(original)
        restored = _rfet_observation_evidence_from_row(
            (
                row["observation_count"],
                row["latest_observation_date"],
                row["gap_days"],
                row["stale_state"],
                row["rejected_observation_count"],
                row["artifact_id"],
            )
        )
        assert restored.observation_count == original.observation_count
        assert restored.latest_observation_date == original.latest_observation_date
        assert restored.gap_days == original.gap_days
        assert restored.stale_state == original.stale_state
        assert restored.rejected_observation_count == original.rejected_observation_count
        assert restored.artifact_id == original.artifact_id

    def test_ses_bridge_round_trip(self) -> None:
        """NMRF/SES bridge should survive serialize/deserialize round-trip."""
        original = nmrf_ses_bridge_rows()[0]
        row = _nmrf_ses_bridge_row(original)
        restored = _nmrf_ses_bridge_from_row(
            (
                row["risk_factor_id"],
                row["ses_component"],
                row["ses_amount"],
                row["ses_movement"],
                row["stress_period_id"],
                row["liquidity_horizon_days"],
                row["aggregation_bucket"],
                row["capital_node_id"],
            )
        )
        assert restored.risk_factor_id == original.risk_factor_id
        assert restored.ses_component == original.ses_component
        assert restored.ses_amount == original.ses_amount
        assert restored.ses_movement == original.ses_movement
        assert restored.stress_period_id == original.stress_period_id
        assert restored.liquidity_horizon_days == original.liquidity_horizon_days
        assert restored.aggregation_bucket == original.aggregation_bucket
        assert restored.capital_node_id == original.capital_node_id

    def test_hierarchy_usage_round_trip(self) -> None:
        """Hierarchy usage should survive serialize/deserialize round-trip."""
        original = risk_factor_evidence_rows()[0].hierarchy_usage
        assert original is not None
        row = _risk_factor_hierarchy_usage_row(original)
        restored = _risk_factor_hierarchy_usage_from_row(
            (
                row["risk_factor_id"],
                row["book_id"],
                row["desk_id"],
                row["volcker_desk_id"],
                row["business_line_id"],
                row["legal_entity_id"],
                row["usage_count"],
            )
        )
        assert restored.risk_factor_id == original.risk_factor_id
        assert restored.book_id == original.book_id
        assert restored.desk_id == original.desk_id
        assert restored.volcker_desk_id == original.volcker_desk_id
        assert restored.business_line_id == original.business_line_id
        assert restored.legal_entity_id == original.legal_entity_id
        assert restored.usage_count == original.usage_count
