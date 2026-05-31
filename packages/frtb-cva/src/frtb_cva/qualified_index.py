"""
SA-CVA qualified-index routing per Basel MAR50.50.
"""

from __future__ import annotations

from frtb_cva.data_models import (
    CvaRegulatoryProfile,
    SaCvaIndexTreatment,
    SaCvaRiskClass,
    SaCvaSensitivity,
)
from frtb_cva.sa_cva_reference_data import (
    CCS_QUALIFIED_INDEX_BUCKET,
    EQUITY_QUALIFIED_INDEX_BUCKETS,
)
from frtb_cva.validation import CvaInputError

_SECTOR_CONCENTRATION_THRESHOLD = 0.75
_CCS_INDEX_BUCKETS = frozenset({"1", "2", "3", "4", "5", "6", "7", CCS_QUALIFIED_INDEX_BUCKET})


def resolve_sa_cva_bucket(
    sensitivity: SaCvaSensitivity,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[str, tuple[str, ...]]:
    """Return the effective bucket id and citation ids for one sensitivity row."""

    _ = profile
    bucket = sensitivity.bucket_id
    if sensitivity.index_treatment is SaCvaIndexTreatment.LOOK_THROUGH_REQUIRED:
        raise CvaInputError(
            "non-qualified index requires constituent look-through sensitivities",
            field="index_treatment",
            record_id=sensitivity.sensitivity_id,
        )

    if sensitivity.risk_class is SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD:
        return _resolve_ccs_bucket(sensitivity, bucket)

    if sensitivity.risk_class is SaCvaRiskClass.REFERENCE_CREDIT_SPREAD:
        return _resolve_rcs_bucket(sensitivity, bucket)

    if sensitivity.risk_class is SaCvaRiskClass.EQUITY:
        return _resolve_equity_bucket(sensitivity, bucket)

    if sensitivity.index_treatment is not None:
        raise CvaInputError(
            "qualified-index routing is only supported for CCS, RCS, and equity",
            field="index_treatment",
            record_id=sensitivity.sensitivity_id,
        )
    return bucket, ()


def _resolve_ccs_bucket(sensitivity: SaCvaSensitivity, bucket: str) -> tuple[str, tuple[str, ...]]:
    if bucket not in _CCS_INDEX_BUCKETS and sensitivity.index_treatment is not None:
        raise CvaInputError(
            f"CCS bucket {bucket} does not support qualified-index treatment",
            field="bucket_id",
            record_id=sensitivity.sensitivity_id,
        )
    if bucket != CCS_QUALIFIED_INDEX_BUCKET:
        if sensitivity.index_treatment is SaCvaIndexTreatment.QUALIFIED_INDEX:
            raise CvaInputError(
                "qualified CCS index must use bucket 8",
                field="bucket_id",
                record_id=sensitivity.sensitivity_id,
            )
        return bucket, ()

    if sensitivity.index_treatment is not SaCvaIndexTreatment.QUALIFIED_INDEX:
        raise CvaInputError(
            "CCS bucket 8 requires qualified-index treatment metadata",
            field="index_treatment",
            record_id=sensitivity.sensitivity_id,
        )
    remapped = _sector_concentration_bucket(sensitivity, default_bucket=bucket)
    return remapped, ("basel_mar50_50", "basel_mar50_63")


def _resolve_rcs_bucket(sensitivity: SaCvaSensitivity, bucket: str) -> tuple[str, tuple[str, ...]]:
    if bucket == "8":
        if sensitivity.index_treatment is not SaCvaIndexTreatment.QUALIFIED_INDEX:
            raise CvaInputError(
                "RCS qualified index requires QUALIFIED_INDEX treatment",
                field="index_treatment",
                record_id=sensitivity.sensitivity_id,
            )
        remapped = _sector_concentration_bucket(sensitivity, default_bucket=bucket)
        return remapped, ("basel_mar50_50",)
    if sensitivity.index_treatment is SaCvaIndexTreatment.QUALIFIED_INDEX:
        raise CvaInputError(
            "RCS qualified index must use bucket 8",
            field="bucket_id",
            record_id=sensitivity.sensitivity_id,
        )
    return bucket, ()


def _resolve_equity_bucket(
    sensitivity: SaCvaSensitivity,
    bucket: str,
) -> tuple[str, tuple[str, ...]]:
    if bucket in EQUITY_QUALIFIED_INDEX_BUCKETS:
        if sensitivity.index_treatment is not SaCvaIndexTreatment.QUALIFIED_INDEX:
            raise CvaInputError(
                "equity qualified-index buckets 12/13 require QUALIFIED_INDEX treatment",
                field="index_treatment",
                record_id=sensitivity.sensitivity_id,
            )
        return bucket, ("basel_mar50_50", "basel_mar50_72")
    if sensitivity.index_treatment is SaCvaIndexTreatment.QUALIFIED_INDEX:
        raise CvaInputError(
            "qualified equity index must use buckets 12 or 13",
            field="bucket_id",
            record_id=sensitivity.sensitivity_id,
        )
    return bucket, ()


def _sector_concentration_bucket(sensitivity: SaCvaSensitivity, *, default_bucket: str) -> str:
    weight = sensitivity.index_max_sector_weight
    if weight is None:
        return default_bucket
    if weight > _SECTOR_CONCENTRATION_THRESHOLD:
        if not sensitivity.index_homogeneous_sector_quality:
            raise CvaInputError(
                "index with >75% sector concentration must map to single-name bucket",
                field="index_max_sector_weight",
                record_id=sensitivity.sensitivity_id,
            )
        return "2"
    return default_bucket


__all__ = ["resolve_sa_cva_bucket"]
