"""Deterministic audit helpers for DRC result replay."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

from frtb_common import jsonable

from frtb_drc._hashing import hash_payload as _stable_hash_payload
from frtb_drc.data_models import (
    CategoryDrc,
    DefaultDirection,
    DrcCapitalResult,
    DrcPosition,
    DrcRiskClass,
)
from frtb_drc.regimes import get_rule_profile
from frtb_drc.validation import DrcInputError


def input_snapshot_hash(positions: Iterable[DrcPosition]) -> str:
    """Hash canonical DRC inputs in deterministic position-id order."""

    payload = [
        position.as_dict()
        for position in sorted(
            positions,
            key=lambda position: (position.position_id, position.source_row_id),
        )
    ]
    return _hash_payload(payload)


def rule_profile_hash(profile_id: str) -> str:
    """Return the selected rule profile content hash."""

    return get_rule_profile(profile_id).content_hash


def serialize_result(result: DrcCapitalResult) -> dict[str, object]:
    """Return a JSON-ready deterministic result snapshot."""

    return _sort_mapping(jsonable(result.as_dict()))


def result_json(result: DrcCapitalResult) -> str:
    """Serialize a result with stable JSON key order and compact separators."""

    return json.dumps(serialize_result(result), sort_keys=True, separators=(",", ":"))


def validate_reconciliation(result: DrcCapitalResult, *, tolerance: float = 1e-12) -> None:
    """Validate bucket/category/total reconciliation and HBR arithmetic."""

    category_total = 0.0
    for category in result.categories:
        bucket_total = _expected_category_capital(category)
        if abs(bucket_total - category.capital) > tolerance:
            raise DrcInputError(f"category capital does not reconcile: {category.category_id}")
        category_total += category.capital
        for bucket in category.bucket_results:
            expected_denominator = bucket.hbr.aggregate_net_long + bucket.hbr.aggregate_net_short
            if abs(expected_denominator - bucket.hbr.denominator) > tolerance:
                raise DrcInputError(f"HBR denominator does not reconcile: {bucket.bucket_id}")
            expected_ratio = (
                0.0
                if bucket.hbr.denominator == 0.0
                else bucket.hbr.aggregate_net_long / bucket.hbr.denominator
            )
            if abs(expected_ratio - bucket.hbr.ratio) > tolerance:
                raise DrcInputError(f"HBR ratio does not reconcile: {bucket.bucket_id}")

    if abs(category_total - result.total_drc) > tolerance:
        raise DrcInputError("total DRC does not reconcile to category capital")

    _validate_net_records(result)


def _expected_category_capital(category: CategoryDrc) -> float:
    risk_class = DrcRiskClass(category.risk_class)
    bucket_results = category.bucket_results
    if risk_class == DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        aggregated = sum(
            max(bucket.capital, 0.0) + 0.5 * min(bucket.capital, 0.0) for bucket in bucket_results
        )
        return max(aggregated, 0.0)
    return sum(bucket.capital for bucket in bucket_results)


def _validate_net_records(result: DrcCapitalResult) -> None:
    for record in result.net_jtds:
        if DefaultDirection(record.net_direction) == DefaultDirection.LONG:
            signed_amount = record.net_amount
        else:
            signed_amount = -record.net_amount
        signed_scaled = record.scaled_long - record.scaled_short
        if abs(signed_amount - signed_scaled) > 1e-12:
            raise DrcInputError(f"net JTD does not reconcile to scaled legs: {record.net_jtd_id}")


def _hash_payload(payload: object) -> str:
    return _stable_hash_payload(payload)


def _sort_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):  # pragma: no cover - DrcCapitalResult is always a mapping.
        raise TypeError("serialized DRC result must be a mapping")
    return {str(key): _sort_value(item) for key, item in sorted(value.items())}


def _sort_value(value: Any) -> object:
    if isinstance(value, Mapping):
        return {str(key): _sort_value(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_sort_value(item) for item in value]
    return value
