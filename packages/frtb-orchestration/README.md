# frtb-orchestration

Partial package for suite-level capital aggregation.

`frtb-orchestration` is the only package allowed to depend on multiple capital
component packages. It will eventually compose IMA, SBM, DRC, RRAO, and CVA
outputs, including the SA total from `frtb-sbm + frtb-drc + frtb-rrao`.

The package does not calculate suite capital yet. Public aggregation entry
points raise `NotImplementedCapitalComponentError` from `frtb-common`; they must
not emit zero or placeholder capital.

The current handoff slice can recognise audited Standardised Approach component
result shapes structurally and summarize them for future aggregation:

- the public `frtb-rrao` `RraoCapitalResult` shape;
- the public `frtb-drc` non-securitisation `DrcCapitalResult` shape; and
- the planned `frtb-sbm` result shape used to settle the SA handoff contract
  before SBM runtime implementation.

SA composition validates supplied component handoffs but still fails explicitly
before aggregation arithmetic. It must not import capital sibling packages at
runtime; component contracts are recognized structurally so orchestration stays
the only cross-component boundary.
