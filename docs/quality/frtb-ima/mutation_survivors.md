# Mutation Survivor Notes

This file records surviving mutants that were reviewed and treated as equivalent
or intentionally deferred for the current prototype.

The 2026-07-02 mutation baseline has **no allowlisted survivors**. All 254
surviving mutants are counted in the denominator for the `84.25%` killed-only
score documented in `docs/quality/frtb-ima/mutation_baseline.md`.

## Current Survivor Categories

The remaining survivors are not excluded from the score. They are retained as
future hardening targets.

- Public-wrapper validation duplicates, where a wrapper mutation is rejected by
  the lower-level calculation helper before an incorrect result can escape.
- Logging and diagnostic-field mutations inside calculation modules, especially
  IMCC diagnostics and lower-priority PLA diagnostic payload details.
- Residual threshold-boundary and ordering mutations in PLA and reduced-set
  workflows after the 2026-07-02 edge-case fixture expansion.
- Capital assembly mutants around eligibility/add-on branches that require
  narrower desk-level scenario fixtures beyond the current public audit
  contract.

## Allowlisting Rule

Do not remove a survivor from the mutation denominator without adding a specific
entry below with the mutant id, module, rationale, reviewer, and date.

No survivor entries are currently allowlisted.
