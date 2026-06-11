"""Position and column ingress adapters for DRC canonical batches."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from typing import TYPE_CHECKING

from frtb_drc._batch_columns import (
    ColumnInput,
    NullableColumnInput,
    _bool_array,
    _enum_array,
    _freeze_citation_ids,
    _freeze_source_column_maps,
    _nullable_enum_array,
    _optional_float_array,
    _optional_text_array,
    _require_lengths,
    _required_float_array,
    _required_text_array,
    _text_array_with_default,
)
from frtb_drc.data_models import (
    CreditQuality,
    DefaultDirection,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
)
from frtb_drc.validation import US_NPR_2_0_PROFILE_ID, DrcInputError, validate_positions

if TYPE_CHECKING:
    from frtb_drc.batch import DrcPositionBatch


def build_drc_nonsec_batch_from_positions(
    positions: Iterable[DrcPosition],
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> DrcPositionBatch:
    """Build a DRC batch from existing canonical position rows.

    Compatibility bridge for callers that already hold dataclasses; adapters
    should prefer column or Arrow handoff builders at volume.

    Parameters
    ----------
    positions : iterable of DrcPosition
        Validated canonical position rows to materialise into arrays.
    source_hash : str, optional
        Precomputed source digest for the input rows.
    handoff_hash : str, optional
        Normalised handoff digest when positions originate from an adapter.
    diagnostics : sequence of mapping, optional
        Adapter diagnostics to attach to the batch envelope.
    profile_id : str, optional
        Active DRC rule profile identifier (default US NPR 2.0).

    Returns
    -------
    DrcPositionBatch
        Columnar non-securitisation batch with deterministic ``input_hash``.
    """

    validated = _sorted_positions(validate_positions(positions, profile_id=profile_id))
    if not validated:
        raise DrcInputError("DRC batch requires at least one position")
    return build_drc_nonsec_batch_from_columns(
        position_ids=[position.position_id for position in validated],
        source_row_ids=[position.source_row_id for position in validated],
        desk_ids=[position.desk_id for position in validated],
        legal_entities=[position.legal_entity for position in validated],
        risk_classes=[DrcRiskClass(position.risk_class).value for position in validated],
        instrument_types=[
            DrcInstrumentType(position.instrument_type).value for position in validated
        ],
        default_directions=[
            DefaultDirection(position.default_direction).value for position in validated
        ],
        issuer_ids=[position.issuer_id for position in validated],
        tranche_ids=[position.tranche_id for position in validated],
        index_series_ids=[position.index_series_id for position in validated],
        bucket_keys=[position.bucket_key for position in validated],
        seniorities=[
            None if position.seniority is None else DrcSeniority(position.seniority).value
            for position in validated
        ],
        credit_qualities=[
            None
            if position.credit_quality is None
            else CreditQuality(position.credit_quality).value
            for position in validated
        ],
        notionals=[position.notional for position in validated],
        market_values=[position.market_value for position in validated],
        cumulative_pnls=[position.cumulative_pnl for position in validated],
        maturity_years=[position.maturity_years for position in validated],
        currencies=[position.currency for position in validated],
        lgd_overrides=[position.lgd_override for position in validated],
        is_defaulted=[position.is_defaulted for position in validated],
        is_gse=[position.is_gse for position in validated],
        is_pse=[position.is_pse for position in validated],
        is_covered_bond=[position.is_covered_bond for position in validated],
        lineage_source_systems=[
            "" if position.lineage is None else position.lineage.source_system
            for position in validated
        ],
        lineage_source_files=[
            "" if position.lineage is None else position.lineage.source_file
            for position in validated
        ],
        lineage_present=[position.lineage is not None for position in validated],
        source_column_maps=[
            ()
            if position.lineage is None
            else tuple(sorted(position.lineage.source_column_map.items()))
            for position in validated
        ],
        citation_ids=[position.citation_ids for position in validated],
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        profile_id=profile_id,
    )


def build_drc_nonsec_batch_from_columns(
    *,
    position_ids: ColumnInput,
    source_row_ids: ColumnInput,
    desk_ids: ColumnInput,
    legal_entities: ColumnInput,
    risk_classes: ColumnInput,
    instrument_types: ColumnInput,
    default_directions: ColumnInput,
    issuer_ids: NullableColumnInput | None,
    tranche_ids: NullableColumnInput | None = None,
    index_series_ids: NullableColumnInput | None = None,
    bucket_keys: NullableColumnInput,
    seniorities: NullableColumnInput | None,
    credit_qualities: NullableColumnInput | None,
    notionals: ColumnInput,
    market_values: NullableColumnInput | None = None,
    cumulative_pnls: NullableColumnInput | None = None,
    maturity_years: ColumnInput,
    currencies: ColumnInput,
    lgd_overrides: NullableColumnInput | None = None,
    is_defaulted: ColumnInput | None = None,
    is_gse: ColumnInput | None = None,
    is_pse: ColumnInput | None = None,
    is_covered_bond: ColumnInput | None = None,
    lineage_source_systems: ColumnInput | None = None,
    lineage_source_files: ColumnInput | None = None,
    lineage_present: ColumnInput | None = None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None = None,
    citation_ids: Sequence[Sequence[str]] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    copy_arrays: bool = True,
    _expected_risk_class: DrcRiskClass = DrcRiskClass.NON_SECURITISATION,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> DrcPositionBatch:
    """Build a validated non-securitisation DRC batch from columnar inputs.

    Parameters
    ----------
    position_ids, source_row_ids, desk_ids, legal_entities, risk_classes,
    instrument_types, default_directions, bucket_keys, notionals,
    maturity_years, currencies :
        Required per-position column inputs aligned in length.
    issuer_ids, tranche_ids, index_series_ids, seniorities, credit_qualities,
    market_values, cumulative_pnls, lgd_overrides, is_defaulted, is_gse,
    is_pse, is_covered_bond, lineage_source_systems, lineage_source_files,
    lineage_present, source_column_maps, citation_ids :
        Optional per-position columns (see function signature).
    source_hash, handoff_hash :
        Optional source and handoff digests for audit metadata.
    diagnostics :
        Optional adapter diagnostics attached to the batch.
    copy_arrays :
        When ``True``, copy inputs before freezing arrays.
    _expected_risk_class :
        Internal risk-class guard for specialised builders.
    profile_id :
        Active DRC rule profile identifier.

    Returns
    -------
    DrcPositionBatch
        Validated batch with ``input_hash`` populated.
    """

    from frtb_drc.batch import DrcPositionBatch, _validate_batch, input_hash_for_drc_batch

    row_count = len(position_ids)
    if row_count == 0:
        raise DrcInputError("DRC batch requires at least one position")
    _require_lengths(
        row_count,
        source_row_ids=source_row_ids,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        risk_classes=risk_classes,
        instrument_types=instrument_types,
        default_directions=default_directions,
        bucket_keys=bucket_keys,
        notionals=notionals,
        maturity_years=maturity_years,
        currencies=currencies,
    )
    optional_lengths = {
        "tranche_ids": tranche_ids,
        "index_series_ids": index_series_ids,
        "issuer_ids": issuer_ids,
        "market_values": market_values,
        "cumulative_pnls": cumulative_pnls,
        "lgd_overrides": lgd_overrides,
        "seniorities": seniorities,
        "credit_qualities": credit_qualities,
        "is_defaulted": is_defaulted,
        "is_gse": is_gse,
        "is_pse": is_pse,
        "is_covered_bond": is_covered_bond,
        "lineage_source_systems": lineage_source_systems,
        "lineage_source_files": lineage_source_files,
        "lineage_present": lineage_present,
        "source_column_maps": source_column_maps,
        "citation_ids": citation_ids,
    }
    for name, values in optional_lengths.items():
        if values is not None and len(values) != row_count:
            raise DrcInputError(f"{name} length does not match position_ids")

    lineage_present_default = (
        lineage_source_systems is not None
        or lineage_source_files is not None
        or source_column_maps is not None
    )
    batch = DrcPositionBatch(
        position_ids=_required_text_array(position_ids, "position_id", copy=copy_arrays),
        source_row_ids=_required_text_array(source_row_ids, "source_row_id", copy=copy_arrays),
        desk_ids=_required_text_array(desk_ids, "desk_id", copy=copy_arrays),
        legal_entities=_required_text_array(legal_entities, "legal_entity", copy=copy_arrays),
        risk_classes=_enum_array(risk_classes, DrcRiskClass, "risk_class", copy=copy_arrays),
        instrument_types=_enum_array(
            instrument_types,
            DrcInstrumentType,
            "instrument_type",
            copy=copy_arrays,
        ),
        default_directions=_enum_array(
            default_directions,
            DefaultDirection,
            "default_direction",
            copy=copy_arrays,
        ),
        issuer_ids=_optional_text_array(issuer_ids, row_count, copy=copy_arrays),
        tranche_ids=_optional_text_array(tranche_ids, row_count, copy=copy_arrays),
        index_series_ids=_optional_text_array(index_series_ids, row_count, copy=copy_arrays),
        bucket_keys=_required_text_array(bucket_keys, "bucket_key", copy=copy_arrays),
        seniorities=_nullable_enum_array(
            seniorities,
            DrcSeniority,
            "seniority",
            row_count,
            copy=copy_arrays,
        ),
        credit_qualities=_nullable_enum_array(
            credit_qualities,
            CreditQuality,
            "credit_quality",
            row_count,
            copy=copy_arrays,
        ),
        notionals=_required_float_array(notionals, "notional", copy=copy_arrays),
        market_values=_optional_float_array(market_values, row_count, copy=copy_arrays),
        cumulative_pnls=_optional_float_array(cumulative_pnls, row_count, copy=copy_arrays),
        maturity_years=_required_float_array(maturity_years, "maturity_years", copy=copy_arrays),
        currencies=_required_text_array(currencies, "currency", copy=copy_arrays),
        lgd_overrides=_optional_float_array(lgd_overrides, row_count, copy=copy_arrays),
        is_defaulted=_bool_array(is_defaulted, row_count, copy=copy_arrays),
        is_gse=_bool_array(is_gse, row_count, copy=copy_arrays),
        is_pse=_bool_array(is_pse, row_count, copy=copy_arrays),
        is_covered_bond=_bool_array(is_covered_bond, row_count, copy=copy_arrays),
        lineage_source_systems=_text_array_with_default(
            lineage_source_systems,
            row_count,
            default="",
            copy=copy_arrays,
        ),
        lineage_source_files=_text_array_with_default(
            lineage_source_files,
            row_count,
            default="",
            copy=copy_arrays,
        ),
        lineage_present=_bool_array(
            lineage_present,
            row_count,
            default=lineage_present_default,
            copy=copy_arrays,
        ),
        source_column_maps=_freeze_source_column_maps(source_column_maps, row_count),
        citation_ids=_freeze_citation_ids(citation_ids, row_count),
        input_hash="",
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=tuple(dict(item) for item in diagnostics),
    )
    _validate_batch(batch, expected_risk_class=_expected_risk_class, profile_id=profile_id)
    return replace(batch, input_hash=input_hash_for_drc_batch(batch))


def build_drc_securitisation_non_ctp_batch_from_columns(
    *,
    position_ids: ColumnInput,
    source_row_ids: ColumnInput,
    desk_ids: ColumnInput,
    legal_entities: ColumnInput,
    risk_classes: ColumnInput,
    instrument_types: ColumnInput,
    default_directions: ColumnInput,
    issuer_ids: NullableColumnInput | None,
    tranche_ids: NullableColumnInput | None = None,
    index_series_ids: NullableColumnInput | None = None,
    bucket_keys: NullableColumnInput,
    seniorities: NullableColumnInput | None = None,
    credit_qualities: NullableColumnInput | None = None,
    notionals: ColumnInput,
    market_values: NullableColumnInput | None = None,
    cumulative_pnls: NullableColumnInput | None = None,
    maturity_years: ColumnInput,
    currencies: ColumnInput,
    lgd_overrides: NullableColumnInput | None = None,
    is_defaulted: ColumnInput | None = None,
    is_gse: ColumnInput | None = None,
    is_pse: ColumnInput | None = None,
    is_covered_bond: ColumnInput | None = None,
    lineage_source_systems: ColumnInput | None = None,
    lineage_source_files: ColumnInput | None = None,
    lineage_present: ColumnInput | None = None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None = None,
    citation_ids: Sequence[Sequence[str]] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    copy_arrays: bool = True,
) -> DrcPositionBatch:
    """Build a validated securitisation non-CTP DRC batch from columnar inputs.

    Parameters
    ----------
    position_ids, source_row_ids, desk_ids, legal_entities, risk_classes,
    instrument_types, default_directions, bucket_keys, notionals,
    maturity_years, currencies :
        Required per-position column inputs (see signature for optional columns).
    source_hash, handoff_hash, diagnostics, copy_arrays :
        Optional audit metadata and array copy behaviour.

    Returns
    -------
    DrcPositionBatch
        Securitisation non-CTP batch delegated to the shared column builder.
    """

    return build_drc_nonsec_batch_from_columns(
        position_ids=position_ids,
        source_row_ids=source_row_ids,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        risk_classes=risk_classes,
        instrument_types=instrument_types,
        default_directions=default_directions,
        issuer_ids=issuer_ids,
        tranche_ids=tranche_ids,
        index_series_ids=index_series_ids,
        bucket_keys=bucket_keys,
        seniorities=seniorities,
        credit_qualities=credit_qualities,
        notionals=notionals,
        market_values=market_values,
        cumulative_pnls=cumulative_pnls,
        maturity_years=maturity_years,
        currencies=currencies,
        lgd_overrides=lgd_overrides,
        is_defaulted=is_defaulted,
        is_gse=is_gse,
        is_pse=is_pse,
        is_covered_bond=is_covered_bond,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        lineage_present=lineage_present,
        source_column_maps=source_column_maps,
        citation_ids=citation_ids,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        copy_arrays=copy_arrays,
        _expected_risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        profile_id=US_NPR_2_0_PROFILE_ID,
    )


def build_drc_ctp_batch_from_columns(
    *,
    position_ids: ColumnInput,
    source_row_ids: ColumnInput,
    desk_ids: ColumnInput,
    legal_entities: ColumnInput,
    risk_classes: ColumnInput,
    instrument_types: ColumnInput,
    default_directions: ColumnInput,
    issuer_ids: NullableColumnInput | None,
    tranche_ids: NullableColumnInput | None = None,
    index_series_ids: NullableColumnInput | None = None,
    bucket_keys: NullableColumnInput,
    seniorities: NullableColumnInput | None = None,
    credit_qualities: NullableColumnInput | None = None,
    notionals: ColumnInput,
    market_values: NullableColumnInput | None = None,
    cumulative_pnls: NullableColumnInput | None = None,
    maturity_years: ColumnInput,
    currencies: ColumnInput,
    lgd_overrides: NullableColumnInput | None = None,
    is_defaulted: ColumnInput | None = None,
    is_gse: ColumnInput | None = None,
    is_pse: ColumnInput | None = None,
    is_covered_bond: ColumnInput | None = None,
    lineage_source_systems: ColumnInput | None = None,
    lineage_source_files: ColumnInput | None = None,
    lineage_present: ColumnInput | None = None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None = None,
    citation_ids: Sequence[Sequence[str]] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    copy_arrays: bool = True,
) -> DrcPositionBatch:
    """Build a validated CTP DRC batch from columnar inputs.

    Parameters
    ----------
    position_ids, source_row_ids, desk_ids, legal_entities, risk_classes,
    instrument_types, default_directions, bucket_keys, notionals,
    maturity_years, currencies :
        Required per-position column inputs (see signature for optional columns).
    source_hash, handoff_hash, diagnostics, copy_arrays :
        Optional audit metadata and array copy behaviour.

    Returns
    -------
    DrcPositionBatch
        Correlation-trading-portfolio batch delegated to the shared column builder.
    """

    return build_drc_nonsec_batch_from_columns(
        position_ids=position_ids,
        source_row_ids=source_row_ids,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        risk_classes=risk_classes,
        instrument_types=instrument_types,
        default_directions=default_directions,
        issuer_ids=issuer_ids,
        tranche_ids=tranche_ids,
        index_series_ids=index_series_ids,
        bucket_keys=bucket_keys,
        seniorities=seniorities,
        credit_qualities=credit_qualities,
        notionals=notionals,
        market_values=market_values,
        cumulative_pnls=cumulative_pnls,
        maturity_years=maturity_years,
        currencies=currencies,
        lgd_overrides=lgd_overrides,
        is_defaulted=is_defaulted,
        is_gse=is_gse,
        is_pse=is_pse,
        is_covered_bond=is_covered_bond,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        lineage_present=lineage_present,
        source_column_maps=source_column_maps,
        citation_ids=citation_ids,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        copy_arrays=copy_arrays,
        _expected_risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
    )


def _sorted_positions(positions: tuple[DrcPosition, ...]) -> tuple[DrcPosition, ...]:
    return tuple(
        sorted(positions, key=lambda position: (position.position_id, position.source_row_id))
    )


__all__ = [
    "build_drc_ctp_batch_from_columns",
    "build_drc_nonsec_batch_from_columns",
    "build_drc_nonsec_batch_from_positions",
    "build_drc_securitisation_non_ctp_batch_from_columns",
]
