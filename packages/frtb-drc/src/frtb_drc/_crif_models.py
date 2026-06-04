"""Public result models for the DRC CRIF ingress adapter."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from frtb_common import AdapterDiagnostic, NormalizedArrowTable

from frtb_drc.data_models import DrcPosition, DrcRiskClass


class DrcCrifDirectionStrategy(StrEnum):
    """How source rows encode long/short default direction."""

    EXPLICIT_FIELD = "EXPLICIT_FIELD"
    SIGNED_NOTIONAL = "SIGNED_NOTIONAL"
    SIGNED_MARKET_VALUE = "SIGNED_MARKET_VALUE"


@dataclass(frozen=True)
class DrcRejectedCrifRow:
    """Rejected CRIF/vendor row with deterministic diagnostics."""

    source_row_id: str
    reason_code: str
    message: str
    source_columns: tuple[str, ...] = ()
    source_values: Mapping[str, object | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_columns", tuple(self.source_columns))
        object.__setattr__(self, "source_values", MappingProxyType(dict(self.source_values)))

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready representation."""

        return {
            "message": self.message,
            "reason_code": self.reason_code,
            "source_columns": list(self.source_columns),
            "source_row_id": self.source_row_id,
            "source_values": dict(self.source_values),
        }


@dataclass(frozen=True)
class DrcCrifAdapterResult:
    """Accepted DRC positions plus rejected-row audit records."""

    positions: tuple[DrcPosition, ...]
    rejected_rows: tuple[DrcRejectedCrifRow, ...]
    diagnostics: tuple[AdapterDiagnostic, ...]
    source_hash: str
    source_system: str
    source_file: str
    direction_strategy: DrcCrifDirectionStrategy

    def __post_init__(self) -> None:
        from frtb_drc._crif_position import _coerce_direction_strategy

        object.__setattr__(self, "positions", tuple(self.positions))
        object.__setattr__(self, "rejected_rows", tuple(self.rejected_rows))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        object.__setattr__(
            self,
            "direction_strategy",
            _coerce_direction_strategy(self.direction_strategy),
        )

    @property
    def accepted_count(self) -> int:
        """Number of accepted canonical positions."""

        return len(self.positions)

    @property
    def rejected_count(self) -> int:
        """Number of rejected source rows."""

        return len(self.rejected_rows)

    def to_arrow_tables(self) -> Mapping[DrcRiskClass, NormalizedArrowTable]:
        """Return one normalized DRC Arrow table per accepted risk class."""

        from frtb_drc._crif_arrow_adapter import drc_crif_result_to_arrow_tables

        return drc_crif_result_to_arrow_tables(self)
