"""Risk-factor metadata propagation for SBM audit records.

SBM consumes calculation-ready risk-factor attributes supplied by upstream
metadata owners. This module only preserves supplied identifiers and source
provenance on material result records; it does not infer canonical mapping
data or query the result store.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import cast

from frtb_sbm.batch import SbmSensitivityBatch
from frtb_sbm.data_models import (
    RiskClassCapital,
    SbmSensitivity,
    WeightedSensitivity,
)


@dataclass(frozen=True)
class _RiskFactorMetadata:
    risk_factor_id: str | None = None
    risk_factor_mapping_version: str | None = None
    bucket_label: str | None = None
    source_system: str | None = None
    source_row_id: str | None = None


def attach_risk_factor_metadata_from_sensitivities(
    risk_class_results: Sequence[RiskClassCapital],
    sensitivities: Sequence[SbmSensitivity],
) -> tuple[RiskClassCapital, ...]:
    """Return risk-class results carrying supplied row metadata.

    Parameters
    ----------
    risk_class_results
        Capital records produced by an SBM row calculation.
    sensitivities
        Validated input sensitivities that supplied optional risk-factor
        metadata and source lineage.

    Returns
    -------
    tuple[RiskClassCapital, ...]
        Capital records with metadata copied onto material weighted
        sensitivities where the contributing input rows resolve uniquely.
    """

    metadata_by_id = {
        sensitivity.sensitivity_id: _RiskFactorMetadata(
            risk_factor_id=sensitivity.risk_factor_id,
            risk_factor_mapping_version=sensitivity.risk_factor_mapping_version,
            bucket_label=sensitivity.bucket_label,
            source_system=sensitivity.lineage.source_system,
            source_row_id=sensitivity.source_row_id,
        )
        for sensitivity in sensitivities
    }
    return tuple(_attach_to_risk_class(result, metadata_by_id) for result in risk_class_results)


def attach_risk_factor_metadata_from_batch(
    risk_class_result: RiskClassCapital,
    batch: SbmSensitivityBatch,
) -> RiskClassCapital:
    """Return a batch result carrying supplied columnar row metadata.

    Parameters
    ----------
    risk_class_result
        Capital record produced by an SBM batch calculation.
    batch
        Package-owned batch carrying optional risk-factor metadata arrays and
        required source lineage arrays.

    Returns
    -------
    RiskClassCapital
        Capital record with metadata copied onto material weighted
        sensitivities where the contributing batch rows resolve uniquely.
    """

    metadata_by_id: dict[str, _RiskFactorMetadata] = {}
    for row_index in range(batch.row_count):
        sensitivity_id = cast(str, batch.sensitivity_ids[row_index])
        metadata_by_id[sensitivity_id] = _RiskFactorMetadata(
            risk_factor_id=_optional_str_at(batch.risk_factor_ids, row_index),
            risk_factor_mapping_version=_optional_str_at(
                batch.risk_factor_mapping_versions,
                row_index,
            ),
            bucket_label=_optional_str_at(batch.bucket_labels, row_index),
            source_system=cast(str, batch.lineage_source_systems[row_index]),
            source_row_id=cast(str, batch.source_row_ids[row_index]),
        )
    return _attach_to_risk_class(risk_class_result, metadata_by_id)


def _attach_to_risk_class(
    risk_class_result: RiskClassCapital,
    metadata_by_id: Mapping[str, _RiskFactorMetadata],
) -> RiskClassCapital:
    return replace(
        risk_class_result,
        buckets=tuple(
            replace(
                bucket,
                weighted_sensitivities=tuple(
                    _attach_to_weighted(weighted, metadata_by_id)
                    for weighted in bucket.weighted_sensitivities
                ),
            )
            for bucket in risk_class_result.buckets
        ),
    )


def _attach_to_weighted(
    weighted: WeightedSensitivity,
    metadata_by_id: Mapping[str, _RiskFactorMetadata],
) -> WeightedSensitivity:
    contributors = weighted.contributing_sensitivity_ids or (weighted.sensitivity_id,)
    metadata = tuple(metadata_by_id[item] for item in contributors if item in metadata_by_id)
    if not metadata:
        return weighted
    return replace(
        weighted,
        risk_factor_id=_single_metadata_value(metadata, "risk_factor_id"),
        risk_factor_mapping_version=_single_metadata_value(
            metadata,
            "risk_factor_mapping_version",
        ),
        bucket_label=_single_metadata_value(metadata, "bucket_label"),
        source_system=_single_metadata_value(metadata, "source_system"),
        source_row_id=_single_metadata_value(metadata, "source_row_id"),
    )


def _single_metadata_value(
    metadata: tuple[_RiskFactorMetadata, ...],
    field_name: str,
) -> str | None:
    values = {
        value
        for item in metadata
        if (value := cast(str | None, getattr(item, field_name))) is not None
    }
    if len(values) == 1:
        return next(iter(values))
    return None


def _optional_str_at(values: object | None, row_index: int) -> str | None:
    if values is None:
        return None
    value = values[row_index]  # type: ignore[index]
    if value is None:
        return None
    return cast(str, value)


__all__ = [
    "attach_risk_factor_metadata_from_batch",
    "attach_risk_factor_metadata_from_sensitivities",
]
