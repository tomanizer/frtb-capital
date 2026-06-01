"""Tests for IMA Arrow-backed metadata and RFET handoffs."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pyarrow as pa
import pytest
from frtb_common import normalized_handoff_hash, source_content_hash

from frtb_ima import (
    BusinessCalendar,
    LiquidityHorizon,
    RegulatoryRegime,
    RFETEvidence,
    RFETNewIssuanceEvidence,
    RFETRepresentativenessEvidence,
    RiskClass,
    RiskFactorBucket,
    RiskFactorDefinition,
    ScenarioSetType,
    assess_rfet_evidence,
    assess_rfet_observation_batch,
    build_rfet_observation_batch_from_handoff,
    build_scenario_metadata_batch_from_handoff,
    get_policy,
    input_hash_for_rfet_observation_batch,
    input_hash_for_scenario_metadata_batch,
    normalize_ima_rfet_observation_arrow_table,
    normalize_ima_scenario_metadata_arrow_table,
)

AS_OF = date(2025, 6, 30)


def test_scenario_metadata_arrow_handoff_builds_columnar_batch_with_lineage() -> None:
    source_hash = source_content_hash("ima scenario metadata")
    table = pa.table(
        {
            "scenario_id": ["stress-00001", "stress-00002"],
            "scenario_date": [date(2025, 1, 2), date(2025, 1, 3)],
            "set_type": pa.chunked_array(
                [
                    pa.array(
                        ["STRESS"],
                        type=pa.dictionary(pa.int8(), pa.string()),
                    ),
                    pa.array(
                        ["STRESS"],
                        type=pa.dictionary(pa.int8(), pa.string()),
                    ),
                ]
            ),
            "calibrationWindow": ["2008-2009", "2008-2009"],
            "source": ["risk-engine", "risk-engine"],
            "provenanceJson": [
                json.dumps({"window": "global-financial-crisis"}),
                json.dumps({"window": "global-financial-crisis"}),
            ],
            "sourceRowId": ["scenario-row-1", "scenario-row-2"],
        }
    )

    handoff = normalize_ima_scenario_metadata_arrow_table(
        table,
        metadata={"desk": "Rates"},
        source_hash=source_hash,
    )
    batch = build_scenario_metadata_batch_from_handoff(handoff)
    metadata = batch.to_metadata()

    assert handoff.accepted.column_names == [
        "scenario_id",
        "scenario_date",
        "scenario_set",
        "calibration_window",
        "source",
        "provenance_json",
        "source_row_id",
    ]
    assert batch.scenario_count == 2
    assert batch.source_hash == source_hash
    assert batch.handoff_hash == normalized_handoff_hash(handoff)
    assert batch.input_hash == input_hash_for_scenario_metadata_batch(batch)
    assert not batch.scenario_ids.flags.writeable
    assert metadata[0].scenario_id == "stress-00001"
    assert metadata[0].scenario_set is ScenarioSetType.STRESS
    assert metadata[0].provenance == {"window": "global-financial-crisis"}


def test_scenario_metadata_arrow_handoff_defaults_optional_columns() -> None:
    handoff = normalize_ima_scenario_metadata_arrow_table(
        pa.table(
            {
                "scenarioId": ["scenario-00000"],
                "scenarioDate": [AS_OF],
            }
        )
    )

    batch = build_scenario_metadata_batch_from_handoff(handoff)
    metadata = batch.to_metadata()

    assert batch.scenario_sets.tolist() == [ScenarioSetType.CURRENT.value]
    assert batch.calibration_windows.tolist() == [""]
    assert metadata[0].source == ""
    assert metadata[0].provenance == {}


def test_scenario_metadata_arrow_handoff_rejects_invalid_provenance_json() -> None:
    handoff = normalize_ima_scenario_metadata_arrow_table(
        pa.table(
            {
                "scenarioId": ["scenario-00000"],
                "scenarioDate": [AS_OF],
                "provenanceJson": ["["],
            }
        )
    )

    with pytest.raises(ValueError, match="provenance_json contains invalid JSON"):
        build_scenario_metadata_batch_from_handoff(handoff)


def test_rfet_observation_arrow_handoff_assesses_without_row_materialization() -> None:
    risk_factor = _risk_factor()
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    handoff = normalize_ima_rfet_observation_arrow_table(
        _rfet_observation_table(),
        source_hash=source_content_hash("ima rfet observations"),
    )
    batch = build_rfet_observation_batch_from_handoff(handoff)

    batch_result = assess_rfet_observation_batch(
        risk_factor,
        batch,
        policy,
        as_of_date=AS_OF,
        qualitative_pass=True,
        bucket_id="USD_RATES",
    )
    row_result = assess_rfet_evidence(
        risk_factor,
        RFETEvidence(
            risk_factor_name=risk_factor.name,
            as_of_date=AS_OF,
            observations=batch.to_observations(),
            qualitative_pass=True,
            bucket_id="USD_RATES",
        ),
        policy,
    )

    assert batch.observation_count == 25
    assert batch.source_hash == handoff.source_hash
    assert batch.handoff_hash == normalized_handoff_hash(handoff)
    assert batch.input_hash == input_hash_for_rfet_observation_batch(batch)
    assert batch_result.as_dict() == row_result.as_dict()


def test_rfet_observation_arrow_handoff_normalizes_nulls_and_scalar_fallbacks() -> None:
    handoff = normalize_ima_rfet_observation_arrow_table(
        pa.table(
            {
                "riskFactorName": ["USD_SWAP_5Y"],
                "observationDate": [AS_OF.isoformat()],
                "source": pa.array([None], type=pa.string()),
                "vendorId": pa.array(
                    [None],
                    type=pa.dictionary(pa.int8(), pa.string()),
                ),
                "observationTimestamp": ["2025-06-30T09:30:00+00:00"],
                "verifiable": pa.array([None], type=pa.int8()),
            }
        )
    )

    batch = build_rfet_observation_batch_from_handoff(handoff)
    observation = batch.to_observations()[0]

    assert batch.sources.tolist() == [""]
    assert batch.vendor_ids.tolist() == [""]
    assert batch.verifiable.tolist() == [True]
    assert observation.observation_timestamp == datetime(2025, 6, 30, 9, 30, tzinfo=UTC)


def test_rfet_observation_arrow_handoff_defaults_optional_columns() -> None:
    handoff = normalize_ima_rfet_observation_arrow_table(
        pa.table(
            {
                "riskFactorName": ["USD_SWAP_5Y"],
                "observationDate": [AS_OF],
            }
        )
    )

    batch = build_rfet_observation_batch_from_handoff(handoff)

    assert batch.sources.tolist() == [""]
    assert batch.vendor_ids.tolist() == [""]
    assert batch.verifiable.tolist() == [True]
    assert batch.observation_timestamps.astype("datetime64[us]").astype(str).tolist() == ["NaT"]


def test_arrow_handoff_batch_builders_reject_wrong_handoff_type() -> None:
    with pytest.raises(ValueError, match="NormalizedTabularHandoff"):
        build_scenario_metadata_batch_from_handoff(object())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="NormalizedTabularHandoff"):
        build_rfet_observation_batch_from_handoff(object())  # type: ignore[arg-type]


def test_rfet_observation_batch_rejects_empty_risk_factor_names() -> None:
    handoff = normalize_ima_rfet_observation_arrow_table(
        pa.table(
            {
                "riskFactorName": [""],
                "observationDate": [AS_OF],
            }
        )
    )

    with pytest.raises(ValueError, match="risk_factor_names"):
        build_rfet_observation_batch_from_handoff(handoff)


def test_rfet_observation_batch_rejects_empty_batches() -> None:
    handoff = normalize_ima_rfet_observation_arrow_table(
        pa.table(
            {
                "riskFactorName": pa.array([], type=pa.string()),
                "observationDate": pa.array([], type=pa.date32()),
            }
        )
    )

    with pytest.raises(ValueError, match="must be non-empty"):
        build_rfet_observation_batch_from_handoff(handoff)


def test_rfet_observation_batch_matches_row_path_for_exclusion_branches() -> None:
    risk_factor = _risk_factor()
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    handoff = normalize_ima_rfet_observation_arrow_table(_rfet_exclusion_table())
    batch = build_rfet_observation_batch_from_handoff(handoff)

    batch_result = assess_rfet_observation_batch(
        risk_factor,
        batch,
        policy,
        as_of_date=AS_OF,
        qualitative_pass=True,
        bucket_id="USD_RATES",
    )
    row_result = assess_rfet_evidence(
        risk_factor,
        RFETEvidence(
            risk_factor_name=risk_factor.name,
            as_of_date=AS_OF,
            observations=batch.to_observations(),
            qualitative_pass=True,
            bucket_id="USD_RATES",
        ),
        policy,
    )

    assert batch_result.as_dict() == row_result.as_dict()


def test_rfet_observation_batch_matches_row_path_for_calendar_and_new_issuance() -> None:
    risk_factor = _risk_factor()
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    holiday = date(2024, 12, 25)
    calendar = BusinessCalendar(
        business_dates=_weekdays(date(2024, 7, 1), AS_OF, holidays={holiday}),
        official_holidays=(holiday,),
        source="FED",
        version="2026.1",
    )
    new_issuance = RFETNewIssuanceEvidence(
        issue_date=date(2025, 6, 1),
        prorating_approved=True,
        policy_citation="internal-policy-rfet-new-issuance",
    )
    handoff = normalize_ima_rfet_observation_arrow_table(
        pa.table(
            {
                "riskFactorName": ["USD_SWAP_5Y", "USD_SWAP_5Y", "USD_SWAP_5Y"],
                "observationDate": [holiday, date(2025, 1, 4), AS_OF],
                "source": ["VENDOR_A", "VENDOR_A", "VENDOR_A"],
            }
        )
    )
    batch = build_rfet_observation_batch_from_handoff(handoff)

    batch_result = assess_rfet_observation_batch(
        risk_factor,
        batch,
        policy,
        as_of_date=AS_OF,
        qualitative_pass=True,
        bucket_id="USD_RATES",
        calendar=calendar,
        new_issuance=new_issuance,
    )
    row_result = assess_rfet_evidence(
        risk_factor,
        RFETEvidence(
            risk_factor_name=risk_factor.name,
            as_of_date=AS_OF,
            observations=batch.to_observations(),
            qualitative_pass=True,
            bucket_id="USD_RATES",
            new_issuance=new_issuance,
        ),
        policy,
        calendar=calendar,
    )

    assert batch_result.as_dict() == row_result.as_dict()


def test_rfet_observation_batch_matches_row_path_for_representativeness_evidence() -> None:
    risk_factor = _risk_factor()
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    representativeness = (
        RFETRepresentativenessEvidence(
            bucket_id="USD_RATES",
            methodology="curve-node-proximity",
            passed=False,
            rationale="Observed tenors do not represent the 5Y node.",
        ),
    )
    handoff = normalize_ima_rfet_observation_arrow_table(
        pa.table(
            {
                "riskFactorName": ["USD_SWAP_5Y"],
                "observationDate": [AS_OF],
                "source": ["VENDOR_A"],
            }
        )
    )
    batch = build_rfet_observation_batch_from_handoff(handoff)

    batch_result = assess_rfet_observation_batch(
        risk_factor,
        batch,
        policy,
        as_of_date=AS_OF,
        qualitative_pass=True,
        bucket_id="USD_RATES",
        representativeness=representativeness,
    )
    row_result = assess_rfet_evidence(
        risk_factor,
        RFETEvidence(
            risk_factor_name=risk_factor.name,
            as_of_date=AS_OF,
            observations=batch.to_observations(),
            qualitative_pass=True,
            bucket_id="USD_RATES",
            representativeness=representativeness,
        ),
        policy,
    )

    assert batch_result.as_dict() == row_result.as_dict()


def _risk_factor() -> RiskFactorDefinition:
    bucket = RiskFactorBucket(
        bucket_id="USD_RATES",
        risk_class=RiskClass.GIRR,
        liquidity_horizon=LiquidityHorizon.LH10,
    )
    return RiskFactorDefinition(
        name="USD_SWAP_5Y",
        risk_class=RiskClass.GIRR,
        liquidity_horizon=LiquidityHorizon.LH10,
        bucket=bucket,
    )


def _rfet_observation_table() -> pa.Table:
    observation_dates = [AS_OF - timedelta(days=index * 10) for index in range(24)]
    observation_dates.append(AS_OF - timedelta(days=10))
    sources = ["VENDOR_A"] * 24 + ["VENDOR_B"]
    return pa.table(
        {
            "riskFactorName": ["USD_SWAP_5Y"] * len(observation_dates),
            "observationDate": observation_dates,
            "source": pa.chunked_array(
                [
                    pa.array(
                        sources[:12],
                        type=pa.dictionary(pa.int8(), pa.string()),
                    ),
                    pa.array(
                        sources[12:],
                        type=pa.dictionary(pa.int8(), pa.string()),
                    ),
                ]
            ),
            "sourceRowId": [f"rfet-row-{index:03d}" for index in range(len(observation_dates))],
        }
    )


def _rfet_exclusion_table() -> pa.Table:
    rows = [
        {
            "observation_date": AS_OF - timedelta(days=1),
            "source": "TRADE_STORE",
            "vendor_id": "INTERNAL",
            "venue": "SEF_A",
            "feed": "EXECUTIONS",
            "observation_timestamp": None,
            "date_normalization_evidence": "",
            "verifiable": True,
            "vendor_audit_evidence_id": "internal-lineage-control-2026",
        },
        {
            "observation_date": AS_OF - timedelta(days=1),
            "source": "TRADE_STORE",
            "vendor_id": "INTERNAL",
            "venue": "SEF_A",
            "feed": "EXECUTIONS",
            "observation_timestamp": None,
            "date_normalization_evidence": "",
            "verifiable": True,
            "vendor_audit_evidence_id": "internal-lineage-control-2026",
        },
        {
            "observation_date": AS_OF + timedelta(days=1),
            "source": "VENDOR_A",
            "vendor_id": "",
            "venue": "",
            "feed": "",
            "observation_timestamp": None,
            "date_normalization_evidence": "",
            "verifiable": True,
            "vendor_audit_evidence_id": "",
        },
        {
            "observation_date": AS_OF - timedelta(days=400),
            "source": "VENDOR_A",
            "vendor_id": "",
            "venue": "",
            "feed": "",
            "observation_timestamp": None,
            "date_normalization_evidence": "",
            "verifiable": True,
            "vendor_audit_evidence_id": "",
        },
        {
            "observation_date": AS_OF - timedelta(days=2),
            "source": "",
            "vendor_id": "",
            "venue": "",
            "feed": "",
            "observation_timestamp": None,
            "date_normalization_evidence": "",
            "verifiable": True,
            "vendor_audit_evidence_id": "",
        },
        {
            "observation_date": AS_OF - timedelta(days=3),
            "source": "VENDOR_A",
            "vendor_id": "",
            "venue": "",
            "feed": "",
            "observation_timestamp": None,
            "date_normalization_evidence": "",
            "verifiable": False,
            "vendor_audit_evidence_id": "",
        },
        {
            "observation_date": AS_OF - timedelta(days=4),
            "source": "VENDOR_A",
            "vendor_id": "",
            "venue": "",
            "feed": "",
            "observation_timestamp": datetime(2025, 6, 25, 23, 0, tzinfo=UTC),
            "date_normalization_evidence": "",
            "verifiable": True,
            "vendor_audit_evidence_id": "",
        },
        {
            "observation_date": AS_OF - timedelta(days=5),
            "source": "VENDOR_A",
            "vendor_id": "VENDOR_A",
            "venue": "SEF_A",
            "feed": "COMPOSITE",
            "observation_timestamp": None,
            "date_normalization_evidence": "",
            "verifiable": True,
            "vendor_audit_evidence_id": "",
        },
    ]
    return pa.table(
        {
            "riskFactorName": ["USD_SWAP_5Y"] * len(rows),
            "observationDate": [row["observation_date"] for row in rows],
            "source": [row["source"] for row in rows],
            "vendorId": [row["vendor_id"] for row in rows],
            "venue": [row["venue"] for row in rows],
            "feed": [row["feed"] for row in rows],
            "observationTimestamp": pa.array(
                [row["observation_timestamp"] for row in rows],
                type=pa.timestamp("us", tz="UTC"),
            ),
            "dateNormalizationEvidence": [row["date_normalization_evidence"] for row in rows],
            "verifiable": [row["verifiable"] for row in rows],
            "vendorAuditEvidenceId": [row["vendor_audit_evidence_id"] for row in rows],
        }
    )


def _weekdays(start: date, end: date, *, holidays: set[date]) -> tuple[date, ...]:
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5 and current not in holidays:
            days.append(current)
        current += timedelta(days=1)
    return tuple(days)
