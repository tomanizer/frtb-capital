"""Sensitivity batch ingress adapters for SBM column and row inputs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

from frtb_common import (
    CalculationScope,
    RiskFactorId,
    RiskFactorMappingVersion,
    RiskFactorPrimitiveError,
)

from frtb_sbm.assembly.hashes import INPUT_HASH_ALGORITHM_JSON_ROW_V1
from frtb_sbm.data_models import SbmCalculationContext, SbmRiskClass, SbmRiskMeasure
from frtb_sbm.org_scope import validate_scope_metadata
from frtb_sbm.registry import sbm_batch_spec
from frtb_sbm.validation import SbmInputError, coerce_risk_class, coerce_risk_measure
from frtb_sbm.validation.batch import validate_homogeneous_batch_arrays
from frtb_sbm.validation.batch_arrays import (
    FloatArray,
    ObjectArray,
    float_array,
    normalise_risk_class_array,
    normalise_risk_measure_array,
    normalise_sign_convention_array,
    object_array,
    optional_object_array,
    require_common_length,
    require_non_empty_length,
)
from frtb_sbm.validation.batch_lineage import (
    validate_mapping_citations,
    validate_source_column_maps,
)

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
    risk_factor_ids: Iterable[object] | None = None,
    risk_factor_mapping_versions: Iterable[object] | None = None,
    bucket_labels: Iterable[object] | None = None,
    up_shock_ids: Iterable[object] | None = None,
    down_shock_ids: Iterable[object] | None = None,
    surface_ids: Iterable[object] | None = None,
    surface_point_ids: Iterable[object] | None = None,
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None = None,
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None = None,
    org_scopes: Iterable[object] | None = None,
    input_hash: str | None = None,
    input_hash_algorithm: str = INPUT_HASH_ALGORITHM_JSON_ROW_V1,
    copy_arrays: bool = True,
) -> SbmSensitivityBatch:
    """Build a homogeneous SBM batch from columnar arrays owned by an adapter.

    Parameters
    ----------
    expected_risk_class, expected_risk_measure, sensitivity_ids, source_row_ids, desk_ids,
    legal_entities, risk_classes, risk_measures, buckets, risk_factors, amounts,
    amount_currencies, sign_conventions, tenors, lineage_source_systems, lineage_source_files,
    source_hash, handoff_hash, diagnostics, position_ids, qualifiers, option_tenors,
    liquidity_horizon_days, maturities, up_shock_amounts, down_shock_amounts, risk_factor_ids,
    risk_factor_mapping_versions, bucket_labels, source_column_maps, mapping_citation_ids,
    liquidity_horizon_days, maturities, up_shock_amounts, down_shock_amounts, up_shock_ids,
    down_shock_ids, surface_ids, surface_point_ids, source_column_maps, mapping_citation_ids,
    copy_arrays
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

    resolved_risk_class = coerce_risk_class(expected_risk_class)
    resolved_risk_measure = coerce_risk_measure(expected_risk_measure)
    columns = locals()
    arrays = _required_arrays_from_columns(columns, copy_arrays=copy_arrays)
    amount_array = float_array(amounts, "amount", copy=copy_arrays)
    row_count = int(amount_array.shape[0])
    _validate_required_arrays(arrays, row_count)
    optional = _optional_arrays_from_columns(columns, row_count=row_count, copy_arrays=copy_arrays)
    scope_metadata = _scope_metadata_from_columns(
        org_scopes,
        row_count=row_count,
        sensitivity_ids=arrays["sensitivity_ids"],
    )
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
        org_scopes=scope_metadata,
        input_hash=input_hash,
        input_hash_algorithm=input_hash_algorithm,
    )


def _batch_module() -> Any:
    import frtb_sbm.batch as batch_module

    return batch_module


def _required_arrays_from_columns(
    columns: Mapping[str, object],
    *,
    copy_arrays: bool,
) -> dict[str, ObjectArray]:
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
        name: object_array(cast(Iterable[object], columns[name]), field, copy=copy_arrays)
        for name, field in fields
    }


def _validate_required_arrays(
    arrays: dict[str, ObjectArray],
    row_count: int,
) -> None:
    require_common_length(row_count, arrays)
    require_non_empty_length(row_count)
    arrays["risk_classes"] = normalise_risk_class_array(
        arrays["risk_classes"],
        sensitivity_ids=arrays["sensitivity_ids"],
    )
    arrays["risk_measures"] = normalise_risk_measure_array(
        arrays["risk_measures"],
        sensitivity_ids=arrays["sensitivity_ids"],
    )
    arrays["sign_conventions"] = normalise_sign_convention_array(
        arrays["sign_conventions"],
        sensitivity_ids=arrays["sensitivity_ids"],
    )


def _optional_arrays_from_columns(
    columns: Mapping[str, object],
    *,
    row_count: int,
    copy_arrays: bool,
) -> dict[str, ObjectArray | None]:
    optional_array = optional_object_array
    fields = (
        ("position_ids", "position_id"),
        ("qualifiers", "qualifier"),
        ("option_tenors", "option_tenor"),
        ("liquidity_horizon_days", "liquidity_horizon_days"),
        ("maturities", "maturity"),
        ("up_shock_amounts", "up_shock_amount"),
        ("down_shock_amounts", "down_shock_amount"),
        ("risk_factor_ids", "risk_factor_id"),
        ("risk_factor_mapping_versions", "risk_factor_mapping_version"),
        ("bucket_labels", "bucket_label"),
        ("up_shock_ids", "up_shock_id"),
        ("down_shock_ids", "down_shock_id"),
        ("surface_ids", "surface_id"),
        ("surface_point_ids", "surface_point_id"),
    )
    return {
        name: optional_array(
            cast(Iterable[object] | None, columns[name]), field, row_count, copy_arrays
        )
        for name, field in fields
    }


def _validate_batch_arrays(
    arrays: Mapping[str, ObjectArray],
    amount_array: FloatArray,
    optional: Mapping[str, ObjectArray | None],
    *,
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None,
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None,
    row_count: int,
    expected_risk_class: SbmRiskClass,
    expected_risk_measure: SbmRiskMeasure,
) -> None:
    validate_source_column_maps(source_column_maps, row_count)
    validate_mapping_citations(mapping_citation_ids, row_count)
    _validate_risk_factor_metadata_arrays(optional, arrays["sensitivity_ids"])
    validate_homogeneous_batch_arrays(
        arrays,
        amount_array,
        expected_risk_class=expected_risk_class,
        expected_risk_measure=expected_risk_measure,
        optional_arrays=optional,
    )


def _batch_with_hash(
    arrays: Mapping[str, ObjectArray],
    amount_array: FloatArray,
    optional: Mapping[str, ObjectArray | None],
    *,
    source_hash: str | None,
    handoff_hash: str | None,
    diagnostics: Sequence[Mapping[str, object]],
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None,
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None,
    org_scopes: tuple[CalculationScope | None, ...] | None,
    input_hash: str | None,
    input_hash_algorithm: str,
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
        input_hash="" if input_hash is None else input_hash,
        input_hash_algorithm=input_hash_algorithm,
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
        risk_factor_ids=optional["risk_factor_ids"],
        risk_factor_mapping_versions=optional["risk_factor_mapping_versions"],
        bucket_labels=optional["bucket_labels"],
        up_shock_ids=optional["up_shock_ids"],
        down_shock_ids=optional["down_shock_ids"],
        surface_ids=optional["surface_ids"],
        surface_point_ids=optional["surface_point_ids"],
        source_column_maps=source_column_maps,
        mapping_citation_ids=mapping_citation_ids,
        org_scopes=org_scopes,
    )
    if input_hash is not None:
        return cast("SbmSensitivityBatch", batch_without_hash)
    return cast(
        "SbmSensitivityBatch",
        replace(
            batch_without_hash,
            input_hash=batch_module.input_hash_for_batch(batch_without_hash),
            input_hash_algorithm=INPUT_HASH_ALGORITHM_JSON_ROW_V1,
        ),
    )


def _scope_metadata_from_columns(
    org_scopes: Iterable[object] | None,
    *,
    row_count: int,
    sensitivity_ids: ObjectArray,
) -> tuple[CalculationScope | None, ...] | None:
    if org_scopes is None:
        return None
    rows = tuple(org_scopes)
    if len(rows) != row_count:
        raise SbmInputError("org_scopes length must match batch row count", field="org_scopes")
    validated = tuple(
        validate_scope_metadata(
            scope,
            field="org_scopes",
            sensitivity_id=cast(str, sensitivity_ids[index]),
        )
        for index, scope in enumerate(rows)
    )
    if not any(scope is not None for scope in validated):
        return None
    return validated


def _validate_risk_factor_metadata_arrays(
    optional: Mapping[str, ObjectArray | None],
    sensitivity_ids: ObjectArray,
) -> None:
    _validate_risk_factor_id_array(optional["risk_factor_ids"], sensitivity_ids)
    _validate_mapping_version_array(
        optional["risk_factor_mapping_versions"],
        sensitivity_ids,
    )
    _validate_optional_text_array(optional["bucket_labels"], "bucket_label", sensitivity_ids)


def _validate_risk_factor_id_array(
    values: ObjectArray | None,
    sensitivity_ids: ObjectArray,
) -> None:
    if values is None:
        return
    for row_index, value in enumerate(values):
        if value is None:
            continue
        try:
            RiskFactorId(cast(str, value))
        except (AttributeError, RiskFactorPrimitiveError, TypeError) as exc:
            raise SbmInputError(
                "invalid risk_factor_id",
                field="risk_factor_id",
                sensitivity_id=cast(str, sensitivity_ids[row_index]),
            ) from exc


def _validate_mapping_version_array(
    values: ObjectArray | None,
    sensitivity_ids: ObjectArray,
) -> None:
    if values is None:
        return
    for row_index, value in enumerate(values):
        if value is None:
            continue
        try:
            RiskFactorMappingVersion(cast(str, value))
        except (AttributeError, RiskFactorPrimitiveError, TypeError) as exc:
            raise SbmInputError(
                "invalid risk_factor_mapping_version",
                field="risk_factor_mapping_version",
                sensitivity_id=cast(str, sensitivity_ids[row_index]),
            ) from exc


def _validate_optional_text_array(
    values: ObjectArray | None,
    field: str,
    sensitivity_ids: ObjectArray,
) -> None:
    if values is None:
        return
    for row_index, value in enumerate(values):
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise SbmInputError(
                f"{field} must be a non-empty string",
                field=field,
                sensitivity_id=cast(str, sensitivity_ids[row_index]),
            )


__all__ = [
    "build_sbm_batch",
    "build_sbm_batch_from_columns",
]
