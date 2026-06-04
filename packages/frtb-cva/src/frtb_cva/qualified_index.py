"""
SA-CVA qualified-index routing per Basel MAR50.50.
"""

from __future__ import annotations

import math

from frtb_cva.data_models import (
    CvaRegulatoryProfile,
    SaCvaIndexTreatment,
    SaCvaRiskClass,
    SaCvaSensitivity,
)
from frtb_cva.reference_data import profile_citation_id
from frtb_cva.sa_cva_reference_data import (
    CCS_QUALIFIED_INDEX_BUCKET,
    CCS_SINGLE_NAME_BUCKETS,
    EQUITY_QUALIFIED_INDEX_BUCKETS,
    RCS_DELTA_RISK_WEIGHTS,
    ccs_single_name_bucket_for_sector,
    parse_ccs_entity_key,
)
from frtb_cva.validation import CvaInputError

_SECTOR_CONCENTRATION_THRESHOLD = 0.75
_CCS_INDEX_BUCKETS = frozenset({"1", "2", "3", "4", "5", "6", "7", CCS_QUALIFIED_INDEX_BUCKET})
_RCS_SINGLE_NAME_BUCKETS = frozenset(RCS_DELTA_RISK_WEIGHTS) - {CCS_QUALIFIED_INDEX_BUCKET}


def resolve_sa_cva_bucket(
    sensitivity: SaCvaSensitivity,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[str, tuple[str, ...]]:
    """Return the effective bucket id and citation ids for one sensitivity row.

Parameters
----------
sensitivity :
    Single SA-CVA sensitivity row prior to weighting.

profile, optional :
    Optional regulatory profile label or ``CvaRegulatoryProfile`` value; defaults to Basel MAR50 (2020).

Returns
-------
tuple[str, tuple[str, ...]]
    Result of ``resolve_sa_cva_bucket`` for audit and downstream aggregation."""

    bucket = sensitivity.bucket_id
    if sensitivity.index_treatment is SaCvaIndexTreatment.LOOK_THROUGH_REQUIRED:
        raise CvaInputError(
            "non-qualified index requires constituent look-through sensitivities",
            field="index_treatment",
            record_id=sensitivity.sensitivity_id,
        )

    if sensitivity.risk_class is SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD:
        return _resolve_ccs_bucket(sensitivity, bucket, profile=profile)

    if sensitivity.risk_class is SaCvaRiskClass.REFERENCE_CREDIT_SPREAD:
        return _resolve_rcs_bucket(sensitivity, bucket, profile=profile)

    if sensitivity.risk_class is SaCvaRiskClass.EQUITY:
        return _resolve_equity_bucket(sensitivity, bucket, profile=profile)

    if sensitivity.index_treatment is not None:
        raise CvaInputError(
            "qualified-index routing is only supported for CCS, RCS, and equity",
            field="index_treatment",
            record_id=sensitivity.sensitivity_id,
        )
    return bucket, ()


def _resolve_ccs_bucket(
    sensitivity: SaCvaSensitivity,
    bucket: str,
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[str, tuple[str, ...]]:
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
    return remapped, (
        profile_citation_id("basel_mar50_50", profile),
        profile_citation_id("basel_mar50_63", profile),
    )


def _resolve_rcs_bucket(
    sensitivity: SaCvaSensitivity,
    bucket: str,
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[str, tuple[str, ...]]:
    if bucket == "8":
        if sensitivity.index_treatment is not SaCvaIndexTreatment.QUALIFIED_INDEX:
            raise CvaInputError(
                "RCS qualified index requires QUALIFIED_INDEX treatment",
                field="index_treatment",
                record_id=sensitivity.sensitivity_id,
            )
        remapped = _sector_concentration_bucket(sensitivity, default_bucket=bucket)
        return remapped, (profile_citation_id("basel_mar50_50", profile),)
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
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[str, tuple[str, ...]]:
    if bucket in EQUITY_QUALIFIED_INDEX_BUCKETS:
        if sensitivity.index_treatment is not SaCvaIndexTreatment.QUALIFIED_INDEX:
            raise CvaInputError(
                "equity qualified-index buckets 12/13 require QUALIFIED_INDEX treatment",
                field="index_treatment",
                record_id=sensitivity.sensitivity_id,
            )
        return bucket, (
            profile_citation_id("basel_mar50_50", profile),
            profile_citation_id("basel_mar50_72", profile),
        )
    if sensitivity.index_treatment is SaCvaIndexTreatment.QUALIFIED_INDEX:
        raise CvaInputError(
            "qualified equity index must use buckets 12 or 13",
            field="bucket_id",
            record_id=sensitivity.sensitivity_id,
        )
    return bucket, ()


def _validate_sector_weight(weight: float, *, record_id: str) -> None:
    if not math.isfinite(weight) or not (0.0 <= weight <= 1.0):
        raise CvaInputError(
            "index_max_sector_weight must be a finite probability between 0.0 and 1.0",
            field="index_max_sector_weight",
            record_id=record_id,
        )


def _sector_concentration_bucket(sensitivity: SaCvaSensitivity, *, default_bucket: str) -> str:
    weight = sensitivity.index_max_sector_weight
    if weight is None:
        return default_bucket
    _validate_sector_weight(weight, record_id=sensitivity.sensitivity_id)
    if weight <= _SECTOR_CONCENTRATION_THRESHOLD:
        return default_bucket
    if not sensitivity.index_homogeneous_sector_quality:
        raise CvaInputError(
            "index with >75% sector concentration must map to single-name bucket",
            field="index_max_sector_weight",
            record_id=sensitivity.sensitivity_id,
        )
    return _resolve_concentration_remap_bucket(sensitivity)


def _resolve_concentration_remap_bucket(sensitivity: SaCvaSensitivity) -> str:
    if sensitivity.index_remap_bucket_id is not None:
        bucket = sensitivity.index_remap_bucket_id.strip()
        if not bucket:
            raise CvaInputError(
                "index_remap_bucket_id must be a non-empty bucket id",
                field="index_remap_bucket_id",
                record_id=sensitivity.sensitivity_id,
            )
        _validate_remap_bucket(sensitivity.risk_class, bucket, record_id=sensitivity.sensitivity_id)
        return bucket

    if sensitivity.risk_class is SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD:
        if sensitivity.index_dominant_sector is None:
            raise CvaInputError(
                "CCS index sector concentration requires index_dominant_sector "
                "or index_remap_bucket_id",
                field="index_dominant_sector",
                record_id=sensitivity.sensitivity_id,
            )
        _, credit_quality, _ = parse_ccs_entity_key(sensitivity.risk_factor_key)
        bucket, _ = ccs_single_name_bucket_for_sector(
            sensitivity.index_dominant_sector,
            credit_quality,
        )
        return bucket

    raise CvaInputError(
        "index with >75% sector concentration requires index_remap_bucket_id for this risk class",
        field="index_remap_bucket_id",
        record_id=sensitivity.sensitivity_id,
    )


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
        return
    if risk_class is SaCvaRiskClass.REFERENCE_CREDIT_SPREAD:
        if bucket not in _RCS_SINGLE_NAME_BUCKETS:
            raise CvaInputError(
                f"RCS index remap bucket {bucket} is not a single-name bucket",
                field="index_remap_bucket_id",
                record_id=record_id,
            )


__all__ = ["resolve_sa_cva_bucket"]
