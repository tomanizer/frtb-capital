from __future__ import annotations

from dataclasses import replace
from typing import cast

import numpy as np
import pytest
from frtb_cva import (
    CvaSector,
    CvaSourceLineage,
    SaCvaIndexTreatment,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
    build_sa_cva_sensitivity_batch_from_sensitivities,
)
from frtb_cva._sa_batch_routing import (
    _resolve_sa_cva_bucket_decision_from_batch,
    _sensitivity_from_batch_row,
)
from frtb_cva.qualified_index import resolve_sa_cva_bucket
from frtb_cva.validation import CvaInputError


def _lineage(row_id: str) -> CvaSourceLineage:
    return CvaSourceLineage(
        source_system="synthetic",
        source_file="sensitivities.csv",
        source_row_id=row_id,
    )


def _sensitivity(
    sensitivity_id: str,
    risk_class: SaCvaRiskClass,
    bucket_id: str,
    risk_factor_key: str,
    *,
    index_treatment: SaCvaIndexTreatment | None = None,
    **overrides: object,
) -> SaCvaSensitivity:
    base = dict(
        sensitivity_id=sensitivity_id,
        risk_class=risk_class,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id=bucket_id,
        risk_factor_key=risk_factor_key,
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id=f"row-{sensitivity_id}",
        tenor="5y",
        index_treatment=index_treatment,
        lineage=_lineage(f"row-{sensitivity_id}"),
    )
    base.update(overrides)
    return SaCvaSensitivity(**base)  # type: ignore[arg-type]


def _ccs_sensitivity(**overrides: object) -> SaCvaSensitivity:
    base: dict[str, object] = {
        "sensitivity_id": "sens-ccs-index",
        "bucket_id": "8",
        "index_treatment": SaCvaIndexTreatment.QUALIFIED_INDEX,
        "index_homogeneous_sector_quality": True,
    }
    base.update(overrides)
    return _sensitivity(
        cast(str, base.pop("sensitivity_id")),
        SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        cast(str, base.pop("bucket_id")),
        "INDEX|INVESTMENT_GRADE",
        index_treatment=cast(SaCvaIndexTreatment | None, base.pop("index_treatment")),
        **base,
    )


@pytest.mark.parametrize(
    "sensitivity",
    [
        _ccs_sensitivity(),
        _ccs_sensitivity(
            sensitivity_id="sens-ccs-concentrated",
            index_max_sector_weight=0.8,
            index_dominant_sector=CvaSector.FINANCIALS,
        ),
        _sensitivity(
            "sens-rcs-index",
            SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
            "16",
            "INDEX",
            index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
        ),
        _sensitivity(
            "sens-rcs-remap",
            SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
            "17",
            "INDEX",
            index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
            index_max_sector_weight=0.8,
            index_homogeneous_sector_quality=True,
            index_remap_bucket_id="1",
        ),
        _sensitivity(
            "sens-equity-index",
            SaCvaRiskClass.EQUITY,
            "12",
            "INDEX",
            index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
        ),
        _sensitivity(
            "sens-girr-single-name",
            SaCvaRiskClass.GIRR,
            "USD",
            "5y",
        ),
    ],
)
def test_batch_and_row_qualified_index_routing_decisions_match(
    sensitivity: SaCvaSensitivity,
) -> None:
    batch = build_sa_cva_sensitivity_batch_from_sensitivities((sensitivity,))

    assert _sensitivity_from_batch_row(batch, 0) == sensitivity
    assert _resolve_sa_cva_bucket_decision_from_batch(
        batch,
        0,
        profile="BASEL_MAR50_2020",
    ) == resolve_sa_cva_bucket(sensitivity, profile="BASEL_MAR50_2020")


@pytest.mark.parametrize(
    "sensitivity",
    [
        _ccs_sensitivity(
            sensitivity_id="sens-look-through",
            bucket_id="2",
            index_treatment=SaCvaIndexTreatment.LOOK_THROUGH_REQUIRED,
        ),
        _sensitivity(
            "sens-girr-index",
            SaCvaRiskClass.GIRR,
            "USD",
            "5y",
            index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
        ),
        _ccs_sensitivity(
            sensitivity_id="sens-ccs-wrong-bucket",
            bucket_id="1",
        ),
        _sensitivity(
            "sens-rcs-missing-remap",
            SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
            "16",
            "INDEX",
            index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
            index_max_sector_weight=0.8,
            index_homogeneous_sector_quality=True,
        ),
    ],
)
def test_batch_and_row_qualified_index_routing_failures_match(
    sensitivity: SaCvaSensitivity,
) -> None:
    batch = build_sa_cva_sensitivity_batch_from_sensitivities((sensitivity,))

    with pytest.raises(CvaInputError) as row_error:
        resolve_sa_cva_bucket(sensitivity, profile="BASEL_MAR50_2020")
    with pytest.raises(CvaInputError) as batch_error:
        _resolve_sa_cva_bucket_decision_from_batch(batch, 0, profile="BASEL_MAR50_2020")

    assert batch_error.value.field == row_error.value.field
    assert batch_error.value.record_id == row_error.value.record_id


def test_batch_optional_string_and_enum_nan_values_materialize_as_none() -> None:
    sensitivity = _sensitivity(
        "sens-nan-optionals",
        SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        "16",
        "INDEX",
        index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
        hedge_id="hedge-1",
        index_dominant_sector=CvaSector.FINANCIALS,
        index_remap_bucket_id="1",
    )
    batch = build_sa_cva_sensitivity_batch_from_sensitivities((sensitivity,))
    nan_batch = replace(
        batch,
        tenors=np.asarray([float("nan")], dtype=object),
        hedge_ids=np.asarray([float("nan")], dtype=object),
        index_treatments=np.asarray([float("nan")], dtype=object),
        index_dominant_sectors=np.asarray([float("nan")], dtype=object),
        index_remap_bucket_ids=np.asarray([float("nan")], dtype=object),
    )

    materialized = _sensitivity_from_batch_row(nan_batch, 0)

    assert materialized.tenor is None
    assert materialized.hedge_id is None
    assert materialized.index_treatment is None
    assert materialized.index_dominant_sector is None
    assert materialized.index_remap_bucket_id is None
