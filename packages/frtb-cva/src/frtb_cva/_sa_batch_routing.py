"""SA-CVA batch qualified-index bucket routing adapters."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import TypeVar, cast

from frtb_cva._batch_columns import _optional_float_value
from frtb_cva._batch_contracts import SaCvaSensitivityBatch
from frtb_cva.data_models import (
    CvaRegulatoryProfile,
    CvaSector,
    CvaSourceLineage,
    SaCvaIndexTreatment,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
)
from frtb_cva.qualified_index import resolve_sa_cva_bucket

_OptionalEnum = TypeVar("_OptionalEnum", bound=StrEnum)


def _resolve_sa_cva_bucket_from_batch(
    batch: SaCvaSensitivityBatch,
    index: int,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> str:
    bucket_id, _ = _resolve_sa_cva_bucket_decision_from_batch(
        batch,
        index,
        profile=profile,
    )
    return bucket_id


def _resolve_sa_cva_bucket_decision_from_batch(
    batch: SaCvaSensitivityBatch,
    index: int,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[str, tuple[str, ...]]:
    return resolve_sa_cva_bucket(_sensitivity_from_batch_row(batch, index), profile=profile)


def _sensitivity_from_batch_row(batch: SaCvaSensitivityBatch, index: int) -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id=cast(str, batch.sensitivity_ids[index]),
        risk_class=SaCvaRiskClass(cast(str, batch.risk_classes[index])),
        risk_measure=SaCvaRiskMeasure(cast(str, batch.risk_measures[index])),
        sensitivity_tag=SensitivityTag(cast(str, batch.sensitivity_tags[index])),
        bucket_id=cast(str, batch.bucket_ids[index]),
        risk_factor_key=cast(str, batch.risk_factor_keys[index]),
        amount=float(batch.amounts[index]),
        amount_currency=cast(str, batch.amount_currencies[index]),
        sign_convention=cast(str, batch.sign_conventions[index]),
        source_row_id=cast(str, batch.source_row_ids[index]),
        tenor=_optional_str(batch.tenors[index]),
        volatility_input=_optional_float_value(batch.volatility_inputs[index]),
        hedge_id=_optional_str(batch.hedge_ids[index]),
        index_treatment=_optional_enum(batch.index_treatments[index], SaCvaIndexTreatment),
        index_max_sector_weight=_optional_float_value(batch.index_max_sector_weights[index]),
        index_homogeneous_sector_quality=bool(batch.index_homogeneous_sector_quality[index]),
        index_dominant_sector=_optional_enum(batch.index_dominant_sectors[index], CvaSector),
        index_remap_bucket_id=_optional_str(batch.index_remap_bucket_ids[index]),
        lineage=CvaSourceLineage(
            source_system=cast(str, batch.lineage_source_systems[index]),
            source_file=cast(str, batch.lineage_source_files[index]),
            source_row_id=cast(str, batch.lineage_source_row_ids[index]),
            source_column_map=batch.source_column_maps[index],
        ),
    )


def _optional_str(value: object) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return str(value)


def _optional_enum(value: object, enum_type: type[_OptionalEnum]) -> _OptionalEnum | None:
    text = _optional_str(value)
    if text is None:
        return None
    return enum_type(text)
