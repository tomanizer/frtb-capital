"""Netting-set column adapter for CVA batch contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from frtb_cva._batch_columns import (
    ColumnInput,
    _bool_array,
    _default_text_sequence,
    _float_array,
    _freeze_source_column_maps,
    _normalised_ead_array,
    _require_lengths,
    _require_optional_lengths,
    _required_text_array,
)
from frtb_cva._batch_contracts import CvaNettingSetBatch
from frtb_cva._batch_validation import _validate_netting_set_batch
from frtb_cva.validation import CvaInputError


def build_cva_netting_set_batch_from_columns(
    *,
    netting_set_ids: ColumnInput,
    counterparty_ids: ColumnInput,
    eads: ColumnInput,
    effective_maturities: ColumnInput,
    discount_factors: ColumnInput,
    currencies: ColumnInput,
    sign_conventions: ColumnInput,
    uses_imm_eads: ColumnInput,
    source_row_ids: ColumnInput,
    carved_out_to_ba_cva: ColumnInput | None = None,
    discount_factor_explicit: ColumnInput | None = None,
    lineage_source_systems: ColumnInput | None = None,
    lineage_source_files: ColumnInput | None = None,
    lineage_source_row_ids: ColumnInput | None = None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    copy_arrays: bool = True,
) -> CvaNettingSetBatch:
    """Build a validated netting-set batch from aligned column inputs.

    Parameters
    ----------
    netting_set_ids, counterparty_ids, eads, effective_maturities, discount_factors,
    currencies, sign_conventions, uses_imm_eads, source_row_ids : ColumnInput
        Required per-row columns with matching lengths.
    carved_out_to_ba_cva, discount_factor_explicit, lineage_source_systems,
    lineage_source_files, lineage_source_row_ids, source_column_maps : optional
        Carve-out, discount-factor, and audit lineage metadata.

    Returns
    -------
    CvaNettingSetBatch
        Columnar batch with EAD amounts normalised to the sign convention.
    """
    row_count = len(netting_set_ids)
    if row_count == 0:
        raise CvaInputError("netting-set batch requires at least one row", field="netting_sets")
    _require_netting_lengths(
        row_count,
        counterparty_ids=counterparty_ids,
        eads=eads,
        effective_maturities=effective_maturities,
        discount_factors=discount_factors,
        currencies=currencies,
        sign_conventions=sign_conventions,
        uses_imm_eads=uses_imm_eads,
        source_row_ids=source_row_ids,
        carved_out_to_ba_cva=carved_out_to_ba_cva,
        discount_factor_explicit=discount_factor_explicit,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        lineage_source_row_ids=lineage_source_row_ids,
        source_column_maps=source_column_maps,
    )
    batch = CvaNettingSetBatch(
        **_netting_batch_fields(
            row_count=row_count,
            netting_set_ids=netting_set_ids,
            counterparty_ids=counterparty_ids,
            eads=eads,
            effective_maturities=effective_maturities,
            discount_factors=discount_factors,
            currencies=currencies,
            sign_conventions=sign_conventions,
            uses_imm_eads=uses_imm_eads,
            source_row_ids=source_row_ids,
            carved_out_to_ba_cva=carved_out_to_ba_cva,
            discount_factor_explicit=discount_factor_explicit,
            lineage_source_systems=lineage_source_systems,
            lineage_source_files=lineage_source_files,
            lineage_source_row_ids=lineage_source_row_ids,
            source_column_maps=source_column_maps,
            source_hash=source_hash,
            handoff_hash=handoff_hash,
            diagnostics=diagnostics,
            copy_arrays=copy_arrays,
        )
    )
    _validate_netting_set_batch(batch)
    return batch


def _require_netting_lengths(
    row_count: int,
    *,
    counterparty_ids: ColumnInput,
    eads: ColumnInput,
    effective_maturities: ColumnInput,
    discount_factors: ColumnInput,
    currencies: ColumnInput,
    sign_conventions: ColumnInput,
    uses_imm_eads: ColumnInput,
    source_row_ids: ColumnInput,
    carved_out_to_ba_cva: ColumnInput | None,
    discount_factor_explicit: ColumnInput | None,
    lineage_source_systems: ColumnInput | None,
    lineage_source_files: ColumnInput | None,
    lineage_source_row_ids: ColumnInput | None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None,
) -> None:
    _require_lengths(
        row_count,
        counterparty_ids=counterparty_ids,
        eads=eads,
        effective_maturities=effective_maturities,
        discount_factors=discount_factors,
        currencies=currencies,
        sign_conventions=sign_conventions,
        uses_imm_eads=uses_imm_eads,
        source_row_ids=source_row_ids,
    )
    _require_optional_lengths(
        row_count,
        carved_out_to_ba_cva=carved_out_to_ba_cva,
        discount_factor_explicit=discount_factor_explicit,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        lineage_source_row_ids=lineage_source_row_ids,
        source_column_maps=source_column_maps,
    )


def _netting_batch_fields(
    *,
    row_count: int,
    netting_set_ids: ColumnInput,
    counterparty_ids: ColumnInput,
    eads: ColumnInput,
    effective_maturities: ColumnInput,
    discount_factors: ColumnInput,
    currencies: ColumnInput,
    sign_conventions: ColumnInput,
    uses_imm_eads: ColumnInput,
    source_row_ids: ColumnInput,
    carved_out_to_ba_cva: ColumnInput | None,
    discount_factor_explicit: ColumnInput | None,
    lineage_source_systems: ColumnInput | None,
    lineage_source_files: ColumnInput | None,
    lineage_source_row_ids: ColumnInput | None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None,
    source_hash: str | None,
    handoff_hash: str | None,
    diagnostics: Sequence[Mapping[str, object]],
    copy_arrays: bool,
) -> dict[str, Any]:
    netting_set_id_array = _required_text_array(netting_set_ids, "netting_set_id", copy=copy_arrays)
    sign_convention_array = _required_text_array(
        sign_conventions,
        "sign_convention",
        copy=copy_arrays,
    )
    return {
        "netting_set_ids": netting_set_id_array,
        "counterparty_ids": _required_text_array(
            counterparty_ids, "counterparty_id", copy=copy_arrays
        ),
        "eads": _normalised_ead_array(
            _float_array(eads, "ead", copy=copy_arrays),
            sign_convention_array,
            record_ids=netting_set_id_array,
        ),
        "effective_maturities": _float_array(
            effective_maturities, "effective_maturity", copy=copy_arrays
        ),
        "discount_factors": _float_array(discount_factors, "discount_factor", copy=copy_arrays),
        "currencies": _required_text_array(currencies, "currency", copy=copy_arrays),
        "sign_conventions": sign_convention_array,
        "uses_imm_eads": _bool_array(uses_imm_eads, row_count, default=False, copy=copy_arrays),
        "source_row_ids": _required_text_array(source_row_ids, "source_row_id", copy=copy_arrays),
        "carved_out_to_ba_cva": _bool_array(
            carved_out_to_ba_cva, row_count, default=False, copy=copy_arrays
        ),
        "discount_factor_explicit": _bool_array(
            discount_factor_explicit, row_count, default=False, copy=copy_arrays
        ),
        "lineage_source_systems": _required_text_array(
            _default_text_sequence(lineage_source_systems, row_count, "cva-batch"),
            "lineage.source_system",
            copy=copy_arrays,
        ),
        "lineage_source_files": _required_text_array(
            _default_text_sequence(lineage_source_files, row_count, "columns"),
            "lineage.source_file",
            copy=copy_arrays,
        ),
        "lineage_source_row_ids": _required_text_array(
            source_row_ids if lineage_source_row_ids is None else lineage_source_row_ids,
            "lineage.source_row_id",
            copy=copy_arrays,
        ),
        "source_column_maps": _freeze_source_column_maps(source_column_maps, row_count),
        "source_hash": source_hash,
        "handoff_hash": handoff_hash,
        "diagnostics": tuple(dict(item) for item in diagnostics),
    }
