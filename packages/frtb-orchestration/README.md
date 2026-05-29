# frtb-orchestration

Partial package for suite-level capital aggregation.

`frtb-orchestration` is the only package allowed to depend on multiple capital
component packages. It will eventually compose IMA, SBM, DRC, RRAO, and CVA
outputs, including the SA total from `frtb-sbm + frtb-drc + frtb-rrao`.

The package does not calculate suite capital yet. Public aggregation entry
points raise `NotImplementedCapitalComponentError` from `frtb-common`; they must
not emit zero or placeholder capital.

The current handoff slice can recognise the public `frtb-rrao`
`RraoCapitalResult` shape structurally and summarize it for future
Standardised Approach aggregation. SA composition still fails explicitly until
SBM and DRC expose compatible audited result contracts.
