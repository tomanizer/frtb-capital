"""CRIF normalization public contracts and package-neutral defaults."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TypeAlias

from frtb_common.arrow_table import (
    ColumnSpec,
    NormalizedTableError,
    NullPolicy,
    TabularLogicalType,
)

CRIF_SOURCE_SYSTEM = "crif"
CRIF_SOURCE_ROW_ID_COLUMN = "source_row_id"
CRIF_RISK_TYPE_COLUMN = "risk_type"
_FLOAT_TEXT_PATTERN = r"^[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?$"
_INTEGER_TEXT_PATTERN = r"^[+-]?\d+$"
_NON_FINITE_TEXT_VALUES = frozenset(
    {
        "NAN",
        "+NAN",
        "-NAN",
        "INF",
        "+INF",
        "-INF",
        "INFINITY",
        "+INFINITY",
        "-INFINITY",
    }
)

CrifRiskTypeMapper: TypeAlias = Callable[
    [str, Mapping[str, object]],
    Mapping[str, object] | None,
]


@dataclass(frozen=True, slots=True)
class CrifColumnSpec:
    """Package-neutral CRIF source column extraction rule."""

    name: str
    aliases: tuple[str, ...] = ()
    logical_type: TabularLogicalType = TabularLogicalType.STRING
    required: bool = False
    default: object | None = None

    def __post_init__(self) -> None:
        _validate_non_empty(self.name, "CRIF column name")
        aliases = tuple(self.aliases)
        for alias in aliases:
            _validate_non_empty(alias, f"alias for {self.name!r}")
        if len(set(aliases)) != len(aliases):
            raise NormalizedTableError(f"CRIF column spec {self.name!r} repeats an alias")
        object.__setattr__(self, "aliases", aliases)

    def as_column_spec(self) -> ColumnSpec:
        """Return the generic handoff column declaration for this CRIF field.

        Returns
        -------
        ColumnSpec
            Shared :class:`~frtb_common.arrow_table.ColumnSpec` with CRIF null policy.
        """

        return ColumnSpec(
            self.name,
            logical_type=self.logical_type,
            required=self.required,
            null_policy=NullPolicy.FORBID if self.required else NullPolicy.ALLOW,
        )


@dataclass(frozen=True, slots=True)
class CrifRiskTypeMapping:
    """Package-supplied mapping from CRIF RiskType values to output constants."""

    source_values: tuple[str, ...]
    output_values: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        values = tuple(_normalise_risk_type(value) for value in self.source_values)
        if not values:
            raise NormalizedTableError("CRIF risk-type mapping requires at least one value")
        if len(set(values)) != len(values):
            raise NormalizedTableError("CRIF risk-type mapping repeats a source value")
        frozen_outputs = MappingProxyType(dict(self.output_values))
        for key in frozen_outputs:
            _validate_non_empty(key, "CRIF risk-type output column")
        object.__setattr__(self, "source_values", values)
        object.__setattr__(self, "output_values", frozen_outputs)


def _normalise_risk_type(value: object) -> str:
    return str(value).strip().upper()


def _column_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _stringify_record_value(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _validate_non_empty(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise NormalizedTableError(f"{label} must be a non-empty string")


DEFAULT_CRIF_COLUMN_SPECS: tuple[CrifColumnSpec, ...] = (
    CrifColumnSpec(
        "sensitivity_id",
        aliases=("SensitivityId", "Sensitivity ID", "TradeId", "TradeID"),
    ),
    CrifColumnSpec(
        CRIF_SOURCE_ROW_ID_COLUMN,
        aliases=("RowId", "RowID", "sourceRowId", "source_row_id"),
    ),
    CrifColumnSpec(
        CRIF_RISK_TYPE_COLUMN,
        aliases=("RiskType", "risk_type", "RiskClass"),
        required=True,
    ),
    CrifColumnSpec("qualifier", aliases=("Qualifier",)),
    CrifColumnSpec("bucket", aliases=("Bucket",)),
    CrifColumnSpec("label1", aliases=("Label1", "Tenor", "tenor")),
    CrifColumnSpec("label2", aliases=("Label2", "OptionTenor", "option_tenor")),
    CrifColumnSpec(
        "amount",
        aliases=("Amount", "amount", "AmountUSD", "AmountUsd"),
        logical_type=TabularLogicalType.FLOAT,
    ),
    CrifColumnSpec(
        "amount_currency",
        aliases=("AmountCurrency", "amount_currency", "Currency", "currency"),
    ),
    CrifColumnSpec("desk_id", aliases=("DeskId", "DeskID", "desk_id", "Desk")),
    CrifColumnSpec(
        "legal_entity",
        aliases=("LegalEntity", "LegalEntityID", "legal_entity", "Entity"),
    ),
    CrifColumnSpec(
        "up_shock_amount",
        aliases=("CvrUp", "UpShock", "up_shock_amount"),
        logical_type=TabularLogicalType.FLOAT,
    ),
    CrifColumnSpec(
        "down_shock_amount",
        aliases=("CvrDown", "DownShock", "down_shock_amount"),
        logical_type=TabularLogicalType.FLOAT,
    ),
)


def normalise_crif_risk_type(value: object) -> str:
    """Return the deterministic key used for CRIF RiskType mapping.

    Parameters
    ----------
    value : object
        Raw RiskType cell value from a CRIF row or column.

    Returns
    -------
    str
        Uppercased, stripped RiskType key.
    """

    return _normalise_risk_type(value)


__all__ = [
    "CRIF_RISK_TYPE_COLUMN",
    "CRIF_SOURCE_ROW_ID_COLUMN",
    "CRIF_SOURCE_SYSTEM",
    "DEFAULT_CRIF_COLUMN_SPECS",
    "CrifColumnSpec",
    "CrifRiskTypeMapper",
    "CrifRiskTypeMapping",
    "normalise_crif_risk_type",
]
