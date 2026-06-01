# frtb-sbm

Standardised Approach sensitivities-based method component for the
`frtb-capital` suite.

## Status

The package exposes `calculate_sbm_capital` for the phase-1 cited delta, vega,
and row-wise curvature slices under the Basel MAR21 profile. Unsupported
profiles and unsupported sub-features fail closed with explicit errors.

| Area | Status |
| --- | --- |
| GIRR delta and vega capital paths | Implemented (phase 1) |
| FX, equity, and commodity delta capital paths | Implemented (phase 1) |
| CSR delta capital paths | Implemented (phase 1) |
| FX, equity, commodity, and CSR vega capital paths | Implemented (phase 1 row and Arrow/batch API) |
| Curvature capital | Implemented for BASEL_MAR21 row and Arrow/batch inputs; unsupported sub-features fail closed |
| Unsupported profiles and unmapped sub-features | Unsupported capital (fail-closed) |
| Arrow handoff | Supported BASEL_MAR21 delta, vega, and curvature capital paths implemented; portfolio dispatcher available |
| CRIF/CSV adapters | Implemented row-dict canonical mapping for supported BASEL_MAR21 delta/vega/curvature paths; GIRR delta CRIF-to-Arrow handoff |

Outputs from this prototype package are not final regulatory capital.

## Documentation

| Document | Purpose |
| --- | --- |
| [REGULATORY_TRACEABILITY.md](docs/REGULATORY_TRACEABILITY.md) | Code-to-regulation map and phase-1 support status |
| [REGULATORY_ASSUMPTIONS.md](docs/REGULATORY_ASSUMPTIONS.md) | Source-cited implementation boundaries |
| [regulatory_sources.yml](docs/regulatory_sources.yml) | Link-only regulatory source manifest |
| [SBM batch/Arrow performance report](../../docs/performance/frtb-sbm-batch-arrow-report.md) | High-volume handoff benchmark evidence and remaining performance boundaries |
| [Module planning pack](../../docs/modules/frtb-sbm/README.md) | PRD, architecture, requirements registry |
| [Requirements registry](../../docs/modules/frtb-sbm/requirements/BASEL_FRTB_SBM.yml) | Requirement ids and implementation status |

## Public API

```python
from frtb_sbm import PACKAGE_METADATA, calculate_sbm_capital
```

High-volume supported BASEL_MAR21 delta, vega, and curvature inputs can be
converted to package-owned `SbmSensitivityBatch` objects without creating one
accepted `SbmSensitivity` per row. Single-path handoff helpers remain available;
portfolio callers can pass multiple normalized handoffs to the dispatcher.

```python
from frtb_sbm.arrow_handoff import (
    calculate_sbm_portfolio_capital_from_handoffs,
    calculate_sbm_capital_from_commodity_delta_handoff,
    calculate_sbm_capital_from_commodity_vega_handoff,
    calculate_sbm_capital_from_commodity_curvature_handoff,
    calculate_sbm_capital_from_csr_nonsec_delta_handoff,
    calculate_sbm_capital_from_csr_nonsec_vega_handoff,
    calculate_sbm_capital_from_csr_nonsec_curvature_handoff,
    calculate_sbm_capital_from_csr_sec_ctp_delta_handoff,
    calculate_sbm_capital_from_csr_sec_ctp_vega_handoff,
    calculate_sbm_capital_from_csr_sec_ctp_curvature_handoff,
    calculate_sbm_capital_from_csr_sec_nonctp_delta_handoff,
    calculate_sbm_capital_from_csr_sec_nonctp_vega_handoff,
    calculate_sbm_capital_from_csr_sec_nonctp_curvature_handoff,
    calculate_sbm_capital_from_equity_delta_handoff,
    calculate_sbm_capital_from_equity_vega_handoff,
    calculate_sbm_capital_from_equity_curvature_handoff,
    calculate_sbm_capital_from_fx_delta_handoff,
    calculate_sbm_capital_from_fx_vega_handoff,
    calculate_sbm_capital_from_fx_curvature_handoff,
    calculate_sbm_capital_from_girr_delta_handoff,
    calculate_sbm_capital_from_girr_vega_handoff,
    calculate_sbm_capital_from_girr_curvature_handoff,
    normalize_commodity_delta_arrow_table,
    normalize_commodity_vega_arrow_table,
    normalize_commodity_curvature_arrow_table,
    normalize_csr_nonsec_delta_arrow_table,
    normalize_csr_nonsec_vega_arrow_table,
    normalize_csr_nonsec_curvature_arrow_table,
    normalize_csr_sec_ctp_delta_arrow_table,
    normalize_csr_sec_ctp_vega_arrow_table,
    normalize_csr_sec_ctp_curvature_arrow_table,
    normalize_csr_sec_nonctp_delta_arrow_table,
    normalize_csr_sec_nonctp_vega_arrow_table,
    normalize_csr_sec_nonctp_curvature_arrow_table,
    normalize_equity_delta_arrow_table,
    normalize_equity_vega_arrow_table,
    normalize_equity_curvature_arrow_table,
    normalize_fx_delta_arrow_table,
    normalize_fx_vega_arrow_table,
    normalize_fx_curvature_arrow_table,
    normalize_girr_curvature_arrow_table,
    normalize_girr_delta_arrow_table,
    normalize_girr_vega_arrow_table,
)
```

The package-owned batch type represents one homogeneous SBM
`(risk_class, risk_measure)` path. The portfolio dispatcher groups incoming
batches by that metadata and concatenates split batches for the same path before
capital aggregation, preserving cross-row correlations without falling back to
input-row dataclasses.

For FX curvature rows that use the optional MAR21.98 non-reporting-currency
pair scalar, set `FX_CURVATURE_SCALAR_1_5_FLAG` in `mapping_citation_ids` and
provide the two-currency pair in `qualifier`, for example `EUR/GBP`.

The migrated Arrow handoff paths avoid accepted-row `SbmSensitivity` dataclass
materialization. The row API remains available for compatibility and tests, but
high-volume callers should hand off Arrow tables to the public normalizers and
capital-from-handoff helpers.

CRIF-shaped row dictionaries can use `adapt_crif_records` to map supported
BASEL_MAR21 delta, vega, and curvature risk types into canonical
`SbmSensitivity` rows with auditable rejected rows. GIRR delta inputs can also
use the package-owned CRIF-to-Arrow handoff, which delegates package-neutral
column discovery and rejected-row partitioning to `frtb_common.crif` while
retaining SBM RiskType semantics in `frtb_sbm`:

```python
from frtb_sbm.crif import adapt_crif_records, normalize_girr_delta_crif_arrow_table
```

See `AGENTS.md` for package boundary rules.
