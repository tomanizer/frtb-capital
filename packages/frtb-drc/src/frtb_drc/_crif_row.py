"""Source-row normalization and rejection diagnostics for DRC CRIF ingress."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from frtb_common import AdapterDiagnostic, DiagnosticSeverity

from frtb_drc._crif_models import DrcRejectedCrifRow
from frtb_drc._crif_values import _FIELD_ALIASES, _field_key
from frtb_drc.validation import DrcInputError


class _RejectedRowError(Exception):
    def __init__(self, reason_code: str, message: str, field_names: Sequence[str]) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.field_names = tuple(field_names)


class _NormalizedRow:
    def __init__(self, row: Mapping[str, object]) -> None:
        self._row = row
        by_key: dict[str, list[str]] = {}
        for column_name in row:
            if not isinstance(column_name, str) or not column_name.strip():
                raise DrcInputError("CRIF row field names must be non-empty strings")
            by_key.setdefault(_field_key(column_name), []).append(column_name)
        self._by_key = by_key

    def value(self, field_name: str) -> object | None:
        source_column = self.source_column(field_name)
        if source_column is None:
            return None
        return self._row[source_column]

    def source_column(self, field_name: str) -> str | None:
        matches: list[str] = []
        for alias in _FIELD_ALIASES[field_name]:
            matches.extend(self._by_key.get(_field_key(alias), ()))
        unique_matches = tuple(dict.fromkeys(matches))
        if len(unique_matches) > 1:
            raise _RejectedRowError(
                "drc_crif.ambiguous_source_column",
                f"{field_name} matches multiple source columns: {unique_matches!r}",
                (field_name,),
            )
        return unique_matches[0] if unique_matches else None

    def source_column_map(self) -> Mapping[str, str]:
        resolved = {
            field_name: source_column
            for field_name in _FIELD_ALIASES
            if (source_column := self.source_column(field_name)) is not None
        }
        return MappingProxyType(resolved)


def _rejection_from_error(
    exc: _RejectedRowError,
    row: _NormalizedRow,
    *,
    source_row_id: str,
) -> tuple[DrcRejectedCrifRow, AdapterDiagnostic]:
    rejected_row = DrcRejectedCrifRow(
        source_row_id=source_row_id,
        reason_code=exc.reason_code,
        message=exc.message,
        source_columns=_source_columns_for_error(row, exc.field_names),
        source_values={field_name: row.value(field_name) for field_name in exc.field_names},
    )
    diagnostic = AdapterDiagnostic(
        code=exc.reason_code,
        message=exc.message,
        severity=DiagnosticSeverity.ERROR,
        row_id=source_row_id,
        column_name=next(iter(exc.field_names), None),
    )
    return rejected_row, diagnostic


def _source_columns_for_error(row: _NormalizedRow, field_names: tuple[str, ...]) -> tuple[str, ...]:
    columns: list[str] = []
    for field_name in field_names:
        try:
            source_column = row.source_column(field_name)
        except _RejectedRowError:
            continue
        if source_column is not None:
            columns.append(source_column)
    return tuple(columns)
