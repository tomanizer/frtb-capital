"""DRC path registry for class-specific batch ingress adapters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from frtb_common import ColumnSpec, NullPolicy, TabularLogicalType

from frtb_drc.data_models import DrcRiskClass

DRC_NONSEC_PATH = "nonsec"
DRC_SECURITISATION_NON_CTP_PATH = "securitisation_non_ctp"
DRC_CTP_PATH = "ctp"


@dataclass(frozen=True)
class DrcPathSpec:
    """Registry metadata for one homogeneous DRC batch path."""

    path: str
    risk_class: DrcRiskClass
    arrow_column_specs: tuple[ColumnSpec, ...]


def _replace_column_spec(
    spec: ColumnSpec,
    *,
    required: bool,
    null_policy: NullPolicy,
) -> ColumnSpec:
    return ColumnSpec(
        spec.name,
        aliases=spec.aliases,
        logical_type=spec.logical_type,
        required=required,
        null_policy=null_policy,
        chunk_policy=spec.chunk_policy,
        dictionary_policy=spec.dictionary_policy,
    )


DRC_NONSEC_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("position_id", aliases=("positionId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("source_row_id", aliases=("sourceRowId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("desk_id", aliases=("deskId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("legal_entity", aliases=("legalEntity",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("risk_class", aliases=("riskClass",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "instrument_type",
        aliases=("instrumentType",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "default_direction",
        aliases=("defaultDirection",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("issuer_id", aliases=("issuerId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "tranche_id",
        aliases=("trancheId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "index_series_id",
        aliases=("indexSeriesId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec("bucket_key", aliases=("bucketKey",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("seniority", logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "credit_quality",
        aliases=("creditQuality",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("notional", logical_type=TabularLogicalType.FLOAT),
    ColumnSpec(
        "market_value",
        aliases=("marketValue",),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "cumulative_pnl",
        aliases=("cumulativePnl", "cumulativePnL"),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec("maturity_years", aliases=("maturityYears",), logical_type=TabularLogicalType.FLOAT),
    ColumnSpec("currency", logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "lgd_override",
        aliases=("lgdOverride",),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "is_defaulted",
        aliases=("isDefaulted",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "is_gse",
        aliases=("isGse",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "is_pse",
        aliases=("isPse",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "is_covered_bond",
        aliases=("isCoveredBond",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "lineage_source_system",
        aliases=("source_system", "sourceSystem"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "lineage_source_file",
        aliases=("source_file", "sourceFile"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "citation_ids",
        aliases=("citationIds",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = tuple(
    _replace_column_spec(spec, required=False, null_policy=NullPolicy.ALLOW)
    if spec.name in {"seniority", "credit_quality"}
    else _replace_column_spec(spec, required=True, null_policy=NullPolicy.ALLOW)
    if spec.name == "issuer_id"
    else spec
    for spec in DRC_NONSEC_ARROW_COLUMN_SPECS
)

DRC_CTP_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = tuple(
    _replace_column_spec(spec, required=False, null_policy=NullPolicy.ALLOW)
    if spec.name in {"seniority", "credit_quality", "issuer_id"}
    else spec
    for spec in DRC_NONSEC_ARROW_COLUMN_SPECS
)

DRC_PATH_SPECS: Mapping[str, DrcPathSpec] = {
    DRC_NONSEC_PATH: DrcPathSpec(
        path=DRC_NONSEC_PATH,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        arrow_column_specs=DRC_NONSEC_ARROW_COLUMN_SPECS,
    ),
    DRC_SECURITISATION_NON_CTP_PATH: DrcPathSpec(
        path=DRC_SECURITISATION_NON_CTP_PATH,
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        arrow_column_specs=DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS,
    ),
    DRC_CTP_PATH: DrcPathSpec(
        path=DRC_CTP_PATH,
        risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        arrow_column_specs=DRC_CTP_ARROW_COLUMN_SPECS,
    ),
}


def get_drc_path_spec(path: str) -> DrcPathSpec:
    """Return registry metadata for a DRC batch path.

    Parameters
    ----------
    path : str
        Registry path key such as ``"nonsec"``, ``"securitisation_non_ctp"``,
        or ``"ctp"``.

    Returns
    -------
    DrcPathSpec
        Homogeneous DRC ingress metadata for the requested path.
    """

    try:
        return DRC_PATH_SPECS[path]
    except KeyError as exc:
        known = ", ".join(sorted(DRC_PATH_SPECS))
        raise ValueError(f"unsupported DRC path {path!r}; expected one of: {known}") from exc


def drc_path_spec_for_risk_class(risk_class: DrcRiskClass | str) -> DrcPathSpec:
    """Return registry metadata for a homogeneous DRC risk class.

    Parameters
    ----------
    risk_class : DrcRiskClass or str
        Risk class represented by one homogeneous DRC batch path.

    Returns
    -------
    DrcPathSpec
        Homogeneous DRC ingress metadata for the requested risk class.
    """

    requested = DrcRiskClass(risk_class)
    for spec in DRC_PATH_SPECS.values():
        if spec.risk_class is requested:
            return spec
    raise ValueError(f"unsupported DRC risk class {requested.value!r}")


__all__ = [
    "DRC_CTP_ARROW_COLUMN_SPECS",
    "DRC_CTP_PATH",
    "DRC_NONSEC_ARROW_COLUMN_SPECS",
    "DRC_NONSEC_PATH",
    "DRC_PATH_SPECS",
    "DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS",
    "DRC_SECURITISATION_NON_CTP_PATH",
    "DrcPathSpec",
    "drc_path_spec_for_risk_class",
    "get_drc_path_spec",
]
