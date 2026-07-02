# RRAO Mutation Survivor Notes

This file records surviving mutants reviewed for the 2026-07-02 baseline.

The baseline has **no allowlisted survivors**. All 14 surviving mutants are
counted in the denominator for the `94.29%` killed-only score documented in
`mutation_baseline.md`.

## Current Survivor Categories

The remaining survivors are retained as future hardening targets.

- Audit reconciliation helper branch mutations where downstream checks still
  reject incorrect capital results through a later invariant.
- Classification helper mutations around citation merging and hint-compatibility
  branches where existing tests focus on final decisions and key citations.
- The 10 timeout-classified audit mutants are tracked in `results.txt` output
  from `make mutation-rrao`; they are not allowlisted survivors and remain
  future runtime-stability targets.

## Allowlisting Rule

Do not remove a survivor from the mutation denominator without adding a specific
entry below with the mutant id, module, rationale, reviewer, and date.

No survivor entries are currently allowlisted.
