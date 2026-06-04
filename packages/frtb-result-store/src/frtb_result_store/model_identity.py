"""Canonical run identity payloads and deterministic ids."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from types import MappingProxyType

from frtb_common.hashing import stable_json_hash

from frtb_result_store.model_validation import (
    _require_mapping,
    _require_non_empty_text,
    _require_plain_date,
)


def canonical_run_identity_payload(
    *,
    as_of_date: date,
    regime_id: str,
    calculation_scope: str,
    input_snapshot_id: str,
    calculation_policy_id: str,
    engine_version: str,
    code_version: str,
) -> Mapping[str, object]:
    """Return the canonical payload used to derive a run storage id.
    Parameters
    ----------
    as_of_date : date
        As of date.
    regime_id : str
        Regime id.
    calculation_scope : str
        Calculation scope.
    input_snapshot_id : str
        Input snapshot id.
    calculation_policy_id : str
        Calculation policy id.
    engine_version : str
        Engine version.
    code_version : str
        Code version.

    Returns
    -------
    Mapping[str, object]
        Result of the operation.
    """

    _require_plain_date(as_of_date, "as_of_date")
    for field_name, value in (
        ("regime_id", regime_id),
        ("calculation_scope", calculation_scope),
        ("input_snapshot_id", input_snapshot_id),
        ("calculation_policy_id", calculation_policy_id),
        ("engine_version", engine_version),
        ("code_version", code_version),
    ):
        _require_non_empty_text(value, field_name)
    return MappingProxyType(
        {
            "as_of_date": as_of_date.isoformat(),
            "regime_id": regime_id,
            "calculation_scope": calculation_scope,
            "input_snapshot_id": input_snapshot_id,
            "calculation_policy_id": calculation_policy_id,
            "engine_version": engine_version,
            "code_version": code_version,
        }
    )


def canonical_run_group_identity_payload(
    *,
    as_of_date: date,
    calculation_scope: str,
    input_snapshot_id: str,
    calculation_policy_group_id: str,
    engine_version: str,
    code_version: str,
    group_purpose: str,
) -> Mapping[str, object]:
    """Return the canonical payload used to link comparable regime runs.
    Parameters
    ----------
    as_of_date : date
        As of date.
    calculation_scope : str
        Calculation scope.
    input_snapshot_id : str
        Input snapshot id.
    calculation_policy_group_id : str
        Calculation policy group id.
    engine_version : str
        Engine version.
    code_version : str
        Code version.
    group_purpose : str
        Group purpose.

    Returns
    -------
    Mapping[str, object]
        Result of the operation.
    """

    _require_plain_date(as_of_date, "as_of_date")
    for field_name, value in (
        ("calculation_scope", calculation_scope),
        ("input_snapshot_id", input_snapshot_id),
        ("calculation_policy_group_id", calculation_policy_group_id),
        ("engine_version", engine_version),
        ("code_version", code_version),
        ("group_purpose", group_purpose),
    ):
        _require_non_empty_text(value, field_name)
    return MappingProxyType(
        {
            "as_of_date": as_of_date.isoformat(),
            "calculation_scope": calculation_scope,
            "input_snapshot_id": input_snapshot_id,
            "calculation_policy_group_id": calculation_policy_group_id,
            "engine_version": engine_version,
            "code_version": code_version,
            "group_purpose": group_purpose,
        }
    )


def generate_run_id(identity_payload: Mapping[str, object]) -> str:
    """Generate the full deterministic storage id for a run identity payload.
    Parameters
    ----------
    identity_payload : Mapping[str, object]
        Identity payload.

    Returns
    -------
    str
        Result of the operation.
    """

    _require_mapping(identity_payload, "identity_payload")
    return stable_json_hash(identity_payload)


def generate_run_group_id(identity_payload: Mapping[str, object]) -> str:
    """Generate the full deterministic storage id for a run-group payload.
    Parameters
    ----------
    identity_payload : Mapping[str, object]
        Identity payload.

    Returns
    -------
    str
        Result of the operation.
    """

    _require_mapping(identity_payload, "run_group_identity_payload")
    return stable_json_hash(identity_payload)
