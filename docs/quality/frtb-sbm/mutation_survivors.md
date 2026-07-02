# SBM Mutation Survivor Notes

This file records surviving mutants reviewed for the 2026-07-02 baseline.

The baseline has **no allowlisted survivors**. All 207 surviving mutants are
counted in the denominator for the `78.44%` killed-only score documented in
`mutation_baseline.md`.

## Current Survivor Categories

The remaining survivors are retained as future hardening targets.

- Public SBM capital assembly mutations where tests assert final capital and
  selected branch results but do not pin every citation, ordering, and audit
  metadata field independently.
- Batch calculation routing and supported-path guard mutations where current
  tests cover supported/unsupported regimes but leave some diagnostic and
  iterator-equivalent changes alive.
- GIRR curvature selection, weighting, and floor-citation mutations where tests
  exercise representative curvature branches but do not exhaust every generated
  scenario label, optional text value, and citation-list field.
- Curvature factor aggregation mutations where total curvature capital catches
  many incorrect values but equivalent-looking ordering, set construction, and
  intermediate branch metadata mutations survive.
- CSR non-securitisation weighted-sensitivity mutations where selected
  risk-weight and tenor cases are covered, but some batch metadata, grouping,
  and per-sensitivity field substitutions remain alive.

## Allowlisting Rule

Do not remove a survivor from the mutation denominator without adding a specific
entry below with the mutant id, module, rationale, reviewer, and date.

No survivor entries are currently allowlisted.
