"""Package-owned sensitivity batches for high-volume SBM kernels.

Regulatory traceability:
    Basel MAR21.4-MAR21.7 and MAR21.39-MAR21.42 — GIRR delta weighting,
    factor netting, and aggregation. Other supported SBM paths use the same
    package-owned tabular boundary before path-specific weighting.
    SBM-NFR-001, SBM-NFR-002, SBM-AUDIT-001.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import cast

import numpy as np
import numpy.typing as npt
from frtb_common import CalculationScope

from frtb_sbm.assembly.hashes import (
    INPUT_HASH_ALGORITHM_JSON_ROW_V1,
)
from frtb_sbm.assembly.hashes import (
    input_hash_algorithm_for_sbm_batches as _input_hash_algorithm_for_sbm_batches,
)
from frtb_sbm.assembly.hashes import (
    input_hash_for_sbm_batch as _input_hash_for_sbm_batch,
)
from frtb_sbm.assembly.hashes import (
    input_hash_for_sbm_batches as _input_hash_for_sbm_batches,
)
from frtb_sbm.data_models import (
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
)
from frtb_sbm.validation import (
    SbmInputError,
    coerce_risk_class,
    coerce_risk_measure,
    validate_sbm_sensitivities,
)

ObjectArray = npt.NDArray[np.object_]
FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class SbmSensitivityBatch:
    """
    Kernel-facing SBM sensitivity batch.

    The hot fields are immutable NumPy arrays. Non-array metadata is lineage and
    adapter evidence only; kernels must not require Arrow or row dataclasses.
    """

    sensitivity_ids: ObjectArray
    source_row_ids: ObjectArray
    desk_ids: ObjectArray
    legal_entities: ObjectArray
    risk_classes: ObjectArray
    risk_measures: ObjectArray
    buckets: ObjectArray
    risk_factors: ObjectArray
    amounts: FloatArray
    amount_currencies: ObjectArray
    sign_conventions: ObjectArray
    tenors: ObjectArray
    lineage_source_systems: ObjectArray
    lineage_source_files: ObjectArray
    input_hash: str
    input_hash_algorithm: str = INPUT_HASH_ALGORITHM_JSON_ROW_V1
    source_hash: str | None = None
    handoff_hash: str | None = None
    diagnostics: tuple[Mapping[str, object], ...] = ()
    position_ids: ObjectArray | None = None
    qualifiers: ObjectArray | None = None
    option_tenors: ObjectArray | None = None
    liquidity_horizon_days: ObjectArray | None = None
    maturities: ObjectArray | None = None
    up_shock_amounts: ObjectArray | None = None
    down_shock_amounts: ObjectArray | None = None
    risk_factor_ids: ObjectArray | None = None
    risk_factor_mapping_versions: ObjectArray | None = None
    bucket_labels: ObjectArray | None = None
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None = None
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None = None
    org_scopes: tuple[CalculationScope | None, ...] | None = None
    accepted_row_dataclasses_materialized: int = 0

    @property
    def row_count(self) -> int:
        """Return the number of accepted sensitivity rows represented.
        Returns
        -------
        int
        """

        return int(self.amounts.shape[0])

    @property
    def risk_class(self) -> SbmRiskClass:
        """Return the homogeneous risk class represented by this batch.
        Returns
        -------
        SbmRiskClass
        """

        if self.row_count == 0:
            raise SbmInputError("batch must not be empty", field="batch")
        return coerce_risk_class(cast(SbmRiskClass | str, self.risk_classes[0]))

    @property
    def risk_measure(self) -> SbmRiskMeasure:
        """Return the homogeneous risk measure represented by this batch.
        Returns
        -------
        SbmRiskMeasure
        """

        if self.row_count == 0:
            raise SbmInputError("batch must not be empty", field="batch")
        return coerce_risk_measure(cast(SbmRiskMeasure | str, self.risk_measures[0]))


def build_sbm_batch_from_sensitivities(
    sensitivities: object,
    *,
    expected_risk_class: SbmRiskClass | str | None = None,
    expected_risk_measure: SbmRiskMeasure | str | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """Build a homogeneous SBM batch from existing row-wise canonical sensitivities.

    This is a compatibility builder for callers that already hold
    ``SbmSensitivity`` rows. High-volume adapters should use
    ``build_sbm_batch_from_columns`` so accepted rows are never materialised as
    dataclasses.
    Parameters
    ----------
    sensitivities, expected_risk_class, expected_risk_measure, source_hash, handoff_hash,
    diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

    validated = validate_sbm_sensitivities(sensitivities)
    _require_non_empty(validated)
    risk_class, risk_measure = _homogeneous_path_from_sensitivities(validated)
    if expected_risk_class is not None:
        expected = coerce_risk_class(expected_risk_class)
        if risk_class is not expected:
            raise SbmInputError(
                f"batch only accepts {expected.value} sensitivities",
                field="risk_class",
            )
    if expected_risk_measure is not None:
        expected_measure = coerce_risk_measure(expected_risk_measure)
        if risk_measure is not expected_measure:
            raise SbmInputError(
                f"batch only accepts {expected_measure.value} sensitivities",
                field="risk_measure",
            )

    optional_arrays = _optional_arrays_from_sensitivities(validated)
    source_column_maps = _source_column_maps_from_sensitivities(validated)
    mapping_citations = _mapping_citations_from_sensitivities(validated)
    org_scopes = _org_scopes_from_sensitivities(validated)
    batch = build_sbm_batch_from_columns(
        expected_risk_class=risk_class,
        expected_risk_measure=risk_measure,
        sensitivity_ids=[item.sensitivity_id for item in validated],
        source_row_ids=[item.source_row_id for item in validated],
        desk_ids=[item.desk_id for item in validated],
        legal_entities=[item.legal_entity for item in validated],
        risk_classes=[item.risk_class.value for item in validated],
        risk_measures=[item.risk_measure.value for item in validated],
        buckets=[item.bucket for item in validated],
        risk_factors=[item.risk_factor for item in validated],
        amounts=[item.amount for item in validated],
        amount_currencies=[item.amount_currency for item in validated],
        sign_conventions=[item.sign_convention.value for item in validated],
        tenors=[item.tenor for item in validated],
        lineage_source_systems=[item.lineage.source_system for item in validated],
        lineage_source_files=[item.lineage.source_file for item in validated],
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        source_column_maps=source_column_maps,
        mapping_citation_ids=mapping_citations,
        org_scopes=org_scopes,
        copy_arrays=True,
        position_ids=optional_arrays["position_ids"],
        qualifiers=optional_arrays["qualifiers"],
        option_tenors=optional_arrays["option_tenors"],
        liquidity_horizon_days=optional_arrays["liquidity_horizon_days"],
        maturities=optional_arrays["maturities"],
        up_shock_amounts=optional_arrays["up_shock_amounts"],
        down_shock_amounts=optional_arrays["down_shock_amounts"],
        risk_factor_ids=optional_arrays["risk_factor_ids"],
        risk_factor_mapping_versions=optional_arrays["risk_factor_mapping_versions"],
        bucket_labels=optional_arrays["bucket_labels"],
    )
    return replace(batch, accepted_row_dataclasses_materialized=len(validated))


def input_hash_for_batch(batch: SbmSensitivityBatch) -> str:
    """Return the canonical row-equivalent input hash for an SBM batch.

    Parameters
    ----------
    batch
        Homogeneous SBM sensitivity batch.

    Returns
    -------
    str
    """

    return _input_hash_for_sbm_batch(batch)


def input_hash_algorithm_for_sbm_batches(batches: object) -> str:
    """Return the deterministic input hash algorithm for batch portfolios.

    Parameters
    ----------
    batches : object
        Iterable of ``SbmSensitivityBatch`` instances.

    Returns
    -------
    str
        Result-level input hash algorithm label for the batch collection.
    """

    validated = coerce_sbm_batch_sequence(batches)
    return _input_hash_algorithm_for_sbm_batches(validated)


def input_hash_for_sbm_batches(batches: object) -> str:
    """Return the row-equivalent deterministic input hash for batch portfolios.
    Parameters
    ----------
    batches : object
        See signature.

    Returns
    -------
    str
    """

    validated = coerce_sbm_batch_sequence(batches)
    return _input_hash_for_sbm_batches(validated)


def concatenate_sbm_batches(batches: object) -> SbmSensitivityBatch:
    """Concatenate homogeneous SBM batches without materialising row dataclasses.
    Parameters
    ----------
    batches : object
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    validated = coerce_sbm_batch_sequence(batches)
    if len(validated) == 1:
        return validated[0]

    expected_risk_class = validated[0].risk_class
    expected_risk_measure = validated[0].risk_measure
    for batch in validated[1:]:
        if batch.risk_class is not expected_risk_class:
            raise SbmInputError(
                "cannot concatenate batches with different risk_class values",
                field="risk_class",
            )
        if batch.risk_measure is not expected_risk_measure:
            raise SbmInputError(
                "cannot concatenate batches with different risk_measure values",
                field="risk_measure",
            )

    combined = build_sbm_batch_from_columns(
        expected_risk_class=expected_risk_class,
        expected_risk_measure=expected_risk_measure,
        sensitivity_ids=_concat_required_arrays(validated, "sensitivity_ids"),
        source_row_ids=_concat_required_arrays(validated, "source_row_ids"),
        desk_ids=_concat_required_arrays(validated, "desk_ids"),
        legal_entities=_concat_required_arrays(validated, "legal_entities"),
        risk_classes=_concat_required_arrays(validated, "risk_classes"),
        risk_measures=_concat_required_arrays(validated, "risk_measures"),
        buckets=_concat_required_arrays(validated, "buckets"),
        risk_factors=_concat_required_arrays(validated, "risk_factors"),
        amounts=_concat_float_arrays(validated, "amounts"),
        amount_currencies=_concat_required_arrays(validated, "amount_currencies"),
        sign_conventions=_concat_required_arrays(validated, "sign_conventions"),
        tenors=_concat_required_arrays(validated, "tenors"),
        lineage_source_systems=_concat_required_arrays(validated, "lineage_source_systems"),
        lineage_source_files=_concat_required_arrays(validated, "lineage_source_files"),
        source_hash=None,
        handoff_hash=None,
        diagnostics=tuple(diagnostic for batch in validated for diagnostic in batch.diagnostics),
        position_ids=_concat_optional_arrays(validated, "position_ids"),
        qualifiers=_concat_optional_arrays(validated, "qualifiers"),
        option_tenors=_concat_optional_arrays(validated, "option_tenors"),
        liquidity_horizon_days=_concat_optional_arrays(validated, "liquidity_horizon_days"),
        maturities=_concat_optional_arrays(validated, "maturities"),
        up_shock_amounts=_concat_optional_arrays(validated, "up_shock_amounts"),
        down_shock_amounts=_concat_optional_arrays(validated, "down_shock_amounts"),
        risk_factor_ids=_concat_optional_arrays(validated, "risk_factor_ids"),
        risk_factor_mapping_versions=_concat_optional_arrays(
            validated, "risk_factor_mapping_versions"
        ),
        bucket_labels=_concat_optional_arrays(validated, "bucket_labels"),
        source_column_maps=_concat_source_column_maps(validated),
        mapping_citation_ids=_concat_mapping_citation_ids(validated),
        org_scopes=_concat_org_scopes(validated),
        copy_arrays=False,
    )
    return replace(
        combined,
        accepted_row_dataclasses_materialized=sum(
            batch.accepted_row_dataclasses_materialized for batch in validated
        ),
    )


def sorted_sbm_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in stable risk-class, bucket, factor, and id order.
    Parameters
    ----------
    batch : SbmSensitivityBatch
        See signature.

    Returns
    -------
    npt.NDArray[np.int64]
    """

    return np.lexsort(
        (
            batch.sensitivity_ids,
            batch.risk_factors,
            batch.buckets,
            batch.risk_measures,
            batch.risk_classes,
        )
    )


def sorted_girr_delta_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise GIRR delta weighting.
    Parameters
    ----------
    batch : SbmSensitivityBatch
        See signature.

    Returns
    -------
    npt.NDArray[np.int64]
    """

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="GIRR delta",
    )
    return sorted_sbm_batch_indices(batch)


def sorted_girr_vega_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise GIRR vega weighting.
    Parameters
    ----------
    batch : SbmSensitivityBatch
        See signature.

    Returns
    -------
    npt.NDArray[np.int64]
    """

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.VEGA,
        label="GIRR vega",
    )
    return sorted_sbm_batch_indices(batch)


def sorted_girr_curvature_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise GIRR curvature helpers.
    Parameters
    ----------
    batch : SbmSensitivityBatch
        See signature.

    Returns
    -------
    npt.NDArray[np.int64]
    """

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.CURVATURE,
        label="GIRR curvature",
    )
    return sorted_sbm_batch_indices(batch)


def sorted_curvature_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise curvature helpers.
    Parameters
    ----------
    batch : SbmSensitivityBatch
        See signature.

    Returns
    -------
    npt.NDArray[np.int64]
    """

    if batch.row_count == 0:
        raise SbmInputError("curvature batch must not be empty", field="batch")
    if batch.risk_measure is not SbmRiskMeasure.CURVATURE:
        raise SbmInputError("curvature batch only accepts CURVATURE sensitivities")
    return sorted_sbm_batch_indices(batch)


def sorted_fx_delta_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise FX delta weighting.
    Parameters
    ----------
    batch : SbmSensitivityBatch
        See signature.

    Returns
    -------
    npt.NDArray[np.int64]
    """

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.FX,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="FX delta",
    )
    return sorted_sbm_batch_indices(batch)


def sorted_equity_delta_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise equity delta weighting.
    Parameters
    ----------
    batch : SbmSensitivityBatch
        See signature.

    Returns
    -------
    npt.NDArray[np.int64]
    """

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.EQUITY,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="equity delta",
    )
    return sorted_sbm_batch_indices(batch)


def sorted_commodity_delta_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise commodity delta weighting.
    Parameters
    ----------
    batch : SbmSensitivityBatch
        See signature.

    Returns
    -------
    npt.NDArray[np.int64]
    """

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.COMMODITY,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="commodity delta",
    )
    return sorted_sbm_batch_indices(batch)


def sorted_csr_nonsec_delta_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise CSR non-sec weighting.
    Parameters
    ----------
    batch : SbmSensitivityBatch
        See signature.

    Returns
    -------
    npt.NDArray[np.int64]
    """

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.CSR_NONSEC,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="CSR non-securitisation delta",
    )
    return sorted_sbm_batch_indices(batch)


def sorted_csr_sec_nonctp_delta_batch_indices(
    batch: SbmSensitivityBatch,
) -> npt.NDArray[np.int64]:
    """Return indices in the stable order used by row-wise CSR sec non-CTP weighting.
    Parameters
    ----------
    batch : SbmSensitivityBatch
        See signature.

    Returns
    -------
    npt.NDArray[np.int64]
    """

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="CSR securitisation non-CTP delta",
    )
    return sorted_sbm_batch_indices(batch)


def sorted_csr_sec_ctp_delta_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise CSR sec CTP weighting.
    Parameters
    ----------
    batch : SbmSensitivityBatch
        See signature.

    Returns
    -------
    npt.NDArray[np.int64]
    """

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.CSR_SEC_CTP,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="CSR securitisation CTP delta",
    )
    return sorted_sbm_batch_indices(batch)


def _optional_arrays_from_sensitivities(
    sensitivities: tuple[SbmSensitivity, ...],
) -> dict[str, Iterable[object] | None]:
    optional_fields = {
        "position_ids": tuple(item.position_id for item in sensitivities),
        "qualifiers": tuple(item.qualifier for item in sensitivities),
        "option_tenors": tuple(item.option_tenor for item in sensitivities),
        "liquidity_horizon_days": tuple(item.liquidity_horizon_days for item in sensitivities),
        "maturities": tuple(item.maturity for item in sensitivities),
        "up_shock_amounts": tuple(item.up_shock_amount for item in sensitivities),
        "down_shock_amounts": tuple(item.down_shock_amount for item in sensitivities),
        "risk_factor_ids": tuple(item.risk_factor_id for item in sensitivities),
        "risk_factor_mapping_versions": tuple(
            item.risk_factor_mapping_version for item in sensitivities
        ),
        "bucket_labels": tuple(item.bucket_label for item in sensitivities),
    }
    return {
        field_name: values if any(value is not None for value in values) else None
        for field_name, values in optional_fields.items()
    }


def _source_column_maps_from_sensitivities(
    sensitivities: tuple[SbmSensitivity, ...],
) -> tuple[tuple[tuple[str, str], ...], ...] | None:
    source_column_maps = tuple(item.lineage.source_column_map for item in sensitivities)
    if not any(source_column_maps):
        return None
    return source_column_maps


def _mapping_citations_from_sensitivities(
    sensitivities: tuple[SbmSensitivity, ...],
) -> tuple[tuple[str, ...], ...] | None:
    mapping_citations = tuple(item.mapping_citation_ids for item in sensitivities)
    if not any(mapping_citations):
        return None
    return mapping_citations


def _org_scopes_from_sensitivities(
    sensitivities: tuple[SbmSensitivity, ...],
) -> tuple[CalculationScope | None, ...] | None:
    org_scopes = tuple(item.org_scope for item in sensitivities)
    if not any(scope is not None for scope in org_scopes):
        return None
    return org_scopes


def _homogeneous_path_from_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
) -> tuple[SbmRiskClass, SbmRiskMeasure]:
    first = sensitivities[0]
    risk_class = first.risk_class
    risk_measure = first.risk_measure
    for sensitivity in sensitivities[1:]:
        if sensitivity.risk_class is not risk_class:
            raise SbmInputError(
                "batch requires one homogeneous risk_class",
                field="risk_class",
                sensitivity_id=sensitivity.sensitivity_id,
            )
        if sensitivity.risk_measure is not risk_measure:
            raise SbmInputError(
                "batch requires one homogeneous risk_measure",
                field="risk_measure",
                sensitivity_id=sensitivity.sensitivity_id,
            )
    return risk_class, risk_measure


def coerce_sbm_batch_sequence(batches: object) -> tuple[SbmSensitivityBatch, ...]:
    """Return a validated non-empty tuple of package-owned SBM batches.
    Parameters
    ----------
    batches : object
        See signature.

    Returns
    -------
    tuple[SbmSensitivityBatch, ...]
    """

    if isinstance(batches, SbmSensitivityBatch):
        return (batches,)
    try:
        candidates: tuple[object, ...] = tuple(batches)  # type: ignore[arg-type]
    except TypeError as exc:
        raise SbmInputError(
            "batches must be an iterable of SbmSensitivityBatch objects",
            field="batches",
        ) from exc
    if not candidates:
        raise SbmInputError("batches must not be empty", field="batches")
    for candidate in candidates:
        if not isinstance(candidate, SbmSensitivityBatch):
            raise SbmInputError(
                "batches must contain only SbmSensitivityBatch objects",
                field="batches",
            )
    return cast(tuple[SbmSensitivityBatch, ...], candidates)


def _coerce_batch_sequence(batches: object) -> tuple[SbmSensitivityBatch, ...]:
    return coerce_sbm_batch_sequence(batches)


def _concat_required_arrays(
    batches: Sequence[SbmSensitivityBatch],
    field_name: str,
) -> ObjectArray:
    return cast(
        ObjectArray,
        np.concatenate([getattr(batch, field_name) for batch in batches]).astype(
            object,
            copy=False,
        ),
    )


def _concat_float_arrays(
    batches: Sequence[SbmSensitivityBatch],
    field_name: str,
) -> FloatArray:
    return cast(
        FloatArray,
        np.concatenate([getattr(batch, field_name) for batch in batches]).astype(
            np.float64,
            copy=False,
        ),
    )


def _concat_optional_arrays(
    batches: Sequence[SbmSensitivityBatch],
    field_name: str,
) -> ObjectArray | None:
    arrays = [cast(ObjectArray | None, getattr(batch, field_name)) for batch in batches]
    if not any(array is not None for array in arrays):
        return None
    parts = [
        array if array is not None else np.full(batch.row_count, None, dtype=object)
        for batch, array in zip(batches, arrays, strict=True)
    ]
    return cast(ObjectArray, np.concatenate(parts).astype(object, copy=False))


def _concat_source_column_maps(
    batches: Sequence[SbmSensitivityBatch],
) -> tuple[tuple[tuple[str, str], ...], ...] | None:
    if not any(batch.source_column_maps is not None for batch in batches):
        return None
    rows: list[tuple[tuple[str, str], ...]] = []
    for batch in batches:
        if batch.source_column_maps is None:
            rows.extend(() for _ in range(batch.row_count))
        else:
            rows.extend(batch.source_column_maps)
    return tuple(rows)


def _concat_mapping_citation_ids(
    batches: Sequence[SbmSensitivityBatch],
) -> tuple[tuple[str, ...], ...] | None:
    if not any(batch.mapping_citation_ids is not None for batch in batches):
        return None
    rows: list[tuple[str, ...]] = []
    for batch in batches:
        if batch.mapping_citation_ids is None:
            rows.extend(() for _ in range(batch.row_count))
        else:
            rows.extend(batch.mapping_citation_ids)
    return tuple(rows)


def _concat_org_scopes(
    batches: Sequence[SbmSensitivityBatch],
) -> tuple[CalculationScope | None, ...] | None:
    if not any(batch.org_scopes is not None for batch in batches):
        return None
    rows: list[CalculationScope | None] = []
    for batch in batches:
        if batch.org_scopes is None:
            rows.extend([None] * batch.row_count)
        else:
            rows.extend(batch.org_scopes)
    return tuple(rows)


def _require_non_empty(values: Sequence[SbmSensitivity]) -> None:
    if len(values) == 0:
        raise SbmInputError("SBM batch must not be empty", field="sensitivities")


def _require_batch_path(
    batch: SbmSensitivityBatch,
    *,
    expected_risk_class: SbmRiskClass,
    expected_risk_measure: SbmRiskMeasure,
    label: str,
) -> None:
    if batch.risk_class is not expected_risk_class:
        raise SbmInputError(
            f"{label} batch only accepts {expected_risk_class.value} sensitivities",
            field="risk_class",
        )
    if batch.risk_measure is not expected_risk_measure:
        raise SbmInputError(
            f"{label} batch only accepts {expected_risk_measure.value} sensitivities",
            field="risk_measure",
        )


from frtb_sbm.adapters.sensitivities import (  # noqa: E402
    build_sbm_batch,
    build_sbm_batch_from_columns,
)

__all__ = [
    "SbmSensitivityBatch",
    "build_sbm_batch",
    "build_sbm_batch_from_columns",
    "build_sbm_batch_from_sensitivities",
    "coerce_sbm_batch_sequence",
    "concatenate_sbm_batches",
    "input_hash_algorithm_for_sbm_batches",
    "input_hash_for_batch",
    "input_hash_for_sbm_batches",
    "sorted_commodity_delta_batch_indices",
    "sorted_csr_nonsec_delta_batch_indices",
    "sorted_csr_sec_ctp_delta_batch_indices",
    "sorted_csr_sec_nonctp_delta_batch_indices",
    "sorted_curvature_batch_indices",
    "sorted_equity_delta_batch_indices",
    "sorted_fx_delta_batch_indices",
    "sorted_girr_curvature_batch_indices",
    "sorted_girr_delta_batch_indices",
    "sorted_girr_vega_batch_indices",
    "sorted_sbm_batch_indices",
]
