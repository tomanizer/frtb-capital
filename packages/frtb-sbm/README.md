# frtb-sbm

Standardised Approach sensitivities-based method component for the
`frtb-capital` suite.

## Status

The package exposes `calculate_sbm_capital` for the phase-1 cited
`BASEL_MAR21` delta, vega, and curvature slices across all seven SBM risk
classes. Unsupported profiles and unsupported sub-features fail closed with
explicit errors.

| Area | Status |
| --- | --- |
| BASEL_MAR21 delta capital paths | Implemented under audit for GIRR, FX, equity, commodity, CSR non-sec, CSR sec non-CTP, and CSR sec CTP |
| BASEL_MAR21 vega capital paths | Implemented under audit for GIRR, FX, equity, commodity, CSR non-sec, CSR sec non-CTP, and CSR sec CTP |
| BASEL_MAR21 curvature capital paths | Implemented under audit for GIRR, FX, equity, commodity, CSR non-sec, CSR sec non-CTP, and CSR sec CTP |
| Unsupported profiles and unmapped sub-features | Unsupported capital (fail-closed) |
| Arrow batch | Supported BASEL_MAR21 delta, vega, and curvature capital paths implemented; portfolio dispatcher available |
| CRIF/CSV adapters | Implemented row-dict canonical mapping for supported BASEL_MAR21 delta/vega/curvature paths; GIRR delta CRIF-to-Arrow batch |
| Attribution and impact | Delta/vega analytical Euler attribution implemented for differentiable selected branches; curvature, active floors, alternative `S_b`, and incomplete pairwise evidence emit explicit unsupported residuals. Baseline-vs-candidate impact is finite difference, not marginal contribution. |

Outputs from this prototype package are not final regulatory capital.
`PACKAGE_METADATA.validation_status` remains `PENDING`; current evidence is
synthetic and internal. The single source of package support status is the
matrix in [REGULATORY_TRACEABILITY.md](docs/REGULATORY_TRACEABILITY.md).

**Integration journey (Arrow → capital → attribution → SA/suite/store):**
[`docs/PACKAGE_JOURNEY.md`](docs/PACKAGE_JOURNEY.md)

## Documentation

| Document | Purpose |
| --- | --- |
| [PACKAGE_JOURNEY.md](docs/PACKAGE_JOURNEY.md) | End-to-end client flow, tiers, portfolio dispatcher, orchestration boundaries |
| [PUBLIC_API.md](../../docs/modules/frtb-sbm/PUBLIC_API.md) | Stable client integration surface, handoff specs, and top-level imports |
| [REGULATORY_TRACEABILITY.md](docs/REGULATORY_TRACEABILITY.md) | Code-to-regulation map and phase-1 support status |
| [REGULATORY_ASSUMPTIONS.md](docs/REGULATORY_ASSUMPTIONS.md) | Source-cited implementation boundaries |
| [ATTRIBUTION.md](ATTRIBUTION.md) | Capital attribution method, inputs, supported grains, and limitations |
| [regulatory_sources.yml](docs/regulatory_sources.yml) | Link-only regulatory source manifest |
| [SBM batch/Arrow performance report](../../docs/performance/frtb-sbm-batch-arrow-report.md) | High-volume handoff benchmark evidence and remaining performance boundaries |
| [Module planning pack](../../docs/modules/frtb-sbm/README.md) | PRD, architecture, requirements registry |
| [Requirements registry](docs/requirements/BASEL_FRTB_SBM.yml) | Requirement ids and implementation status |

## Public API

```python
from frtb_sbm import (
    PACKAGE_METADATA,
    calculate_sbm_attribution,
    calculate_sbm_capital,
    calculate_sbm_capital_impact,
)
```

High-volume supported BASEL_MAR21 delta, vega, and curvature inputs can be
converted to package-owned `SbmSensitivityBatch` objects without creating one
accepted `SbmSensitivity` per row. Single-path handoff helpers remain available;
portfolio callers can pass multiple normalized handoffs to the dispatcher.

```python
from frtb_sbm.arrow_batch import (
    calculate_sbm_portfolio_capital_from_arrow_tables,
    calculate_sbm_capital_from_commodity_delta_arrow,
    calculate_sbm_capital_from_commodity_vega_arrow,
    calculate_sbm_capital_from_commodity_curvature_arrow,
    calculate_sbm_capital_from_csr_nonsec_delta_arrow,
    calculate_sbm_capital_from_csr_nonsec_vega_arrow,
    calculate_sbm_capital_from_csr_nonsec_curvature_arrow,
    calculate_sbm_capital_from_csr_sec_ctp_delta_arrow,
    calculate_sbm_capital_from_csr_sec_ctp_vega_arrow,
    calculate_sbm_capital_from_csr_sec_ctp_curvature_arrow,
    calculate_sbm_capital_from_csr_sec_nonctp_delta_arrow,
    calculate_sbm_capital_from_csr_sec_nonctp_vega_arrow,
    calculate_sbm_capital_from_csr_sec_nonctp_curvature_arrow,
    calculate_sbm_capital_from_equity_delta_arrow,
    calculate_sbm_capital_from_equity_vega_arrow,
    calculate_sbm_capital_from_equity_curvature_arrow,
    calculate_sbm_capital_from_fx_delta_arrow,
    calculate_sbm_capital_from_fx_vega_arrow,
    calculate_sbm_capital_from_fx_curvature_arrow,
    calculate_sbm_capital_from_girr_delta_arrow,
    calculate_sbm_capital_from_girr_vega_arrow,
    calculate_sbm_capital_from_girr_curvature_arrow,
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

The migrated Arrow batch paths avoid accepted-row `SbmSensitivity` dataclass
materialization. The row API remains available for compatibility and tests, but
high-volume callers should hand off Arrow tables to the public normalizers and
capital-from-handoff helpers.

CRIF-shaped row dictionaries can use `adapt_crif_records` to map supported
BASEL_MAR21 delta, vega, and curvature risk types into canonical
`SbmSensitivity` rows with auditable rejected rows. GIRR delta inputs can also
use the package-owned CRIF-to-Arrow batch, which delegates package-neutral
column discovery and rejected-row partitioning to `frtb_common.crif` while
retaining SBM RiskType semantics in `frtb_sbm`:

```python
from frtb_sbm.crif import adapt_crif_records, normalize_girr_delta_crif_arrow_table
```

See `AGENTS.md` for package boundary rules.

## End-to-end examples

See `examples/run_demo.py` for a self-contained synthetic demo that constructs
`SbmSensitivity` lists (GIRR/Equity/FX/Commodity/CSR delta, GIRR vega, GIRR
curvature) and calls `calculate_sbm_capital` under the BASEL_MAR21 profile,
printing `SbmCapitalResult` totals and bucket breakdowns.

```bash
uv run python packages/frtb-sbm/examples/run_demo.py
```

See `tests/fixtures/*/loader.py` and the public API / batch / Arrow tests for
additional construction and fixture-based workflow patterns.
