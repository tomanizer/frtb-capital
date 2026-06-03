from __future__ import annotations

import inspect
from datetime import date

import numpy as np
import pyarrow as pa
import pytest
from frtb_common import UnsupportedRegulatoryFeatureError, source_content_hash
from frtb_sbm import (
    SbmCalculationContext,
    SbmPairwiseEvidenceMode,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    build_csr_nonsec_delta_batch_from_sensitivities,
    build_csr_sec_ctp_delta_batch_from_sensitivities,
    build_csr_sec_nonctp_delta_batch_from_sensitivities,
    calculate_sbm_capital,
    calculate_sbm_capital_from_csr_nonsec_delta_batch,
    calculate_sbm_capital_from_csr_sec_ctp_delta_batch,
    calculate_sbm_capital_from_csr_sec_nonctp_delta_batch,
    input_hash_for_sensitivities,
    weight_csr_sec_ctp_delta_sensitivity_batch,
)
from frtb_sbm.arrow_handoff import (
    build_csr_nonsec_delta_batch_from_arrow,
    build_csr_sec_ctp_delta_batch_from_arrow,
    build_csr_sec_nonctp_delta_batch_from_arrow,
    calculate_sbm_capital_from_csr_nonsec_delta_arrow,
    calculate_sbm_capital_from_csr_sec_ctp_delta_arrow,
    calculate_sbm_capital_from_csr_sec_nonctp_delta_arrow,
    normalize_csr_nonsec_delta_arrow_table,
    normalize_csr_sec_ctp_delta_arrow_table,
    normalize_csr_sec_nonctp_delta_arrow_table,
)
from frtb_sbm.csr_nonsec_reference_data import (
    CSR_BOND_RISK_FACTOR,
    CSR_CDS_RISK_FACTOR,
    CSR_DIFFERENT_CURVE_CORRELATION,
    CSR_NAME_CORRELATION,
    CSR_TENOR_CORRELATION,
)
from frtb_sbm.csr_sec_ctp_reference_data import (
    CSR_CTP_DIFFERENT_BASIS_CORRELATION,
    CSR_SEC_CTP_DECOMPOSITION_REQUIRED_FLAG,
)
from frtb_sbm.csr_sec_nonctp_reference_data import (
    CSR_SEC_DIFFERENT_BASIS_CORRELATION,
    CSR_SEC_OTHER_SECTOR_BUCKET,
    CSR_SEC_TENOR_DIFFERENT_CORRELATION,
    CSR_SEC_TRANCHE_DIFFERENT_CORRELATION,
)
from frtb_sbm.risk_classes.csr_nonsec import (
    calculate_csr_nonsec_delta_risk_class_capital_from_batch,
)
from frtb_sbm.risk_classes.csr_sec_ctp import (
    calculate_csr_sec_ctp_delta_risk_class_capital_from_batch,
)
from frtb_sbm.risk_classes.csr_sec_nonctp import (
    calculate_csr_sec_nonctp_delta_risk_class_capital_from_batch,
)


def sample_context(run_id: str) -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id=run_id,
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def sample_lineage(row_id: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm-csr-delta.csv",
        source_row_id=row_id,
    )


def csr_nonsec_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _sensitivity(
            sensitivity_id="csr-ns-bond-a-1y",
            source_row_id="row-ns-001",
            risk_class=SbmRiskClass.CSR_NONSEC,
            bucket="4",
            risk_factor=CSR_BOND_RISK_FACTOR,
            qualifier="ISS-A",
            tenor="1y",
            amount=1_000_000.0,
        ),
        _sensitivity(
            sensitivity_id="csr-ns-cds-a-5y",
            source_row_id="row-ns-002",
            risk_class=SbmRiskClass.CSR_NONSEC,
            bucket="4",
            risk_factor=CSR_CDS_RISK_FACTOR,
            qualifier="ISS-A",
            tenor="5y",
            amount=-400_000.0,
        ),
        _sensitivity(
            sensitivity_id="csr-ns-bond-b-1y",
            source_row_id="row-ns-003",
            risk_class=SbmRiskClass.CSR_NONSEC,
            bucket="5",
            risk_factor=CSR_BOND_RISK_FACTOR,
            qualifier="ISS-B",
            tenor="1y",
            amount=750_000.0,
        ),
    )


def csr_sec_nonctp_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _sensitivity(
            sensitivity_id="csr-sec-nctp-bond-a-5y",
            source_row_id="row-nctp-001",
            risk_class=SbmRiskClass.CSR_SEC_NONCTP,
            bucket="1",
            risk_factor=CSR_BOND_RISK_FACTOR,
            qualifier="TR-A",
            tenor="5y",
            amount=1_000_000.0,
        ),
        _sensitivity(
            sensitivity_id="csr-sec-nctp-cds-a-3y",
            source_row_id="row-nctp-002",
            risk_class=SbmRiskClass.CSR_SEC_NONCTP,
            bucket="1",
            risk_factor=CSR_CDS_RISK_FACTOR,
            qualifier="TR-A",
            tenor="3y",
            amount=-650_000.0,
        ),
        _sensitivity(
            sensitivity_id="csr-sec-nctp-other-1y",
            source_row_id="row-nctp-003",
            risk_class=SbmRiskClass.CSR_SEC_NONCTP,
            bucket=CSR_SEC_OTHER_SECTOR_BUCKET,
            risk_factor=CSR_BOND_RISK_FACTOR,
            qualifier="TR-OTHER",
            tenor="1y",
            amount=500_000.0,
        ),
    )


def csr_sec_ctp_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _sensitivity(
            sensitivity_id="csr-sec-ctp-bond-a-5y",
            source_row_id="row-ctp-001",
            risk_class=SbmRiskClass.CSR_SEC_CTP,
            bucket="3",
            risk_factor=CSR_BOND_RISK_FACTOR,
            qualifier="UND-A",
            tenor="5y",
            amount=550_000.0,
        ),
        _sensitivity(
            sensitivity_id="csr-sec-ctp-cds-a-3y",
            source_row_id="row-ctp-002",
            risk_class=SbmRiskClass.CSR_SEC_CTP,
            bucket="3",
            risk_factor=CSR_CDS_RISK_FACTOR,
            qualifier="UND-A",
            tenor="3y",
            amount=-250_000.0,
        ),
        _sensitivity(
            sensitivity_id="csr-sec-ctp-bond-b-5y",
            source_row_id="row-ctp-003",
            risk_class=SbmRiskClass.CSR_SEC_CTP,
            bucket="10",
            risk_factor=CSR_BOND_RISK_FACTOR,
            qualifier="UND-B",
            tenor="5y",
            amount=800_000.0,
        ),
    )


def _sensitivity(
    *,
    sensitivity_id: str,
    source_row_id: str,
    risk_class: SbmRiskClass,
    bucket: str,
    risk_factor: str,
    qualifier: str,
    tenor: str,
    amount: float,
    mapping_citation_ids: tuple[str, ...] = (),
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=source_row_id,
        desk_id="credit-desk",
        legal_entity="LE-001",
        risk_class=risk_class,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=bucket,
        risk_factor=risk_factor,
        qualifier=qualifier,
        tenor=tenor,
        amount=amount,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=sample_lineage(source_row_id),
        mapping_citation_ids=mapping_citation_ids,
    )


def arrow_table(sensitivities: tuple[SbmSensitivity, ...]) -> pa.Table:
    return pa.table(
        {
            "sensitivity_id": [item.sensitivity_id for item in sensitivities],
            "source_row_id": [item.source_row_id for item in sensitivities],
            "desk_id": [item.desk_id for item in sensitivities],
            "legal_entity": [item.legal_entity for item in sensitivities],
            "risk_class": _dictionary([item.risk_class.value for item in sensitivities]),
            "risk_measure": _dictionary([item.risk_measure.value for item in sensitivities]),
            "bucket": _dictionary([item.bucket for item in sensitivities]),
            "risk_factor": _dictionary([item.risk_factor for item in sensitivities]),
            "qualifier": _dictionary([item.qualifier for item in sensitivities]),
            "tenor": _dictionary([item.tenor for item in sensitivities]),
            "amount": pa.array([item.amount for item in sensitivities], type=pa.float64()),
            "amount_currency": _dictionary([item.amount_currency for item in sensitivities]),
            "sign_convention": _dictionary([item.sign_convention.value for item in sensitivities]),
            "lineage_source_system": [item.lineage.source_system for item in sensitivities],
            "lineage_source_file": [item.lineage.source_file for item in sensitivities],
        }
    )


def _dictionary(values: list[str | None]) -> pa.Array:
    return pa.array(values).dictionary_encode()


def test_csr_nonsec_delta_batch_and_handoff_match_row_capital() -> None:
    context = sample_context("csr-nonsec-batch-run")
    sensitivities = csr_nonsec_sensitivities()
    source_hash = source_content_hash("synthetic CSR non-sec delta source")
    handoff = normalize_csr_nonsec_delta_arrow_table(
        arrow_table(sensitivities),
        source_hash=source_hash,
    )

    row_result = calculate_sbm_capital(sensitivities, context=context)
    row_batch = build_csr_nonsec_delta_batch_from_sensitivities(sensitivities)
    arrow_batch = build_csr_nonsec_delta_batch_from_arrow(handoff)
    batch_result = calculate_sbm_capital_from_csr_nonsec_delta_batch(
        arrow_batch,
        context=context,
    )
    handoff_result = calculate_sbm_capital_from_csr_nonsec_delta_arrow(
        handoff,
        context=context,
    )

    assert row_batch.input_hash == input_hash_for_sensitivities(sensitivities)
    assert arrow_batch.input_hash == row_batch.input_hash
    assert arrow_batch.source_hash == source_hash
    assert arrow_batch.handoff_hash is not None
    np.testing.assert_array_equal(arrow_batch.qualifiers, row_batch.qualifiers)
    np.testing.assert_array_equal(arrow_batch.tenors, row_batch.tenors)
    _assert_capital_equivalent(batch_result, row_result)
    _assert_capital_equivalent(handoff_result, row_result)


def test_csr_sec_nonctp_delta_batch_and_handoff_match_row_capital() -> None:
    context = sample_context("csr-sec-nonctp-batch-run")
    sensitivities = csr_sec_nonctp_sensitivities()
    handoff = normalize_csr_sec_nonctp_delta_arrow_table(
        arrow_table(sensitivities),
        source_hash=source_content_hash("synthetic CSR sec non-CTP delta source"),
    )

    row_result = calculate_sbm_capital(sensitivities, context=context)
    row_batch = build_csr_sec_nonctp_delta_batch_from_sensitivities(sensitivities)
    arrow_batch = build_csr_sec_nonctp_delta_batch_from_arrow(handoff)
    batch_result = calculate_sbm_capital_from_csr_sec_nonctp_delta_batch(
        arrow_batch,
        context=context,
    )
    handoff_result = calculate_sbm_capital_from_csr_sec_nonctp_delta_arrow(
        handoff,
        context=context,
    )

    assert arrow_batch.input_hash == row_batch.input_hash
    np.testing.assert_array_equal(arrow_batch.qualifiers, row_batch.qualifiers)
    np.testing.assert_array_equal(arrow_batch.tenors, row_batch.tenors)
    _assert_capital_equivalent(batch_result, row_result)
    _assert_capital_equivalent(handoff_result, row_result)


def test_csr_sec_ctp_delta_batch_and_handoff_match_row_capital() -> None:
    context = sample_context("csr-sec-ctp-batch-run")
    sensitivities = csr_sec_ctp_sensitivities()
    handoff = normalize_csr_sec_ctp_delta_arrow_table(
        arrow_table(sensitivities),
        source_hash=source_content_hash("synthetic CSR sec CTP delta source"),
    )

    row_result = calculate_sbm_capital(sensitivities, context=context)
    row_batch = build_csr_sec_ctp_delta_batch_from_sensitivities(sensitivities)
    arrow_batch = build_csr_sec_ctp_delta_batch_from_arrow(handoff)
    batch_result = calculate_sbm_capital_from_csr_sec_ctp_delta_batch(
        arrow_batch,
        context=context,
    )
    handoff_result = calculate_sbm_capital_from_csr_sec_ctp_delta_arrow(
        handoff,
        context=context,
    )

    assert arrow_batch.input_hash == row_batch.input_hash
    np.testing.assert_array_equal(arrow_batch.qualifiers, row_batch.qualifiers)
    np.testing.assert_array_equal(arrow_batch.tenors, row_batch.tenors)
    _assert_capital_equivalent(batch_result, row_result)
    _assert_capital_equivalent(handoff_result, row_result)


def _assert_capital_equivalent(left: object, right: object) -> None:
    assert left.total_capital == pytest.approx(right.total_capital)  # type: ignore[attr-defined]
    assert left.input_hash == right.input_hash  # type: ignore[attr-defined]
    assert len(left.risk_classes) == len(right.risk_classes) == 1  # type: ignore[attr-defined]
    left_risk_class = left.risk_classes[0]  # type: ignore[attr-defined]
    right_risk_class = right.risk_classes[0]  # type: ignore[attr-defined]
    assert left_risk_class.selected_scenario == right_risk_class.selected_scenario
    assert left_risk_class.scenario_totals == pytest.approx(right_risk_class.scenario_totals)
    assert tuple(bucket.bucket_id for bucket in left_risk_class.buckets) == tuple(
        bucket.bucket_id for bucket in right_risk_class.buckets
    )
    for left_bucket, right_bucket in zip(
        left_risk_class.buckets,
        right_risk_class.buckets,
        strict=True,
    ):
        assert left_bucket.kb == pytest.approx(right_bucket.kb)
        assert left_bucket.sb == pytest.approx(right_bucket.sb)
        assert [item.sensitivity_id for item in left_bucket.weighted_sensitivities] == [
            item.sensitivity_id for item in right_bucket.weighted_sensitivities
        ]


def test_csr_delta_batches_preserve_credit_factor_axes() -> None:
    nonsec_result = calculate_csr_nonsec_delta_risk_class_capital_from_batch(
        build_csr_nonsec_delta_batch_from_sensitivities(
            (
                csr_nonsec_sensitivities()[0],
                csr_nonsec_sensitivities()[1],
                _sensitivity(
                    sensitivity_id="csr-ns-bond-b-1y",
                    source_row_id="row-ns-axis-003",
                    risk_class=SbmRiskClass.CSR_NONSEC,
                    bucket="4",
                    risk_factor=CSR_BOND_RISK_FACTOR,
                    qualifier="ISS-B",
                    tenor="1y",
                    amount=300_000.0,
                ),
            )
        ),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        pairwise_evidence_mode=SbmPairwiseEvidenceMode.FULL,
    )
    nonsec_pairs = _medium_pairwise(nonsec_result, "4")
    assert nonsec_pairs[("csr-ns-bond-a-1y", "csr-ns-cds-a-5y")] == pytest.approx(
        CSR_TENOR_CORRELATION * CSR_DIFFERENT_CURVE_CORRELATION
    )
    assert nonsec_pairs[("csr-ns-bond-a-1y", "csr-ns-bond-b-1y")] == pytest.approx(
        CSR_NAME_CORRELATION
    )

    nonctp_result = calculate_csr_sec_nonctp_delta_risk_class_capital_from_batch(
        build_csr_sec_nonctp_delta_batch_from_sensitivities(
            (
                csr_sec_nonctp_sensitivities()[0],
                csr_sec_nonctp_sensitivities()[1],
                _sensitivity(
                    sensitivity_id="csr-sec-nctp-bond-b-5y",
                    source_row_id="row-nctp-axis-003",
                    risk_class=SbmRiskClass.CSR_SEC_NONCTP,
                    bucket="1",
                    risk_factor=CSR_BOND_RISK_FACTOR,
                    qualifier="TR-B",
                    tenor="5y",
                    amount=300_000.0,
                ),
            )
        ),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        pairwise_evidence_mode=SbmPairwiseEvidenceMode.FULL,
    )
    nonctp_pairs = _medium_pairwise(nonctp_result, "1")
    assert nonctp_pairs[("csr-sec-nctp-bond-a-5y", "csr-sec-nctp-cds-a-3y")] == pytest.approx(
        CSR_SEC_TENOR_DIFFERENT_CORRELATION * CSR_SEC_DIFFERENT_BASIS_CORRELATION
    )
    assert nonctp_pairs[("csr-sec-nctp-bond-a-5y", "csr-sec-nctp-bond-b-5y")] == pytest.approx(
        CSR_SEC_TRANCHE_DIFFERENT_CORRELATION
    )

    ctp_result = calculate_csr_sec_ctp_delta_risk_class_capital_from_batch(
        build_csr_sec_ctp_delta_batch_from_sensitivities(
            (
                csr_sec_ctp_sensitivities()[0],
                csr_sec_ctp_sensitivities()[1],
                _sensitivity(
                    sensitivity_id="csr-sec-ctp-bond-b-5y",
                    source_row_id="row-ctp-axis-003",
                    risk_class=SbmRiskClass.CSR_SEC_CTP,
                    bucket="3",
                    risk_factor=CSR_BOND_RISK_FACTOR,
                    qualifier="UND-B",
                    tenor="5y",
                    amount=300_000.0,
                ),
            )
        ),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        pairwise_evidence_mode=SbmPairwiseEvidenceMode.FULL,
    )
    ctp_pairs = _medium_pairwise(ctp_result, "3")
    assert ctp_pairs[("csr-sec-ctp-bond-a-5y", "csr-sec-ctp-cds-a-3y")] == pytest.approx(
        CSR_TENOR_CORRELATION * CSR_CTP_DIFFERENT_BASIS_CORRELATION
    )
    assert ctp_pairs[("csr-sec-ctp-bond-a-5y", "csr-sec-ctp-bond-b-5y")] == pytest.approx(
        CSR_NAME_CORRELATION
    )


def _medium_pairwise(result: object, bucket_id: str) -> dict[tuple[str, str], float]:
    detail = next(item for item in result.scenario_details if item.scenario.value == "MEDIUM")
    intra = next(item for item in detail.intra_buckets if item.bucket_id == bucket_id)
    pairs: dict[tuple[str, str], float] = {}
    for record in intra.pairwise_correlations:
        if record.sensitivity_a == record.sensitivity_b:
            continue
        pairs[tuple(sorted((record.sensitivity_a, record.sensitivity_b)))] = record.correlation
    return pairs


def test_csr_sec_nonctp_other_sector_batch_preserves_absolute_weight_treatment() -> None:
    result = calculate_csr_sec_nonctp_delta_risk_class_capital_from_batch(
        build_csr_sec_nonctp_delta_batch_from_sensitivities(
            (
                _sensitivity(
                    sensitivity_id="csr-sec-nctp-other-long",
                    source_row_id="row-nctp-other-001",
                    risk_class=SbmRiskClass.CSR_SEC_NONCTP,
                    bucket=CSR_SEC_OTHER_SECTOR_BUCKET,
                    risk_factor=CSR_BOND_RISK_FACTOR,
                    qualifier="TR-X",
                    tenor="1y",
                    amount=1_000_000.0,
                ),
                _sensitivity(
                    sensitivity_id="csr-sec-nctp-other-short",
                    source_row_id="row-nctp-other-002",
                    risk_class=SbmRiskClass.CSR_SEC_NONCTP,
                    bucket=CSR_SEC_OTHER_SECTOR_BUCKET,
                    risk_factor=CSR_CDS_RISK_FACTOR,
                    qualifier="TR-Y",
                    tenor="1y",
                    amount=-600_000.0,
                ),
            )
        ),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )
    bucket_25 = next(
        bucket for bucket in result.buckets if bucket.bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET
    )

    assert bucket_25.kb == pytest.approx(56_000.0)
    assert bucket_25.sb == pytest.approx(14_000.0)
    assert "basel_mar21_68" in bucket_25.citation_ids


def test_csr_sec_ctp_batch_decomposition_evidence_fails_closed() -> None:
    bad_batch = build_csr_sec_ctp_delta_batch_from_sensitivities(
        (
            _sensitivity(
                sensitivity_id="csr-sec-ctp-needs-evidence",
                source_row_id="row-ctp-bad-001",
                risk_class=SbmRiskClass.CSR_SEC_CTP,
                bucket="3",
                risk_factor=CSR_BOND_RISK_FACTOR,
                qualifier="UND-A",
                tenor="5y",
                amount=500_000.0,
                mapping_citation_ids=(CSR_SEC_CTP_DECOMPOSITION_REQUIRED_FLAG,),
            ),
        )
    )

    with pytest.raises(UnsupportedRegulatoryFeatureError, match="decomposition evidence"):
        weight_csr_sec_ctp_delta_sensitivity_batch(
            bad_batch,
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        )


def test_csr_delta_handoff_contracts_require_credit_axes() -> None:
    nonsec_without_tenor = arrow_table(csr_nonsec_sensitivities()).drop(["tenor"])
    nonctp_without_qualifier = arrow_table(csr_sec_nonctp_sensitivities()).drop(["qualifier"])
    ctp_without_tenor = arrow_table(csr_sec_ctp_sensitivities()).drop(["tenor"])

    with pytest.raises(ValueError, match="tenor"):
        normalize_csr_nonsec_delta_arrow_table(nonsec_without_tenor)
    with pytest.raises(ValueError, match="qualifier"):
        normalize_csr_sec_nonctp_delta_arrow_table(nonctp_without_qualifier)
    with pytest.raises(ValueError, match="tenor"):
        normalize_csr_sec_ctp_delta_arrow_table(ctp_without_tenor)


def test_csr_arrow_handoff_builders_do_not_construct_row_dataclasses() -> None:
    import frtb_sbm.arrow_handoff as arrow_handoff

    source = inspect.getsource(arrow_handoff)

    assert "SbmSensitivity(" not in source
    assert "from frtb_sbm.data_models import SbmSensitivity" not in source
