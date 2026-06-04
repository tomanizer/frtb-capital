# frtb-drc decisions and implementation plan

## Decision log

### DRC-DEC-001: Implement non-securitisation first

**Decision:** The first capital-producing implementation slice supported
non-securitisation debt and equity positions only.

**Reason:** Non-securitisation DRC provides the core JTD, maturity, netting,
HBR, bucket, and category mechanics. Securitisation non-CTP and CTP require
separate tranche, replication, and banking-book risk-weight mappings that would
make the first slice too broad.

**Current status:** That first slice is delivered. U.S. NPR 2.0
securitisation non-CTP and CTP row/batch slices are now implemented with cited
upstream evidence contracts. Basel MAR22 non-securitisation and securitisation
non-CTP row/batch slices are implemented with cited profile-specific mappings.
Basel MAR22 CTP row/batch slices are implemented with typed MAR22.42
risk-weight and decomposition evidence. EU CRR3 non-securitisation row/batch is
implemented with Article 325w, Article 325x, Article 325y, and ECAI/CQS mapping
evidence. EU CRR3 securitisation non-CTP, EU CRR3 CTP, and PRA UK CRR remain
fail-closed until profile-specific mappings and tests are implemented.

### DRC-DEC-002: Keep data contracts package-local initially

**Decision:** DRC-specific dataclasses, enums, and citations start in
`frtb_drc.data_models`.

**Reason:** `frtb-common` is still a small scaffold. Moving DRC-specific
issuer, tranche, seniority, bucket, and JTD types into common would prematurely
couple future SBM, RRAO, and CVA package design to DRC internals.

**Implication:** Only truly shared primitives, such as unsupported-feature
exceptions and future generic rule-profile identity, should move to
`frtb-common` under a separate cross-cutting issue and ADR if needed.

### DRC-DEC-003: Profiles own parameters; kernels receive typed values

**Decision:** LGD values, maturity rules, bucket definitions, risk weights, and
supported-feature switches belong in versioned rule profiles and reference-data
helpers. Calculation kernels receive typed values and do not branch on global
regime names.

**Reason:** This matches the suite documentation pattern and keeps regulatory
traceability and reproducibility separate from numeric code.

**Implication:** Tests must cover profile lookup separately from calculations.

### DRC-DEC-004: Direction is explicit

**Decision:** `DefaultDirection` is a required input field after adapter
normalisation. Kernels must not infer long/short default direction from
accounting side or notional sign alone.

**Reason:** Basel MAR22.10 and proposed U.S. section `__.210(b)(1)(ii)` define
direction by default loss or gain.

**Implication:** CRIF/vendor adapters must map source sign conventions into
explicit default direction and record the mapping in lineage.

### DRC-DEC-005: Store shorts as readable magnitudes in public records

**Decision:** Public gross/net/HBR records store long and short amounts as
positive magnitudes plus explicit direction fields. Internal kernels may use
signed `numpy` arrays after validation.

**Reason:** Audit reviewers read magnitude-plus-direction records more easily,
while signed arrays simplify aggregation once direction is normalised.

**Implication:** Conversion between public records and kernel arrays must be
tested.

### DRC-DEC-006: No cross-category diversification

**Decision:** The initial total DRC result sums category-level DRC without
cross-category diversification.

**Reason:** Proposed U.S. section `__.210(a)(4)` explicitly prohibits
diversification benefits across default-risk categories. Basel MAR22 also
treats non-securitisation, securitisation non-CTP, and CTP as separate DRC
sub-frameworks.

**Implication:** Any future profile with a different aggregation treatment must
cite the rule and add tests before changing this behavior.

### DRC-DEC-007: Audit graph and attribution

**Decision:** The implementation provides deterministic bucket and
netting-group explain records with attribution-ready lineage and emits
attribution records outside the capital kernel. Analytical Euler is used where
the active branch is stable; explicit residual or unsupported records are used
where floors, zero HBR denominators, missing risk-weight lineage, or unsupported
branch shapes prevent exact Euler decomposition. Baseline-vs-candidate impact
remains a later enhancement.

**Reason:** The package first needs a stable capital chain. Euler allocation is
useful for explainability and change control but should not delay the cited
calculation path. It is also branch-sensitive: floors, zero denominators,
bucket moves, and unsupported paths must be labelled before a contribution
method can be trusted.

**Implication:** The first slice must retain stable ids and branch metadata from
position through total result. `attribution.py` follows
[ADR 0012](../../decisions/0012-capital-impact-attribution.md) and
[ADR 0031](../../decisions/0031-drc-attribution-method-contract.md);
`impact.py` remains future work.

### DRC-DEC-008: Securitisation and CTP fail closed until cited evidence exists

**Decision:** Securitisation non-CTP and CTP modules should produce capital
only where cited data contracts and fixture packs are complete; otherwise they
must be explicit unsupported-feature gates.

**Reason:** Both paths require additional profile data and product structures.
Returning partial values would violate the package's no-placeholder-capital
rule.

**Current status:** U.S. NPR 2.0 securitisation non-CTP and CTP paths are
implemented for row and batch APIs using typed risk-weight evidence, explicit
replication evidence, and deterministic tests. U.S. NPR 2.0 securitisation
non-CTP also supports profile-controlled fair-value cap evidence. Basel MAR22
securitisation non-CTP is implemented with typed MAR22.34 evidence. Basel
MAR22 CTP is implemented with typed MAR22.42 evidence. EU CRR3 non-securitisation
is implemented; EU CRR3 securitisation non-CTP, EU CRR3 CTP, and PRA UK CRR
paths still fail closed.

## Implementation sequence

1. Complete issue 62 scaffold and keep DRC calculation entry points failing
   explicitly.
2. Add DRC package model documentation and traceability skeleton.
3. Implement data models and validation.
4. Implement rule profiles and reference data for the first U.S. NPR
   non-securitisation vertical slice.
5. Implement gross JTD.
6. Implement maturity scaling and netting.
7. Implement HBR, bucket capital, category total, and run result.
8. Add audit/replay artifacts and synthetic validation pack.
9. Add explicit attribution readiness to the public docs and result graph.
10. Integrate DRC package output contract into orchestration, without composing
   SA until SBM and RRAO outputs exist.
11. Implement securitisation non-CTP.
12. Implement CTP.
13. Add optional CRIF adapter, validation notebooks, performance checks, and
    analytical Euler attribution.
14. Add finite-difference impact assessment in a later issue.

## Documentation deliverables

Each implementation slice must update:

- `docs/modules/frtb-drc/DETAILED_REQUIREMENTS.md`;
- `docs/modules/frtb-drc/REGULATORY_REQUIREMENTS.md`;
- `packages/frtb-drc/docs/requirements/BASEL_FRTB_DRC.yml`;
- `packages/frtb-drc/README.md`;
- package-local regulatory traceability once calculation modules exist;
- validation fixtures and audit reports when result formats change.

## Delivered vertical slices and remaining gaps

The first useful release of `frtb-drc` was a U.S. NPR 2.0
non-securitisation slice:

- canonical positions;
- cited LGD mapping;
- gross JTD;
- maturity weighting with three-month floor;
- same-obligor seniority-aware netting;
- four proposed non-securitisation buckets;
- cited risk weights for supported fixtures;
- HBR and bucket capital;
- no cross-category diversification;
- deterministic audit output.

This is narrow enough to implement and review, but broad enough to exercise the
core DRC mechanics.

The current partial runtime also includes U.S. NPR 2.0 securitisation non-CTP
and CTP row/batch paths, Basel MAR22 non-securitisation row/batch paths,
Basel MAR22 securitisation non-CTP and CTP row/batch paths, Arrow/batch fast
paths, EU CRR3 non-securitisation row/batch paths, and attribution records.
Remaining gaps are deliberate: EU CRR3 securitisation non-CTP and CTP, PRA UK
CRR, internal banking-book securitisation risk-weight derivation, and
baseline-vs-candidate impact analysis remain outside the current implemented
scope.

## Open design questions

1. Should `DrcRuleProfile` remain package-local for DRC v1 or move to
   `frtb-common` before SBM and RRAO implement their profiles?
2. Should money amounts remain `float64` throughout kernels or should input
   adapters preserve `Decimal` amounts for audit while kernels receive floats?
3. Which U.S. NPR risk-weight tables should be supported in the first fixture:
   only the minimum non-securitisation table entries needed for examples, or the
   complete proposed non-securitisation table?
4. Should CRIF mapping ship before or after the first canonical-input capital
   slice?
5. What benchmark size is useful enough for DRC without overfitting to synthetic
   data shape?

These are design questions, not blockers for the first data-model and
validation issues.
