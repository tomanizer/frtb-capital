"""Suite-level artifact evidence read models.

This module composes time-series, shock, scenario-vector, and surface evidence
references for Navigator and result-store handoff views. It deliberately stores
only resolved identifiers and status metadata. It does not fetch artifacts,
query result stores, source market data, or alter capital calculations.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from frtb_common import StandardisedComponent

from frtb_orchestration._suite_attribution_models import SuiteCapitalResult
from frtb_orchestration._validation import OrchestrationInputError


class ArtifactEvidenceKind(StrEnum):
    """Artifact metadata families exposed through suite evidence views."""

    TIME_SERIES = "TIME_SERIES"
    SHOCK = "SHOCK"
    SCENARIO_VECTOR = "SCENARIO_VECTOR"
    SURFACE = "SURFACE"


class ArtifactEvidenceStatus(StrEnum):
    """Availability status for one artifact reference."""

    AVAILABLE = "AVAILABLE"
    NO_DATA = "NO_DATA"
    UNSUPPORTED = "UNSUPPORTED"


class SuiteEvidenceComponent(StrEnum):
    """Top-level component buckets used by suite artifact evidence views."""

    IMA = "IMA"
    SA = "SA"
    SBM = "SBM"
    DRC = "DRC"
    RRAO = "RRAO"
    CVA = "CVA"
    SUITE = "SUITE"


_SA_COMPONENT_TO_EVIDENCE_COMPONENT: dict[StandardisedComponent, SuiteEvidenceComponent] = {
    StandardisedComponent.SBM: SuiteEvidenceComponent.SBM,
    StandardisedComponent.DRC: SuiteEvidenceComponent.DRC,
    StandardisedComponent.RRAO: SuiteEvidenceComponent.RRAO,
}


@dataclass(frozen=True)
class ArtifactEvidenceRef:
    """One resolved artifact reference or explicit no-data state."""

    component: SuiteEvidenceComponent
    kind: ArtifactEvidenceKind
    role: str
    artifact_id: str = ""
    status: ArtifactEvidenceStatus = ArtifactEvidenceStatus.AVAILABLE
    source_component: str = ""
    source_field: str = ""
    reason: str = ""
    partition_values: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.component, SuiteEvidenceComponent):
            raise OrchestrationInputError(
                "artifact evidence component must be a SuiteEvidenceComponent",
                field="component",
            )
        if not isinstance(self.kind, ArtifactEvidenceKind):
            raise OrchestrationInputError(
                "artifact evidence kind must be an ArtifactEvidenceKind",
                field="kind",
            )
        if not isinstance(self.status, ArtifactEvidenceStatus):
            raise OrchestrationInputError(
                "artifact evidence status must be an ArtifactEvidenceStatus",
                field="status",
            )
        _require_non_empty_text(self.role, "role")
        if self.status is ArtifactEvidenceStatus.AVAILABLE and not self.artifact_id:
            raise OrchestrationInputError(
                "available artifact evidence requires artifact_id",
                field="artifact_id",
            )
        if self.status is not ArtifactEvidenceStatus.AVAILABLE and not self.reason:
            raise OrchestrationInputError(
                "no-data or unsupported artifact evidence requires reason",
                field="reason",
            )
        if self.artifact_id and not isinstance(self.artifact_id, str):
            raise OrchestrationInputError("artifact_id must be text", field="artifact_id")
        partition_values = dict(self.partition_values)
        for key, value in partition_values.items():
            _require_non_empty_text(key, "partition_values")
            _require_non_empty_text(value, "partition_values")
        object.__setattr__(self, "partition_values", MappingProxyType(partition_values))

    @property
    def evidence_key(self) -> tuple[str, str, str]:
        """Stable duplicate-detection key for this evidence reference.

        Returns
        -------
        tuple[str, str, str]
            Component, artifact kind, and role values used to reject duplicate
            evidence references.
        """

        return (self.component.value, self.kind.value, self.role)

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible evidence payload.

        Returns
        -------
        dict[str, object]
            Evidence reference payload with enum values serialized as strings.
        """

        return {
            "component": self.component.value,
            "kind": self.kind.value,
            "role": self.role,
            "artifact_id": self.artifact_id,
            "status": self.status.value,
            "source_component": self.source_component,
            "source_field": self.source_field,
            "reason": self.reason,
            "partition_values": dict(self.partition_values),
        }


@dataclass(frozen=True)
class ComponentArtifactEvidence:
    """Artifact references grouped for one suite component."""

    component: SuiteEvidenceComponent
    refs: tuple[ArtifactEvidenceRef, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.component, SuiteEvidenceComponent):
            raise OrchestrationInputError(
                "component evidence component must be a SuiteEvidenceComponent",
                field="component",
            )
        refs = tuple(self.refs)
        for ref in refs:
            if not isinstance(ref, ArtifactEvidenceRef):
                raise OrchestrationInputError(
                    "refs must contain ArtifactEvidenceRef values",
                    field="refs",
                )
            if ref.component != self.component:
                raise OrchestrationInputError(
                    "ref component must match ComponentArtifactEvidence component",
                    field="refs",
                )
        object.__setattr__(self, "refs", refs)

    def refs_by_kind(self, kind: ArtifactEvidenceKind) -> tuple[ArtifactEvidenceRef, ...]:
        """Return references for one artifact kind.

        Parameters
        ----------
        kind : ArtifactEvidenceKind
            Artifact family to select from this component.

        Returns
        -------
        tuple[ArtifactEvidenceRef, ...]
            Evidence references whose ``kind`` matches ``kind``.
        """

        return tuple(ref for ref in self.refs if ref.kind is kind)

    def status_counts(self) -> dict[str, int]:
        """Return deterministic availability counts for this component.

        Returns
        -------
        dict[str, int]
            Count of references by ``ArtifactEvidenceStatus`` value.
        """

        counts = {status.value: 0 for status in ArtifactEvidenceStatus}
        for ref in self.refs:
            counts[ref.status.value] += 1
        return counts

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible component payload.

        Returns
        -------
        dict[str, object]
            Component payload containing status counts and serialized refs.
        """

        return {
            "component": self.component.value,
            "status_counts": self.status_counts(),
            "refs": [ref.as_dict() for ref in self.refs],
        }


@dataclass(frozen=True)
class SuiteArtifactEvidenceView:
    """Suite-level artifact evidence view for Navigator drill-downs."""

    run_id: str
    calculation_date: str
    base_currency: str
    components: tuple[ComponentArtifactEvidence, ...]

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.calculation_date, "calculation_date")
        _require_non_empty_text(self.base_currency, "base_currency")
        components = tuple(self.components)
        seen_components: set[SuiteEvidenceComponent] = set()
        for component in components:
            if not isinstance(component, ComponentArtifactEvidence):
                raise OrchestrationInputError(
                    "components must contain ComponentArtifactEvidence values",
                    field="components",
                )
            if component.component in seen_components:
                raise OrchestrationInputError(
                    "duplicate component artifact evidence",
                    field="components",
                )
            seen_components.add(component.component)
        object.__setattr__(self, "components", components)

    def component(self, component: SuiteEvidenceComponent) -> ComponentArtifactEvidence:
        """Return evidence for one component.

        Parameters
        ----------
        component : SuiteEvidenceComponent
            Component bucket to retrieve from the suite evidence view.

        Returns
        -------
        ComponentArtifactEvidence
            Evidence grouped for the requested component.
        """

        for item in self.components:
            if item.component is component:
                return item
        raise KeyError(f"No artifact evidence for component {component.value}")

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible suite evidence payload.

        Returns
        -------
        dict[str, object]
            Suite-level payload containing run context, status counts, and
            serialized component evidence.
        """

        return {
            "run_id": self.run_id,
            "calculation_date": self.calculation_date,
            "base_currency": self.base_currency,
            "status_counts": _suite_status_counts(self.components),
            "components": [component.as_dict() for component in self.components],
        }


def build_suite_artifact_evidence_view(
    suite_result: SuiteCapitalResult,
    refs: Sequence[ArtifactEvidenceRef],
) -> SuiteArtifactEvidenceView:
    """Group resolved artifact references under a suite capital run.

    Parameters
    ----------
    suite_result : SuiteCapitalResult
        Completed suite capital result that supplies run context.
    refs : Sequence[ArtifactEvidenceRef]
        Already-resolved artifact references or explicit no-data states.

    Returns
    -------
    SuiteArtifactEvidenceView
        Component-grouped view suitable for Navigator/result-store handoff.
    """

    if not isinstance(suite_result, SuiteCapitalResult):
        raise OrchestrationInputError(
            "suite_result must be a SuiteCapitalResult",
            field="suite_result",
        )
    refs_tuple = tuple(refs)
    _reject_duplicate_refs(refs_tuple)
    grouped = _component_ordered_refs(suite_result, refs_tuple)
    return SuiteArtifactEvidenceView(
        run_id=suite_result.run_id,
        calculation_date=suite_result.calculation_date.isoformat(),
        base_currency=suite_result.base_currency,
        components=tuple(
            ComponentArtifactEvidence(component=component, refs=component_refs)
            for component, component_refs in grouped
        ),
    )


def _component_ordered_refs(
    suite_result: SuiteCapitalResult,
    refs: tuple[ArtifactEvidenceRef, ...],
) -> tuple[tuple[SuiteEvidenceComponent, tuple[ArtifactEvidenceRef, ...]], ...]:
    known_components = [
        SuiteEvidenceComponent.IMA,
        SuiteEvidenceComponent.SA,
        *_sa_evidence_components(suite_result),
        SuiteEvidenceComponent.CVA,
        SuiteEvidenceComponent.SUITE,
    ]
    ref_map: dict[SuiteEvidenceComponent, list[ArtifactEvidenceRef]] = {
        component: [] for component in known_components
    }
    for ref in refs:
        if ref.component not in ref_map:
            raise OrchestrationInputError(
                "artifact evidence component is not present in the suite result",
                field="refs",
            )
        ref_map[ref.component].append(ref)
    return tuple(
        (component, tuple(sorted(component_refs, key=_ref_sort_key)))
        for component, component_refs in ref_map.items()
        if component_refs
    )


def _sa_evidence_components(suite_result: SuiteCapitalResult) -> tuple[SuiteEvidenceComponent, ...]:
    sa_result = suite_result.sa_result
    if sa_result is None:
        return ()
    components: list[SuiteEvidenceComponent] = []
    for subtotal in sa_result.component_subtotals:
        component = _SA_COMPONENT_TO_EVIDENCE_COMPONENT.get(subtotal.component)
        if component is None:
            raise OrchestrationInputError(
                "SA component is not mapped to an artifact evidence component",
                field="sa_result.component_subtotals",
            )
        components.append(component)
    return tuple(components)


def _reject_duplicate_refs(refs: tuple[ArtifactEvidenceRef, ...]) -> None:
    seen: set[tuple[str, str, str]] = set()
    for ref in refs:
        if not isinstance(ref, ArtifactEvidenceRef):
            raise OrchestrationInputError(
                "refs must contain ArtifactEvidenceRef values",
                field="refs",
            )
        key = ref.evidence_key
        if key in seen:
            raise OrchestrationInputError(
                "duplicate artifact evidence ref",
                field="refs",
            )
        seen.add(key)


def _ref_sort_key(ref: ArtifactEvidenceRef) -> tuple[str, str, str]:
    return (ref.kind.value, ref.role, ref.artifact_id)


def _suite_status_counts(components: tuple[ComponentArtifactEvidence, ...]) -> dict[str, int]:
    counts = {status.value: 0 for status in ArtifactEvidenceStatus}
    for component in components:
        for status, count in component.status_counts().items():
            counts[status] += count
    return counts


def _require_non_empty_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise OrchestrationInputError(f"{field} must be non-empty text", field=field)


__all__ = [
    "ArtifactEvidenceKind",
    "ArtifactEvidenceRef",
    "ArtifactEvidenceStatus",
    "ComponentArtifactEvidence",
    "SuiteArtifactEvidenceView",
    "SuiteEvidenceComponent",
    "build_suite_artifact_evidence_view",
]
