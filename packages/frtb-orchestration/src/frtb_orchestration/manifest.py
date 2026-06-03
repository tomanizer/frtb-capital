"""Manifest-driven client ingress for Standardised Approach handoffs."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType

import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import (
    ComponentCapitalSummary,
    NormalizedArrowTable,
    StandardisedComponent,
    arrow_table_content_hash,
    normalized_arrow_table_hash,
)

from frtb_orchestration.standardised import (
    OrchestrationInputError,
    StandardisedApproachCapitalResult,
    compose_standardised_approach_capital,
    standardised_jurisdiction_family,
)

SBM_GIRR_DELTA_HANDOFF = "sbm.girr_delta"
DRC_NONSEC_HANDOFF = "drc.nonsec"
DRC_SECURITISATION_NON_CTP_HANDOFF = "drc.securitisation_non_ctp"
DRC_CTP_HANDOFF = "drc.ctp"
RRAO_POSITIONS_HANDOFF = "rrao.positions"
CVA_COUNTERPARTY_HANDOFF = "cva.counterparty"
CVA_NETTING_SET_HANDOFF = "cva.netting_set"
CVA_HEDGE_HANDOFF = "cva.hedge"
CVA_SA_SENSITIVITY_HANDOFF = "cva.sa_sensitivity"

STANDARDISED_REQUIRED_INPUT_TABLE_KEYS = (
    SBM_GIRR_DELTA_HANDOFF,
    DRC_NONSEC_HANDOFF,
    RRAO_POSITIONS_HANDOFF,
)
STANDARDISED_REQUIRED_HANDOFF_KEYS = STANDARDISED_REQUIRED_INPUT_TABLE_KEYS


NormalizeCallable = Callable[..., NormalizedArrowTable]
BuildBatchCallable = Callable[[NormalizedArrowTable], object]
CalculateBatchCallable = Callable[..., object]
ToComponentSummaryCallable = Callable[[object], ComponentCapitalSummary]


@dataclass(frozen=True)
class CapitalRunManifest:
    """Client-supplied tables and run context for one capital run."""

    run_id: str
    calculation_date: date
    profile_id: str
    base_currency: str
    handoffs: Mapping[str, pa.Table]
    sbm_context: object | None = None
    drc_context: object | None = None
    rrao_context: object | None = None
    cva_context: object | None = None
    reference_attachments: Mapping[str, pa.Table] = field(default_factory=dict)
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run_id")
        if not isinstance(self.calculation_date, date):
            raise OrchestrationInputError(
                "calculation_date must be a date", field="calculation_date"
            )
        _require_text(self.profile_id, "profile_id")
        _require_text(self.base_currency, "base_currency")
        object.__setattr__(self, "handoffs", _freeze_table_mapping(self.handoffs, "handoffs"))
        object.__setattr__(
            self,
            "reference_attachments",
            _freeze_table_mapping(self.reference_attachments, "reference_attachments"),
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class ManifestHandoffRoute:
    """Registered public package callables for one manifest handoff key."""

    logical_name: str
    component: StandardisedComponent | None
    normalize: NormalizeCallable
    build_batch: BuildBatchCallable | None = None
    calculate_batch: CalculateBatchCallable | None = None
    to_component_summary: ToComponentSummaryCallable | None = None
    context_attr: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.logical_name, "logical_name")
        if self.component is not None and not isinstance(self.component, StandardisedComponent):
            raise OrchestrationInputError("component must be a StandardisedComponent")
        if self.calculate_batch is not None and self.context_attr is None:
            raise OrchestrationInputError(
                "context_attr is required when calculate_batch is supplied",
                field="context_attr",
            )


@dataclass(frozen=True)
class ManifestHandoffValidation:
    """Validation result for one manifest handoff table."""

    logical_name: str
    accepted_row_count: int
    rejected_row_count: int
    diagnostics: tuple[Mapping[str, object], ...]
    source_hash: str | None
    handoff_hash: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "accepted_row_count": self.accepted_row_count,
            "diagnostics": [dict(item) for item in self.diagnostics],
            "handoff_hash": self.handoff_hash,
            "logical_name": self.logical_name,
            "rejected_row_count": self.rejected_row_count,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True)
class ManifestValidationResult:
    """Validation-only result for a capital run manifest."""

    run_id: str
    profile_id: str
    base_currency: str
    jurisdiction_family: str | None
    handoffs: tuple[ManifestHandoffValidation, ...]
    missing_required_handoffs: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.missing_required_handoffs and not self.errors

    def as_dict(self) -> dict[str, object]:
        return {
            "base_currency": self.base_currency,
            "errors": list(self.errors),
            "handoffs": [handoff.as_dict() for handoff in self.handoffs],
            "jurisdiction_family": self.jurisdiction_family,
            "missing_required_handoffs": list(self.missing_required_handoffs),
            "profile_id": self.profile_id,
            "run_id": self.run_id,
            "valid": self.valid,
        }


@dataclass(frozen=True)
class SaManifestRunResult:
    """Result of running validation and available SA component routes."""

    validation: ManifestValidationResult
    component_summaries: tuple[ComponentCapitalSummary, ...] = ()
    standardised_result: StandardisedApproachCapitalResult | None = None
    orchestration_error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "component_summaries": [
                _component_summary_as_dict(summary) for summary in self.component_summaries
            ],
            "orchestration_error": self.orchestration_error,
            "standardised_result": None
            if self.standardised_result is None
            else self.standardised_result.as_dict(),
            "validation": self.validation.as_dict(),
        }


def validate_capital_run_manifest(
    manifest: CapitalRunManifest,
    *,
    routes: Mapping[str, ManifestHandoffRoute],
    required_handoff_keys: Sequence[str] = STANDARDISED_REQUIRED_INPUT_TABLE_KEYS,
) -> ManifestValidationResult:
    """Validate manifest handoff tables without calculating capital."""

    validations: list[ManifestHandoffValidation] = []
    errors: list[str] = []
    try:
        jurisdiction_family = standardised_jurisdiction_family(manifest.profile_id)
    except OrchestrationInputError as exc:
        jurisdiction_family = None
        errors.append(str(exc))

    for logical_name in sorted(manifest.handoffs):
        table = manifest.handoffs[logical_name]
        route = routes.get(logical_name)
        if route is None:
            errors.append(f"no route registered for handoff {logical_name}")
            continue
        validations.append(_validate_one_handoff(logical_name, table, route))

    errors.extend(
        _profile_consistency_errors(
            manifest,
            routes=routes,
            manifest_jurisdiction_family=jurisdiction_family,
        )
    )
    missing = tuple(key for key in required_handoff_keys if key not in manifest.handoffs)
    return ManifestValidationResult(
        run_id=manifest.run_id,
        profile_id=manifest.profile_id,
        base_currency=manifest.base_currency,
        jurisdiction_family=jurisdiction_family,
        handoffs=tuple(validations),
        missing_required_handoffs=missing,
        errors=tuple(errors),
    )


def run_standardised_approach_from_manifest(
    manifest: CapitalRunManifest,
    *,
    routes: Mapping[str, ManifestHandoffRoute],
    required_handoff_keys: Sequence[str] = STANDARDISED_REQUIRED_INPUT_TABLE_KEYS,
) -> SaManifestRunResult:
    """Validate, route available SA handoffs, and compose SA capital if complete."""

    validation = validate_capital_run_manifest(
        manifest,
        routes=routes,
        required_handoff_keys=required_handoff_keys,
    )
    component_summaries: list[ComponentCapitalSummary] = []
    orchestration_error: str | None = None

    for logical_name in sorted(manifest.handoffs):
        route = routes.get(logical_name)
        if route is None or route.calculate_batch is None or route.to_component_summary is None:
            continue
        try:
            source_hash = arrow_table_content_hash(manifest.handoffs[logical_name])
            handoff = route.normalize(manifest.handoffs[logical_name], source_hash=source_hash)
            batch = handoff if route.build_batch is None else route.build_batch(handoff)
            context_attr = route.context_attr or ""
            context = getattr(manifest, context_attr, None)
            if context is None:
                raise OrchestrationInputError(
                    f"Required context {context_attr!r} is missing from the manifest",
                    field=context_attr,
                )
            calculation = route.calculate_batch(batch, context=context)
            result = getattr(calculation, "result", calculation)
            component_summaries.append(route.to_component_summary(result))
        except Exception as exc:
            orchestration_error = f"{logical_name}: {exc}"

    if orchestration_error is None:
        try:
            standardised = compose_standardised_approach_capital(
                sbm_summary=_component_summary(component_summaries, StandardisedComponent.SBM),
                drc_summary=_component_summary(component_summaries, StandardisedComponent.DRC),
                rrao_summary=_component_summary(component_summaries, StandardisedComponent.RRAO),
                run_id=manifest.run_id,
            )
        except Exception as exc:
            orchestration_error = str(exc)
            standardised = None
    else:
        standardised = None

    return SaManifestRunResult(
        validation=validation,
        component_summaries=tuple(component_summaries),
        standardised_result=standardised,
        orchestration_error=orchestration_error,
    )


def _validate_one_handoff(
    logical_name: str,
    table: pa.Table,
    route: ManifestHandoffRoute,
) -> ManifestHandoffValidation:
    source_hash = arrow_table_content_hash(table)
    try:
        handoff = route.normalize(table, source_hash=source_hash)
        if route.build_batch is not None:
            route.build_batch(handoff)
    except Exception as exc:
        return ManifestHandoffValidation(
            logical_name=logical_name,
            accepted_row_count=0,
            rejected_row_count=table.num_rows,
            diagnostics=(
                {
                    "code": "MANIFEST_HANDOFF_VALIDATION_ERROR",
                    "message": str(exc),
                    "severity": "error",
                },
            ),
            source_hash=source_hash,
            handoff_hash=None,
        )
    return ManifestHandoffValidation(
        logical_name=logical_name,
        accepted_row_count=handoff.accepted.num_rows,
        rejected_row_count=0 if handoff.rejected is None else handoff.rejected.num_rows,
        diagnostics=tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics),
        source_hash=source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
    )


def _component_summary(
    summaries: Sequence[ComponentCapitalSummary],
    component: StandardisedComponent,
) -> ComponentCapitalSummary | None:
    matches = tuple(summary for summary in summaries if summary.component is component)
    if not matches:
        return None
    if len(matches) > 1:
        raise OrchestrationInputError(
            f"multiple {component.value} component summaries were produced",
            field="component_summaries",
        )
    return matches[0]


def _component_summary_as_dict(summary: ComponentCapitalSummary) -> dict[str, object]:
    return {
        "base_currency": summary.base_currency,
        "calculation_date": summary.calculation_date.isoformat(),
        "citations": list(summary.citations),
        "component": summary.component.value,
        "excluded_line_count": summary.excluded_line_count,
        "input_hash": summary.input_hash,
        "line_count": summary.line_count,
        "package_name": summary.package_name,
        "profile_hash": summary.profile_hash,
        "profile_id": summary.profile_id,
        "run_id": summary.run_id,
        "subtotal_count": summary.subtotal_count,
        "total_capital": summary.total_capital,
        "warnings": list(summary.warnings),
    }


def _profile_consistency_errors(
    manifest: CapitalRunManifest,
    *,
    routes: Mapping[str, ManifestHandoffRoute],
    manifest_jurisdiction_family: str | None,
) -> tuple[str, ...]:
    if manifest_jurisdiction_family is None:
        return ()

    errors: list[str] = []
    for logical_name in sorted(manifest.handoffs):
        route = routes.get(logical_name)
        if route is None or route.context_attr is None:
            continue
        context = getattr(manifest, route.context_attr)
        if context is None:
            errors.append(f"{logical_name} requires manifest.{route.context_attr}")
            continue
        profile_id = _context_profile_id(context)
        if profile_id is None:
            continue
        try:
            context_family = standardised_jurisdiction_family(profile_id)
        except OrchestrationInputError as exc:
            errors.append(f"{logical_name} context profile_id {profile_id!r}: {exc}")
            continue
        if context_family != manifest_jurisdiction_family:
            errors.append(
                f"{logical_name} context profile_id {profile_id!r} is in "
                f"{context_family}, but manifest profile_id {manifest.profile_id!r} is in "
                f"{manifest_jurisdiction_family}"
            )
    return tuple(errors)


def _context_profile_id(context: object) -> str | None:
    raw_profile = getattr(context, "profile_id", None)
    if raw_profile is None:
        raw_profile = getattr(context, "profile", None)
    profile_value = getattr(raw_profile, "value", raw_profile)
    if isinstance(profile_value, str) and profile_value.strip():
        return profile_value
    return None


def _freeze_table_mapping(
    values: Mapping[str, pa.Table],
    field_name: str,
) -> Mapping[str, pa.Table]:
    frozen = dict(values)
    for key, value in frozen.items():
        if not isinstance(key, str) or not key.strip():
            raise OrchestrationInputError(
                f"{field_name} keys must be non-empty text",
                field=field_name,
            )
        if not isinstance(value, pa.Table):
            raise OrchestrationInputError(f"{field_name}[{key!r}] must be a pyarrow.Table")
    return MappingProxyType(frozen)


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise OrchestrationInputError(f"{field_name} must be non-empty text", field=field_name)


__all__ = [
    "CVA_COUNTERPARTY_HANDOFF",
    "CVA_HEDGE_HANDOFF",
    "CVA_NETTING_SET_HANDOFF",
    "CVA_SA_SENSITIVITY_HANDOFF",
    "DRC_CTP_HANDOFF",
    "DRC_NONSEC_HANDOFF",
    "DRC_SECURITISATION_NON_CTP_HANDOFF",
    "RRAO_POSITIONS_HANDOFF",
    "SBM_GIRR_DELTA_HANDOFF",
    "STANDARDISED_REQUIRED_HANDOFF_KEYS",
    "STANDARDISED_REQUIRED_INPUT_TABLE_KEYS",
    "CapitalRunManifest",
    "ManifestHandoffRoute",
    "ManifestHandoffValidation",
    "ManifestValidationResult",
    "SaManifestRunResult",
    "run_standardised_approach_from_manifest",
    "validate_capital_run_manifest",
]
