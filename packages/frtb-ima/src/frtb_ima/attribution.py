"""
Desk-level CapitalContribution projection for IMA audit records.

Regulatory traceability:
    ADR 0038 defines the suite-wide attribution contract. This module projects
    already-computed desk audit records without changing IMA capital numbers.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from numbers import Real
from typing import Any

from frtb_common.attribution import AttributionMethod, CapitalContribution, ReconciliationStatus
from frtb_common.contribution_bundle import ComponentContributionBundle

from frtb_ima.audit import DeskAuditRecord

_RECONCILIATION_TOLERANCE = 1e-6
_ATTRIBUTION_CITATIONS = ("adr_0038",)
_COMPONENT_NAME = "frtb_ima"
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
_SEQUENCE_TYPES = (str, bytes, bytearray)
_NMRF_EXPLAIN_REASON = (
    "NMRF SES risk-factor amount is branch-local evidence only; the SES "
    "square-root aggregation is not emitted as additive Euler capital."
)
_LHA_EXPLAIN_REASON = (
    "Liquidity-horizon ES amount is branch-local evidence only; the LHA "
    "square-root aggregation is not emitted as additive Euler capital."
)


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

    NMRF risk-factor SES and liquidity-horizon ES audit details are emitted as
    explicit ``UNSUPPORTED`` explain records because their square-root and
    scenario-selection mechanics are not additive Euler contributions.

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
    explain_records = _explain_records(record)
    component_total = _record_total(component_records)
    tolerance = _RECONCILIATION_TOLERANCE * max(abs(total), 1.0)
    residual = total - component_total

    if abs(residual) <= tolerance:
        reconciled = tuple(
            _with_status(item, ReconciliationStatus.RECONCILED) for item in component_records
        )
        return reconciled + explain_records

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
    return tuple(records) + explain_records


def build_ima_contribution_bundle(
    records: DeskAuditRecord | Iterable[DeskAuditRecord],
    *,
    total_ima_capital: float | None = None,
) -> ComponentContributionBundle:
    """Return an orchestration-ready IMA contribution bundle.

    Parameters
    ----------
    records : DeskAuditRecord or iterable of DeskAuditRecord
        Completed IMA desk audit records from one run and policy profile.
    total_ima_capital : float, optional
        Expected IMA summary total, for example
        ``ImaCapitalSummary.total_ima_capital``. When omitted, the helper uses
        the sum of the emitted additive contribution and residual amounts.

    Returns
    -------
    ComponentContributionBundle
        Shared suite attribution bundle with ``component="frtb_ima"``.
    """

    desk_records = _normalise_records(records)
    run_id = desk_records[0].run_id
    input_hash = desk_records[0].inputs_hash
    profile_hash = desk_records[0].policy_hash
    for record in desk_records:
        if record.run_id != run_id:
            raise ValueError("IMA contribution bundle records must share one run_id")
        if record.inputs_hash != input_hash:
            raise ValueError("IMA contribution bundle records must share one inputs_hash")
        if record.policy_hash != profile_hash:
            raise ValueError("IMA contribution bundle records must share one policy_hash")

    contributions = tuple(item for record in desk_records for item in desk_contributions(record))
    contribution_total = _contribution_total(contributions)
    component_total = contribution_total
    if total_ima_capital is not None:
        component_total = _required_number(total_ima_capital, "total_ima_capital")
        _validate_contribution_total(contributions, component_total)

    return ComponentContributionBundle(
        component=_COMPONENT_NAME,
        contributions=contributions,
        component_total=component_total,
        component_input_hash=input_hash,
        component_profile_hash=profile_hash,
    )


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


def _explain_records(record: DeskAuditRecord) -> tuple[CapitalContribution, ...]:
    return _nmrf_explain_records(record) + _lha_explain_records(record)


def _nmrf_explain_records(record: DeskAuditRecord) -> tuple[CapitalContribution, ...]:
    ses = record.ses if isinstance(record.ses, Mapping) else None
    if ses is None:
        return ()

    records: list[CapitalContribution] = []
    records.extend(_nmrf_result_records(record, ses.get("type_a_results"), "TYPE_A"))
    records.extend(_nmrf_result_records(record, ses.get("type_b_results"), "TYPE_B"))
    return tuple(records)


def _nmrf_result_records(
    record: DeskAuditRecord,
    raw_results: object,
    route: str,
) -> tuple[CapitalContribution, ...]:
    records: list[CapitalContribution] = []
    for index, raw_item in enumerate(_sequence_items(raw_results)):
        if not isinstance(raw_item, Mapping):
            continue
        amount = _optional_number(raw_item, "ses")
        if amount is None:
            continue
        risk_factor = _source_name(raw_item, ("risk_factor_name", "risk_factor", "name"), index)
        method = str(raw_item.get("method", "UNKNOWN"))
        source = str(raw_item.get("source", "")).strip()
        reason = _NMRF_EXPLAIN_REASON
        if method != "UNKNOWN" or source:
            reason = f"{reason} Upstream method={method}; source={source or 'not provided'}."
        records.append(
            _unsupported_explain_record(
                record,
                source_id=risk_factor,
                source_level="risk_factor",
                category=f"SES_NMRF_{route}",
                base_amount=amount,
                reason=reason,
            )
        )
    return tuple(records)


def _lha_explain_records(record: DeskAuditRecord) -> tuple[CapitalContribution, ...]:
    imcc = record.imcc if isinstance(record.imcc, Mapping) else None
    if imcc is None:
        return ()

    records: list[CapitalContribution] = []
    unconstrained = imcc.get("unconstrained")
    if isinstance(unconstrained, Mapping):
        records.extend(
            _lha_component_records(
                record,
                raw_components=unconstrained.get("components"),
                category="IMCC_LH_UNCONSTRAINED",
                source_prefix="UNCONSTRAINED",
            )
        )

    for raw_component in _sequence_items(imcc.get("constrained_components")):
        if not isinstance(raw_component, Mapping):
            continue
        risk_class = _source_name(raw_component, ("risk_class", "name"), 0)
        lha_result = raw_component.get("lha_es_result")
        if not isinstance(lha_result, Mapping):
            continue
        records.extend(
            _lha_component_records(
                record,
                raw_components=lha_result.get("components"),
                category="IMCC_LH_CONSTRAINED",
                source_prefix=f"CONSTRAINED:{risk_class}",
            )
        )
    return tuple(records)


def _lha_component_records(
    record: DeskAuditRecord,
    *,
    raw_components: object,
    category: str,
    source_prefix: str,
) -> tuple[CapitalContribution, ...]:
    records: list[CapitalContribution] = []
    for index, raw_item in enumerate(_sequence_items(raw_components)):
        if not isinstance(raw_item, Mapping):
            continue
        present = raw_item.get("present", True)
        if present is False:
            continue
        amount = _optional_number(raw_item, "expected_shortfall")
        if amount is None:
            continue
        horizon = _source_name(raw_item, ("liquidity_horizon", "horizon", "name"), index)
        weighted_square = raw_item.get("weighted_square")
        reason = _LHA_EXPLAIN_REASON
        if weighted_square is not None:
            square = _required_number(weighted_square, "weighted_square")
            reason = f"{reason} Weighted square={square:.6g}."
        records.append(
            _unsupported_explain_record(
                record,
                source_id=f"{source_prefix}:{horizon}",
                source_level="liquidity_horizon",
                category=category,
                base_amount=amount,
                reason=reason,
            )
        )
    return tuple(records)


def _unsupported_explain_record(
    record: DeskAuditRecord,
    *,
    source_id: str,
    source_level: str,
    category: str,
    base_amount: float,
    reason: str,
) -> CapitalContribution:
    source_token = _category_token(source_id)
    return CapitalContribution(
        contribution_id=f"ima:{record.run_id}:{record.desk_id}:{category}:{source_token}",
        source_id=source_id,
        source_level=source_level,
        bucket_key=record.run_id,
        category=category,
        base_amount=base_amount,
        marginal_multiplier=None,
        contribution=None,
        method=AttributionMethod.UNSUPPORTED,
        residual=0.0,
        reason=reason,
        citations=_ATTRIBUTION_CITATIONS,
        input_hash=record.inputs_hash,
        profile_hash=record.policy_hash,
        reconciliation_status=ReconciliationStatus.UNKNOWN,
    )


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
    values: Mapping[str, object] | None,
    prefix: str,
    aggregate_amount: float,
) -> tuple[tuple[str, float], ...]:
    details = _reconciling_detail_components(values, prefix, aggregate_amount)
    if details:
        return details
    return ((prefix, aggregate_amount),)


def _reconciling_detail_components(
    values: Mapping[str, object] | None,
    prefix: str,
    aggregate_amount: float,
) -> tuple[tuple[str, float], ...]:
    if not isinstance(values, Mapping):
        return ()
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


def _normalise_records(
    records: DeskAuditRecord | Iterable[DeskAuditRecord],
) -> tuple[DeskAuditRecord, ...]:
    if isinstance(records, DeskAuditRecord):
        normalised = (records,)
    elif isinstance(records, Iterable) and not isinstance(records, (str, bytes, bytearray)):
        normalised = tuple(records)
    else:
        raise ValueError("records must be a DeskAuditRecord or iterable of DeskAuditRecord")
    if not normalised:
        raise ValueError("records must include at least one DeskAuditRecord")
    if not all(isinstance(record, DeskAuditRecord) for record in normalised):
        raise ValueError("records must contain only DeskAuditRecord instances")
    return normalised


def _validate_contribution_total(
    records: tuple[CapitalContribution, ...],
    component_total: float,
) -> None:
    contribution_total = _contribution_total(records)
    tolerance = _RECONCILIATION_TOLERANCE * max(abs(component_total), 1.0)
    if abs(contribution_total - component_total) > tolerance:
        raise ValueError(
            "IMA contribution records do not reconcile to total_ima_capital: "
            f"{contribution_total:.6g} != {component_total:.6g}"
        )


def _contribution_total(records: tuple[CapitalContribution, ...]) -> float:
    return sum((item.contribution or 0.0) + item.residual for item in records)


def _sequence_items(value: object) -> tuple[object, ...]:
    if isinstance(value, Sequence) and not isinstance(value, _SEQUENCE_TYPES):
        return tuple(value)
    return ()


def _source_name(
    values: Mapping[object, object],
    keys: tuple[str, ...],
    fallback_index: int,
) -> str:
    for key in keys:
        name = _source_name_value(values.get(key), keys)
        if name is not None:
            return name
    return f"item_{fallback_index}"


def _source_name_value(value: object, keys: tuple[str, ...]) -> str | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        for key in keys:
            name = _source_name_value(value.get(key), keys)
            if name is not None:
                return name
        return None
    text = str(value).strip()
    return text or None


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


def _optional_number(values: Mapping[Any, object] | None, key: str) -> float | None:
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


__all__ = ["build_ima_contribution_bundle", "desk_contributions"]
