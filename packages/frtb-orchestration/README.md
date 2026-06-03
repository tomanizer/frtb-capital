# frtb-orchestration

Partial package for suite-level capital aggregation.

`frtb-orchestration` is the only package allowed to depend on multiple capital
component packages. It owns the suite boundary that will compose IMA, SBM, DRC,
RRAO, and CVA outputs, including the SA total from
`frtb-sbm + frtb-drc + frtb-rrao`.

The package does not calculate suite capital yet. Top-of-house aggregation
raises `NotImplementedCapitalComponentError` from `frtb-common`; it must not
emit zero or placeholder capital.

Current runtime support is deliberately narrow:

- `CapitalRunManifest` accepts a client run id, calculation date, profile id,
  base currency, explicit Arrow input tables, package-owned calculation
  contexts, optional reference attachments, and run metadata;
- `validate_capital_run_manifest` validates registered input table routes with the
  public package normalizers, reports accepted and rejected rows, diagnostics,
  source hashes, normalized input table hashes, missing required input tables, and ADR
  0022 jurisdiction-family consistency before any capital calculation;
- `run_standardised_approach_from_manifest` validates the manifest, routes
  available public component input table APIs into component result summaries, and
  records any fail-closed aggregation error explicitly in `SaManifestRunResult`;
- `compose_standardised_approach_capital` accepts the shared
  `frtb_common.ComponentCapitalSummary` shape for SBM, DRC, and RRAO, validates
  that each summary is in the expected component slot, applies the ADR 0022
  jurisdiction-family guard, checks calculation date and base currency
  consistency, and returns the additive SA result `SBM + DRC + RRAO`;
- non-IMA-eligible desks can be passed through the structural
  `ima_desk_eligibility` mapping and are recorded as routed to the Standardised
  Approach fallback stack;
- each SA component owns its own `to_component_summary` projection into
  that shared contract;
- `recognise_cva_summary` summarizes the public CVA result shape into
  `CvaCapitalSummary` for future top-of-house aggregation, outside SA
  composition;
- `calculate_suite_capital` remains explicitly unimplemented.

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

Runtime modules must not import capital sibling packages or private batch
internals. Package-local tests may use concrete component fixtures to verify
that public adapters and result shapes remain compatible with the orchestration
contracts.
