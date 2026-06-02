# 27. DRC correlation trading portfolio row path

Date: 2026-06-02

## Status

Accepted

## Context

`frtb-drc` previously supported only U.S. NPR 2.0 non-securitisation DRC and
failed closed for the correlation trading portfolio (CTP). The CTP rules differ
from the non-securitisation path in material ways:

- proposed section `__.210(d)(1)` and Basel MAR22.36-MAR22.37 define CTP gross
  default exposure as market value rather than the non-securitisation LGD,
  notional, and P&L formula;
- proposed section `__.210(d)(2)` and Basel MAR22.39 allow offsetting through
  exact exposure identity, replication, decomposition, and residual treatment,
  but do not allow arbitrary cross-tranche netting;
- proposed section `__.210(d)(3)(iv)` and Basel MAR22.44 use a CTP-wide hedge
  benefit ratio and do not floor bucket-level CTP DRC at zero;
- proposed section `__.210(d)(3)(v)` and Basel MAR22.45 aggregate positive
  bucket capital at 100 percent and negative bucket capital at 50 percent, then
  floor the CTP category at zero.

The package does not implement the banking-book securitisation risk-weight
hierarchy required to derive every tranched CTP risk weight internally. Treating
missing risk weights as zero or reusing non-securitisation bucket weights for
all CTP positions would understate capital and obscure model scope.

## Decision

Implement a CTP row path in `frtb-drc` with explicit run-scoped evidence:

- CTP position rows use the existing `DrcPosition` contract and identify the
  CTP bucket with `bucket_key`.
- CTP gross default exposure is calculated from absolute market value.
- CTP risk weights are supplied as
  `DrcCalculationContext.ctp_risk_weights[position_id]`.
- Cross-tranche, index, and decomposed-single-name offsetting beyond exact row
  identity is allowed only when
  `DrcCalculationContext.ctp_offset_groups[position_id]` assigns positions to
  the same explicit replication group.
- Missing risk weights, unused CTP evidence, mixed risk weights inside a net
  CTP group, LGD overrides, and missing market values fail closed.
- Disallowed long/short offsets inside the same CTP bucket are retained as
  `RejectedOffset` audit records.
- CTP category reconciliation uses the MAR22.45 / proposed section
  `__.210(d)(3)(v)` aggregation formula rather than simple bucket summation.

At the time of this ADR, securitisation non-CTP remained unsupported. It is now
covered separately by ADR 0028.

## Consequences

The public API can calculate mixed non-securitisation and CTP books without
recognising diversification across categories. The model remains conservative
where upstream systems have not supplied CTP risk weights or replication
evidence.

ADR 0029 supersedes the raw-map-only wording here by adding typed
`DrcRiskWeightEvidence` records as the production audit contract while
preserving the raw map as a low-level compatibility input.

This is still not a complete securitisation engine. A future PR may add
banking-book securitisation risk-weight derivation and richer decomposition
lineage. Until then, callers must provide cited, upstream-derived CTP risk
weights and explicit replication groups where they want cross-tranche or
index/single-name offsetting recognition.

## Validation

- Unit tests cover unhedged CTP capital, explicit cross-tranche replication,
  rejected offsets, category floor behavior, missing risk weights, missing
  market value, and mixed risk weights in a net group.
- `tests/fixtures/drc_ctp_v1` provides a hand-checked CTP fixture with one
  replicated CDX.NA.IG tranche package and one CDX_HY short bucket.
