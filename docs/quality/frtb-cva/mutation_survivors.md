# CVA Mutation Survivor Notes

This file records surviving mutants reviewed for the 2026-07-02 baseline.

The baseline has **no allowlisted survivors**. All 530 surviving mutants are
counted in the denominator for the `68.60%` killed-only score documented in
`mutation_baseline.md`.

## Current Survivor Categories

The remaining survivors are retained as future hardening targets.

- BA-CVA standalone and full-portfolio branch mutations where tests assert the
  main capital formulas but do not pin every intermediate component, citation
  list, and hedge-discount diagnostic independently.
- CVA public assembly mutations around optional batch payload routing where the
  current selected mutation suite exercises representative BA-CVA and SA-CVA
  paths but does not assert every absence/presence branch.
- SA-CVA grouping and path-validation mutations where downstream aggregation
  checks still catch many wrong totals but leave equivalent-looking diagnostic
  and ordering changes alive.
- Risk-class configuration mutations in CCS, commodity, equity, FX, GIRR, and
  RCS modules where the current tests cover supported public paths and selected
  risk weights but do not exhaust every generated configuration field.
- Weighted-sensitivity grouping, sorting, risk-factor-key, and per-risk-class
  weighting mutations where current tests emphasize final weighted amounts and
  selected branch behavior rather than every metadata and ordering field.

## Allowlisting Rule

Do not remove a survivor from the mutation denominator without adding a specific
entry below with the mutant id, module, rationale, reviewer, and date.

No survivor entries are currently allowlisted.
