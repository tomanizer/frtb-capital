"""Mapping-suggestion reports for v1 IMA client-data onboarding.

The helpers in this module assist a human authoring ``mapping.yaml`` by
ranking source-profile columns against supported canonical IMA target fields.
They deliberately do not produce an executable mapping spec: every suggestion
requires human review before client data can feed RFET, PLA, ES/IMCC, or SES
workflows.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from frtb_common import ColumnSpec, TabularLogicalType

from frtb_ima.adapters._arrow_specs import IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS
from frtb_ima.adapters._daily_pnl_mapping_types import (
    IMA_DAILY_PNL_VECTOR_ARROW_COLUMN_SPECS,
    IMA_DAILY_PNL_VECTOR_TARGET,
    REQUIRED_DAILY_PNL_FIELDS,
)
from frtb_ima.adapters._mapping_hash import stable_mapping_hash
from frtb_ima.adapters._mapping_suggestion_terms import (
    FIELD_ALIASES,
    GENERIC_MATCH_TOKENS,
    SUPPORTED_SOURCE_TYPES,
)
from frtb_ima.adapters._rfet_observation_mapping_types import (
    IMA_RFET_OBSERVATION_TARGET,
    REQUIRED_RFET_OBSERVATION_FIELDS,
    RFET_OBSERVATION_TARGET_FIELDS,
)
from frtb_ima.adapters._risk_factor_master_mapping_types import (
    IMA_RISK_FACTOR_MASTER_ARROW_COLUMN_SPECS,
    IMA_RISK_FACTOR_MASTER_TARGET,
    REQUIRED_RISK_FACTOR_MASTER_FIELDS,
)
from frtb_ima.adapters._scenario_pnl_mapping_types import (
    IMA_SCENARIO_PNL_VECTOR_ARROW_COLUMN_SPECS,
    IMA_SCENARIO_PNL_VECTOR_TARGET,
    REQUIRED_SCENARIO_PNL_FIELDS,
)
from frtb_ima.adapters.source_profile import SourceColumnProfile, SourceProfile

_NAME_PART_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class MappingColumnCandidate:
    """One ranked source-column candidate for a canonical target field."""

    source_column: str
    confidence: float
    reason: str
    inferred_type: str
    null_rate: float

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable candidate payload.

        Returns
        -------
        dict[str, object]
            Candidate metadata suitable for ``mapping_suggestion_report.json``.
        """

        return {
            "source_column": self.source_column,
            "confidence": self.confidence,
            "reason": self.reason,
            "inferred_type": self.inferred_type,
            "null_rate": self.null_rate,
        }


@dataclass(frozen=True)
class MappingFieldSuggestion:
    """Candidate suggestions for one canonical target field."""

    target_field: str
    required: bool
    logical_type: str
    candidates: tuple[MappingColumnCandidate, ...]

    @property
    def status(self) -> str:
        """Return whether this field has a candidate suggestion.

        Returns
        -------
        str
            ``"suggested"`` when at least one candidate exists, otherwise
            ``"needs_mapping"``.
        """

        return "suggested" if self.candidates else "needs_mapping"

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable field suggestion.

        Returns
        -------
        dict[str, object]
            Field suggestion suitable for ``mapping_suggestion_report.json``.
        """

        return {
            "target_field": self.target_field,
            "required": self.required,
            "logical_type": self.logical_type,
            "status": self.status,
            "candidates": [candidate.as_dict() for candidate in self.candidates],
        }


@dataclass(frozen=True)
class MappingTableSuggestion:
    """Suggestion summary for one canonical IMA table target."""

    table_name: str
    source_name: str
    source_hash: str
    fields: tuple[MappingFieldSuggestion, ...]

    @property
    def suggested_field_count(self) -> int:
        """Return the number of target fields with at least one candidate."""

        return sum(1 for field in self.fields if field.candidates)

    @property
    def missing_required_fields(self) -> tuple[str, ...]:
        """Return required target fields that have no candidate suggestion."""

        return tuple(
            field.target_field for field in self.fields if field.required and not field.candidates
        )

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable table suggestion.

        Returns
        -------
        dict[str, object]
            Table suggestion suitable for ``mapping_suggestion_report.json``.
        """

        return {
            "table_name": self.table_name,
            "source_name": self.source_name,
            "source_hash": self.source_hash,
            "suggested_field_count": self.suggested_field_count,
            "missing_required_fields": list(self.missing_required_fields),
            "fields": [field.as_dict() for field in self.fields],
        }


@dataclass(frozen=True)
class ImaMappingSuggestionReport:
    """Aggregate v1 ``mapping_suggestion_report.json`` payload."""

    target_schema: str
    source_system: str
    report_hash: str
    tables: tuple[MappingTableSuggestion, ...]

    @property
    def missing_required_field_count(self) -> int:
        """Return the aggregate count of required fields without candidates."""

        return sum(len(table.missing_required_fields) for table in self.tables)

    @property
    def source_hashes(self) -> Mapping[str, str]:
        """Return source hashes keyed by canonical table name."""

        return MappingProxyType({table.table_name: table.source_hash for table in self.tables})

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable aggregate suggestion report.

        Returns
        -------
        dict[str, object]
            Payload suitable for writing as v1 ``mapping_suggestion_report.json``.
        """

        return {
            "report_schema": "ima-mapping-suggestion-report-v1",
            "target_schema": self.target_schema,
            "source_system": self.source_system,
            "report_hash": self.report_hash,
            "human_review_required": True,
            "missing_required_field_count": self.missing_required_field_count,
            "source_hashes": dict(self.source_hashes),
            "tables": [table.as_dict() for table in self.tables],
        }

    def to_json(self) -> str:
        """Serialize this report using stable JSON formatting.

        Returns
        -------
        str
            Stable, indented JSON representation of this suggestion report.
        """

        return json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class _TargetSpec:
    table_name: str
    column_specs: tuple[ColumnSpec, ...]
    required_fields: frozenset[str]


_TARGET_SPECS: Mapping[str, _TargetSpec] = {
    IMA_DAILY_PNL_VECTOR_TARGET: _TargetSpec(
        table_name=IMA_DAILY_PNL_VECTOR_TARGET,
        column_specs=IMA_DAILY_PNL_VECTOR_ARROW_COLUMN_SPECS,
        required_fields=REQUIRED_DAILY_PNL_FIELDS,
    ),
    IMA_RISK_FACTOR_MASTER_TARGET: _TargetSpec(
        table_name=IMA_RISK_FACTOR_MASTER_TARGET,
        column_specs=IMA_RISK_FACTOR_MASTER_ARROW_COLUMN_SPECS,
        required_fields=REQUIRED_RISK_FACTOR_MASTER_FIELDS,
    ),
    IMA_RFET_OBSERVATION_TARGET: _TargetSpec(
        table_name=IMA_RFET_OBSERVATION_TARGET,
        column_specs=tuple(
            spec
            for spec in IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS
            if spec.name in RFET_OBSERVATION_TARGET_FIELDS
        ),
        required_fields=REQUIRED_RFET_OBSERVATION_FIELDS,
    ),
    IMA_SCENARIO_PNL_VECTOR_TARGET: _TargetSpec(
        table_name=IMA_SCENARIO_PNL_VECTOR_TARGET,
        column_specs=IMA_SCENARIO_PNL_VECTOR_ARROW_COLUMN_SPECS,
        required_fields=REQUIRED_SCENARIO_PNL_FIELDS,
    ),
}


def build_ima_mapping_suggestion_report(
    profiles: Mapping[str, SourceProfile],
    *,
    target_schema: str,
    source_system: str,
    targets: Sequence[str] | None = None,
    max_candidates_per_field: int = 3,
) -> ImaMappingSuggestionReport:
    """Build a v1 mapping-suggestion report from source profiles.

    Parameters
    ----------
    profiles : Mapping[str, SourceProfile]
        Source profiles keyed by canonical table target name. A profile may also
        be supplied under ``"default"`` when the same export should be ranked
        against every requested target.
    target_schema : str
        Canonical schema name the future human-authored mapping will target.
    source_system : str
        Client source-system identifier recorded in the report.
    targets : Sequence[str] | None, optional
        Canonical table targets to score. Defaults to every supported target
        present in ``profiles``, or every supported target when ``default`` is
        provided.
    max_candidates_per_field : int, optional
        Maximum candidates retained per target field.

    Returns
    -------
    ImaMappingSuggestionReport
        Deterministic, human-review-only suggestion report.
    """

    if not profiles:
        raise ValueError("at least one source profile is required")
    if not target_schema:
        raise ValueError("target_schema must be non-empty")
    if not source_system:
        raise ValueError("source_system must be non-empty")
    if max_candidates_per_field < 1:
        raise ValueError("max_candidates_per_field must be positive")

    target_names = _target_names(profiles, targets)
    tables = tuple(
        _build_table_suggestion(
            target_name,
            _profile_for_target(profiles, target_name),
            max_candidates_per_field=max_candidates_per_field,
        )
        for target_name in target_names
    )
    payload = {
        "target_schema": target_schema,
        "source_system": source_system,
        "tables": [table.as_dict() for table in tables],
    }
    return ImaMappingSuggestionReport(
        target_schema=target_schema,
        source_system=source_system,
        report_hash=stable_mapping_hash(payload),
        tables=tables,
    )


def _target_names(
    profiles: Mapping[str, SourceProfile], targets: Sequence[str] | None
) -> tuple[str, ...]:
    if targets is None:
        if "default" in profiles:
            return tuple(sorted(_TARGET_SPECS))
        targets = tuple(profiles)
    names = tuple(dict.fromkeys(str(target) for target in targets))
    unknown = sorted(set(names) - set(_TARGET_SPECS))
    if unknown:
        raise ValueError("unsupported IMA mapping targets: " + ", ".join(unknown))
    return tuple(sorted(names))


def _profile_for_target(profiles: Mapping[str, SourceProfile], target_name: str) -> SourceProfile:
    profile = profiles.get(target_name, profiles.get("default"))
    if profile is None:
        raise ValueError(f"missing source profile for {target_name}")
    return profile


def _build_table_suggestion(
    target_name: str,
    profile: SourceProfile,
    *,
    max_candidates_per_field: int,
) -> MappingTableSuggestion:
    target = _TARGET_SPECS[target_name]
    fields = tuple(
        _field_suggestion(spec, profile, target.required_fields, max_candidates_per_field)
        for spec in target.column_specs
    )
    return MappingTableSuggestion(
        table_name=target.table_name,
        source_name=profile.source_name,
        source_hash=profile.source_hash,
        fields=fields,
    )


def _field_suggestion(
    spec: ColumnSpec,
    profile: SourceProfile,
    required_fields: frozenset[str],
    max_candidates_per_field: int,
) -> MappingFieldSuggestion:
    candidates = tuple(
        sorted(
            (
                candidate
                for column in profile.columns
                if (candidate := _candidate_for_column(spec, column)) is not None
            ),
            key=lambda item: (-item.confidence, item.source_column),
        )[:max_candidates_per_field]
    )
    return MappingFieldSuggestion(
        target_field=spec.name,
        required=spec.name in required_fields,
        logical_type=spec.logical_type.value,
        candidates=candidates,
    )


def _candidate_for_column(
    spec: ColumnSpec, column: SourceColumnProfile
) -> MappingColumnCandidate | None:
    name_score, reason = _name_score(spec.name, column.name)
    type_score = _type_score(spec.logical_type, column.inferred_type)
    confidence = max(0.0, min(0.99, name_score + type_score - column.null_rate * 0.15))
    if confidence < 0.40:
        return None
    return MappingColumnCandidate(
        source_column=column.name,
        confidence=round(confidence, 3),
        reason=reason if type_score else f"{reason}; type needs review",
        inferred_type=column.inferred_type,
        null_rate=round(column.null_rate, 6),
    )


def _name_score(target_field: str, source_column: str) -> tuple[float, str]:
    target_key = _compact(target_field)
    source_key = _compact(source_column)
    alias_keys = {_compact(alias) for alias in FIELD_ALIASES.get(target_field, ())}
    if source_key == target_key:
        return 0.84, "exact normalized name match"
    if source_key in alias_keys:
        return 0.78, "known source alias match"
    if target_key in source_key or source_key in target_key:
        return 0.66, "partial normalized name match"
    source_tokens = set(_tokens(source_column))
    target_tokens = set(_tokens(target_field))
    alias_tokens = set().union(*(_tokens(alias) for alias in FIELD_ALIASES.get(target_field, ())))
    expected_tokens = target_tokens | alias_tokens
    matched_tokens = source_tokens & expected_tokens
    meaningful_tokens = matched_tokens - GENERIC_MATCH_TOKENS
    if meaningful_tokens:
        return min(0.58, 0.28 + 0.10 * len(matched_tokens)), "token overlap match"
    return 0.0, "no name match"


def _type_score(logical_type: TabularLogicalType, inferred_type: str) -> float:
    if inferred_type in SUPPORTED_SOURCE_TYPES.get(logical_type, frozenset()):
        return 0.15
    if logical_type is TabularLogicalType.STRING and inferred_type != "empty":
        return 0.08
    return 0.0


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_NAME_PART_RE.findall(value.lower()))


def _compact(value: str) -> str:
    return "".join(_tokens(value))
