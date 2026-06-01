# frtb-sbm

Standardised Approach sensitivities-based method component for the
`frtb-capital` suite.

## Status

The package exposes `calculate_sbm_capital` for the phase-1 cited GIRR delta,
GIRR vega, and FX delta slices under the Basel MAR21 profile. Curvature, FX
vega, and remaining non-GIRR risk classes fail closed with explicit errors.

| Area | Status |
| --- | --- |
| GIRR delta and vega capital paths | Implemented (phase 1) |
| FX delta capital path | Implemented (phase 1) |
| Curvature, FX vega, remaining risk classes | Unsupported (fail-closed) |
| Arrow handoff | GIRR delta and vega batch paths implemented; broader adapters pending |
| CRIF/CSV adapters | Partial: row-dict compatibility plus GIRR delta CRIF-to-Arrow handoff |

Outputs from this prototype package are not final regulatory capital.

## Documentation

| Document | Purpose |
| --- | --- |
| [REGULATORY_TRACEABILITY.md](docs/REGULATORY_TRACEABILITY.md) | Code-to-regulation map and phase-1 support status |
| [REGULATORY_ASSUMPTIONS.md](docs/REGULATORY_ASSUMPTIONS.md) | Source-cited implementation boundaries |
| [regulatory_sources.yml](docs/regulatory_sources.yml) | Link-only regulatory source manifest |
| [Module planning pack](../../docs/modules/frtb-sbm/README.md) | PRD, architecture, requirements registry |
| [Requirements registry](../../docs/modules/frtb-sbm/requirements/BASEL_FRTB_SBM.yml) | Requirement ids and implementation status |

## Public API

```python
from frtb_sbm import PACKAGE_METADATA, calculate_sbm_capital
```

High-volume GIRR delta and vega inputs can be converted to the package-owned
`SbmSensitivityBatch` without creating one accepted `SbmSensitivity` per row:

```python
from frtb_sbm.arrow_handoff import (
    calculate_sbm_capital_from_girr_delta_handoff,
    calculate_sbm_capital_from_girr_vega_handoff,
    normalize_girr_delta_arrow_table,
    normalize_girr_vega_arrow_table,
)
```

The package-owned batch type now represents one homogeneous SBM
`(risk_class, risk_measure)` path. GIRR delta and GIRR vega have public
capital-from-Arrow handoffs; broader path-specific Arrow entrypoints are tracked
under #270.

CRIF-shaped GIRR delta inputs can first use the package-owned CRIF mapping,
which delegates package-neutral column discovery and rejected-row partitioning
to `frtb_common.crif` while retaining SBM RiskType semantics in `frtb_sbm`:

```python
from frtb_sbm.crif import normalize_girr_delta_crif_arrow_table
```

See `AGENTS.md` for package boundary rules.
