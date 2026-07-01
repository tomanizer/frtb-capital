"""Shared risk-factor identifier and metadata carrier primitives.

The classes in this module are intentionally narrow. They provide immutable,
deterministic value objects for risk-factor IDs, mapping provenance, and
calculation-ready metadata codes that can cross package boundaries. They do not
own canonical risk-factor metadata records, regulatory mapping tables, RFET
evidence, or component-specific calculation semantics; those stay in the
result store and component packages that own them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "BucketId",
    "CurrencyCode",
    "RiskFactorId",
    "RiskFactorLineageId",
    "RiskFactorMappingVersion",
    "RiskFactorPrimitiveError",
    "RiskFactorRiskClassCode",
    "RiskFactorTypeCode",
    "SensitivityTypeCode",
    "Tenor",
]

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_:/.-]*$")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_TENOR_PATTERN = re.compile(r"^[1-9][0-9]*(D|W|M|Y)$")


class RiskFactorPrimitiveError(ValueError):
    """Raised when a risk-factor value primitive violates its shared contract."""

    def __init__(self, message: str, *, field: str = "") -> None:
        self.field = field
        super().__init__(message)


@dataclass(frozen=True, order=True, slots=True)
class RiskFactorId:
    """Stable risk-factor identifier supplied by canonical metadata owners.

    The value is stripped, case-preserved, and restricted to an identifier-safe
    alphabet so equality, ordering, string representation, and persisted keys
    remain deterministic across component packages.
    """

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalise_identifier(self.value, field="risk_factor_id"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True, slots=True)
class RiskFactorMappingVersion:
    """Stable mapping or taxonomy version token for risk-factor metadata."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _normalise_identifier(self.value, field="risk_factor_mapping_version"),
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True, slots=True)
class RiskFactorLineageId:
    """Stable source/evidence lineage identifier linked to a risk factor."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", _normalise_identifier(self.value, field="risk_factor_lineage_id")
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True, slots=True)
class BucketId:
    """Opaque regulatory or package bucket identifier carried with metadata."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalise_identifier(self.value, field="bucket_id"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True, slots=True)
class RiskFactorRiskClassCode:
    """Opaque risk-class code carried from an owning taxonomy or mapping table."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", _normalise_code(self.value, field="risk_factor_risk_class")
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True, slots=True)
class RiskFactorTypeCode:
    """Opaque risk-type code carried from an owning taxonomy or mapping table."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalise_code(self.value, field="risk_factor_type"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True, slots=True)
class SensitivityTypeCode:
    """Opaque sensitivity-type code carried from an owning taxonomy or input row."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalise_code(self.value, field="sensitivity_type"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True, slots=True)
class CurrencyCode:
    """ISO-style three-letter currency code used as risk-factor metadata."""

    value: str

    def __post_init__(self) -> None:
        normalised = _normalise_text(self.value, field="currency_code").upper()
        if not _CURRENCY_PATTERN.match(normalised):
            raise RiskFactorPrimitiveError(
                "currency_code must be a three-letter alphabetic code",
                field="currency_code",
            )
        object.__setattr__(self, "value", normalised)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True, slots=True)
class Tenor:
    """Simple tenor bucket token used as risk-factor metadata."""

    value: str

    def __post_init__(self) -> None:
        normalised = _normalise_text(self.value, field="tenor").upper()
        if not _TENOR_PATTERN.match(normalised):
            raise RiskFactorPrimitiveError(
                "tenor must use a positive integer followed by D, W, M, or Y",
                field="tenor",
            )
        object.__setattr__(self, "value", normalised)

    def __str__(self) -> str:
        return self.value


def _normalise_identifier(value: object, *, field: str) -> str:
    normalised = _normalise_text(value, field=field)
    if not _IDENTIFIER_PATTERN.match(normalised):
        raise RiskFactorPrimitiveError(
            f"{field} contains unsupported identifier characters",
            field=field,
        )
    return normalised


def _normalise_code(value: object, *, field: str) -> str:
    normalised = _normalise_text(value, field=field).upper()
    if not _CODE_PATTERN.match(normalised):
        raise RiskFactorPrimitiveError(
            f"{field} contains unsupported code characters",
            field=field,
        )
    return normalised


def _normalise_text(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise RiskFactorPrimitiveError(f"{field} must be text", field=field)
    normalised = value.strip()
    if not normalised:
        raise RiskFactorPrimitiveError(f"{field} must be non-empty text", field=field)
    if any(character.isspace() for character in normalised):
        raise RiskFactorPrimitiveError(f"{field} must not contain whitespace", field=field)
    if any(ord(character) < 32 for character in normalised):
        raise RiskFactorPrimitiveError(f"{field} must not contain control characters", field=field)
    return normalised
