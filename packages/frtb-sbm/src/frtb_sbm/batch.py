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
    """Build a GIRR delta batch from existing row-wise canonical sensitivities.

    This compatibility builder is intentionally outside the high-volume Arrow
    path: it starts from already-materialised ``SbmSensitivity`` rows, then
    converts them to the same batch representation used by Arrow batches.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
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
    """Build a GIRR vega batch from existing row-wise canonical sensitivities.

    This compatibility builder starts from already-materialised
    ``SbmSensitivity`` rows. High-volume Arrow adapters should use
    ``build_girr_vega_batch_from_columns``.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
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
    """Build an FX vega batch from existing row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_sbm_batch_from_columns``.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
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
    """Build an equity vega batch from existing row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_sbm_batch_from_columns``.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
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
    """Build a commodity vega batch from existing row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_sbm_batch_from_columns``.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
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
    """Build a CSR non-securitisation vega batch from row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_sbm_batch_from_columns``.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
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
    """Build a CSR securitisation non-CTP vega batch from row-wise sensitivities.

    High-volume Arrow adapters should use ``build_sbm_batch_from_columns``.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
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
    """Build a CSR securitisation CTP vega batch from row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_sbm_batch_from_columns``.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
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
    """Build a GIRR curvature batch from existing row-wise canonical sensitivities.

    This validates and preserves the separate up/down shock arrays used by the
    curvature contract. Public curvature capital is available through the row
    API; this compatibility builder does not provide a batch capital entrypoint.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
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
    """Build an FX curvature batch from row-wise canonical sensitivities.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

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
    """Build an equity curvature batch from row-wise canonical sensitivities.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

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
    """Build a commodity curvature batch from row-wise canonical sensitivities.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

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
    """Build a CSR non-securitisation curvature batch from row-wise sensitivities.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

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
    """Build a CSR securitisation non-CTP curvature batch from row-wise sensitivities.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

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
    """Build a CSR securitisation CTP curvature batch from row-wise sensitivities.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

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
    """Build an FX delta batch from existing row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_fx_delta_batch_from_columns``.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
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
    """Build an equity delta batch from existing row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_equity_delta_batch_from_columns``.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
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
    """Build a commodity delta batch from existing row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_commodity_delta_batch_from_columns``.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
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
    """Build a CSR non-securitisation delta batch from row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_csr_nonsec_delta_batch_from_columns``.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
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
    """Build a CSR securitisation non-CTP delta batch from row-wise canonical sensitivities.

    High-volume Arrow adapters should use
    ``build_csr_sec_nonctp_delta_batch_from_columns``.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
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
    """Build a CSR securitisation CTP delta batch from row-wise canonical sensitivities.

    High-volume Arrow adapters should use ``build_csr_sec_ctp_delta_batch_from_columns``.
    Parameters
    ----------
    sensitivities, source_hash, handoff_hash, diagnostics :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=SbmRiskClass.CSR_SEC_CTP,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


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
    """Build a GIRR delta batch from columnar arrays owned by an adapter.
    Parameters
    ----------
    sensitivity_ids, source_row_ids, desk_ids, legal_entities, risk_classes, risk_measures,
    buckets, risk_factors, amounts, amount_currencies, sign_conventions, tenors,
    lineage_source_systems, lineage_source_files, source_hash, handoff_hash, diagnostics,
    position_ids, qualifiers, option_tenors, liquidity_horizon_days, maturities, up_shock_amounts,
    down_shock_amounts, source_column_maps, mapping_citation_ids, copy_arrays :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

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
    """Build a GIRR vega batch from columnar arrays owned by an adapter.
    Parameters
    ----------
    sensitivity_ids, source_row_ids, desk_ids, legal_entities, risk_classes, risk_measures,
    buckets, risk_factors, amounts, amount_currencies, sign_conventions, tenors, option_tenors,
    lineage_source_systems, lineage_source_files, source_hash, handoff_hash, diagnostics,
    position_ids, qualifiers, liquidity_horizon_days, maturities, up_shock_amounts,
    down_shock_amounts, source_column_maps, mapping_citation_ids, copy_arrays :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

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
    """Build a GIRR curvature batch from columnar arrays owned by an adapter.

    The curvature contract intentionally keeps ``up_shock_amounts`` and
    ``down_shock_amounts`` as separate arrays at the batch boundary.
    Parameters
    ----------
    sensitivity_ids, source_row_ids, desk_ids, legal_entities, risk_classes, risk_measures,
    buckets, risk_factors, amounts, amount_currencies, sign_conventions, tenors, up_shock_amounts,
    down_shock_amounts, lineage_source_systems, lineage_source_files, source_hash, handoff_hash,
    diagnostics, position_ids, qualifiers, option_tenors, liquidity_horizon_days, maturities,
    source_column_maps, mapping_citation_ids, copy_arrays :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
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
    """Build an FX delta batch from columnar arrays owned by an adapter.
    Parameters
    ----------
    sensitivity_ids, source_row_ids, desk_ids, legal_entities, risk_classes, risk_measures,
    buckets, risk_factors, amounts, amount_currencies, sign_conventions, tenors,
    lineage_source_systems, lineage_source_files, source_hash, handoff_hash, diagnostics,
    position_ids, qualifiers, option_tenors, liquidity_horizon_days, maturities, up_shock_amounts,
    down_shock_amounts, source_column_maps, mapping_citation_ids, copy_arrays :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

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
    """Build an equity delta batch from columnar arrays owned by an adapter.
    Parameters
    ----------
    sensitivity_ids, source_row_ids, desk_ids, legal_entities, risk_classes, risk_measures,
    buckets, risk_factors, amounts, amount_currencies, sign_conventions, tenors,
    lineage_source_systems, lineage_source_files, source_hash, handoff_hash, diagnostics,
    position_ids, qualifiers, option_tenors, liquidity_horizon_days, maturities, up_shock_amounts,
    down_shock_amounts, source_column_maps, mapping_citation_ids, copy_arrays :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

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
    """Build a commodity delta batch from columnar arrays owned by an adapter.
    Parameters
    ----------
    sensitivity_ids, source_row_ids, desk_ids, legal_entities, risk_classes, risk_measures,
    buckets, risk_factors, amounts, amount_currencies, sign_conventions, tenors,
    lineage_source_systems, lineage_source_files, source_hash, handoff_hash, diagnostics,
    position_ids, qualifiers, option_tenors, liquidity_horizon_days, maturities, up_shock_amounts,
    down_shock_amounts, source_column_maps, mapping_citation_ids, copy_arrays :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

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
    """Build a CSR non-securitisation delta batch from columnar adapter arrays.
    Parameters
    ----------
    sensitivity_ids, source_row_ids, desk_ids, legal_entities, risk_classes, risk_measures,
    buckets, risk_factors, amounts, amount_currencies, sign_conventions, tenors,
    lineage_source_systems, lineage_source_files, source_hash, handoff_hash, diagnostics,
    position_ids, qualifiers, option_tenors, liquidity_horizon_days, maturities, up_shock_amounts,
    down_shock_amounts, source_column_maps, mapping_citation_ids, copy_arrays :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

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
    """Build a CSR securitisation non-CTP delta batch from columnar adapter arrays.
    Parameters
    ----------
    sensitivity_ids, source_row_ids, desk_ids, legal_entities, risk_classes, risk_measures,
    buckets, risk_factors, amounts, amount_currencies, sign_conventions, tenors,
    lineage_source_systems, lineage_source_files, source_hash, handoff_hash, diagnostics,
    position_ids, qualifiers, option_tenors, liquidity_horizon_days, maturities, up_shock_amounts,
    down_shock_amounts, source_column_maps, mapping_citation_ids, copy_arrays :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

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
    """Build a CSR securitisation CTP delta batch from columnar adapter arrays.
    Parameters
    ----------
    sensitivity_ids, source_row_ids, desk_ids, legal_entities, risk_classes, risk_measures,
    buckets, risk_factors, amounts, amount_currencies, sign_conventions, tenors,
    lineage_source_systems, lineage_source_files, source_hash, handoff_hash, diagnostics,
    position_ids, qualifiers, option_tenors, liquidity_horizon_days, maturities, up_shock_amounts,
    down_shock_amounts, source_column_maps, mapping_citation_ids, copy_arrays :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

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
    "build_sbm_batch",
    "build_sbm_batch_from_columns",
    "build_sbm_batch_from_sensitivities",
    "coerce_sbm_batch_sequence",
    "concatenate_sbm_batches",
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
