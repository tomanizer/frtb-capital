"""Result-store enum contracts and registries."""

from __future__ import annotations

from enum import StrEnum
from typing import TypeVar


class ResultStoreContractError(ValueError):
    """Raised when a result-store contract would produce unauditable output."""

    def __init__(self, message: str, *, field: str = "") -> None:
        self.field = field
        super().__init__(message)


class StorageBackend(StrEnum):
    """Supported or reserved storage backend modes."""

    LOCAL_PARQUET = "local_parquet"
    S3_PARQUET = "s3_parquet"
    DUCKLAKE = "ducklake"


class FrtbComponent(StrEnum):
    """FRTB result components served by the store."""

    TOP_OF_HOUSE = "TOP_OF_HOUSE"
    IMA = "IMA"
    STANDARDISED_APPROACH = "SA"
    SBM = "SBM"
    DRC = "DRC"
    RRAO = "RRAO"
    CVA = "CVA"


class NodeType(StrEnum):
    """Capital graph node classes used for FRTB drilldown."""

    ROOT = "ROOT"
    COMPONENT = "COMPONENT"
    DESK = "DESK"
    PORTFOLIO = "PORTFOLIO"
    BOOK = "BOOK"
    RISK_CLASS = "RISK_CLASS"
    BUCKET = "BUCKET"
    ISSUER = "ISSUER"
    COUNTERPARTY = "COUNTERPARTY"
    HEDGE_SET = "HEDGE_SET"
    MEASURE_BRANCH = "MEASURE_BRANCH"
    RISK_FACTOR = "RISK_FACTOR"
    POSITION = "POSITION"


class EdgeType(StrEnum):
    """Capital graph relationship types."""

    AGGREGATES = "AGGREGATES"
    DRILLDOWN = "DRILLDOWN"
    ATTRIBUTION_BRANCH = "ATTRIBUTION_BRANCH"


class ArtifactType(StrEnum):
    """Large drillthrough artifacts stored outside scalar measure rows."""

    IMA_PNL_VECTOR = "IMA_PNL_VECTOR"
    IMA_TAIL_OBSERVATION = "IMA_TAIL_OBSERVATION"
    IMA_LIQUIDITY_HORIZON_VECTOR = "IMA_LIQUIDITY_HORIZON_VECTOR"
    SBM_SENSITIVITY_TABLE = "SBM_SENSITIVITY_TABLE"
    SBM_CORRELATION_INPUT = "SBM_CORRELATION_INPUT"
    DRC_JTD_TABLE = "DRC_JTD_TABLE"
    RRAO_EXPOSURE_TABLE = "RRAO_EXPOSURE_TABLE"
    CVA_EXPOSURE_TABLE = "CVA_EXPOSURE_TABLE"
    ATTRIBUTION_VECTOR = "ATTRIBUTION_VECTOR"
    MOVEMENT_EXPLAIN = "MOVEMENT_EXPLAIN"
    OTHER = "OTHER"


class RunStatus(StrEnum):
    """Append-only lifecycle status for a committed calculation run."""

    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    OFFICIAL = "OFFICIAL"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class ResultEventSeverity(StrEnum):
    """Severity for non-lifecycle result events."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ResultEventType(StrEnum):
    """Non-lifecycle event categories emitted by callers or store validation."""

    DATA_QUALITY = "DATA_QUALITY"
    CALCULATION_WARNING = "CALCULATION_WARNING"
    UNSUPPORTED_FEATURE = "UNSUPPORTED_FEATURE"
    SCHEMA_WARNING = "SCHEMA_WARNING"
    STORE_WRITE_WARNING = "STORE_WRITE_WARNING"
    VALIDATION_WARNING = "VALIDATION_WARNING"


class TelemetryPhase(StrEnum):
    """Compact persisted telemetry phases."""

    BASE_TABLE_WRITE = "BASE_TABLE_WRITE"
    ARTIFACT_WRITE = "ARTIFACT_WRITE"
    MART_GENERATION = "MART_GENERATION"
    CATALOG_REFRESH = "CATALOG_REFRESH"
    EXPORT = "EXPORT"


class CapitalNodeFamily(StrEnum):
    """Canonical ID-bearing FRTB capital node families."""

    COMPONENT = "component"
    RISK_CLASS = "risk_class"
    BUCKET = "bucket"
    ISSUER = "issuer"
    COUNTERPARTY = "counterparty"
    RESIDUAL_BRANCH = "residual_branch"
    RISK_FACTOR = "risk_factor"
    POSITION = "position"


VALID_MEASURE_NAMES = frozenset(
    {
        "capital",
    }
)

VALID_ATTRIBUTION_TARGET_TYPES = frozenset(
    {
        "POSITION",
        "SENSITIVITY",
        "RISK_FACTOR",
        "ISSUER",
        "COUNTERPARTY",
        "DESK",
        "PORTFOLIO",
        "BOOK",
        "RESIDUAL_BRANCH",
        "UNSUPPORTED_BRANCH",
    }
)


EnumT = TypeVar("EnumT", bound=StrEnum)
