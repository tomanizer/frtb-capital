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
  base currency, explicit Arrow handoff tables, package-owned calculation
  contexts, optional reference attachments, and run metadata;
- `validate_capital_run_manifest` validates registered handoff routes with the
  public package normalizers, reports accepted and rejected rows, diagnostics,
  source hashes, normalized handoff hashes, missing required handoffs, and ADR
  0022 jurisdiction-family consistency before any capital calculation;
- `run_standardised_approach_from_manifest` validates the manifest, routes
  available public component handoff APIs into component result handoffs, and
  records any fail-closed aggregation error explicitly in `SaManifestRunResult`;
- `compose_standardised_approach_capital` accepts the shared
  `frtb_common.ComponentResultHandoff` shape for SBM, DRC, and RRAO, validates
  that each handoff is in the expected component slot, applies the ADR 0022
  jurisdiction-family guard, checks calculation date and base currency
  consistency, and returns the additive SA result `SBM + DRC + RRAO`;
- non-IMA-eligible desks can be passed through the structural
  `ima_desk_eligibility` mapping and are recorded as routed to the Standardised
  Approach fallback stack;
- each SA component owns its own `to_orchestration_handoff` projection into
  that shared contract;
- `recognise_cva_result` summarizes the public CVA result shape into
  `CvaResultHandoff` for future top-of-house aggregation, outside SA
  composition;
- `calculate_suite_capital` remains explicitly unimplemented.

Manifest v1 uses explicit logical names rather than opaque payloads:

| Constant | Logical name | Purpose |
| --- | --- | --- |
| `SBM_GIRR_DELTA_HANDOFF` | `sbm.girr_delta` | Minimal public SBM route for GIRR delta sensitivity handoff. |
| `DRC_NONSEC_HANDOFF` | `drc.nonsec` | DRC non-securitisation handoff. |
| `DRC_SECURITISATION_NON_CTP_HANDOFF` | `drc.securitisation_non_ctp` | DRC securitisation non-CTP handoff. |
| `DRC_CTP_HANDOFF` | `drc.ctp` | DRC correlation trading portfolio handoff. |
| `RRAO_POSITIONS_HANDOFF` | `rrao.positions` | RRAO residual-risk positions handoff. |
| `CVA_COUNTERPARTY_HANDOFF` | `cva.counterparty` | CVA counterparty reference handoff. |
| `CVA_NETTING_SET_HANDOFF` | `cva.netting_set` | CVA netting-set exposure handoff. |
| `CVA_HEDGE_HANDOFF` | `cva.hedge` | CVA hedge handoff. |
| `CVA_SA_SENSITIVITY_HANDOFF` | `cva.sa_sensitivity` | SA-CVA sensitivity handoff. |

Clients supply `pa.Table` objects to the manifest. File IO, path expansion, and
client delivery-pack validation stay outside this runtime package.

Runtime modules must not import capital sibling packages or private batch
internals. Package-local tests may use concrete component fixtures to verify
that public adapters and result shapes remain compatible with the orchestration
contracts.
