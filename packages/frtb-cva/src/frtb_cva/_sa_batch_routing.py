"""SA-CVA batch qualified-index bucket routing."""

from __future__ import annotations

import math
from typing import cast

from frtb_cva._batch_contracts import SaCvaSensitivityBatch
from frtb_cva.data_models import CvaSector, SaCvaIndexTreatment, SaCvaRiskClass
from frtb_cva.sa_cva_reference_data import (
    CCS_QUALIFIED_INDEX_BUCKET,
    CCS_SINGLE_NAME_BUCKETS,
    EQUITY_QUALIFIED_INDEX_BUCKETS,
    RCS_QUALIFIED_INDEX_BUCKETS,
    RCS_SINGLE_NAME_BUCKETS,
    ccs_single_name_bucket_for_sector,
    parse_ccs_entity_key,
)
from frtb_cva.validation import CvaInputError


def _resolve_sa_cva_bucket_from_batch(batch: SaCvaSensitivityBatch, index: int) -> str:
    risk_class = SaCvaRiskClass(cast(str, batch.risk_classes[index]))
    bucket = cast(str, batch.bucket_ids[index])
    treatment = (
        None
        if batch.index_treatments[index] is None
        else SaCvaIndexTreatment(cast(str, batch.index_treatments[index]))
    )
    record_id = cast(str, batch.sensitivity_ids[index])
    if treatment is SaCvaIndexTreatment.LOOK_THROUGH_REQUIRED:
        raise CvaInputError(
            "non-qualified index requires constituent look-through sensitivities",
            field="index_treatment",
            record_id=record_id,
        )
    if risk_class is SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD:
        return _resolve_ccs_bucket(batch, index, bucket, treatment)
    if risk_class is SaCvaRiskClass.REFERENCE_CREDIT_SPREAD:
        return _resolve_rcs_bucket(batch, index, bucket, treatment)
    if risk_class is SaCvaRiskClass.EQUITY:
        return _resolve_equity_bucket(batch, index, bucket, treatment)
    if treatment is not None:
        raise CvaInputError(
            "qualified-index routing is only supported for CCS, RCS, and equity",
            field="index_treatment",
            record_id=record_id,
        )
    return bucket


def _resolve_ccs_bucket(
    batch: SaCvaSensitivityBatch,
    index: int,
    bucket: str,
    treatment: SaCvaIndexTreatment | None,
) -> str:
    record_id = cast(str, batch.sensitivity_ids[index])
    ccs_index_buckets = frozenset({"1", "2", "3", "4", "5", "6", "7", CCS_QUALIFIED_INDEX_BUCKET})
    if bucket not in ccs_index_buckets and treatment is not None:
        raise CvaInputError(
            f"CCS bucket {bucket} does not support qualified-index treatment",
            field="bucket_id",
            record_id=record_id,
        )
    if bucket != CCS_QUALIFIED_INDEX_BUCKET:
        if treatment is SaCvaIndexTreatment.QUALIFIED_INDEX:
            raise CvaInputError(
                "qualified CCS index must use bucket 8",
                field="bucket_id",
                record_id=record_id,
            )
        return bucket
    if treatment is not SaCvaIndexTreatment.QUALIFIED_INDEX:
        raise CvaInputError(
            "CCS bucket 8 requires qualified-index treatment metadata",
            field="index_treatment",
            record_id=record_id,
        )
    return _sector_concentration_bucket(batch, index, default_bucket=bucket)


def _resolve_rcs_bucket(
    batch: SaCvaSensitivityBatch,
    index: int,
    bucket: str,
    treatment: SaCvaIndexTreatment | None,
) -> str:
    record_id = cast(str, batch.sensitivity_ids[index])
    if bucket in RCS_QUALIFIED_INDEX_BUCKETS:
        if treatment is not SaCvaIndexTreatment.QUALIFIED_INDEX:
            raise CvaInputError(
                "RCS qualified-index buckets 16/17 require QUALIFIED_INDEX treatment",
                field="index_treatment",
                record_id=record_id,
            )
        return _sector_concentration_bucket(batch, index, default_bucket=bucket)
    if treatment is SaCvaIndexTreatment.QUALIFIED_INDEX:
        raise CvaInputError(
            "RCS qualified index must use buckets 16 or 17",
            field="bucket_id",
            record_id=record_id,
        )
    return bucket


def _resolve_equity_bucket(
    batch: SaCvaSensitivityBatch,
    index: int,
    bucket: str,
    treatment: SaCvaIndexTreatment | None,
) -> str:
    record_id = cast(str, batch.sensitivity_ids[index])
    if bucket in EQUITY_QUALIFIED_INDEX_BUCKETS:
        if treatment is not SaCvaIndexTreatment.QUALIFIED_INDEX:
            raise CvaInputError(
                "equity qualified-index buckets 12/13 require QUALIFIED_INDEX treatment",
                field="index_treatment",
                record_id=record_id,
            )
        return bucket
    if treatment is SaCvaIndexTreatment.QUALIFIED_INDEX:
        raise CvaInputError(
            "qualified equity index must use buckets 12 or 13",
            field="bucket_id",
            record_id=record_id,
        )
    return bucket


def _sector_concentration_bucket(
    batch: SaCvaSensitivityBatch,
    index: int,
    *,
    default_bucket: str,
) -> str:
    weight = float(batch.index_max_sector_weights[index])
    if math.isnan(weight):
        return default_bucket
    record_id = cast(str, batch.sensitivity_ids[index])
    if not math.isfinite(weight) or not (0.0 <= weight <= 1.0):
        raise CvaInputError(
            "index_max_sector_weight must be a finite probability between 0.0 and 1.0",
            field="index_max_sector_weight",
            record_id=record_id,
        )
    if weight <= 0.75:
        return default_bucket
    if not bool(batch.index_homogeneous_sector_quality[index]):
        raise CvaInputError(
            "index with >75% sector concentration must map to single-name bucket",
            field="index_max_sector_weight",
            record_id=record_id,
        )
    remap_bucket = batch.index_remap_bucket_ids[index]
    if remap_bucket is not None:
        return _explicit_remap_bucket(batch, index, cast(str, remap_bucket), record_id=record_id)
    risk_class = SaCvaRiskClass(cast(str, batch.risk_classes[index]))
    if risk_class is SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD:
        return _ccs_sector_concentration_bucket(batch, index, record_id=record_id)
    raise CvaInputError(
        "index with >75% sector concentration requires index_remap_bucket_id for this risk class",
        field="index_remap_bucket_id",
        record_id=record_id,
    )


def _explicit_remap_bucket(
    batch: SaCvaSensitivityBatch,
    index: int,
    remap_bucket: str,
    *,
    record_id: str,
) -> str:
    bucket = remap_bucket.strip()
    if not bucket:
        raise CvaInputError(
            "index_remap_bucket_id must be a non-empty bucket id",
            field="index_remap_bucket_id",
            record_id=record_id,
        )
    _validate_remap_bucket(
        SaCvaRiskClass(cast(str, batch.risk_classes[index])), bucket, record_id=record_id
    )
    return bucket


def _ccs_sector_concentration_bucket(
    batch: SaCvaSensitivityBatch,
    index: int,
    *,
    record_id: str,
) -> str:
    dominant_sector = batch.index_dominant_sectors[index]
    if dominant_sector is None:
        raise CvaInputError(
            "CCS index sector concentration requires index_dominant_sector "
            "or index_remap_bucket_id",
            field="index_dominant_sector",
            record_id=record_id,
        )
    _, credit_quality, _ = parse_ccs_entity_key(cast(str, batch.risk_factor_keys[index]))
    bucket, _ = ccs_single_name_bucket_for_sector(
        CvaSector(cast(str, dominant_sector)),
        credit_quality,
    )
    return bucket


def _validate_remap_bucket(
    risk_class: SaCvaRiskClass,
    bucket: str,
    *,
    record_id: str,
) -> None:
    if risk_class is SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD:
        if bucket not in CCS_SINGLE_NAME_BUCKETS:
            raise CvaInputError(
                f"CCS index remap bucket {bucket} is not a single-name bucket",
                field="index_remap_bucket_id",
                record_id=record_id,
            )
    if risk_class is SaCvaRiskClass.REFERENCE_CREDIT_SPREAD:
        if bucket not in RCS_SINGLE_NAME_BUCKETS:
            raise CvaInputError(
                f"RCS index remap bucket {bucket} is not a single-name bucket",
                field="index_remap_bucket_id",
                record_id=record_id,
            )
