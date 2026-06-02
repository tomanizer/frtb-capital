# ADR 0030: DRC securitisation fair-value cap evidence

## Status

Accepted.

## Context

The securitisation non-CTP path calculates gross default exposure from market
value under proposed U.S. section `__.210(c)(1)` and Basel MAR22.27, then
applies maturity scaling, permitted netting, HBR, bucket floors, and category
summation. Basel MAR22.34 permits the capital requirement for an individual cash
securitisation position to be capped at the transaction fair value, and the
U.S. NPR securitisation bucket formula is anchored in proposed section
`__.210(c)(3)(iii)`.

Applying that cap silently would hide an optional branch that changes the
capital number and would make later attribution analysis ambiguous.

## Decision

`frtb-drc` will apply securitisation non-CTP fair-value caps only through a
profile-controlled typed evidence record:

- `DrcCalculationContext.securitisation_non_ctp_fair_value_cap_evidence` is the
  run-scoped evidence map.
- `DrcFairValueCapEvidence` records position id, source profile, eligibility,
  cap amount, eligibility reason, as-of date, source id, lineage, citations, and
  stale/validation flags.
- The U.S. NPR 2.0 profile explicitly allows this control with citations
  `US_NPR_210_C_3_III` and `BASEL_MAR22_34`.
- Missing evidence means no cap is applied and the branch metadata says market
  value was used.
- Eligible evidence applies `min(abs(market_value), fair_value_cap_amount)`
  before maturity scaling.
- Ineligible evidence keeps market value and records the ineligibility reason.
- Duplicate, unused, stale, uncited, future-dated, profile-mismatched, negative,
  non-finite, or incomplete evidence fails closed.

## Consequences

The row path preserves the cap decision in `GrossJtd.branch_metadata` and the
used evidence in `DrcCapitalResult.fair_value_cap_evidence`. The batch path
applies the same cap array before maturity scaling, keeps the result row-free,
and records the cap decision in result-level branch metadata plus used evidence.

Legacy no-cap behavior remains unchanged when no cap evidence is supplied.
