"""Sensitivity batch ingress adapters for SBM column and row inputs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

from frtb_sbm.data_models import SbmCalculationContext, SbmRiskClass, SbmRiskMeasure
from frtb_sbm.registry import sbm_batch_spec
from frtb_sbm.validation import SbmInputError, coerce_risk_class, coerce_risk_measure

if TYPE_CHECKING:
    from frtb_sbm.batch import SbmSensitivityBatch


def build_sbm_batch(
    sensitivities: object,
    risk_class: SbmRiskClass | str,
    measure: SbmRiskMeasure | str,
    *,
    context: SbmCalculationContext | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """Build an SBM batch through the canonical path registry.

    Parameters
    ----------
    sensitivities, risk_class, measure, context, source_hash, handoff_hash, diagnostics
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

    from frtb_sbm.batch import build_sbm_batch_from_sensitivities

    expected_risk_class = coerce_risk_class(risk_class)
    expected_risk_measure = coerce_risk_measure(measure)
    sbm_batch_spec(expected_risk_class, expected_risk_measure)
    if context is not None and not isinstance(context, SbmCalculationContext):
        raise SbmInputError(
            "calculation context must be SbmCalculationContext",
            field="context",
        )
    return build_sbm_batch_from_sensitivities(
        sensitivities,
        expected_risk_class=expected_risk_class,
        expected_risk_measure=expected_risk_measure,
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
    """Build a homogeneous SBM batch from columnar arrays owned by an adapter.

    Parameters
    ----------
    expected_risk_class, expected_risk_measure, sensitivity_ids, source_row_ids, desk_ids,
    legal_entities, risk_classes, risk_measures, buckets, risk_factors, amounts,
    amount_currencies, sign_conventions, tenors, lineage_source_systems, lineage_source_files,
    source_hash, handoff_hash, diagnostics, position_ids, qualifiers, option_tenors,
    liquidity_horizon_days, maturities, up_shock_amounts, down_shock_amounts, source_column_maps,
    mapping_citation_ids, copy_arrays
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

    resolved_risk_class = coerce_risk_class(expected_risk_class)
    resolved_risk_measure = coerce_risk_measure(expected_risk_measure)
    columns = locals()
    arrays = _required_arrays_from_columns(columns, copy_arrays=copy_arrays)
    amount_array = _batch_module()._float_array(amounts, "amount", copy=copy_arrays)
    row_count = int(amount_array.shape[0])
    _validate_required_arrays(arrays, row_count)
    optional = _optional_arrays_from_columns(columns, row_count=row_count, copy_arrays=copy_arrays)
    _validate_batch_arrays(
        arrays,
        amount_array,
        optional,
        source_column_maps=source_column_maps,
        mapping_citation_ids=mapping_citation_ids,
        row_count=row_count,
        expected_risk_class=resolved_risk_class,
        expected_risk_measure=resolved_risk_measure,
    )
    return _batch_with_hash(
        arrays,
        amount_array,
        optional,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        source_column_maps=source_column_maps,
        mapping_citation_ids=mapping_citation_ids,
    )


def _batch_module() -> Any:
    import frtb_sbm.batch as batch_module

    return batch_module


def _required_arrays_from_columns(
    columns: Mapping[str, object],
    *,
    copy_arrays: bool,
) -> dict[str, object]:
    batch_module = _batch_module()
    fields = (
        ("sensitivity_ids", "sensitivity_id"),
        ("source_row_ids", "source_row_id"),
        ("desk_ids", "desk_id"),
        ("legal_entities", "legal_entity"),
        ("risk_classes", "risk_class"),
        ("risk_measures", "risk_measure"),
        ("buckets", "bucket"),
        ("risk_factors", "risk_factor"),
        ("amount_currencies", "amount_currency"),
        ("sign_conventions", "sign_convention"),
        ("tenors", "tenor"),
        ("lineage_source_systems", "lineage_source_system"),
        ("lineage_source_files", "lineage_source_file"),
    )
    return {
        name: batch_module._object_array(columns[name], field, copy=copy_arrays)
        for name, field in fields
    }


def _validate_required_arrays(
    arrays: dict[str, object],
    row_count: int,
) -> None:
    batch_module = _batch_module()
    batch_module._require_common_length(row_count, arrays)
    batch_module._require_non_empty_length(row_count)
    arrays["risk_classes"] = batch_module._normalise_risk_class_array(
        arrays["risk_classes"],
        sensitivity_ids=arrays["sensitivity_ids"],
    )
    arrays["risk_measures"] = batch_module._normalise_risk_measure_array(
        arrays["risk_measures"],
        sensitivity_ids=arrays["sensitivity_ids"],
    )
    arrays["sign_conventions"] = batch_module._normalise_sign_convention_array(
        arrays["sign_conventions"],
        sensitivity_ids=arrays["sensitivity_ids"],
    )


def _optional_arrays_from_columns(
    columns: Mapping[str, object],
    *,
    row_count: int,
    copy_arrays: bool,
) -> dict[str, object]:
    batch_module = _batch_module()
    optional_array = batch_module._optional_object_array
    fields = (
        ("position_ids", "position_id"),
        ("qualifiers", "qualifier"),
        ("option_tenors", "option_tenor"),
        ("liquidity_horizon_days", "liquidity_horizon_days"),
        ("maturities", "maturity"),
        ("up_shock_amounts", "up_shock_amount"),
        ("down_shock_amounts", "down_shock_amount"),
    )
    return {
        name: optional_array(columns[name], field, row_count, copy_arrays) for name, field in fields
    }


def _validate_batch_arrays(
    arrays: dict[str, object],
    amount_array: object,
    optional: dict[str, object],
    *,
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None,
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None,
    row_count: int,
    expected_risk_class: SbmRiskClass,
    expected_risk_measure: SbmRiskMeasure,
) -> None:
    batch_module = _batch_module()
    batch_module._validate_source_column_maps(source_column_maps, row_count)
    batch_module._validate_mapping_citations(mapping_citation_ids, row_count)
    batch_module._validate_homogeneous_batch_arrays(
        arrays,
        amount_array,
        expected_risk_class=expected_risk_class,
        expected_risk_measure=expected_risk_measure,
        optional_arrays=optional,
    )


def _batch_with_hash(
    arrays: dict[str, object],
    amount_array: object,
    optional: dict[str, object],
    *,
    source_hash: str | None,
    handoff_hash: str | None,
    diagnostics: Sequence[Mapping[str, object]],
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None,
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None,
) -> SbmSensitivityBatch:
    batch_module = _batch_module()
    diagnostic_payloads = tuple(MappingProxyType(dict(item)) for item in diagnostics)
    batch_without_hash = batch_module.SbmSensitivityBatch(
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
    return cast(
        "SbmSensitivityBatch",
        replace(
            batch_without_hash,
            input_hash=batch_module.input_hash_for_batch(batch_without_hash),
        ),
    )


__all__ = [
    "build_sbm_batch",
    "build_sbm_batch_from_columns",
]
