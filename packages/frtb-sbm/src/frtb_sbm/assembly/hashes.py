"""Deterministic hash payload assembly for SBM inputs and profiles.

Regulatory traceability:
    SBM-AUDIT-001 requires stable replay hashes for accepted input rows and
    supported profile content. This module owns the hash payload shape used by
    row, batch, and profile ingress paths.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from datetime import date
from typing import TYPE_CHECKING, cast

import numpy as np
import numpy.typing as npt
from frtb_common import stable_json_hash

from frtb_sbm.data_models import (
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSourceLineage,
)
from frtb_sbm.org_scope import scope_at, scope_payload
from frtb_sbm.reference_data import profile_reference_payload

if TYPE_CHECKING:
    from frtb_sbm.batch import SbmSensitivityBatch

ObjectArray = npt.NDArray[np.object_]

INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2 = "arrow-columnar-v2"
INPUT_HASH_ALGORITHM_ARROW_PORTFOLIO_V2 = "arrow-columnar-v2-portfolio"
INPUT_HASH_ALGORITHM_JSON_ROW_V1 = "json-row-v1"


def input_hash_for_validated_sensitivities(
    sensitivities: tuple[SbmSensitivity, ...],
) -> str:
    """Return an input hash for an already validated sensitivity tuple.

    Parameters
    ----------
    sensitivities
        Validated canonical SBM sensitivity rows.

    Returns
    -------
    str
    """

    return stable_json_hash(
        {"sensitivities": [sensitivity_payload(sensitivity) for sensitivity in sensitivities]}
    )


def input_hash_for_sbm_batch(batch: SbmSensitivityBatch) -> str:
    """Return the row-equivalent deterministic input hash for a homogeneous batch.

    Parameters
    ----------
    batch
        Kernel-facing SBM sensitivity batch.

    Returns
    -------
    str
    """

    return stable_json_hash({"sensitivities": list(sensitivity_payloads_from_batch(batch))})


def input_hash_for_sbm_batches(batches: Iterable[SbmSensitivityBatch]) -> str:
    """Return the deterministic input hash for a batch portfolio.

    Parameters
    ----------
    batches : Iterable[SbmSensitivityBatch]
        Validated package-owned SBM batches.

    Returns
    -------
    str
        Row JSON digest for row/column batches, or an Arrow portfolio digest
        when every batch carries ``arrow-columnar-v2``.
    """

    batch_tuple = tuple(batches)
    if _all_arrow_columnar_batches(batch_tuple):
        digest = hashlib.sha256()
        digest.update(INPUT_HASH_ALGORITHM_ARROW_PORTFOLIO_V2.encode("utf-8"))
        digest.update(b"\0")
        for batch in sorted(
            batch_tuple,
            key=lambda item: (item.risk_class.value, item.risk_measure.value, item.input_hash),
        ):
            digest.update(batch.input_hash.encode("utf-8"))
        return digest.hexdigest()

    return stable_json_hash(
        {
            "sensitivities": [
                payload
                for batch in batch_tuple
                for payload in sensitivity_payloads_from_batch(batch)
            ]
        }
    )


def input_hash_algorithm_for_sbm_batches(batches: Iterable[SbmSensitivityBatch]) -> str:
    """Return the result-level input hash algorithm for a batch portfolio.

    Parameters
    ----------
    batches : Iterable[SbmSensitivityBatch]
        Validated package-owned SBM batches.

    Returns
    -------
    str
        ``arrow-columnar-v2-portfolio`` when all batches are Arrow-columnar,
        otherwise ``json-row-v1``.
    """

    batch_tuple = tuple(batches)
    if _all_arrow_columnar_batches(batch_tuple):
        return INPUT_HASH_ALGORITHM_ARROW_PORTFOLIO_V2
    return INPUT_HASH_ALGORITHM_JSON_ROW_V1


def _all_arrow_columnar_batches(batches: tuple[SbmSensitivityBatch, ...]) -> bool:
    return bool(batches) and all(
        batch.input_hash_algorithm == INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2 for batch in batches
    )


def profile_content_hash_from_parts(
    *,
    profile: SbmRegulatoryProfile,
    metadata: Mapping[str, object],
    supported_measures: Mapping[SbmRiskClass, frozenset[SbmRiskMeasure]],
) -> str:
    """Return the deterministic content hash for supported profile parts.

    Parameters
    ----------
    profile
        Supported regulatory profile.
    metadata
        Profile metadata used in the public ``SbmRuleProfile``.
    supported_measures
        Supported risk-class/measure matrix for the profile.

    Returns
    -------
    str
    """

    return stable_json_hash(
        {
            "metadata": {
                key: value.isoformat() if isinstance(value, date) else value
                for key, value in sorted(metadata.items())
            },
            "supported_measures": {
                risk_class.value: sorted(measure.value for measure in measures)
                for risk_class, measures in sorted(
                    supported_measures.items(),
                    key=lambda item: item[0].value,
                )
            },
            "reference_data": profile_reference_payload(profile),
        }
    )


def sensitivity_payload(sensitivity: SbmSensitivity) -> dict[str, object]:
    """Return the stable row-hash payload for one canonical sensitivity.

    Parameters
    ----------
    sensitivity
        Canonical SBM sensitivity row.

    Returns
    -------
    dict[str, object]
    """

    payload: dict[str, object] = {
        "sensitivity_id": sensitivity.sensitivity_id,
        "source_row_id": sensitivity.source_row_id,
        "desk_id": sensitivity.desk_id,
        "legal_entity": sensitivity.legal_entity,
        "risk_class": sensitivity.risk_class.value,
        "risk_measure": sensitivity.risk_measure.value,
        "bucket": sensitivity.bucket,
        "risk_factor": sensitivity.risk_factor,
        "amount": sensitivity.amount,
        "amount_currency": sensitivity.amount_currency,
        "sign_convention": sensitivity.sign_convention.value,
        "lineage": lineage_payload(sensitivity.lineage),
        "mapping_citation_ids": list(sensitivity.mapping_citation_ids),
    }
    optional_fields = {
        "position_id": sensitivity.position_id,
        "qualifier": sensitivity.qualifier,
        "tenor": sensitivity.tenor,
        "option_tenor": sensitivity.option_tenor,
        "liquidity_horizon_days": sensitivity.liquidity_horizon_days,
        "maturity": sensitivity.maturity,
        "up_shock_amount": sensitivity.up_shock_amount,
        "down_shock_amount": sensitivity.down_shock_amount,
        "risk_factor_id": sensitivity.risk_factor_id,
        "risk_factor_mapping_version": sensitivity.risk_factor_mapping_version,
        "bucket_label": sensitivity.bucket_label,
    }
    for field_name, value in optional_fields.items():
        if value is not None:
            payload[field_name] = value
    org_scope = scope_payload(sensitivity.org_scope)
    if org_scope is not None:
        payload["org_scope"] = org_scope
    return payload


def lineage_payload(lineage: SbmSourceLineage) -> dict[str, object]:
    """Return the stable row-hash payload for source lineage.

    Parameters
    ----------
    lineage
        Source lineage attached to a canonical SBM sensitivity row.

    Returns
    -------
    dict[str, object]
    """

    return {
        "source_system": lineage.source_system,
        "source_file": lineage.source_file,
        "source_row_id": lineage.source_row_id,
        "source_column_map": [list(pair) for pair in lineage.source_column_map],
    }


def sensitivity_payloads_from_batch(
    batch: SbmSensitivityBatch,
) -> Iterable[dict[str, object]]:
    """Yield row-equivalent stable hash payloads from an SBM batch.

    Parameters
    ----------
    batch
        Kernel-facing SBM sensitivity batch.

    Returns
    -------
    Iterable[dict[str, object]]
    """

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
        org_scope = scope_payload(scope_at(batch.org_scopes, row_index))
        if org_scope is not None:
            payload["org_scope"] = org_scope
        _add_optional_payload_field(payload, "risk_factor_id", batch.risk_factor_ids, row_index)
        _add_optional_payload_field(
            payload,
            "risk_factor_mapping_version",
            batch.risk_factor_mapping_versions,
            row_index,
        )
        _add_optional_payload_field(payload, "bucket_label", batch.bucket_labels, row_index)
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


def _str_at(values: ObjectArray, row_index: int) -> str:
    return cast(str, values[row_index])


__all__ = [
    "INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2",
    "INPUT_HASH_ALGORITHM_ARROW_PORTFOLIO_V2",
    "INPUT_HASH_ALGORITHM_JSON_ROW_V1",
    "input_hash_algorithm_for_sbm_batches",
    "input_hash_for_sbm_batch",
    "input_hash_for_sbm_batches",
    "input_hash_for_validated_sensitivities",
    "lineage_payload",
    "profile_content_hash_from_parts",
    "sensitivity_payload",
    "sensitivity_payloads_from_batch",
]
