# frtb-sbm

Standardised Approach sensitivities-based method component for the
`frtb-capital` suite.

## Status

The package exposes `calculate_sbm_capital` for the phase-1 cited GIRR delta,
GIRR vega, FX delta, equity delta, commodity delta, CSR delta, and curvature
slices under the Basel MAR21 profile. FX/equity/commodity/CSR vega and
unsupported profiles fail closed with explicit errors.

| Area | Status |
| --- | --- |
| GIRR delta and vega capital paths | Implemented (phase 1) |
| FX, equity, and commodity delta capital paths | Implemented (phase 1) |
| CSR delta capital paths | Implemented (phase 1) |
| Curvature capital | Implemented for BASEL_MAR21 row-wise inputs; unsupported sub-features fail closed |
| FX/equity/commodity/CSR vega and unsupported profiles | Unsupported capital (fail-closed) |
| Arrow handoff | GIRR delta/vega, non-credit delta, and CSR delta capital paths implemented; GIRR curvature validation handoff implemented |
| CRIF/CSV adapters | Partial: row-dict compatibility plus GIRR delta CRIF-to-Arrow handoff |

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

High-volume GIRR delta/vega, supported non-credit delta, and CSR delta inputs can
be converted to the package-owned `SbmSensitivityBatch` without creating one
accepted `SbmSensitivity` per row. Curvature capital is currently exposed
through the row-wise public API. GIRR curvature inputs can use the Arrow handoff
boundary for validation and branch-selection preparation, but not yet for
capital calculation.

```python
from frtb_sbm.arrow_handoff import (
    calculate_sbm_capital_from_commodity_delta_handoff,
    calculate_sbm_capital_from_csr_nonsec_delta_handoff,
    calculate_sbm_capital_from_csr_sec_ctp_delta_handoff,
    calculate_sbm_capital_from_csr_sec_nonctp_delta_handoff,
    calculate_sbm_capital_from_equity_delta_handoff,
    calculate_sbm_capital_from_fx_delta_handoff,
    calculate_sbm_capital_from_girr_delta_handoff,
    calculate_sbm_capital_from_girr_vega_handoff,
    build_girr_curvature_batch_from_handoff,
    normalize_commodity_delta_arrow_table,
    normalize_csr_nonsec_delta_arrow_table,
    normalize_csr_sec_ctp_delta_arrow_table,
    normalize_csr_sec_nonctp_delta_arrow_table,
    normalize_equity_delta_arrow_table,
    normalize_fx_delta_arrow_table,
    normalize_girr_curvature_arrow_table,
    normalize_girr_delta_arrow_table,
    normalize_girr_vega_arrow_table,
)
```

The package-owned batch type now represents one homogeneous SBM
`(risk_class, risk_measure)` path. GIRR delta/vega, FX, equity, commodity,
and CSR delta have public capital-from-Arrow handoffs. GIRR curvature has a
validation-only Arrow handoff that keeps `up_shock_amount` and
`down_shock_amount` as separate arrays; curvature capital still uses the row API
until the high-volume curvature batch path is implemented.

For FX curvature rows that use the optional MAR21.98 non-reporting-currency
pair scalar, set `FX_CURVATURE_SCALAR_1_5_FLAG` in `mapping_citation_ids` and
provide the two-currency pair in `qualifier`, for example `EUR/GBP`.

The migrated Arrow handoff paths avoid accepted-row `SbmSensitivity` dataclass
materialization. The row API remains available for compatibility and tests, but
high-volume callers should hand off Arrow tables to the public normalizers and
capital-from-handoff helpers.

CRIF-shaped GIRR delta inputs can first use the package-owned CRIF mapping,
which delegates package-neutral column discovery and rejected-row partitioning
to `frtb_common.crif` while retaining SBM RiskType semantics in `frtb_sbm`:

```python
from frtb_sbm.crif import normalize_girr_delta_crif_arrow_table
```

See `AGENTS.md` for package boundary rules.
