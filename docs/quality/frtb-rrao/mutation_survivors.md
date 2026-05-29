# RRAO Mutation Survivor Notes

This file records surviving mutants reviewed for the 2026-05-29 baseline.

The baseline has **no allowlisted survivors**. All 184 surviving mutants are
counted in the denominator for the `85.47%` killed-only score documented in
`mutation_baseline.md`.

## Current Survivor Categories

The remaining survivors are retained as future hardening targets.

- Audit serialization field-presence and diagnostic-message mutations where the
  current tests pin stable JSON output and selected reconciliation failures but
  do not assert every payload key independently.
- Reconciliation and partition helper branch mutations where downstream checks
  still reject incorrect capital results through a later invariant.
- Classification helper mutations around citation merging and hint-compatibility
  branches where existing tests focus on final decisions and key citations.
- Validation metadata and boundary-condition mutations, especially around
  equivalent error-message construction, exact-match diagnostics, and
  investment-fund descriptor field diagnostics.

## Allowlisting Rule

Do not remove a survivor from the mutation denominator without adding a specific
entry below with the mutant id, module, rationale, reviewer, and date.

No survivor entries are currently allowlisted.
