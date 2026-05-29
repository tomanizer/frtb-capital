# frtb-sbm

Standardised Approach sensitivities-based method component for the
`frtb-capital` suite.

## Status

The package is importable and exposes its planned public boundary. Phase 1
implements a cited GIRR delta vertical slice (parent issue #151). Until that
slice lands, `calculate_sbm_capital` raises `NotImplementedCapitalComponentError`
from `frtb-common`; it must not emit zero or placeholder capital.

| Area | Status |
| --- | --- |
| Public calculation boundary | Scaffold |
| GIRR delta capital path | Planned (phase 1) |
| Vega, curvature, non-GIRR risk classes | Unsupported (fail-closed) |
| CRIF/CSV adapters | Out of scope (phase 1) |

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

See `AGENTS.md` for package boundary rules.
