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
from types import MappingProxyType
from typing import Any, cast

import numpy as np
import numpy.typing as npt

from frtb_sbm.audit import _hash_payload
from frtb_sbm.data_models import (
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
)
from frtb_sbm.validation import (
    SbmInputError,
    coerce_risk_class,
    coerce_risk_measure,
    coerce_sign_convention,
    normalise_currency_code,
    validate_sbm_sensitivities,
)

ObjectArray = npt.NDArray[np.object_]
FloatArray = npt.NDArray[np.float64]

_CORE_REQUIRED_TEXT_FIELDS = frozenset(
    {
        "sensitivity_ids",
        "source_row_ids",
        "desk_ids",
        "legal_entities",
        "risk_classes",
        "risk_measures",
        "buckets",
        "risk_factors",
        "amount_currencies",
        "sign_conventions",
        "lineage_source_systems",
        "lineage_source_files",
    }
)

_TENOR_REQUIRED_PATHS = frozenset(
    {
        (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA),
    }
)

_OPTION_TENOR_REQUIRED_PATHS = frozenset(
    {(risk_class, SbmRiskMeasure.VEGA) for risk_class in SbmRiskClass}
)

_CURVATURE_REQUIRED_PATHS = frozenset(
    {(risk_class, SbmRiskMeasure.CURVATURE) for risk_class in SbmRiskClass}
)

_QUALIFIER_REQUIRED_RISK_CLASSES = frozenset(
    {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskClass.EQUITY,
        SbmRiskClass.COMMODITY,
    }
)


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
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None = None
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None = None
    accepted_row_dataclasses_materialized: int = 0

    @property
    def row_count(self) -> int:
        """Return the number of accepted sensitivity rows represented."""

        return int(self.amounts.shape[0])

    @property
    def risk_class(self) -> SbmRiskClass:
        """Return the homogeneous risk class represented by this batch."""

        if self.row_count == 0:
            raise SbmInputError("batch must not be empty", field="batch")
        return coerce_risk_class(cast(SbmRiskClass | str, self.risk_classes[0]))

    @property
    def risk_measure(self) -> SbmRiskMeasure:
        """Return the homogeneous risk measure represented by this batch."""

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
    """
    Build a homogeneous SBM batch from existing row-wise canonical sensitivities.

    This is a compatibility builder for callers that already hold
    ``SbmSensitivity`` rows. High-volume adapters should use
    ``build_sbm_batch_from_columns`` so accepted rows are never materialised as
    dataclasses.
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
        copy_arrays=True,
        **optional_arrays,
    )
    return replace(batch, accepted_row_dataclasses_materialized=len(validated))


def build_girr_delta_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """
    Build a GIRR delta batch from existing row-wise canonical sensitivities.

    This compatibility builder is intentionally outside the high-volume Arrow
    path: it starts from already-materialised ``SbmSensitivity`` rows, then
    converts them to the same batch representation used by Arrow handoffs.
    """

    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_girr_vega_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """
    Build a GIRR vega batch from existing row-wise canonical sensitivities.

    This compatibility builder starts from already-materialised
    ``SbmSensitivity`` rows. High-volume Arrow adapters should use
    ``build_girr_vega_batch_from_columns``.
    """

    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.VEGA,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_fx_vega_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """
    Build an FX vega batch from existing row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_sbm_batch_from_columns``.
    """

    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.FX,
        expected_risk_measure=SbmRiskMeasure.VEGA,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_equity_vega_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """
    Build an equity vega batch from existing row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_sbm_batch_from_columns``.
    """

    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.EQUITY,
        expected_risk_measure=SbmRiskMeasure.VEGA,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_commodity_vega_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """
    Build a commodity vega batch from existing row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_sbm_batch_from_columns``.
    """

    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.COMMODITY,
        expected_risk_measure=SbmRiskMeasure.VEGA,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_csr_nonsec_vega_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """
    Build a CSR non-securitisation vega batch from row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_sbm_batch_from_columns``.
    """

    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.CSR_NONSEC,
        expected_risk_measure=SbmRiskMeasure.VEGA,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_csr_sec_nonctp_vega_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """
    Build a CSR securitisation non-CTP vega batch from row-wise sensitivities.

    High-volume Arrow adapters should use ``build_sbm_batch_from_columns``.
    """

    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        expected_risk_measure=SbmRiskMeasure.VEGA,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_csr_sec_ctp_vega_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """
    Build a CSR securitisation CTP vega batch from row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_sbm_batch_from_columns``.
    """

    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.CSR_SEC_CTP,
        expected_risk_measure=SbmRiskMeasure.VEGA,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_girr_curvature_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """
    Build a GIRR curvature batch from existing row-wise canonical sensitivities.

    This validates and preserves the separate up/down shock arrays used by the
    curvature contract. Public curvature capital is available through the row
    API; this compatibility builder does not provide a batch capital entrypoint.
    """

    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.CURVATURE,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def _build_curvature_batch_from_sensitivities(
    sensitivities: object,
    *,
    expected_risk_class: SbmRiskClass,
    source_hash: str | None,
    handoff_hash: str | None,
    diagnostics: Sequence[Mapping[str, object]],
) -> SbmSensitivityBatch:
    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=expected_risk_class,
        expected_risk_measure=SbmRiskMeasure.CURVATURE,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_fx_curvature_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """Build an FX curvature batch from row-wise canonical sensitivities."""

    return _build_curvature_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.FX,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_equity_curvature_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """Build an equity curvature batch from row-wise canonical sensitivities."""

    return _build_curvature_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.EQUITY,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_commodity_curvature_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """Build a commodity curvature batch from row-wise canonical sensitivities."""

    return _build_curvature_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.COMMODITY,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_csr_nonsec_curvature_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """Build a CSR non-securitisation curvature batch from row-wise sensitivities."""

    return _build_curvature_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.CSR_NONSEC,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_csr_sec_nonctp_curvature_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """Build a CSR securitisation non-CTP curvature batch from row-wise sensitivities."""

    return _build_curvature_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_csr_sec_ctp_curvature_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """Build a CSR securitisation CTP curvature batch from row-wise sensitivities."""

    return _build_curvature_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.CSR_SEC_CTP,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_fx_delta_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """
    Build an FX delta batch from existing row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_fx_delta_batch_from_columns``.
    """

    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.FX,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_equity_delta_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """
    Build an equity delta batch from existing row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_equity_delta_batch_from_columns``.
    """

    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.EQUITY,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_commodity_delta_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """
    Build a commodity delta batch from existing row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_commodity_delta_batch_from_columns``.
    """

    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.COMMODITY,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_csr_nonsec_delta_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """
    Build a CSR non-securitisation delta batch from row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_csr_nonsec_delta_batch_from_columns``.
    """

    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.CSR_NONSEC,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_csr_sec_nonctp_delta_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """
    Build a CSR securitisation non-CTP delta batch from row-wise canonical sensitivities.

    High-volume Arrow adapters should use
    ``build_csr_sec_nonctp_delta_batch_from_columns``.
    """

    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_csr_sec_ctp_delta_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """
    Build a CSR securitisation CTP delta batch from row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_csr_sec_ctp_delta_batch_from_columns``.
    """

    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.CSR_SEC_CTP,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_sbm_batch_from_columns(
    *,
    expected_risk_class: SbmRiskClass | str,
    expected_risk_measure: SbmRiskMeasure | str,
    sensitivity_ids: Iterable[object],
    source_row_ids: Iterable[object],
    desk_ids: Iterable[object],
    legal_entities: Iterable[object],
    risk_classes: Iterable[object],
    risk_measures: Iterable[object],
    buckets: Iterable[object],
    risk_factors: Iterable[object],
    amounts: Iterable[object],
    amount_currencies: Iterable[object],
    sign_conventions: Iterable[object],
    tenors: Iterable[object],
    lineage_source_systems: Iterable[object],
    lineage_source_files: Iterable[object],
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    position_ids: Iterable[object] | None = None,
    qualifiers: Iterable[object] | None = None,
    option_tenors: Iterable[object] | None = None,
    liquidity_horizon_days: Iterable[object] | None = None,
    maturities: Iterable[object] | None = None,
    up_shock_amounts: Iterable[object] | None = None,
    down_shock_amounts: Iterable[object] | None = None,
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None = None,
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None = None,
    copy_arrays: bool = True,
) -> SbmSensitivityBatch:
    """Build a homogeneous SBM batch from columnar arrays owned by an adapter."""

    resolved_risk_class = coerce_risk_class(expected_risk_class)
    resolved_risk_measure = coerce_risk_measure(expected_risk_measure)
    arrays = {
        "sensitivity_ids": _object_array(sensitivity_ids, "sensitivity_id", copy=copy_arrays),
        "source_row_ids": _object_array(source_row_ids, "source_row_id", copy=copy_arrays),
        "desk_ids": _object_array(desk_ids, "desk_id", copy=copy_arrays),
        "legal_entities": _object_array(legal_entities, "legal_entity", copy=copy_arrays),
        "risk_classes": _object_array(risk_classes, "risk_class", copy=copy_arrays),
        "risk_measures": _object_array(risk_measures, "risk_measure", copy=copy_arrays),
        "buckets": _object_array(buckets, "bucket", copy=copy_arrays),
        "risk_factors": _object_array(risk_factors, "risk_factor", copy=copy_arrays),
        "amount_currencies": _object_array(
            amount_currencies,
            "amount_currency",
            copy=copy_arrays,
        ),
        "sign_conventions": _object_array(
            sign_conventions,
            "sign_convention",
            copy=copy_arrays,
        ),
        "tenors": _object_array(tenors, "tenor", copy=copy_arrays),
        "lineage_source_systems": _object_array(
            lineage_source_systems,
            "lineage_source_system",
            copy=copy_arrays,
        ),
        "lineage_source_files": _object_array(
            lineage_source_files,
            "lineage_source_file",
            copy=copy_arrays,
        ),
    }
    amount_array = _float_array(amounts, "amount", copy=copy_arrays)
    row_count = int(amount_array.shape[0])
    _require_common_length(row_count, arrays)
    _require_non_empty_length(row_count)
    arrays["risk_classes"] = _normalise_risk_class_array(
        arrays["risk_classes"],
        sensitivity_ids=arrays["sensitivity_ids"],
    )
    arrays["risk_measures"] = _normalise_risk_measure_array(
        arrays["risk_measures"],
        sensitivity_ids=arrays["sensitivity_ids"],
    )
    arrays["sign_conventions"] = _normalise_sign_convention_array(
        arrays["sign_conventions"],
        sensitivity_ids=arrays["sensitivity_ids"],
    )

    optional = {
        "position_ids": _optional_object_array(position_ids, "position_id", row_count, copy_arrays),
        "qualifiers": _optional_object_array(qualifiers, "qualifier", row_count, copy_arrays),
        "option_tenors": _optional_object_array(
            option_tenors,
            "option_tenor",
            row_count,
            copy_arrays,
        ),
        "liquidity_horizon_days": _optional_object_array(
            liquidity_horizon_days,
            "liquidity_horizon_days",
            row_count,
            copy_arrays,
        ),
        "maturities": _optional_object_array(maturities, "maturity", row_count, copy_arrays),
        "up_shock_amounts": _optional_object_array(
            up_shock_amounts,
            "up_shock_amount",
            row_count,
            copy_arrays,
        ),
        "down_shock_amounts": _optional_object_array(
            down_shock_amounts,
            "down_shock_amount",
            row_count,
            copy_arrays,
        ),
    }

    _validate_source_column_maps(source_column_maps, row_count)
    _validate_mapping_citations(mapping_citation_ids, row_count)
    _validate_homogeneous_batch_arrays(
        arrays,
        amount_array,
        expected_risk_class=resolved_risk_class,
        expected_risk_measure=resolved_risk_measure,
        optional_arrays=optional,
    )
    diagnostic_payloads = tuple(MappingProxyType(dict(item)) for item in diagnostics)
    batch_without_hash = SbmSensitivityBatch(
        sensitivity_ids=arrays["sensitivity_ids"],
        source_row_ids=arrays["source_row_ids"],
        desk_ids=arrays["desk_ids"],
        legal_entities=arrays["legal_entities"],
        risk_classes=arrays["risk_classes"],
        risk_measures=arrays["risk_measures"],
        buckets=arrays["buckets"],
        risk_factors=arrays["risk_factors"],
        amounts=amount_array,
        amount_currencies=arrays["amount_currencies"],
        sign_conventions=arrays["sign_conventions"],
        tenors=arrays["tenors"],
        lineage_source_systems=arrays["lineage_source_systems"],
        lineage_source_files=arrays["lineage_source_files"],
        input_hash="",
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostic_payloads,
        position_ids=optional["position_ids"],
        qualifiers=optional["qualifiers"],
        option_tenors=optional["option_tenors"],
        liquidity_horizon_days=optional["liquidity_horizon_days"],
        maturities=optional["maturities"],
        up_shock_amounts=optional["up_shock_amounts"],
        down_shock_amounts=optional["down_shock_amounts"],
        source_column_maps=source_column_maps,
        mapping_citation_ids=mapping_citation_ids,
    )
    return replace(batch_without_hash, input_hash=input_hash_for_sbm_batch(batch_without_hash))


def build_girr_delta_batch_from_columns(
    *,
    sensitivity_ids: Iterable[object],
    source_row_ids: Iterable[object],
    desk_ids: Iterable[object],
    legal_entities: Iterable[object],
    risk_classes: Iterable[object],
    risk_measures: Iterable[object],
    buckets: Iterable[object],
    risk_factors: Iterable[object],
    amounts: Iterable[object],
    amount_currencies: Iterable[object],
    sign_conventions: Iterable[object],
    tenors: Iterable[object],
    lineage_source_systems: Iterable[object],
    lineage_source_files: Iterable[object],
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    position_ids: Iterable[object] | None = None,
    qualifiers: Iterable[object] | None = None,
    option_tenors: Iterable[object] | None = None,
    liquidity_horizon_days: Iterable[object] | None = None,
    maturities: Iterable[object] | None = None,
    up_shock_amounts: Iterable[object] | None = None,
    down_shock_amounts: Iterable[object] | None = None,
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None = None,
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None = None,
    copy_arrays: bool = True,
) -> SbmSensitivityBatch:
    """Build a GIRR delta batch from columnar arrays owned by an adapter."""

    return build_sbm_batch_from_columns(
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        sensitivity_ids=sensitivity_ids,
        source_row_ids=source_row_ids,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        risk_classes=risk_classes,
        risk_measures=risk_measures,
        buckets=buckets,
        risk_factors=risk_factors,
        amounts=amounts,
        amount_currencies=amount_currencies,
        sign_conventions=sign_conventions,
        tenors=tenors,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        position_ids=position_ids,
        qualifiers=qualifiers,
        option_tenors=option_tenors,
        liquidity_horizon_days=liquidity_horizon_days,
        maturities=maturities,
        up_shock_amounts=up_shock_amounts,
        down_shock_amounts=down_shock_amounts,
        source_column_maps=source_column_maps,
        mapping_citation_ids=mapping_citation_ids,
        copy_arrays=copy_arrays,
    )


def build_girr_vega_batch_from_columns(
    *,
    sensitivity_ids: Iterable[object],
    source_row_ids: Iterable[object],
    desk_ids: Iterable[object],
    legal_entities: Iterable[object],
    risk_classes: Iterable[object],
    risk_measures: Iterable[object],
    buckets: Iterable[object],
    risk_factors: Iterable[object],
    amounts: Iterable[object],
    amount_currencies: Iterable[object],
    sign_conventions: Iterable[object],
    tenors: Iterable[object],
    option_tenors: Iterable[object],
    lineage_source_systems: Iterable[object],
    lineage_source_files: Iterable[object],
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    position_ids: Iterable[object] | None = None,
    qualifiers: Iterable[object] | None = None,
    liquidity_horizon_days: Iterable[object] | None = None,
    maturities: Iterable[object] | None = None,
    up_shock_amounts: Iterable[object] | None = None,
    down_shock_amounts: Iterable[object] | None = None,
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None = None,
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None = None,
    copy_arrays: bool = True,
) -> SbmSensitivityBatch:
    """Build a GIRR vega batch from columnar arrays owned by an adapter."""

    return build_sbm_batch_from_columns(
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.VEGA,
        sensitivity_ids=sensitivity_ids,
        source_row_ids=source_row_ids,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        risk_classes=risk_classes,
        risk_measures=risk_measures,
        buckets=buckets,
        risk_factors=risk_factors,
        amounts=amounts,
        amount_currencies=amount_currencies,
        sign_conventions=sign_conventions,
        tenors=tenors,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        position_ids=position_ids,
        qualifiers=qualifiers,
        option_tenors=option_tenors,
        liquidity_horizon_days=liquidity_horizon_days,
        maturities=maturities,
        up_shock_amounts=up_shock_amounts,
        down_shock_amounts=down_shock_amounts,
        source_column_maps=source_column_maps,
        mapping_citation_ids=mapping_citation_ids,
        copy_arrays=copy_arrays,
    )


def build_girr_curvature_batch_from_columns(
    *,
    sensitivity_ids: Iterable[object],
    source_row_ids: Iterable[object],
    desk_ids: Iterable[object],
    legal_entities: Iterable[object],
    risk_classes: Iterable[object],
    risk_measures: Iterable[object],
    buckets: Iterable[object],
    risk_factors: Iterable[object],
    amounts: Iterable[object],
    amount_currencies: Iterable[object],
    sign_conventions: Iterable[object],
    tenors: Iterable[object],
    up_shock_amounts: Iterable[object],
    down_shock_amounts: Iterable[object],
    lineage_source_systems: Iterable[object],
    lineage_source_files: Iterable[object],
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    position_ids: Iterable[object] | None = None,
    qualifiers: Iterable[object] | None = None,
    option_tenors: Iterable[object] | None = None,
    liquidity_horizon_days: Iterable[object] | None = None,
    maturities: Iterable[object] | None = None,
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None = None,
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None = None,
    copy_arrays: bool = True,
) -> SbmSensitivityBatch:
    """
    Build a GIRR curvature batch from columnar arrays owned by an adapter.

    The curvature contract intentionally keeps ``up_shock_amounts`` and
    ``down_shock_amounts`` as separate arrays at the batch boundary.
    """

    return build_sbm_batch_from_columns(
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.CURVATURE,
        sensitivity_ids=sensitivity_ids,
        source_row_ids=source_row_ids,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        risk_classes=risk_classes,
        risk_measures=risk_measures,
        buckets=buckets,
        risk_factors=risk_factors,
        amounts=amounts,
        amount_currencies=amount_currencies,
        sign_conventions=sign_conventions,
        tenors=tenors,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        position_ids=position_ids,
        qualifiers=qualifiers,
        option_tenors=option_tenors,
        liquidity_horizon_days=liquidity_horizon_days,
        maturities=maturities,
        up_shock_amounts=up_shock_amounts,
        down_shock_amounts=down_shock_amounts,
        source_column_maps=source_column_maps,
        mapping_citation_ids=mapping_citation_ids,
        copy_arrays=copy_arrays,
    )


def build_fx_delta_batch_from_columns(
    *,
    sensitivity_ids: Iterable[object],
    source_row_ids: Iterable[object],
    desk_ids: Iterable[object],
    legal_entities: Iterable[object],
    risk_classes: Iterable[object],
    risk_measures: Iterable[object],
    buckets: Iterable[object],
    risk_factors: Iterable[object],
    amounts: Iterable[object],
    amount_currencies: Iterable[object],
    sign_conventions: Iterable[object],
    tenors: Iterable[object],
    lineage_source_systems: Iterable[object],
    lineage_source_files: Iterable[object],
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    position_ids: Iterable[object] | None = None,
    qualifiers: Iterable[object] | None = None,
    option_tenors: Iterable[object] | None = None,
    liquidity_horizon_days: Iterable[object] | None = None,
    maturities: Iterable[object] | None = None,
    up_shock_amounts: Iterable[object] | None = None,
    down_shock_amounts: Iterable[object] | None = None,
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None = None,
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None = None,
    copy_arrays: bool = True,
) -> SbmSensitivityBatch:
    """Build an FX delta batch from columnar arrays owned by an adapter."""

    return build_sbm_batch_from_columns(
        expected_risk_class=SbmRiskClass.FX,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        sensitivity_ids=sensitivity_ids,
        source_row_ids=source_row_ids,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        risk_classes=risk_classes,
        risk_measures=risk_measures,
        buckets=buckets,
        risk_factors=risk_factors,
        amounts=amounts,
        amount_currencies=amount_currencies,
        sign_conventions=sign_conventions,
        tenors=tenors,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        position_ids=position_ids,
        qualifiers=qualifiers,
        option_tenors=option_tenors,
        liquidity_horizon_days=liquidity_horizon_days,
        maturities=maturities,
        up_shock_amounts=up_shock_amounts,
        down_shock_amounts=down_shock_amounts,
        source_column_maps=source_column_maps,
        mapping_citation_ids=mapping_citation_ids,
        copy_arrays=copy_arrays,
    )


def build_equity_delta_batch_from_columns(
    *,
    sensitivity_ids: Iterable[object],
    source_row_ids: Iterable[object],
    desk_ids: Iterable[object],
    legal_entities: Iterable[object],
    risk_classes: Iterable[object],
    risk_measures: Iterable[object],
    buckets: Iterable[object],
    risk_factors: Iterable[object],
    amounts: Iterable[object],
    amount_currencies: Iterable[object],
    sign_conventions: Iterable[object],
    tenors: Iterable[object],
    lineage_source_systems: Iterable[object],
    lineage_source_files: Iterable[object],
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    position_ids: Iterable[object] | None = None,
    qualifiers: Iterable[object] | None = None,
    option_tenors: Iterable[object] | None = None,
    liquidity_horizon_days: Iterable[object] | None = None,
    maturities: Iterable[object] | None = None,
    up_shock_amounts: Iterable[object] | None = None,
    down_shock_amounts: Iterable[object] | None = None,
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None = None,
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None = None,
    copy_arrays: bool = True,
) -> SbmSensitivityBatch:
    """Build an equity delta batch from columnar arrays owned by an adapter."""

    return build_sbm_batch_from_columns(
        expected_risk_class=SbmRiskClass.EQUITY,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        sensitivity_ids=sensitivity_ids,
        source_row_ids=source_row_ids,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        risk_classes=risk_classes,
        risk_measures=risk_measures,
        buckets=buckets,
        risk_factors=risk_factors,
        amounts=amounts,
        amount_currencies=amount_currencies,
        sign_conventions=sign_conventions,
        tenors=tenors,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        position_ids=position_ids,
        qualifiers=qualifiers,
        option_tenors=option_tenors,
        liquidity_horizon_days=liquidity_horizon_days,
        maturities=maturities,
        up_shock_amounts=up_shock_amounts,
        down_shock_amounts=down_shock_amounts,
        source_column_maps=source_column_maps,
        mapping_citation_ids=mapping_citation_ids,
        copy_arrays=copy_arrays,
    )


def build_commodity_delta_batch_from_columns(
    *,
    sensitivity_ids: Iterable[object],
    source_row_ids: Iterable[object],
    desk_ids: Iterable[object],
    legal_entities: Iterable[object],
    risk_classes: Iterable[object],
    risk_measures: Iterable[object],
    buckets: Iterable[object],
    risk_factors: Iterable[object],
    amounts: Iterable[object],
    amount_currencies: Iterable[object],
    sign_conventions: Iterable[object],
    tenors: Iterable[object],
    lineage_source_systems: Iterable[object],
    lineage_source_files: Iterable[object],
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    position_ids: Iterable[object] | None = None,
    qualifiers: Iterable[object] | None = None,
    option_tenors: Iterable[object] | None = None,
    liquidity_horizon_days: Iterable[object] | None = None,
    maturities: Iterable[object] | None = None,
    up_shock_amounts: Iterable[object] | None = None,
    down_shock_amounts: Iterable[object] | None = None,
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None = None,
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None = None,
    copy_arrays: bool = True,
) -> SbmSensitivityBatch:
    """Build a commodity delta batch from columnar arrays owned by an adapter."""

    return build_sbm_batch_from_columns(
        expected_risk_class=SbmRiskClass.COMMODITY,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        sensitivity_ids=sensitivity_ids,
        source_row_ids=source_row_ids,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        risk_classes=risk_classes,
        risk_measures=risk_measures,
        buckets=buckets,
        risk_factors=risk_factors,
        amounts=amounts,
        amount_currencies=amount_currencies,
        sign_conventions=sign_conventions,
        tenors=tenors,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        position_ids=position_ids,
        qualifiers=qualifiers,
        option_tenors=option_tenors,
        liquidity_horizon_days=liquidity_horizon_days,
        maturities=maturities,
        up_shock_amounts=up_shock_amounts,
        down_shock_amounts=down_shock_amounts,
        source_column_maps=source_column_maps,
        mapping_citation_ids=mapping_citation_ids,
        copy_arrays=copy_arrays,
    )


def build_csr_nonsec_delta_batch_from_columns(
    *,
    sensitivity_ids: Iterable[object],
    source_row_ids: Iterable[object],
    desk_ids: Iterable[object],
    legal_entities: Iterable[object],
    risk_classes: Iterable[object],
    risk_measures: Iterable[object],
    buckets: Iterable[object],
    risk_factors: Iterable[object],
    amounts: Iterable[object],
    amount_currencies: Iterable[object],
    sign_conventions: Iterable[object],
    tenors: Iterable[object],
    lineage_source_systems: Iterable[object],
    lineage_source_files: Iterable[object],
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    position_ids: Iterable[object] | None = None,
    qualifiers: Iterable[object] | None = None,
    option_tenors: Iterable[object] | None = None,
    liquidity_horizon_days: Iterable[object] | None = None,
    maturities: Iterable[object] | None = None,
    up_shock_amounts: Iterable[object] | None = None,
    down_shock_amounts: Iterable[object] | None = None,
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None = None,
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None = None,
    copy_arrays: bool = True,
) -> SbmSensitivityBatch:
    """Build a CSR non-securitisation delta batch from columnar adapter arrays."""

    return build_sbm_batch_from_columns(
        expected_risk_class=SbmRiskClass.CSR_NONSEC,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        sensitivity_ids=sensitivity_ids,
        source_row_ids=source_row_ids,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        risk_classes=risk_classes,
        risk_measures=risk_measures,
        buckets=buckets,
        risk_factors=risk_factors,
        amounts=amounts,
        amount_currencies=amount_currencies,
        sign_conventions=sign_conventions,
        tenors=tenors,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        position_ids=position_ids,
        qualifiers=qualifiers,
        option_tenors=option_tenors,
        liquidity_horizon_days=liquidity_horizon_days,
        maturities=maturities,
        up_shock_amounts=up_shock_amounts,
        down_shock_amounts=down_shock_amounts,
        source_column_maps=source_column_maps,
        mapping_citation_ids=mapping_citation_ids,
        copy_arrays=copy_arrays,
    )


def build_csr_sec_nonctp_delta_batch_from_columns(
    *,
    sensitivity_ids: Iterable[object],
    source_row_ids: Iterable[object],
    desk_ids: Iterable[object],
    legal_entities: Iterable[object],
    risk_classes: Iterable[object],
    risk_measures: Iterable[object],
    buckets: Iterable[object],
    risk_factors: Iterable[object],
    amounts: Iterable[object],
    amount_currencies: Iterable[object],
    sign_conventions: Iterable[object],
    tenors: Iterable[object],
    lineage_source_systems: Iterable[object],
    lineage_source_files: Iterable[object],
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    position_ids: Iterable[object] | None = None,
    qualifiers: Iterable[object] | None = None,
    option_tenors: Iterable[object] | None = None,
    liquidity_horizon_days: Iterable[object] | None = None,
    maturities: Iterable[object] | None = None,
    up_shock_amounts: Iterable[object] | None = None,
    down_shock_amounts: Iterable[object] | None = None,
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None = None,
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None = None,
    copy_arrays: bool = True,
) -> SbmSensitivityBatch:
    """Build a CSR securitisation non-CTP delta batch from columnar adapter arrays."""

    return build_sbm_batch_from_columns(
        expected_risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        sensitivity_ids=sensitivity_ids,
        source_row_ids=source_row_ids,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        risk_classes=risk_classes,
        risk_measures=risk_measures,
        buckets=buckets,
        risk_factors=risk_factors,
        amounts=amounts,
        amount_currencies=amount_currencies,
        sign_conventions=sign_conventions,
        tenors=tenors,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        position_ids=position_ids,
        qualifiers=qualifiers,
        option_tenors=option_tenors,
        liquidity_horizon_days=liquidity_horizon_days,
        maturities=maturities,
        up_shock_amounts=up_shock_amounts,
        down_shock_amounts=down_shock_amounts,
        source_column_maps=source_column_maps,
        mapping_citation_ids=mapping_citation_ids,
        copy_arrays=copy_arrays,
    )


def build_csr_sec_ctp_delta_batch_from_columns(
    *,
    sensitivity_ids: Iterable[object],
    source_row_ids: Iterable[object],
    desk_ids: Iterable[object],
    legal_entities: Iterable[object],
    risk_classes: Iterable[object],
    risk_measures: Iterable[object],
    buckets: Iterable[object],
    risk_factors: Iterable[object],
    amounts: Iterable[object],
    amount_currencies: Iterable[object],
    sign_conventions: Iterable[object],
    tenors: Iterable[object],
    lineage_source_systems: Iterable[object],
    lineage_source_files: Iterable[object],
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    position_ids: Iterable[object] | None = None,
    qualifiers: Iterable[object] | None = None,
    option_tenors: Iterable[object] | None = None,
    liquidity_horizon_days: Iterable[object] | None = None,
    maturities: Iterable[object] | None = None,
    up_shock_amounts: Iterable[object] | None = None,
    down_shock_amounts: Iterable[object] | None = None,
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None = None,
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None = None,
    copy_arrays: bool = True,
) -> SbmSensitivityBatch:
    """Build a CSR securitisation CTP delta batch from columnar adapter arrays."""

    return build_sbm_batch_from_columns(
        expected_risk_class=SbmRiskClass.CSR_SEC_CTP,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        sensitivity_ids=sensitivity_ids,
        source_row_ids=source_row_ids,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        risk_classes=risk_classes,
        risk_measures=risk_measures,
        buckets=buckets,
        risk_factors=risk_factors,
        amounts=amounts,
        amount_currencies=amount_currencies,
        sign_conventions=sign_conventions,
        tenors=tenors,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        position_ids=position_ids,
        qualifiers=qualifiers,
        option_tenors=option_tenors,
        liquidity_horizon_days=liquidity_horizon_days,
        maturities=maturities,
        up_shock_amounts=up_shock_amounts,
        down_shock_amounts=down_shock_amounts,
        source_column_maps=source_column_maps,
        mapping_citation_ids=mapping_citation_ids,
        copy_arrays=copy_arrays,
    )


def input_hash_for_sbm_batch(batch: SbmSensitivityBatch) -> str:
    """Return the row-equivalent deterministic input hash for a homogeneous batch."""

    return _hash_payload({"sensitivities": list(_sensitivity_payloads_from_batch(batch))})


def input_hash_for_sbm_batches(batches: object) -> str:
    """Return the row-equivalent deterministic input hash for batch portfolios."""

    validated = _coerce_batch_sequence(batches)
    return _hash_payload(
        {
            "sensitivities": [
                payload
                for batch in validated
                for payload in _sensitivity_payloads_from_batch(batch)
            ]
        }
    )


def concatenate_sbm_batches(batches: object) -> SbmSensitivityBatch:
    """Concatenate homogeneous SBM batches without materialising row dataclasses."""

    validated = _coerce_batch_sequence(batches)
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
        source_column_maps=_concat_source_column_maps(validated),
        mapping_citation_ids=_concat_mapping_citation_ids(validated),
        copy_arrays=False,
    )
    return replace(
        combined,
        accepted_row_dataclasses_materialized=sum(
            batch.accepted_row_dataclasses_materialized for batch in validated
        ),
    )


def input_hash_for_girr_delta_batch(batch: SbmSensitivityBatch) -> str:
    """Return the row-equivalent deterministic input hash for a GIRR delta batch."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="GIRR delta",
    )
    return input_hash_for_sbm_batch(batch)


def input_hash_for_girr_vega_batch(batch: SbmSensitivityBatch) -> str:
    """Return the row-equivalent deterministic input hash for a GIRR vega batch."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.VEGA,
        label="GIRR vega",
    )
    return input_hash_for_sbm_batch(batch)


def input_hash_for_girr_curvature_batch(batch: SbmSensitivityBatch) -> str:
    """Return the row-equivalent deterministic input hash for a GIRR curvature batch."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.CURVATURE,
        label="GIRR curvature",
    )
    return input_hash_for_sbm_batch(batch)


def input_hash_for_fx_delta_batch(batch: SbmSensitivityBatch) -> str:
    """Return the row-equivalent deterministic input hash for an FX delta batch."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.FX,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="FX delta",
    )
    return input_hash_for_sbm_batch(batch)


def input_hash_for_equity_delta_batch(batch: SbmSensitivityBatch) -> str:
    """Return the row-equivalent deterministic input hash for an equity delta batch."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.EQUITY,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="equity delta",
    )
    return input_hash_for_sbm_batch(batch)


def input_hash_for_commodity_delta_batch(batch: SbmSensitivityBatch) -> str:
    """Return the row-equivalent deterministic input hash for a commodity delta batch."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.COMMODITY,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="commodity delta",
    )
    return input_hash_for_sbm_batch(batch)


def input_hash_for_csr_nonsec_delta_batch(batch: SbmSensitivityBatch) -> str:
    """Return the row-equivalent deterministic input hash for a CSR non-sec delta batch."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.CSR_NONSEC,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="CSR non-securitisation delta",
    )
    return input_hash_for_sbm_batch(batch)


def input_hash_for_csr_sec_nonctp_delta_batch(batch: SbmSensitivityBatch) -> str:
    """Return the row-equivalent deterministic input hash for a CSR sec non-CTP batch."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="CSR securitisation non-CTP delta",
    )
    return input_hash_for_sbm_batch(batch)


def input_hash_for_csr_sec_ctp_delta_batch(batch: SbmSensitivityBatch) -> str:
    """Return the row-equivalent deterministic input hash for a CSR sec CTP batch."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.CSR_SEC_CTP,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="CSR securitisation CTP delta",
    )
    return input_hash_for_sbm_batch(batch)


def sorted_sbm_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in stable risk-class, bucket, factor, and id order."""

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
    """Return indices in the same stable order used by row-wise GIRR delta weighting."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="GIRR delta",
    )
    return sorted_sbm_batch_indices(batch)


def sorted_girr_vega_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise GIRR vega weighting."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.VEGA,
        label="GIRR vega",
    )
    return sorted_sbm_batch_indices(batch)


def sorted_girr_curvature_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise GIRR curvature helpers."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.CURVATURE,
        label="GIRR curvature",
    )
    return sorted_sbm_batch_indices(batch)


def sorted_curvature_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise curvature helpers."""

    if batch.row_count == 0:
        raise SbmInputError("curvature batch must not be empty", field="batch")
    if batch.risk_measure is not SbmRiskMeasure.CURVATURE:
        raise SbmInputError("curvature batch only accepts CURVATURE sensitivities")
    return sorted_sbm_batch_indices(batch)


def sorted_fx_delta_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise FX delta weighting."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.FX,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="FX delta",
    )
    return sorted_sbm_batch_indices(batch)


def sorted_equity_delta_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise equity delta weighting."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.EQUITY,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="equity delta",
    )
    return sorted_sbm_batch_indices(batch)


def sorted_commodity_delta_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise commodity delta weighting."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.COMMODITY,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="commodity delta",
    )
    return sorted_sbm_batch_indices(batch)


def sorted_csr_nonsec_delta_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise CSR non-sec weighting."""

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
    """Return indices in the stable order used by row-wise CSR sec non-CTP weighting."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="CSR securitisation non-CTP delta",
    )
    return sorted_sbm_batch_indices(batch)


def sorted_csr_sec_ctp_delta_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise CSR sec CTP weighting."""

    _require_batch_path(
        batch,
        expected_risk_class=SbmRiskClass.CSR_SEC_CTP,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        label="CSR securitisation CTP delta",
    )
    return sorted_sbm_batch_indices(batch)


def _batch_text_by_id(
    batch: SbmSensitivityBatch,
    values: npt.NDArray[np.object_] | None,
    *,
    field: str,
) -> Mapping[str, str]:
    if values is None:
        raise SbmInputError(f"{field} is required", field=field)
    return {
        str(batch.sensitivity_ids[row_index]): str(values[row_index])
        for row_index in range(batch.row_count)
    }


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


def _sensitivity_payloads_from_batch(batch: SbmSensitivityBatch) -> Iterable[dict[str, object]]:
    for row_index in range(batch.row_count):
        sensitivity_id = _str_at(batch.sensitivity_ids, row_index)
        source_row_id = _str_at(batch.source_row_ids, row_index)
        payload: dict[str, object] = {
            "sensitivity_id": sensitivity_id,
            "source_row_id": source_row_id,
            "desk_id": _str_at(batch.desk_ids, row_index),
            "legal_entity": _str_at(batch.legal_entities, row_index),
            "risk_class": _str_at(batch.risk_classes, row_index),
            "risk_measure": _str_at(batch.risk_measures, row_index),
            "bucket": _str_at(batch.buckets, row_index),
            "risk_factor": _str_at(batch.risk_factors, row_index),
            "amount": float(batch.amounts[row_index]),
            "amount_currency": _str_at(batch.amount_currencies, row_index),
            "sign_convention": _str_at(batch.sign_conventions, row_index),
            "lineage": {
                "source_system": _str_at(batch.lineage_source_systems, row_index),
                "source_file": _str_at(batch.lineage_source_files, row_index),
                "source_row_id": source_row_id,
                "source_column_map": [
                    list(pair) for pair in _source_column_map_at(batch, row_index)
                ],
            },
            "mapping_citation_ids": list(_mapping_citation_ids_at(batch, row_index)),
        }
        _add_optional_payload_field(payload, "position_id", batch.position_ids, row_index)
        _add_optional_payload_field(payload, "qualifier", batch.qualifiers, row_index)
        _add_optional_payload_field(payload, "tenor", batch.tenors, row_index)
        _add_optional_payload_field(payload, "option_tenor", batch.option_tenors, row_index)
        _add_optional_payload_field(
            payload,
            "liquidity_horizon_days",
            batch.liquidity_horizon_days,
            row_index,
        )
        _add_optional_payload_field(payload, "maturity", batch.maturities, row_index)
        _add_optional_payload_field(payload, "up_shock_amount", batch.up_shock_amounts, row_index)
        _add_optional_payload_field(
            payload,
            "down_shock_amount",
            batch.down_shock_amounts,
            row_index,
        )
        yield payload


def _add_optional_payload_field(
    payload: dict[str, object],
    field_name: str,
    values: ObjectArray | None,
    row_index: int,
) -> None:
    if values is None:
        return
    value = values[row_index]
    if value is None:
        return
    if field_name in {"liquidity_horizon_days"}:
        payload[field_name] = int(value)
    elif field_name in {"up_shock_amount", "down_shock_amount"}:
        payload[field_name] = float(value)
    else:
        payload[field_name] = cast(str, value)


def _source_column_map_at(
    batch: SbmSensitivityBatch,
    row_index: int,
) -> tuple[tuple[str, str], ...]:
    if batch.source_column_maps is None:
        return ()
    return batch.source_column_maps[row_index]


def _mapping_citation_ids_at(batch: SbmSensitivityBatch, row_index: int) -> tuple[str, ...]:
    if batch.mapping_citation_ids is None:
        return ()
    return batch.mapping_citation_ids[row_index]


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


def _validate_homogeneous_batch_arrays(
    arrays: Mapping[str, ObjectArray],
    amount_array: FloatArray,
    *,
    expected_risk_class: SbmRiskClass,
    expected_risk_measure: SbmRiskMeasure,
    optional_arrays: Mapping[str, ObjectArray | None],
) -> None:
    sensitivity_ids = arrays["sensitivity_ids"]
    for field_name, column in arrays.items():
        if field_name in _CORE_REQUIRED_TEXT_FIELDS:
            _validate_required_text_column(column, field_name, sensitivity_ids=sensitivity_ids)
        else:
            _validate_optional_text_column(column, field_name, sensitivity_ids=sensitivity_ids)
    _validate_unique_sensitivity_ids(sensitivity_ids)
    _validate_constant_column(
        arrays["risk_classes"],
        expected=expected_risk_class.value,
        field="risk_class",
        message=f"batch only accepts {expected_risk_class.value} sensitivities",
        sensitivity_ids=sensitivity_ids,
    )
    _validate_constant_column(
        arrays["risk_measures"],
        expected=expected_risk_measure.value,
        field="risk_measure",
        message=f"batch only accepts {expected_risk_measure.value} sensitivities",
        sensitivity_ids=sensitivity_ids,
    )
    path = (expected_risk_class, expected_risk_measure)
    if path in _TENOR_REQUIRED_PATHS:
        _validate_required_text_column(
            arrays["tenors"],
            "tenor",
            sensitivity_ids=sensitivity_ids,
        )

    option_tenors = optional_arrays["option_tenors"]
    if path in _OPTION_TENOR_REQUIRED_PATHS:
        if option_tenors is None:
            raise SbmInputError("option_tenor is required", field="option_tenor")
        _validate_required_text_column(
            option_tenors,
            "option_tenor",
            sensitivity_ids=sensitivity_ids,
        )
    elif option_tenors is not None:
        _validate_optional_text_column(
            option_tenors,
            "option_tenor",
            sensitivity_ids=sensitivity_ids,
        )

    qualifiers = optional_arrays["qualifiers"]
    if _qualifier_required_for_path(expected_risk_class, expected_risk_measure):
        if qualifiers is None:
            raise SbmInputError("qualifier is required", field="qualifier")
        _validate_required_text_column(
            qualifiers,
            "qualifier",
            sensitivity_ids=sensitivity_ids,
        )
    elif qualifiers is not None:
        _validate_optional_text_column(qualifiers, "qualifier", sensitivity_ids=sensitivity_ids)

    if path in _CURVATURE_REQUIRED_PATHS:
        for optional_field, field_name in (
            ("up_shock_amounts", "up_shock_amount"),
            ("down_shock_amounts", "down_shock_amount"),
        ):
            shock_values = optional_arrays[optional_field]
            if shock_values is None:
                raise SbmInputError(
                    "curvature inputs require up_shock_amount and down_shock_amount",
                    field=field_name,
                )
            _validate_required_float_column(
                shock_values,
                field_name,
                sensitivity_ids=sensitivity_ids,
            )

    for amount_currency in np.unique(arrays["amount_currencies"]):
        normalise_currency_code(cast(str, amount_currency))
    for sign_convention in np.unique(arrays["sign_conventions"]):
        coerce_sign_convention(sign_convention)
    if not np.all(np.isfinite(amount_array)):
        raise SbmInputError("value must be finite", field="amount")


def _qualifier_required_for_path(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> bool:
    if risk_class is SbmRiskClass.COMMODITY and risk_measure is SbmRiskMeasure.VEGA:
        return False
    return risk_class in _QUALIFIER_REQUIRED_RISK_CLASSES


def _normalise_risk_class_array(
    values: ObjectArray,
    *,
    sensitivity_ids: ObjectArray,
) -> ObjectArray:
    items: list[str] = []
    for row_index, value in enumerate(values):
        try:
            items.append(coerce_risk_class(cast(SbmRiskClass | str, value)).value)
        except SbmInputError as exc:
            raise SbmInputError(
                str(exc),
                field="risk_class",
                sensitivity_id=_sensitivity_id_for_index(sensitivity_ids, row_index),
            ) from exc
    normalised = np.asarray(tuple(items), dtype=object)
    _require_common_length(int(values.shape[0]), {"risk_classes": normalised})
    _freeze_array(normalised)
    return cast(ObjectArray, normalised)


def _normalise_risk_measure_array(
    values: ObjectArray,
    *,
    sensitivity_ids: ObjectArray,
) -> ObjectArray:
    items: list[str] = []
    for row_index, value in enumerate(values):
        try:
            items.append(coerce_risk_measure(cast(SbmRiskMeasure | str, value)).value)
        except SbmInputError as exc:
            raise SbmInputError(
                str(exc),
                field="risk_measure",
                sensitivity_id=_sensitivity_id_for_index(sensitivity_ids, row_index),
            ) from exc
    normalised = np.asarray(tuple(items), dtype=object)
    _require_common_length(int(values.shape[0]), {"risk_measures": normalised})
    _freeze_array(normalised)
    return cast(ObjectArray, normalised)


def _normalise_sign_convention_array(
    values: ObjectArray,
    *,
    sensitivity_ids: ObjectArray,
) -> ObjectArray:
    items: list[str] = []
    for row_index, value in enumerate(values):
        try:
            items.append(coerce_sign_convention(value).value)
        except SbmInputError as exc:
            raise SbmInputError(
                str(exc),
                field="sign_convention",
                sensitivity_id=_sensitivity_id_for_index(sensitivity_ids, row_index),
            ) from exc
    normalised = np.asarray(tuple(items), dtype=object)
    _require_common_length(int(values.shape[0]), {"sign_conventions": normalised})
    _freeze_array(normalised)
    return cast(ObjectArray, normalised)


def _validate_source_column_maps(
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None,
    row_count: int,
) -> None:
    if source_column_maps is None:
        return
    if len(source_column_maps) != row_count:
        raise SbmInputError(
            "source_column_maps length must match batch row count",
            field="lineage.source_column_map",
        )
    for row_map in source_column_maps:
        if not isinstance(row_map, tuple | list):
            raise SbmInputError(
                "source column map rows must be field-pair sequences",
                field="lineage.source_column_map",
            )
        for mapping in row_map:
            if not isinstance(mapping, tuple | list) or len(mapping) != 2:
                raise SbmInputError(
                    "source column map entries must be field pairs",
                    field="lineage.source_column_map",
                )
            source_field, canonical_field = mapping
            if not isinstance(source_field, str) or not source_field.strip():
                raise SbmInputError(
                    "source column map entries require non-empty source fields",
                    field="lineage.source_column_map",
                )
            if not isinstance(canonical_field, str) or not canonical_field.strip():
                raise SbmInputError(
                    "source column map entries require non-empty canonical fields",
                    field="lineage.source_column_map",
                )


def _validate_mapping_citations(
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None,
    row_count: int,
) -> None:
    if mapping_citation_ids is None:
        return
    if len(mapping_citation_ids) != row_count:
        raise SbmInputError(
            "mapping_citation_ids length must match batch row count",
            field="mapping_citation_ids",
        )
    for row_citations in mapping_citation_ids:
        if not isinstance(row_citations, tuple | list):
            raise SbmInputError(
                "mapping_citation_ids rows must be citation-id sequences",
                field="mapping_citation_ids",
            )
        for citation_id in row_citations:
            if not isinstance(citation_id, str) or not citation_id.strip():
                raise SbmInputError(
                    "mapping citation ids must be non-empty strings",
                    field="mapping_citation_ids",
                )


def _coerce_batch_sequence(batches: object) -> tuple[SbmSensitivityBatch, ...]:
    if isinstance(batches, SbmSensitivityBatch):
        return (batches,)
    try:
        candidates: tuple[object, ...] = tuple(batches)  # type: ignore[arg-type]
    except TypeError as exc:
        raise SbmInputError("batches must be an iterable of SbmSensitivityBatch objects") from exc
    if not candidates:
        raise SbmInputError("batches must not be empty", field="batches")
    for candidate in candidates:
        if not isinstance(candidate, SbmSensitivityBatch):
            raise SbmInputError("batches must contain only SbmSensitivityBatch objects")
    return cast(tuple[SbmSensitivityBatch, ...], candidates)


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


def _object_array(values: Iterable[object], field: str, *, copy: bool) -> ObjectArray:
    if isinstance(values, np.ndarray):
        array = values.astype(object, copy=copy)
    else:
        array = np.asarray(tuple(values), dtype=object)
    if array.ndim != 1:
        raise SbmInputError("column arrays must be one-dimensional", field=field)
    _freeze_array(array)
    return cast(ObjectArray, array)


def _float_array(values: Iterable[object], field: str, *, copy: bool) -> FloatArray:
    try:
        if isinstance(values, np.ndarray):
            array = values.astype(np.float64, copy=copy)
        else:
            array = np.asarray(tuple(values), dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise SbmInputError("value must be numeric", field=field) from exc
    if array.ndim != 1:
        raise SbmInputError("column arrays must be one-dimensional", field=field)
    if not np.all(np.isfinite(array)):
        raise SbmInputError("value must be finite", field=field)
    _freeze_array(array)
    return cast(FloatArray, array)


def _optional_object_array(
    values: Iterable[object] | None,
    field: str,
    row_count: int,
    copy: bool,
) -> ObjectArray | None:
    if values is None:
        return None
    array = _object_array(values, field, copy=copy)
    if int(array.shape[0]) != row_count:
        raise SbmInputError(f"{field} length must match batch row count", field=field)
    if not any(value is not None for value in array):
        return None
    if field in {"up_shock_amount", "down_shock_amount"}:
        _validate_optional_float_column(array, field)
    return array


def _require_common_length(row_count: int, arrays: Mapping[str, ObjectArray]) -> None:
    for field_name, array in arrays.items():
        if int(array.shape[0]) != row_count:
            raise SbmInputError(
                f"{field_name} length must match amount length",
                field=field_name,
            )


def _require_non_empty(values: Sequence[SbmSensitivity]) -> None:
    _require_non_empty_length(len(values))


def _require_non_empty_length(row_count: int) -> None:
    if row_count == 0:
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


def _validate_required_text_column(
    values: ObjectArray,
    field: str,
    *,
    sensitivity_ids: ObjectArray,
) -> None:
    invalid_mask = np.fromiter(
        (not isinstance(value, str) or not value.strip() for value in values),
        dtype=np.bool_,
        count=int(values.shape[0]),
    )
    if np.any(invalid_mask):
        row_index = int(np.flatnonzero(invalid_mask)[0])
        raise SbmInputError(
            "non-empty text is required",
            field=field,
            sensitivity_id=_sensitivity_id_for_index(sensitivity_ids, row_index),
        )


def _validate_optional_text_column(
    values: ObjectArray,
    field: str,
    *,
    sensitivity_ids: ObjectArray,
) -> None:
    invalid_mask = np.fromiter(
        (value is not None and not isinstance(value, str) for value in values),
        dtype=np.bool_,
        count=int(values.shape[0]),
    )
    if np.any(invalid_mask):
        row_index = int(np.flatnonzero(invalid_mask)[0])
        raise SbmInputError(
            "text is required when present",
            field=field,
            sensitivity_id=_sensitivity_id_for_index(sensitivity_ids, row_index),
        )


def _validate_unique_sensitivity_ids(sensitivity_ids: ObjectArray) -> None:
    unique_ids, counts = np.unique(sensitivity_ids, return_counts=True)
    duplicate_mask = counts > 1
    if not np.any(duplicate_mask):
        return
    duplicate_id = cast(str, unique_ids[int(np.flatnonzero(duplicate_mask)[0])])
    raise SbmInputError(
        "duplicate sensitivity id",
        field="sensitivity_id",
        sensitivity_id=duplicate_id,
    )


def _validate_constant_column(
    values: ObjectArray,
    *,
    expected: str,
    field: str,
    message: str,
    sensitivity_ids: ObjectArray,
) -> None:
    invalid_mask = values != expected
    if not np.any(invalid_mask):
        return
    row_index = int(np.flatnonzero(invalid_mask)[0])
    if field == "risk_class":
        coerce_risk_class(values[row_index])
    if field == "risk_measure":
        coerce_risk_measure(values[row_index])
    raise SbmInputError(
        message,
        field=field,
        sensitivity_id=_sensitivity_id_for_index(sensitivity_ids, row_index),
    )


def _validate_optional_float_column(values: ObjectArray, field: str) -> None:
    for value in values:
        if value is None:
            continue
        try:
            float_value = float(value)
        except (TypeError, ValueError) as exc:
            raise SbmInputError("value must be numeric", field=field) from exc
        if not np.isfinite(float_value):
            raise SbmInputError("value must be finite", field=field)


def _validate_required_float_column(
    values: ObjectArray,
    field: str,
    *,
    sensitivity_ids: ObjectArray,
) -> None:
    for row_index, value in enumerate(values):
        if value is None:
            raise SbmInputError(
                "curvature inputs require up_shock_amount and down_shock_amount",
                field=field,
                sensitivity_id=_sensitivity_id_for_index(sensitivity_ids, row_index),
            )
        try:
            float_value = float(value)
        except (TypeError, ValueError) as exc:
            raise SbmInputError(
                "value must be numeric",
                field=field,
                sensitivity_id=_sensitivity_id_for_index(sensitivity_ids, row_index),
            ) from exc
        if not np.isfinite(float_value):
            raise SbmInputError(
                "value must be finite",
                field=field,
                sensitivity_id=_sensitivity_id_for_index(sensitivity_ids, row_index),
            )


def _sensitivity_id_for_index(values: ObjectArray, row_index: int) -> str:
    if row_index < int(values.shape[0]) and isinstance(values[row_index], str):
        return cast(str, values[row_index])
    return ""


def _str_at(values: ObjectArray, row_index: int) -> str:
    return cast(str, values[row_index])


def _freeze_array(array: npt.NDArray[Any]) -> None:
    array.setflags(write=False)


__all__ = [
    "SbmSensitivityBatch",
    "build_commodity_curvature_batch_from_sensitivities",
    "build_commodity_delta_batch_from_columns",
    "build_commodity_delta_batch_from_sensitivities",
    "build_commodity_vega_batch_from_sensitivities",
    "build_csr_nonsec_curvature_batch_from_sensitivities",
    "build_csr_nonsec_delta_batch_from_columns",
    "build_csr_nonsec_delta_batch_from_sensitivities",
    "build_csr_nonsec_vega_batch_from_sensitivities",
    "build_csr_sec_ctp_curvature_batch_from_sensitivities",
    "build_csr_sec_ctp_delta_batch_from_columns",
    "build_csr_sec_ctp_delta_batch_from_sensitivities",
    "build_csr_sec_ctp_vega_batch_from_sensitivities",
    "build_csr_sec_nonctp_curvature_batch_from_sensitivities",
    "build_csr_sec_nonctp_delta_batch_from_columns",
    "build_csr_sec_nonctp_delta_batch_from_sensitivities",
    "build_csr_sec_nonctp_vega_batch_from_sensitivities",
    "build_equity_curvature_batch_from_sensitivities",
    "build_equity_delta_batch_from_columns",
    "build_equity_delta_batch_from_sensitivities",
    "build_equity_vega_batch_from_sensitivities",
    "build_fx_curvature_batch_from_sensitivities",
    "build_fx_delta_batch_from_columns",
    "build_fx_delta_batch_from_sensitivities",
    "build_fx_vega_batch_from_sensitivities",
    "build_girr_curvature_batch_from_columns",
    "build_girr_curvature_batch_from_sensitivities",
    "build_girr_delta_batch_from_columns",
    "build_girr_delta_batch_from_sensitivities",
    "build_girr_vega_batch_from_columns",
    "build_girr_vega_batch_from_sensitivities",
    "build_sbm_batch_from_columns",
    "build_sbm_batch_from_sensitivities",
    "concatenate_sbm_batches",
    "input_hash_for_commodity_delta_batch",
    "input_hash_for_csr_nonsec_delta_batch",
    "input_hash_for_csr_sec_ctp_delta_batch",
    "input_hash_for_csr_sec_nonctp_delta_batch",
    "input_hash_for_equity_delta_batch",
    "input_hash_for_fx_delta_batch",
    "input_hash_for_girr_curvature_batch",
    "input_hash_for_girr_delta_batch",
    "input_hash_for_girr_vega_batch",
    "input_hash_for_sbm_batch",
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
