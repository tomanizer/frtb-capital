"""
Desk-level CapitalContribution projection for IMA audit records.

Regulatory traceability:
    ADR 0038 defines the suite-wide attribution contract. This module projects
    already-computed desk audit records without changing IMA capital numbers.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import replace
from numbers import Real

from frtb_common.attribution import AttributionMethod, CapitalContribution, ReconciliationStatus

from frtb_ima.audit import DeskAuditRecord

_RECONCILIATION_TOLERANCE = 1e-6
_ATTRIBUTION_CITATIONS = ("adr_0038",)
_CAPITAL_TOTAL_KEYS = ("total", "models_based_capital", "ima_rc", "IMA_RC")
_COMPONENT_MAP_KEYS = (
    "components",
    "component_breakdown",
    "component_capitals",
    "risk_class_components",
    "risk_class_capitals",
    "bucket_components",
    "bucket_capitals",
)
_COMPONENT_VALUE_KEYS = ("capital", "amount", "contribution", "value")
_CATEGORY_TOKEN_PATTERN = re.compile(r"[^0-9A-Za-z]+")


def desk_contributions(record: DeskAuditRecord) -> tuple[CapitalContribution, ...]:
    """Project one desk audit record to suite-wide attribution records.

    The projection is intentionally read-only: it consumes ``DeskAuditRecord``
    maps and does not recalculate IMA capital. ``input_hash`` is propagated from
    ``record.inputs_hash`` on every emitted record as required by ADR 0038.

    For standard non-floor paths, retained IMCC, SES, and PLA component records
    must reconcile to the desk total within epsilon = 1e-6. If the audit record
    carries reconciling nested component maps, those child components are emitted
    instead of the aggregate. If a max/floor branch is indicated, the unattributed
    difference is emitted as an explicit residual with ``PARTIAL_RESIDUAL`` status.

    Parameters
    ----------
    record : DeskAuditRecord
        Completed desk audit record.

    Returns
    -------
    tuple[CapitalContribution, ...]
        Read-only attribution records for the deepest retained desk grain.
    """
    total = _capital_total(record.capital)
    component_records = _component_records(record)
    component_total = _record_total(component_records)
    tolerance = _RECONCILIATION_TOLERANCE * max(abs(total), 1.0)
    residual = total - component_total

    if abs(residual) <= tolerance:
        return tuple(
            _with_status(item, ReconciliationStatus.RECONCILED) for item in component_records
        )

    status = (
        ReconciliationStatus.PARTIAL_RESIDUAL
        if _floor_or_branch_applied(record.capital)
        else ReconciliationStatus.UNRECONCILED
    )
    reason = (
        "Desk-level max/floor branch creates a residual between component "
        "inputs and selected IMA risk charge."
        if status is ReconciliationStatus.PARTIAL_RESIDUAL
        else "Desk audit components do not reconcile to desk capital total."
    )
    records = [_with_status(item, status) for item in component_records]
    records.append(
        CapitalContribution(
            contribution_id=f"ima:{record.run_id}:{record.desk_id}:IMA_RC_RESIDUAL",
            source_id=record.desk_id,
            source_level="desk",
            bucket_key=record.run_id,
            category="IMA_RC_RESIDUAL",
            base_amount=0.0,
            marginal_multiplier=None,
            contribution=None,
            method=AttributionMethod.RESIDUAL,
            residual=residual,
            reason=reason,
            citations=_ATTRIBUTION_CITATIONS,
            input_hash=record.inputs_hash,
            profile_hash=record.policy_hash,
            reconciliation_status=status,
        )
    )
    return tuple(records)


def _component_records(record: DeskAuditRecord) -> list[CapitalContribution]:
    records: list[CapitalContribution] = []
    for category, amount in _desk_components(record):
        records.append(
            CapitalContribution(
                contribution_id=f"ima:{record.run_id}:{record.desk_id}:{category}",
                source_id=record.desk_id,
                source_level="desk",
                bucket_key=record.run_id,
                category=category,
                base_amount=amount,
                marginal_multiplier=1.0,
                contribution=amount,
                method=AttributionMethod.ANALYTICAL_EULER,
                residual=0.0,
                citations=_ATTRIBUTION_CITATIONS,
                input_hash=record.inputs_hash,
                profile_hash=record.policy_hash,
                reconciliation_status=ReconciliationStatus.UNKNOWN,
            )
        )
    return records


def _desk_components(record: DeskAuditRecord) -> tuple[tuple[str, float], ...]:
    components: list[tuple[str, float]] = []
    imcc = _optional_number(record.capital, "imcc_t_minus_1")
    if imcc is None:
        imcc = _optional_number(record.imcc, "imcc")
    if imcc is not None:
        components.extend(_detail_components_or_aggregate(record.imcc, "IMCC", imcc))

    ses = _optional_number(record.capital, "ses_t_minus_1")
    if ses is None:
        ses = _optional_number(record.ses, "total_ses")
    if ses is not None:
        components.extend(_detail_components_or_aggregate(record.ses, "SES", ses))

    pla_addon = _optional_number(record.capital, "pla_addon")
    if pla_addon is not None:
        components.extend(_detail_components_or_aggregate(record.pla, "PLA_ADDON", pla_addon))

    if not components:
        raise ValueError("DeskAuditRecord must expose at least one IMCC, SES, or PLA component")
    return tuple(components)


def _detail_components_or_aggregate(
    values: Mapping[str, object],
    prefix: str,
    aggregate_amount: float,
) -> tuple[tuple[str, float], ...]:
    details = _reconciling_detail_components(values, prefix, aggregate_amount)
    if details:
        return details
    return ((prefix, aggregate_amount),)


def _reconciling_detail_components(
    values: Mapping[str, object],
    prefix: str,
    aggregate_amount: float,
) -> tuple[tuple[str, float], ...]:
    for key in _COMPONENT_MAP_KEYS:
        raw_components = values.get(key)
        if not isinstance(raw_components, Mapping):
            continue
        details = _detail_component_items(raw_components, prefix, key)
        if not details:
            continue
        detail_total = sum(amount for _, amount in details)
        tolerance = _RECONCILIATION_TOLERANCE * max(abs(aggregate_amount), 1.0)
        if abs(detail_total - aggregate_amount) <= tolerance:
            return details
    return ()


def _detail_component_items(
    raw_components: Mapping[object, object],
    prefix: str,
    map_key: str,
) -> tuple[tuple[str, float], ...]:
    details: list[tuple[str, float]] = []
    for raw_name, raw_amount in raw_components.items():
        amount = _component_amount(raw_amount, f"{map_key}.{raw_name}")
        if amount is None:
            continue
        details.append((f"{prefix}_{_category_token(raw_name)}", amount))
    return tuple(details)


def _component_amount(value: object, field_name: str) -> float | None:
    if isinstance(value, Mapping):
        for key in _COMPONENT_VALUE_KEYS:
            if key in value:
                return _required_number(value[key], f"{field_name}.{key}")
        return None
    return _required_number(value, field_name)


def _category_token(value: object) -> str:
    token = _CATEGORY_TOKEN_PATTERN.sub("_", str(value).strip()).strip("_").upper()
    if not token:
        raise ValueError("component breakdown keys must be non-empty")
    return token


def _capital_total(capital: Mapping[str, object]) -> float:
    for key in _CAPITAL_TOTAL_KEYS:
        value = _optional_number(capital, key)
        if value is not None:
            return value
    allowed = ", ".join(_CAPITAL_TOTAL_KEYS)
    raise ValueError(f"DeskAuditRecord.capital must include one of: {allowed}")


def _optional_number(values: Mapping[str, object] | None, key: str) -> float | None:
    if values is None or key not in values:
        return None
    value = values[key]
    if value is None:
        return None
    return _required_number(value, key)


def _required_number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field_name} must be a finite numeric value")
    amount = float(value)
    if not math.isfinite(amount):
        raise ValueError(f"{field_name} must be finite")
    return amount


def _floor_or_branch_applied(capital: Mapping[str, object] | None) -> bool:
    if capital is None:
        return False
    for key in (
        "floor_applied",
        "imcc_floor_applied",
        "ses_floor_applied",
        "ses_imcc_floor_applied",
    ):
        if bool(capital.get(key, False)):
            return True
    binding_term = capital.get("binding_term")
    return isinstance(binding_term, str) and binding_term.upper() != "SPOT"


def _record_total(records: list[CapitalContribution]) -> float:
    return sum((item.contribution or 0.0) + item.residual for item in records)


def _with_status(
    record: CapitalContribution,
    status: ReconciliationStatus,
) -> CapitalContribution:
    return replace(record, reconciliation_status=status)


__all__ = ["desk_contributions"]
