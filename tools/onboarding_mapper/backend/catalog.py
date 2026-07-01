"""Extended catalog of FRTB canonical input tables for onboarding."""

from __future__ import annotations

import functools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import ColumnSpec, NormalizedArrowTable

NormalizeCallable = Callable[..., NormalizedArrowTable]


@dataclass(frozen=True)
class TableCatalogEntry:
    package: str
    table_id: str
    component: str
    label: str
    description: str
    column_specs: tuple[ColumnSpec, ...]
    normalize: NormalizeCallable
    sbm_risk_class: str | None = None
    sbm_risk_measure: str | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.package, self.table_id)


def _sbm_catalog_entries() -> Sequence[TableCatalogEntry]:
    import frtb_sbm
    from frtb_sbm.adapters.arrow import _arrow_column_specs_for_path

    entries: list[TableCatalogEntry] = []
    for risk_class, risk_measure in frtb_sbm.SBM_BATCH_PATH_ORDER:
        batch_spec = frtb_sbm.SBM_BATCH_SPECS[(risk_class, risk_measure)]
        path_key = batch_spec.path_key

        def _normalize(
            table: pa.Table,
            *,
            _risk_class: frtb_sbm.SbmRiskClass = risk_class,
            _risk_measure: frtb_sbm.SbmRiskMeasure = risk_measure,
            source_hash: str | None = None,
        ) -> NormalizedArrowTable:
            return frtb_sbm.normalize_sbm_arrow_table(
                table,
                _risk_class,
                _risk_measure,
                source_hash=source_hash,
            )

        entries.append(
            TableCatalogEntry(
                package="frtb_sbm",
                table_id=path_key,
                component="SBM",
                label=batch_spec.label,
                description=(
                    f"Standardised Approach sensitivities — {batch_spec.label} "
                    f"({risk_class.value} / {risk_measure.value})."
                ),
                column_specs=_arrow_column_specs_for_path(risk_class, risk_measure),
                normalize=_normalize,
                sbm_risk_class=risk_class.value,
                sbm_risk_measure=risk_measure.value,
            )
        )
    return entries


def _cva_catalog_entries() -> Sequence[TableCatalogEntry]:
    import frtb_cva

    entity_normalize: Mapping[str, NormalizeCallable] = {
        "counterparty": frtb_cva.normalize_cva_counterparty_arrow_table,
        "netting_set": frtb_cva.normalize_cva_netting_set_arrow_table,
        "hedge": frtb_cva.normalize_cva_hedge_arrow_table,
        "sa_cva_sensitivity": frtb_cva.normalize_sa_cva_sensitivity_arrow_table,
    }
    entity_labels: Mapping[str, tuple[str, str]] = {
        "counterparty": ("CVA counterparties", "BA-CVA counterparty reference rows."),
        "netting_set": ("CVA netting sets", "BA-CVA netting-set exposure rows."),
        "hedge": ("CVA hedges", "BA-CVA hedge designation rows."),
        "sa_cva_sensitivity": (
            "SA-CVA sensitivities",
            "SA-CVA delta and vega sensitivity rows by risk class.",
        ),
    }

    entries: list[TableCatalogEntry] = []
    for entity, spec in frtb_cva.CVA_ENTITY_BATCH_SPECS.items():
        label, description = entity_labels[entity]
        entries.append(
            TableCatalogEntry(
                package="frtb_cva",
                table_id=entity,
                component="CVA",
                label=label,
                description=description,
                column_specs=spec.column_specs,
                normalize=entity_normalize[entity],
            )
        )
    return entries


@functools.lru_cache(maxsize=1)
def table_catalog() -> Mapping[tuple[str, str], TableCatalogEntry]:
    """Return the full onboarding catalog keyed by (package, table_id)."""

    from scripts.client_input_table_registry import input_table_registry

    entries: dict[tuple[str, str], TableCatalogEntry] = {}
    component_by_package = {
        "frtb_drc": "DRC",
        "frtb_rrao": "RRAO",
        "frtb_cva": "CVA",
        "frtb_sbm": "SBM",
        "frtb_ima": "IMA",
    }
    labels = {
        ("frtb_drc", "nonsec"): ("DRC non-securitisation", "Default risk charge position rows."),
        ("frtb_drc", "securitisation_non_ctp"): (
            "DRC securitisation non-CTP",
            "Securitisation non-correlation-trading position rows.",
        ),
        ("frtb_drc", "ctp"): (
            "DRC correlation trading",
            "Correlation trading portfolio position rows.",
        ),
        ("frtb_rrao", "positions"): (
            "RRAO positions",
            "Residual risk add-on position rows with classification evidence.",
        ),
        ("frtb_ima", "scenario_metadata"): (
            "IMA scenario metadata",
            "Scenario lineage and metadata for IMA capital runs.",
        ),
        ("frtb_ima", "rfet_observation"): (
            "IMA RFET observations",
            "Risk-factor eligibility test observation rows.",
        ),
    }

    for key, registry_entry in input_table_registry().items():
        if key[0] == "frtb_sbm":
            continue
        if key[0] == "frtb_cva" and key[1] in {"counterparty", "netting_set"}:
            continue
        label, description = labels.get(key, (key[1].replace("_", " ").title(), ""))
        entries[key] = TableCatalogEntry(
            package=registry_entry.package,
            table_id=registry_entry.input_table_id,
            component=component_by_package.get(registry_entry.package, registry_entry.package),
            label=label,
            description=description,
            column_specs=registry_entry.column_specs,
            normalize=registry_entry.normalize,
        )

    for entry in _sbm_catalog_entries():
        entries[entry.key] = entry
    for entry in _cva_catalog_entries():
        entries[entry.key] = entry
    return entries


def resolve_catalog_entry(package: str, table_id: str) -> TableCatalogEntry:
    catalog = table_catalog()
    key = (package, table_id)
    try:
        return catalog[key]
    except KeyError as exc:
        available = ", ".join(f"{pkg}:{table}" for pkg, table in sorted(catalog))
        raise KeyError(f"Unknown table {package}:{table_id}. Available: {available}") from exc
