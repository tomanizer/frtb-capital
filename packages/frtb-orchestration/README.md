# frtb-orchestration

Partial package for suite-level capital aggregation.

`frtb-orchestration` is the only package allowed to depend on multiple capital
component packages. It owns the suite boundary that will compose IMA, SBM, DRC,
RRAO, and CVA outputs, including the SA total from
`frtb-sbm + frtb-drc + frtb-rrao`.

The package does not calculate suite capital yet. Public aggregation entry
points raise `NotImplementedCapitalComponentError` from `frtb-common`; they must
not emit zero or placeholder capital.

Current runtime support is deliberately narrow:

- `compose_standardised_approach_capital` accepts the shared
  `frtb_common.ComponentResultHandoff` shape for SBM, DRC, and RRAO, validates
  that each handoff is in the expected component slot, applies the ADR 0022
  jurisdiction-family guard, then fails closed before SA aggregation
  arithmetic;
- each SA component owns its own `to_orchestration_handoff` projection into
  that shared contract;
- `recognise_cva_result` summarizes the public CVA result shape into
  `CvaResultHandoff` for future top-of-house aggregation, outside SA
  composition;
- `calculate_suite_capital` remains explicitly unimplemented.

Runtime modules must not import capital sibling packages or private batch
internals. Package-local tests may use concrete component fixtures to verify
that public adapters and result shapes remain compatible with the orchestration
contracts.
