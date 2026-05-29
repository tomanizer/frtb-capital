# Validation Evidence

This page records evidence of calculation mechanics. It is not independent
model validation and not regulatory approval.

## Automated Tests

The RRAO test suite covers:

- canonical input validation in `tests/test_validation.py`;
- classification and exclusion rules in `tests/test_classification.py` and
  `tests/test_exclusions.py`;
- additive line capital and subtotals in `tests/test_capital.py`;
- public API and replay in `tests/test_public_api.py`, `tests/test_audit.py`,
  and `tests/test_replay.py`;
- EU CRR3 comparison treatment in `tests/test_eu_profile.py`;
- investment-fund inclusion in `tests/test_investment_fund.py`;
- allocation reports in `tests/test_allocation.py`;
- property tests in `tests/test_properties.py`;
- external comparator tests in `tests/test_external_comparator.py`;
- reconciliation tolerance in `tests/test_reconciliation_tolerance.py`.

## Fixtures And Replay

The U.S. fixture `tests/fixtures/rrao_v1/` covers exotic, other residual risk,
supervisor-directed inclusion, cited exclusions, exact back-to-back pair
evidence, invalid inputs, pinned output values, and deterministic replay.

The EU fixture `tests/fixtures/rrao_eu/` covers Article 1 exotic underlying,
Article 2 Annex other residual-risk evidence, and Article 3 non-presumptive
zero-capital treatment.

`PERFORMANCE.md` records target-scale benchmark hashes and timings. Replay
hashes are engineering controls over deterministic serialization; they are not
regulatory validation by themselves.

## External Comparator

`tests/test_external_comparator.py` uses a small hand-calculated fixture that
does not call RRAO rule helpers. It independently applies the formula:

```text
gross_effective_notional * risk_weight
```

The comparator covers U.S. NPR 2.0 exotic, other residual risk,
supervisor-directed inclusion, listed exclusion, clearable exclusion, exact
back-to-back exclusion, and EU Article 3 non-presumptive zero-capital treatment.

## Property Tests

`tests/test_properties.py` covers additive total reconciliation, exclusion
idempotency, input-order stability after canonical sorting, input hash
separation for distinct inputs, and included/excluded partition disjointness.

## Mutation Evidence

`docs/quality/frtb-rrao/mutation_baseline.md` records the mutmut baseline for
`audit.py`, `capital.py`, `classification.py`, and `validation.py`.
`docs/quality/frtb-rrao/mutation_survivors.md` records survivor handling.
The 2026-05-29 killed-only baseline is `85.47%`, above the IMA precedent of
`75.12%`, with no allowlisted survivors.

## Reconciliation Tolerance

`tests/test_reconciliation_tolerance.py` verifies the shared hybrid tolerance
budget for non-exact-rational simulated weights and excluded-line zero
invariants. The tolerance values are documented in
[`REGULATORY_ASSUMPTIONS.md`](../../../../packages/frtb-rrao/docs/REGULATORY_ASSUMPTIONS.md).
