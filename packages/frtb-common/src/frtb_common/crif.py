"""Compatibility exports for package-neutral CRIF normalization helpers.

The implementation is split across `frtb_common.crif_types`,
`frtb_common.crif_normalization_adapter`, and `frtb_common.crif_vectorized_adapter`; this module
keeps the historical public import path stable.
"""

from frtb_common.crif_normalization_adapter import (
    crif_records_to_arrow_table,
    normalize_crif_arrow_table,
    normalize_crif_records,
    resolve_crif_column_name,
)
from frtb_common.crif_types import (
    CRIF_RISK_TYPE_COLUMN,
    CRIF_SOURCE_ROW_ID_COLUMN,
    CRIF_SOURCE_SYSTEM,
    DEFAULT_CRIF_COLUMN_SPECS,
    CrifColumnSpec,
    CrifRiskTypeMapper,
    CrifRiskTypeMapping,
    normalise_crif_risk_type,
)

__all__ = [
    "CRIF_RISK_TYPE_COLUMN",
    "CRIF_SOURCE_ROW_ID_COLUMN",
    "CRIF_SOURCE_SYSTEM",
    "DEFAULT_CRIF_COLUMN_SPECS",
    "CrifColumnSpec",
    "CrifRiskTypeMapper",
    "CrifRiskTypeMapping",
    "crif_records_to_arrow_table",
    "normalise_crif_risk_type",
    "normalize_crif_arrow_table",
    "normalize_crif_records",
    "resolve_crif_column_name",
]
