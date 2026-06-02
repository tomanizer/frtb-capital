# 29. DRC securitisation and CTP risk-weight evidence contract

Date: 2026-06-02

## Status

Accepted

## Context

ADR 0027 and ADR 0028 implemented CTP and securitisation non-CTP DRC paths with
run-scoped risk weights. That kept the calculation fail-closed, but the
contract was still an opaque `position_id -> float` map. Basel MAR22.34 and
MAR22.42 refer to banking-book securitisation risk weights for securitisation
non-CTP and CTP default risk. Proposed U.S. section `__.210(c)` and
`__.210(d)` use the same boundary: DRC consumes securitisation risk-weight
outcomes but is not itself a complete banking-book securitisation engine.

The package needs an auditable way to consume upstream risk-weight derivations
without silently deriving SEC-SA, SEC-ERBA, SEC-IRBA, STC alternatives, or
jurisdictional banking-book variants inside `frtb-drc`.

## Decision

`frtb-drc` accepts a typed upstream risk-weight evidence handoff for
securitisation non-CTP and CTP:

- `DrcRiskWeightEvidence` records identify the DRC position, risk class, source
  profile, source table, source method, effective risk weight, as-of date,
  source id, lineage, citation ids, stale flag, and validation flags.
- `DrcCalculationContext.securitisation_non_ctp_risk_weight_evidence` and
  `DrcCalculationContext.ctp_risk_weight_evidence` hold immutable maps keyed by
  position id.
- `risk_weight_evidence_by_position()` builds those maps from iterable records
  and rejects duplicate position evidence before context construction.
- The legacy raw float maps remain as low-level compatibility inputs for tests
  and adapters, but typed evidence is the production audit contract.
- Row and batch calculations combine legacy maps and typed evidence into one
  effective map, reject conflicts, and fail closed on missing, duplicate,
  stale, uncited, wrong-risk-class, non-finite, negative, or future-dated
  evidence before capital is calculated.
- Used risk-weight evidence is included in the deterministic input hash and in
  `DrcCapitalResult.risk_weight_evidence`.

The package still does not internally derive banking-book securitisation risk
weights. Upstream systems remain responsible for producing cited derivation
evidence from the applicable banking-book or securitisation framework.

## Consequences

Securitisation non-CTP and CTP DRC can now consume auditable upstream
risk-weight evidence rather than only raw float maps. The result snapshot
contains the evidence lineage needed for replay and documentation review.

Adding `risk_weight_evidence` to `DrcCapitalResult` changes deterministic result
JSON hashes even for runs with no securitisation or CTP evidence, because the
public result schema now includes the empty evidence tuple.

Future work can add Arrow-backed evidence handoff adapters or an internal
banking-book derivation engine, but either option must preserve the same
position-keyed evidence semantics and fail-closed validation.

## Validation

- `test_drc_securitisation.py` covers cited evidence consumption, evidence hash
  participation, duplicate rejection, stale rejection, and uncited rejection.
- `test_drc_ctp.py` covers cited CTP evidence consumption and stale rejection.
- `test_drc_arrow_batch.py` continues to cover batch risk-weight validation and
  result reconciliation through the shared effective-risk-weight path.
