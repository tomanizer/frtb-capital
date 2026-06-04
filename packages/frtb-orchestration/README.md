# frtb-orchestration

Suite-level capital aggregation for the `frtb-capital` workspace.

`frtb-orchestration` is the only package allowed to depend on multiple capital
component packages. It composes Standardised Approach capital from
`frtb-sbm + frtb-drc + frtb-rrao`, prepares IMA and CVA summaries for
top-of-house use, and aggregates `IMA + SA + CVA` through
`calculate_suite_capital`. Unsupported paths fail closed; the package must not
emit zero or placeholder capital.

Outputs are prototype engineering evidence, not final regulatory capital.

## Documentation

| Document | Purpose |
| --- | --- |
| [Module README](../../docs/modules/frtb-orchestration/README.md) | Package status, examples, validation evidence, limitations, Arrow boundary |
| [ATTRIBUTION.md](ATTRIBUTION.md) | Suite attribution aggregation, component bundle rules, and residual behavior |
| [PUBLIC_API.md](../../docs/modules/frtb-orchestration/PUBLIC_API.md) | Stable top-level exports, suite handoffs, manifest table keys, and unsupported paths |
| [ADR 0039](../../docs/decisions/0039-orchestration-suite-capital-aggregation.md) | Top-of-house suite aggregation decision |
| [ADR 0032](../../docs/decisions/0032-orchestration-sa-arithmetic-and-fallback-routing.md) | SA arithmetic and IMA fallback route recording |
| [ADR 0022](../../docs/decisions/0022-sa-jurisdiction-profile-consistency-guard.md) | Jurisdiction-family guard |

## Runtime support

- `compose_standardised_approach_capital` — additive `SBM + DRC + RRAO` from
  `frtb_common.ComponentCapitalSummary` handoffs with ADR 0022 guards.
- `calculate_suite_capital` — additive `IMA + SA + CVA` from
  `ImaCapitalSummary`, `StandardisedApproachCapitalResult`, and
  `CvaCapitalSummary`.
- `recognise_ima_summary` / `recognise_cva_summary` — duck-typed summary
  projection from public component result shapes.
- `CapitalRunManifest`, `validate_capital_run_manifest`, and
  `run_standardised_approach_from_manifest` — manifest validation and SA routing
  from explicit Arrow input tables.
- Structural IMA desk eligibility recording for SA fallback routing.

## Public API

```python
from frtb_orchestration import (
    ImaCapitalSummary,
    SuiteCapitalResult,
    calculate_suite_capital,
    compose_standardised_approach_capital,
    recognise_cva_summary,
    recognise_ima_summary,
)
```

See [`docs/modules/frtb-orchestration/PUBLIC_API.md`](../../docs/modules/frtb-orchestration/PUBLIC_API.md)
for the stable top-level surface, and
[`docs/modules/frtb-orchestration/README.md`](../../docs/modules/frtb-orchestration/README.md)
for examples, validation evidence, and integration limits.

## Manifest input tables

Manifest v1 uses explicit logical names rather than opaque payloads:

| Constant | Logical name | Purpose |
| --- | --- | --- |
| `SBM_GIRR_DELTA_INPUT_TABLE` | `sbm.girr_delta` | Minimal public SBM route for GIRR delta sensitivity input table. |
| `DRC_NONSEC_INPUT_TABLE` | `drc.nonsec` | DRC non-securitisation input table. |
| `DRC_SECURITISATION_NON_CTP_INPUT_TABLE` | `drc.securitisation_non_ctp` | DRC securitisation non-CTP input table. |
| `DRC_CTP_INPUT_TABLE` | `drc.ctp` | DRC correlation trading portfolio input table. |
| `RRAO_POSITIONS_INPUT_TABLE` | `rrao.positions` | RRAO residual-risk positions input table. |
| `CVA_COUNTERPARTY_INPUT_TABLE` | `cva.counterparty` | CVA counterparty reference input table. |
| `CVA_NETTING_SET_INPUT_TABLE` | `cva.netting_set` | CVA netting-set exposure input table. |
| `CVA_HEDGE_INPUT_TABLE` | `cva.hedge` | CVA hedge input table. |
| `CVA_SA_SENSITIVITY_INPUT_TABLE` | `cva.sa_sensitivity` | SA-CVA sensitivity input table. |

Clients supply `pa.Table` objects to the manifest. File IO, path expansion, and
client delivery-pack validation stay outside this runtime package.

## Boundaries

Runtime modules must not import capital sibling packages or private batch
internals. Package-local tests may use concrete component fixtures to verify
that public adapters and result shapes remain compatible with orchestration
contracts.

See `AGENTS.md` for package boundary rules.
